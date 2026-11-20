# EVAL-002 — What area and timing risks differentiate the candidates?
- Status: done
- Traces to: REQ-RULE-002, SPEC-PHY-001, SPEC-HOST-001, SPEC-PROG-001, REQ-GOAL-005
- Compares: ARCH-A, ARCH-B, ARCH-C
- Model: `models/physical/probe_*.v`, `models/physical/run_probes.py`, and the image builder from EVAL-001

## Method

1. Map the full proposed flop stores, including registered read muxes. A has two 64×32-bit program banks and two datapaths. B has one 128×24-bit program bank, a shared datapath, four timed output entries and two capture slots. C has one 64×24-bit program bank, a shared datapath and two lanes with a 16×24-bit descriptor bank each. Each context has eight 16-bit registers and a two-entry return stack. All probes include the same byte-to-word loader front end, two-flop protocol input synchronizers and registered pin outputs. The probes represent datapath structure, not an implementation of the binary interpreter.
2. Map all three with Yosys and ABC against the same IHP typical library and apply the PDK synthesis exclusion list. Run OpenROAD static timing at fast, typical and slow library corners on the unplaced netlists. Then place and repair fanout and wire length for all three at the slow library corner. Use a `50/3 ns` period, 0.25 ns clock uncertainty, 0.15 ns clock transition and 20% maximum I/O delay. The placed estimates use Metal3 signal RC, not routed parasitics.
3. Use the row rectangle from Tiny Tapeout's `tt_block_8x4_pgvdd.def` for the area denominator. The die is 1,724.16 × 710.64 µm; the row rectangle is 1,718.40 × 703.08 µm (1.208 mm²). The experiment does not reuse cell counts or timing results from the 1×1 smoke test.

## Decision use

Prefer results with documented area headroom and a credible 60 MHz implementation path. Neither synthesis probes nor analytical area estimates satisfy routed timing, precheck or system acceptance.

## Results

| Candidate | Mapped cells | Mapped area | Area after placement and repair | Setup slack after repair, slow corner | Hold slack after repair, slow corner |
|---|---:|---:|---:|---:|---:|
| A: independent engines | 16,377 | 0.378 mm² (31.3%) | 0.406 mm² (33.6%) | +3.339 ns | −0.224 ns |
| B: timed-I/O core | 12,969 | 0.295 mm² (24.5%) | 0.316 mm² (26.1%) | +2.934 ns | −0.232 ns |
| C: configurable lanes | 10,717 | 0.251 mm² (20.7%) | 0.266 mm² (22.0%) | +2.289 ns | −0.226 ns |

All three repaired probes met the slow-corner setup target. The worst setup path in each starts at `rst_n` and ends in control logic. Worst register-to-register setup slack was +5.960 ns for A, +5.999 ns for B, and +5.391 ns for C. All three missed hold on an input-to-first-synchronizer path with zero minimum external input delay. The experiment used an ideal clock and did not run clock-tree synthesis, hold repair, routing, or extraction. This does not establish chip-level timing closure or prove that a complete candidate fits.

Unplaced slow-corner setup was negative for all three (A −35.208 ns, B −86.900 ns, C −22.681 ns). Those estimates were dominated by unbuffered loads. The large change after repair is evidence that high-fanout controls must be checked in a placed design, not evidence that B's queue cannot run at 60 MHz.

### Image and implementation tradeoffs

- A can load the UART and SPI images into independent banks. It has the largest measured area and the same 62/64-word I2C pressure as C, but it avoids shared issue arbitration for those protocols.
- B shares the program store across contexts and has 66 words left after the 62-word I2C image. It needs explicit output-queue backpressure and capture ownership. The encoded I2C test filled all four output entries without missing a deadline.
- C was the smallest probe. Its overlap image adds one descriptor per lane, which the host image builder must place as well as program words. The I2C path does not use the lanes and leaves two words free in the program bank.

The image builder already emits the critical-case code and descriptor bytes. All three still need a defined RP2350 transport, bank addressing, a load-complete check and a verified start/reload sequence. The probe front end accepts preframed bytes and an external commit signal. It does not implement the host contract; other omitted costs include final pin allocation, complete decode/control, power distribution and routed timing repairs.

### Reproduce

Used IHP Open PDK `89d42ee6d2fd9b50b86a1aada6fee6673c3e6008`, Tiny Tapeout support tools `0922544e6c7f6126047c3fba720b0437fa32a1b8`, and the local LibreLane `3.1.0.dev4` image (`sha256:af2405f5d48d8fe14d406ecce913811177a95e365e3b625859677307cace2469`). The [summary](EVAL-002/summary.json) records geometry, source hashes for the DEF and Liberty files, and the Yosys version. Per-candidate cell counts and STA reports are in [EVAL-002/](EVAL-002/).

```bash
source scripts/env.sh
python3 -B -m models.physical.run_probes \
  --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
  --def "$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def" --place
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-002/summary.json
```

The last command identifies the probe source revision for the archived run. The mapped netlists and full Yosys logs stay in `test/sim_build/EVAL-002/`.
