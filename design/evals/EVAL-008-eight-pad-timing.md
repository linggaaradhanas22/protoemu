# EVAL-008 — Place the eight-pad issue and retirement probe
- Status: done
- Traces to: BLK-CORE, BLK-DRIVE, BLK-PADS, SPEC-PHY-001, REQ-RULE-002
- Compares: ARCH-B
- Model: `models/physical/pad_path_probe.v`, `models/physical/run_pad_path_probe.py`

## Method

Compare three versions of one slice: compact `pad`/`pad2` only, vector `drivev` only, and both (hybrid). Use the [EVAL-007](EVAL-007-eight-pad-encoding.md) field layouts. Include registered instruction and timestamp inputs, an eight-register bank per context for vector reads, 24-bit deadline arithmetic, ownership and collision checks, four queue entries, and registered pad values and enables. Report separate paths from decode, vector register read, timestamp/offset/timebase, and the queue through output merge. The slice does not include the shifter instructions, program store, full core or loader. The testbench re-presents a blocked request. It does not model the core's pending-operation register.

Map with Yosys and ABC against the typical IHP standard-cell library using the PDK exclusion list. Place and repair each mapped slice inside the 8×4 geometry in OpenROAD. Check the slow and fast corners at a `50/3 ns` period with 0.25 ns clock uncertainty and Metal3 placement RC. Constrain the probe input ports with zero minimum delay. There is no clock-tree synthesis, hold repair or routing. The reports are for the slice, not full-chip sign-off.

## Results

Positive slack means the path has time remaining at the specified clock period. The first four timing columns below are slow-corner setup slack. The last two columns report fast-corner hold slack.

| Variant | Placed area (µm²) | Worst setup (ns) | Decode to queue (ns) | Deadline to admission (ns) | Queue to pad regs (ns) | Worst hold (ns) | Register hold (ns) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Compact | 46,795 | +4.332 | +4.332 | +5.174 | +12.280 | −0.197 | −0.031 |
| Vector | 54,938 | +5.434 | +5.451 | +5.434 | +12.129 | −0.196 | −0.032 |
| Hybrid | 55,542 | +4.566 | +4.566 | +5.794 | +12.161 | −0.199 | −0.037 |

Vector register read to queue had +7.646 ns of slow setup slack in the vector slice and +9.356 ns in the hybrid slice. Setup was positive at both measured corners for all variants. Fast hold failed at probe inputs and on internal register paths. Do not infer that those paths meet hold on the final chip.

Hybrid placed area was 8,747 µm² higher than compact and 604 µm² higher than vector. Synthesis prunes the probe's register bank in the compact-only slice because nothing there reads it. The full core keeps its general registers in all options. The slice area difference is not a measurement of area added to the full core.

The Icarus hybrid smoke check passed: four disjoint entries retire on one edge, the queue reuses a slot on that edge, and the vector update controls output enable and open-drain release. It also checks full, collision, late and ownership responses. All 38 existing Python model checks passed. These are exploration checks, not registered project tests.

## Recommendation

Carry both formats into the draft ISA review. Compact uses fewer words for routine updates in EVAL-007. Vector can update all eight pads with one queue entry. The slice supports using both without adding a pipeline stage for setup in this experiment. Full-core integration, the saved-request path, and routed setup and hold still need evidence. Do not freeze opcodes or change production RTL on the strength of this slice alone.

## Reproduce

From the repository root in WSL:

```bash
source scripts/env.sh
python3 -B -m models.physical.run_pad_path_probe \
  --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
  --def "$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def"
/usr/bin/iverilog -g2005 -Wall -s pad_path_probe_tb -o test/sim_build/EVAL-008/probe.vvp \
  models/physical/pad_path_probe.v models/physical/pad_path_probe_tb.v
/usr/bin/vvp test/sim_build/EVAL-008/probe.vvp
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-008/summary.json
```

See the [summary and tool identifiers](EVAL-008/summary.json) and the per-corner reports in [EVAL-008](EVAL-008/). The Git command identifies the probe revision that produced the archive. Generated netlists stay in `test/sim_build/EVAL-008/`.
