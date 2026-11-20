# CHG-013 — Unguarded timed level wait (`wait_to`)
- Status: proposed
- Size: medium
- Affects: BLK-CORE, BLK-CAPTURE, TEST-UNIT-001, TEST-UNIT-004, TEST-SYS-009

## Reason

Input waits have no time limit. An I2C target that holds SCL low stalls the controller context until the host sends `STOP`, which also stops the other context and needs a reload. [EVAL-017](../evals/EVAL-017-wait-timeout.md) compared host stop, software polling, a timed wait and a watchdog. Only the timed wait detected every stuck bus, kept all 14 I2C cases passing and left the other context untouched.

## Proposed change

**Instruction** `wait_to pin, level, offset, Rt` (provisional opcode 6; fields: pin 3, level 1, offset 9, Rt 3; 21 bits):
- Wait for the synchronized pin to equal `level`, as `wait_save` does, but with no earliest-observation guard: the first observation after the arm edge can match.
- Expiry cycle = `(saved time + offset pair + offset + Rt × 64) mod 2^24`. The core computes it with its deadline adder. It must be 1 to `2^23 − 1` cycles in the future at arm, or the instruction faults, as for timed samples.
- `Rt = 0` means no expiry. `Rt` up to 65,535 gives up to about 70 ms.
- **On a match:** save the observation timestamp and clear the offset pair, as `wait_save` does. `Rt` is unchanged.
- **On expiry:** the slot ends the wait on the expiry edge. The core writes `Rt = 0` and leaves the saved time and offset unchanged. The program tests `Rt` with `jnz`.
- Expiry is not a fault. Stops, faults and flushes follow CHG-008.

**BLK-CAPTURE:** a level arm may be timed. A timed arm is never guarded. It stores the expiry in the slot's existing deadline register and compares with the existing equality check. It adds a timed flag and an expired flag per slot. A match and expiry on the same edge count as a match.

**BLK-CORE:** add `Rt × 64` as a deadline-adder operand for `wait_to`, and the `Rt = 0` write on expiry. Retry rules are unchanged: the expiry is computed once, at the first execute.

**Programs:** the I2C example uses `wait_to` for every SCL rise. On expiry it releases both lines and reports status 2. The limit is host-supplied, for example 25 ms.

**Tests:**
- TEST-UNIT-004: timed arm, match before expiry, expiry with no match, match and expiry on one edge, `Rt = 0`, wrap.
- TEST-UNIT-001: expiry writes only `Rt`, a past expiry faults at arm, and the other context keeps issuing during a long wait.
- TEST-SYS-009: add a stuck-SCL case that must report a timeout while the other context completes.

## Impact

No SPEC or REQ change; legitimate stretches are unaffected. Area in the slots is below synthesis noise in EVAL-017; the core adder operand is not measured. Uses one of the three free opcodes. All blocks are draft, so nothing becomes `suspect`.

Alternatives kept: host `STOP` remains the fallback for any stuck wait. The guarded variant (C1, +5,479 µm²) and the watchdog (+6,753 µm², stops the whole chip) are rejected. Software polling breaks I2C clock timing after a stretch and can starve the other context.

## Approval

medium: waiting for Lingga.

## Close-out

Not started.
