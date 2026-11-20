# EVAL-010 — Decode RC5 with edge capture and elapsed time
- Status: done
- Traces to: BLK-CORE, BLK-CAPTURE, BLK-TIMER, SPEC-PROG-003, SPEC-PROG-002
- Model: `models/benchmarks/g4_edges.py`

## Method

The same 24-bit program runs at all three [RC5 benchmark rates](../../models/benchmarks/rc5/README.md). It waits for the first falling edge and saves its synchronized observation time. It waits for the rising edge, subtracts the saved timestamp modulo `2^24`, and saves the new timestamp. The interval is the measured half-bit. The program checks its range, computes sample offsets from it, and samples both halves of each remaining symbol. It checks that the two halves are complementary and that both start bits are set. It sends each decoded word through `host_put`. The existing monitor checks the decoded fields and sample/report windows. No protocol-specific opcode is used.

Load the image and read the results through the existing SPI host model. For the wrap variant, set the model epoch so the first falling edge is observed five cycles before wrap. Keep the same pin stimulus. Observe the final idle interval. The program expects two frames for this benchmark and does not claim to be a continuous receiver.

## Results

All **six model cases passed**. The program used **39 of 128 words** and reported the expected words `0x3175` and `0x3E8C` once each.

| RC5 half-bit (clocks) | Cases passed: zero / wrap | Min time from sample arm to sample (clocks) | Min monitor window margin (clocks) |
|---:|---:|---:|---:|
| 50,673 | 1 / 1 | 25,308 | 25,336 |
| 53,340 | 1 / 1 | 26,642 | 26,669 |
| 56,007 | 1 / 1 | 27,975 | 28,003 |

At the nominal rate, the wrap run saved `16,777,211` and `53,335` on its first two edges. The modular difference is `53,340` clocks. Directed tests also check either-edge mode, a 65,539-clock interval returned in two words, rejection at the half-range boundary, and invalid operands. The model skips quiet cycles on long input waits. A short directed run matched dense simulation for the issue, capture, sample, payload and completion traces. All 45 Python model checks passed.

## Limits

The model measures from synchronized observation, not the asynchronous pad edge. The modulo result cannot detect a timestamp older than a full wrap that aliases a short interval. Software must bound the time between observations. The tested wait has no built-in timeout. There is one capture slot per context; edges during the rearm gap are not buffered.

The prototype treats a two-register interval result as a single consume. It does not measure register-file write cost, arithmetic delay, or the effect of a different retirement schedule. The provisional encoding also uses seven opcode values for edge and arithmetic operations. [CHG-006](../changes/CHG-006-edge-interval.md) proposes the behavior for review, not an opcode freeze. No production RTL or registered project tests changed.

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-010/results.json
python3 -B -m models.benchmarks.g4_edges --out design/evals/EVAL-010/results.json
python3 -B -m unittest models.benchmarks.test_g4_edges models.benchmarks.test_g4_payload models.benchmarks.test_g4_pad_encoding models.benchmarks.test_g4_isa models.benchmarks.test_g4_timestamp models.benchmarks.test_g4_loader models.benchmarks.test_g4_timing models.benchmarks.test_compare models.benchmarks.test_encoded
```

The Git command identifies the model version for the [per-case results](EVAL-010/results.json).
