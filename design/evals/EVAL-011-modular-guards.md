# EVAL-011 — Fence and wait guards on a 24-bit timer
- Status: done
- Traces to: BLK-CORE, BLK-CAPTURE, BLK-TIMER, SPEC-UART-002, SPEC-I2C-003, SPEC-PROG-003
- Compares: elapsed, sticky, compare, strict
- Model: `models/benchmarks/g4_guards.py`

## Question

`fence` waits until a target time. `wait_save` with a saved time ignores observations before its target. Earlier probes checked both as `elapsed ≥ target`, which needs a counter that never wraps. Hardware has only the 24-bit `cycle`. What should a guard do when its target has already passed, is in the future, or lies across a wrap?

## Rules compared

All rules use `delta = (target − cycle) mod 2^24`. `H = 2^23`.

| Rule | Behavior | State per context |
|---|---|---|
| `elapsed` | Earlier model: open when model time ≥ target. Not buildable with 24 bits; baseline only. | Unbounded counter |
| `sticky` (proposed) | Classify once, at the first execute or arm. `1 ≤ delta < H`: wait until `cycle == target`. `delta = 0` or `delta ≥ H`: open now. Once open, stay open until the operation retires. | One open bit; target already in the pending operation |
| `compare` | No arm state. Open while `(cycle − target) mod 2^24 < H`. | None, but a 24-bit subtract every waiting cycle |
| `strict` | As `sticky`, but fault if the target is not in the future half (the drive admission rule). | One open bit |

A `wait_save` without a saved time has no guard under every rule. The model now marks this explicitly, so the guard does not take a false target at the model epoch.

## Method

Replay the existing ISA jobs (4 SPI, 6 I2C, 48 UART+SPI overlap) at epochs `0` and `2^24 − 500`. Also replay the six RC5 cases from [EVAL-010](EVAL-010-edge-interval.md). Run every case under each rule. Compare a hash of the issue, retirement, capture, sample and payload traces with the `elapsed` baseline. Directed tests cover the boundaries, wrap, two contexts and the encoded instructions.

## Results

| Rule | Cases passed | Same cycle trace as baseline | Guards evaluated | Reached at arm | Future at arm | No guard |
|---|---:|---:|---:|---:|---:|---:|
| `elapsed` | 122 / 122 | 122 | – | – | – | – |
| `sticky` | **122 / 122** | **122** | 1,024 | 192 | 736 | 96 |
| `compare` | 122 / 122 | 122 | 1,024 | 192 | 736 | 96 |
| `strict` | 26 / 122 | 26 | – | – | – | – |

- All 192 targets that had already passed at arm are in the UART receiver. Two per case. It waits for the next start bit "no earlier than" the last stop-bit sample. That time has already passed when the wait arms. `strict` faults on the first one, so all 96 UART cases fail.
- The longest future wait is 5,600,195 cycles (RC5 final idle fence, 67 % of `H`). The I2C wait guards are all in the future, with at most 156 cycles left.
- `sticky` and `compare` behave the same in every replay. They differ only in the directed tests below.

| Directed check (`sticky` unless noted) | Result |
|---|---|
| `delta` = 0, 1, `H−1`, `H`, `H+1`, `2^24−1` at epochs `0` and `2^24−3` | Waits only for 1 and `H−1`; retires on `cycle == target` |
| Future fence across wrap | Retires at the target, after the counter wraps to a smaller value |
| `wait_save` target equals the observation cycle | Matches; the stamp equals the target |
| Already-reached `wait_save` | Matches on the first observation after the arm edge |
| Level arrives `H + 1000` cycles after the guard opened | `sticky` matches 2 cycles after arrival. `compare` had closed again. It matches only when the counter returns to the target, `H − 1000` cycles (~140 ms) after arrival. |
| `delta = H` under `compare` | Waits `H` cycles; `sticky` treats it as past |
| Two contexts, one past and one future target | Each classifies independently |
| `save_now; fence 0` | Already reached, no wait |
| `fence` using a `0x7F:FFF0` split offset | Waits 8,388,592 cycles from the save |
| `wait_save` with no saved time | Recorded as unguarded |
| `strict` with `delta` 0, `H` or `2^24−1` | Faults |

All 58 Python model checks passed, including 13 new ones. EVAL-006, EVAL-009 and EVAL-010 regenerate byte-identical results after the model change.

## Conclusion

Recommend `sticky`. It matches the earlier model on all 122 replays, keeps the "not earlier than" meaning that the UART receiver depends on, and does not lose an open guard during a long idle wait. `compare` saves one bit per context, but a receiver idle for more than ~140 ms would ignore input for another ~140 ms. That is a real failure for UART or RC5 receivers. `strict` breaks the current UART program.

The software rule is the same as for drives and `edge_delta`: arm a guard within `2^23 − 1` cycles (~140 ms at 60 MHz) of its target. A target more than that far in the past aliases as a future one and can wait up to ~140 ms. [CHG-007](../changes/CHG-007-modular-guards.md) proposes the rule.

## Limits

- Hardware cost is **not measured**. The estimate (a guess) is one open bit and one 24-bit equality compare per context. The arm-time check can reuse the drive admission subtractor. Check this in the BLK-CORE timing probe.
- The model classifies a fence on the first cycle the scheduler evaluates it. It does not model a separate execute-stage register.
- Waits have no timeout. A wrong level can stall a context indefinitely; only a global stop clears it.
- The replays never wait longer than `H` after a guard opened. Only the directed test covers that case.
- No production RTL or registered project tests changed. Opcodes are unchanged.

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-011/results.json
python3 -B -m models.benchmarks.g4_guards --out design/evals/EVAL-011/results.json
python3 -B -m unittest models.benchmarks.test_g4_guards models.benchmarks.test_g4_edges models.benchmarks.test_g4_payload models.benchmarks.test_g4_pad_encoding models.benchmarks.test_g4_isa models.benchmarks.test_g4_timestamp models.benchmarks.test_g4_loader models.benchmarks.test_g4_timing models.benchmarks.test_compare models.benchmarks.test_encoded
```

The Git command identifies the model version for the [per-case results](EVAL-011/results.json). Run time is about 15 s.
