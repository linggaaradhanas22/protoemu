# EVAL-006 — Prototype the 24-bit timed instruction encoding
- Status: done
- Traces to: BLK-CORE, BLK-PROGRAM, BLK-TIMER, SPEC-I2C-003, SPEC-SPI-001, REQ-PROTO-004
- Compares: ARCH-B
- Model: `models/benchmarks/g4_isa.py` and `models/benchmarks/run_g4_isa.py`

## Encoding tested

The assembler emits three bytes per word, least significant byte first. Bits `[4:0]` hold the opcode. Operand fields start at bit 5 in the order below. The decoder rejects nonzero reserved bits. This is a benchmark encoding, not the release ISA.

| Opcode | Operation | Operand widths (bits) |
|---:|---|---|
| 3 | `out` | mask 5, values 5, offset 9 |
| 4 | `shift_out` | register 3, data pin 3, extra pin 3, extra value 1, offset 9 |
| 5 | `cap` | pin 3, result register 3, sample mode 2, offset 9 |
| 14 | `fence` | offset 9 |
| 15 | `save_now` | none |
| 16 | `addoff` | signed displacement 15 |
| 17 | `wait_save` | pin 3, level 1, earliest offset 9 |

`wait_save` waits for a synchronized level, saves the observation timestamp on consume and clears the offset pair. With no saved timestamp it permits only a zero guard. `save_now` saves the current counter value on its execute edge and clears the offset pair. The probe uses it to start an output sequence before any capture. A plain timed sample does not overwrite the saved time.

Timed operations add the saved timestamp, a register offset and the instruction's 9-bit offset. Form the absolute deadline modulo `2^24`. For delays above 511 cycles, store the lower 16 bits of the register offset in `R0` and the upper seven bits in `R6`. `addoff` carries across the register boundary. A program may also load both halves with `set`. Reject offsets outside the unsigned 23-bit range. Still check the resulting deadline against the current cycle at admission. The two registers are an offset convention for this probe, not a second timestamp or an approved register assignment.

## Replay results

Both the zero-start run and the run starting 500 cycles before 24-bit wrap passed **58/58 cases**. Each run covers four standalone 1 MHz SPI modes, six Fast-mode I2C cases, and 48 concurrent UART/SPI cases. I2C covers up to 10 µs of stretching and address/data NACK. Concurrent runs sweep 16 UART start phases and SPI starts at −4, 0 and +4 cycles from the original fixture. The SPI test programs account for their modeled first clock-read slot when scheduling the original CS edges. Independent peers and checks from EVAL-001 are unchanged.

| Program | Words of 128 | Min drive admission slack | Min sample admission slack |
|---|---:|---:|---:|
| Standalone 1 MHz SPI | 18–19 | 18 cycles | 48 cycles |
| Fast-mode I2C | 63 | 8 cycles | 8 cycles |
| Concurrent UART RX and SPI | 36 | 13 cycles | 48 cycles |

Slack is the time between admission and the target edge, not electrical timing margin. The 10 µs stretch case retained two cycles of margin on its tightest unstretched SCL period. Concurrent SPI retained a one-cycle half-period margin. No run stalled on a full queue. I2C used all four drive slots and the overlap used both capture slots. All 33 Python model checks passed. Directed tests cover bit packing, invalid timestamp use, an offset that carries across 16 bits, and preserving the saved timestamp through a timed sample.

## Limits and next check

`out` still inherits a five-bit mask from the G3 benchmark encoding. `shift_out` also reserves pin value 7 as a sentinel for the optional extra pin. The prototype does not cover all eight protocol pins or arbitrary output enables. It uses the G3 logical fixture pins, not the approved physical pin map. It also assumes one execute slot to add the timestamp and two offset operands and attempt admission. The model does not show that this path fits 60 MHz after routing. Test alternatives for full pin coverage and measure the add/compare path before proposing an ISA freeze. No RTL, RP2350 driver or registered project tests ran.

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-006/results.json
python3 -B -m models.benchmarks.run_g4_isa --out design/evals/EVAL-006/results.json
python3 -B -m unittest models.benchmarks.test_g4_isa models.benchmarks.test_g4_timestamp models.benchmarks.test_g4_loader models.benchmarks.test_g4_timing models.benchmarks.test_compare models.benchmarks.test_encoded
```

See the [per-case results](EVAL-006/results.json). The Git command identifies the model revision that produced the archive.
