# EVAL-018 — Place the full-core timing probe
- Status: done
- Traces to: BLK-CORE, BLK-PROGRAM, BLK-DRIVE, BLK-CAPTURE, BLK-TIMER, BLK-PADS, SPEC-PHY-001, REQ-RULE-002
- Compares: ARCH-B
- Model: `models/physical/full_core_probe.v`, `models/physical/run_full_core_probe.py`

## What ran

TASK-051 measured the proposed fetch/execute schedule, not production RTL. The probe includes two contexts, a 128 × 24-bit loadable store with registered fetch, the CHG-009 register file, both pad encodings and shift orders, and the saved absolute request path. It includes the 24-bit timebase, four drive slots, two capture slots with guarded `wait_to`, synchronized pin inputs and registered pin outputs. The host boundary supplies load/run controls and ready/data signals directly. The SPI parser, CRC, host FIFOs and final Tiny Tapeout wrapper are absent. The probe uses the provisional ISA encodings and R0/R6 offset pair.

Yosys and ABC mapped the probe to the typical IHP library with the PDK exclusion list. OpenROAD placed it independently at the slow and fast corners in the 8×4 floorplan and ran `repair_design` with placement-estimated RC. The SDC uses a `50/3 ns` period, `0.25 ns` uncertainty and the same probe I/O assumptions as [EVAL-008](EVAL-008-eight-pad-timing.md). It constrains the raw inputs for comparison; those paths are not a board timing claim. No CTS, dedicated timing repair or routing ran.

## Results

**This baseline missed 60 MHz.** The placed probe used 0.381 mm² of cells at both corners rounded to three decimals (0.355 mm² and 17,351 cells before placement). The slow-corner cell area is about 32% of the 8×4 row area. This is not a full-chip fit estimate.

| Corner | Worst setup | Internal setup | Worst hold | Internal hold | Placed cell area |
|---|---:|---:|---:|---:|---:|
| Slow, 1.08 V, 125 °C | −10.226 ns | −8.939 ns | −0.109 ns | +0.185 ns | 380,995 µm² |
| Fast, 1.32 V, −40 °C | +2.382 ns | +5.996 ns | −0.198 ns | −0.055 ns | 380,545 µm² |

| Slow-corner setup path group | Slack |
|---|---:|
| Saved request to drive queue | −6.306 ns |
| Fetched instruction to register-file write | −2.816 ns |
| Fetched instruction to capture deadline | −1.502 ns |
| Fetched instruction to drive queue | −1.085 ns |
| Register file to capture deadline | +2.151 ns |
| Capture timestamp to register-file write | +5.040 ns |
| PC to registered fetch | +9.273 ns |
| Due drive slot to pad output registers | +12.998 ns |
| Registered fault to pad output registers | +13.668 ns |

Mapped net names identify the worst slow path as starting at the cycle counter and ending at the egress handshake; the worst register path starts at the same counter bit and ends in the register file. Pending-drive eligibility, context selection and shared commit logic are coupled in this implementation. OpenSTA reports structural paths; the run did not establish that each worst path is sensitizable. Even the focused instruction-to-queue and instruction-to-capture groups miss setup. The measured PC-to-fetch and due-slot-to-pad groups are not the first targets for a redesign. The worst internal fast hold path is between the two pad synchronizer stages.

The Icarus smoke test passed: four live drive slots, a saved fifth request retried at its original deadline, LSB-first output, progress of the other context, guarded match and expiry, and fault-edge output followed by safe on F+1. All 89 existing Python benchmark checks passed separately. These are exploration checks, not a protocol replay on the probe or registered project verification.

## Recommendation

Do not adopt this issue implementation as-is. First compare an implementation that separates pending-context selection from request validation and commit, and shortens the shared deadline and fault paths. Try to preserve the current issue schedule. Compare a staged version if needed; it must replay the tight Fast-mode I2C and concurrent UART/SPI cases before adoption. Check hold again after CTS and hold repair. This result does not change an agreed contract or establish that ARCH-B cannot meet 60 MHz.

## Reproduce

From WSL at the repo root with the local LibreLane image available:

```bash
source scripts/env.sh
python3 -B -m models.physical.run_full_core_probe \
  --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
  --def "$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def"
iverilog -g2005 -Wall -s full_core_probe_tb -o test/sim_build/EVAL-018/probe.vvp \
  models/physical/full_core_probe_tb.v models/physical/full_core_probe.v \
  models/physical/full_core_drive.v models/physical/full_core_capture.v \
  models/physical/probe_store.v models/physical/regfile_probe.v
vvp test/sim_build/EVAL-018/probe.vvp
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-018/summary.json
```

The Git command identifies the archived model revision. See the [summary with source and tool hashes](EVAL-018/summary.json), [slow-corner report](EVAL-018/slow_1p08V_125C.txt) and [fast-corner report](EVAL-018/fast_1p32V_m40C.txt). Mapped netlists stay in ignored `test/sim_build/EVAL-018/`.
