# EVAL-003 — ARCH-B timed-I/O and shared issue replay
- Status: done
- Traces to: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-TIMER, SPEC-SPI-001, SPEC-I2C-003, REQ-PROTO-004
- Compares: ARCH-B
- Model: `models/benchmarks/g4_timing.py` and the existing EVAL-001 encoded programs and peer monitors

## Method

Run each case one cycle at a time at the specified 60 MHz. A fetch reserves the next execute slot, and a taken branch reserves one redirect slot. At other boundaries, select runnable contexts in round-robin order. Hold blocked requests without refetching or recomputing their deadline. Capture sees the pre-edge synchronized input; the result is eligible on the next cycle and consumes a separate issue slot. The model compares drive deadlines and timed capture by equality on a 24-bit counter. It checks each accepted output retires exactly once at its deadline.

Each run contains four 1 MHz SPI modes, six Fast-mode I2C cases and 48 UART/SPI overlap cases. The I2C cases cover no stretch, 1/5/10 µs stretch, address NACK and data NACK. The overlap sweep uses 16 UART start phases within one chip clock and three shifts of both SPI transfers (−4, 0, +4 clocks). For the wrap rerun, initialize the modeled counter 500 cycles before wrap without moving any peer stimulus in elapsed time.

## Results

| Output slots / counter start | Cases passed | Peak output / capture occupancy | Max runnable wait | Min output admission slack | Most queue-blocked cycles in one case |
|---|---:|---:|---:|---:|---:|
| Four / zero | 58/58 | 4 / 2 | 3 clocks | 10 clocks | 0 |
| Four / near wrap | 58/58 | 4 / 2 | 3 clocks | 10 clocks | 0 |
| Three / zero | 58/58 | 3 / 2 | 3 clocks | 10 clocks | 16 |

Admission slack is the time from acceptance to its deadline, not the protocol timing margin. SPI's tightest half-period margin was one clock; the 10 µs stretch case had two clocks of margin on the tightest unstretched SCL period. The directed model checks also cover disjoint outputs retiring together and reusing a slot at wrap, two captures completing together, arm-edge exclusion, output-mask collision, half-range boundaries, and overcommit faulting before a late drive. All seven directed checks passed; all 12 existing model tests and the original 33 encoded G3 cases still passed.

## Recommendation and limits

Keep the draft four-slot output queue and one capture slot per context. Three slots worked here, but they blocked pending requests in this finite sweep. No reservation was needed in the tested workload; that does not guarantee service under arbitrary load. Keep the measured issue assumptions as the starting point for the ISA work, not as a proven latency bound.

The probe translates G3 program times onto the wrapping timebase at the request interface. It does not implement how the final ISA carries a 24-bit timestamp in or alongside 16-bit registers. It uses a clock-cycle model of synchronizers, not an analog model. It does not test host loading, host backpressure, stop-to-safe propagation, post-route timing or RTL. The G3 level-wait guard and fence continue to use elapsed program time in this probe. The 19 Python checks are not the registered unit or integration tests.

## Reproduce

From the repository root in WSL, with Python 3.11 or newer:

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-003/results.json
python3 -B -m unittest -v models.benchmarks.test_g4_timing models.benchmarks.test_compare models.benchmarks.test_encoded
python3 -B -m models.benchmarks.run_g4_timing --out design/evals/EVAL-003/results.json
python3 -B -m models.benchmarks.run_encoded
```

The first command identifies the commit with the probe, fixtures and archived [per-case results](EVAL-003/results.json).
