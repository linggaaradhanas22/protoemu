# EVAL-005 — 24-bit timestamps in the ARCH-B instruction set
- Status: done
- Traces to: BLK-CORE, BLK-TIMER, BLK-CAPTURE, BLK-DRIVE, SPEC-I2C-003, SPEC-PROG-003, REQ-PROTO-004
- Compares: ARCH-B
- Model: `models/benchmarks/g4_timestamp.py`

## Method

Use the EVAL-003 issue path, capture slots and output queue. Capture an input edge and use the native 24-bit timestamp to schedule a later drive or sample. Compare three instruction sequences:

| Option | Modeled sequence | State and datapath implications |
|---|---|---|
| Split register pair | Capture into two 16-bit registers. Add the delay to the low word. Add carry to the upper eight bits. Issue from the pair. | Uses two general registers and assumes a carry flag. Assumes an atomic capture into the pair. |
| Fused register pair | Capture into the pair. Issue from the pair plus an immediate delay. | Same register use and atomic write assumption. Adds a 24-bit sum to the issue path. |
| Dedicated operand | Capture into one 24-bit timestamp register per context. Issue from that register plus an immediate delay. | Keeps both general registers free. Adds 48 data bits across two contexts, or 50 bits with valid flags. Adds a 24-bit sum to the issue path. These are state counts, not mapped area. |

Sweep timestamps at ordinary time, just before the low 16 bits wrap, and just before the full 24 bits wrap. Compare an idle second context with a competing context executing fetch, execute and branch slots at three offsets. Use 4, 8, 12 and 16 cycles as stress delays. Use 56 cycles for an I2C-like drive and 781 cycles for a UART-like sample. These are isolated sequences using delays from the earlier encoded programs, not complete protocol tests. The model charges a separate capture-consume slot to all three options.

## Results

| Option | Instruction words | Capture to admission, no queue block | Admission with 8-cycle delay | Admission at each 56- and 781-cycle delay |
|---|---:|---:|---:|---:|
| Split register pair | 4 | 7–17 cycles | 3/12 | 12/12 |
| Fused register pair | 2 | 3–7 cycles | 12/12 | 12/12 |
| Dedicated operand | 2 | 3–7 cycles | 12/12 | 12/12 |

The latency ranges use the 56- and 781-cycle cases, where every option admitted the request. A request arriving on its deadline is late. At a 4-cycle delay, the two fused options admit only the idle-context cases (3/12 each). The split pair also misses the tested contended cases at 12 and 16 cycles. These stress delays are not requirements.

The probe ran 222 cases. Every admitted request drove or sampled at its expected cycle, including on either wrap boundary. In the full-queue cases, all options retained the original deadline. They admitted with two cycles to spare when a slot opened in time, and rejected with no late drive when it did not. A directed check also covers one cycle of slack versus zero. All 29 Python checks passed, including four timestamp-specific tests.

## Recommendation and limits

Start with a dedicated captured timestamp per context. It saves two general registers compared with the fused pair and has the same modeled latency. Split arithmetic costs two more program words and increases latency when the other context is busy. Keep the fused pair as an alternative if the dedicated state costs too much area or programs need more than one saved timestamp.

This probe charges per-instruction slots. It does not assemble a new binary ISA, prove that every operand format fits 24 bits, or model the physical delay of the add, admission compare or queue. It does not replay full programs under a new encoding. Before freezing the ISA, check operand encoding and long delays, register pressure, and the 60 MHz execute path. See the [draft decision](../04_decisions/DEC-003-isa-timestamps.md).

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-005/results.json
python3 -B -m models.benchmarks.g4_timestamp --out design/evals/EVAL-005/results.json
python3 -B -m unittest models.benchmarks.test_g4_timestamp models.benchmarks.test_g4_loader models.benchmarks.test_g4_timing models.benchmarks.test_compare models.benchmarks.test_encoded
```

See the [per-case results](EVAL-005/results.json). Intentional late-deadline rejections are recorded, not treated as physical or protocol failures.
