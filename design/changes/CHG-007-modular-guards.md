# CHG-007 — Define 24-bit fence and wait guard behavior
- Status: proposed
- Size: medium
- Affects: BLK-CORE, BLK-CAPTURE, BLK-TIMER, TEST-UNIT-001, TEST-UNIT-004, TEST-UNIT-005

## Reason

The draft ISA says `fence` waits until its time and `wait_save` treats its time as an earliest observation. It does not say what happens when the target has already passed, or how the guard behaves across a timer wrap. The earlier model compared unbounded elapsed time, which hardware cannot do. [EVAL-011](../evals/EVAL-011-modular-guards.md) compares three 24-bit rules.

## Proposed change

| Case at the first execute (`fence`) or arm (`wait_save`) | Behavior |
|---|---|
| `delta = (target − cycle) mod 2^24` is 1 through `2^23 − 1` | Future. Wait until `cycle == target`. A `fence` retires on or after that edge. A `wait_save` accepts observations from that edge on. |
| `delta = 0` | Reached. A `fence` can retire now. A `wait_save` accepts the next observation (not the arm edge, as today). |
| `delta` is `2^23` or more | Already passed. Same as `delta = 0`. **No fault.** |
| `wait_save` without a saved time | No guard. Accept the next observation. |

- Classify the target **once**. After the guard opens, keep it open until the operation retires, is flushed or faults. Do not re-compare.
- Keep the target in the pending operation, as today. Add one "guard open" bit per context. Clear it on reset, flush, fault and retirement.
- Unlike drive and sample admission, a reached or passed guard target is **not** an error. A guard means "not earlier than". Drives and samples keep their current fault rule.
- Software must arm a guard within `2^23 − 1` cycles (~140 ms) of its target. A target further in the past aliases as a future one and waits up to ~140 ms. This is the same bound as for drives and `edge_delta`.
- Do not add a timeout, a wrap counter or opcodes.

Item updates after approval:
- **BLK-CORE**: add the guard rule and the open bit to "Captured time" and the retry rules.
- **BLK-CAPTURE**: a guarded level arm stores the target and open bit. The observation rule is unchanged.
- **BLK-TIMER**: note that guards use the arm-time classification and equality, not a continuous compare.
- **TEST-UNIT-001 / 004 / 005**: add the boundary values `0, 1, 2^23−1, 2^23, 2^24−1`, the across-wrap fence, a reached `wait_save`, and a level that arrives more than `2^23` cycles after the guard opened.
- **ISA draft**: replace the "finite replay does not settle ordering" sentence with this rule.
- **Model**: use the `sticky` rule as the default in the G4 probes.

## Impact

No SPEC or REQ changes. Interfaces between blocks are unchanged; the open bit is internal to BLK-CORE/BLK-CAPTURE. All 122 replays give the same cycle traces as before. Area cost is not measured; the estimate (a guess) is one flop and a 24-bit equality compare per context. All blocks are still draft, so nothing becomes `suspect`.

Rejected alternatives: `compare` (stateless half-range compare) can close an open guard after ~140 ms of idle input. `strict` (fault on a passed target) breaks the UART receiver in all 96 cases.

## Approval

medium: waiting for Lingga.

## Close-out

Not started.
