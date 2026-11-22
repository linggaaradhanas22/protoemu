# EVAL-021 — Shorten fresh instruction writeback
- Status: done
- Traces to: BLK-CORE, BLK-PROGRAM, BLK-DRIVE, BLK-PADS, SPEC-PHY-001
- Compares: ARCH-B
- Model: `models/physical/full_core_probe.v`, `models/physical/run_full_core_cts.py`

## Variants

All three variants keep the registered retry boundary and two-edge fresh fetch/execute schedule from EVAL-020's `OPT=3`. They do not add an issue cycle. All preserve the original drive deadline and the safe edge one cycle after fault detection. The retry boundary can still detect an expired retry one cycle later than same-cycle retry; this was not changed by the writeback work.

- `OPT=3`: shared retirement logic. Rerun the control in this build because the code refactoring changes the mapping relative to the historical result.
- `OPT=5`: give ALU writes and host transfers their own legality and completion signals. Gate a shift result with drive admission. This prevents unrelated capture and deadline checks from delaying simple writes and host handshakes.
- `OPT=6`: also decode the opcode and static word legality in the existing fetch slot. Register them alongside the stored instruction. This decodes on the store read path rather than lengthening the schedule.

## Placement at 60 MHz

Same PDK, clock constraints and corners as EVAL-020. In this table the clock is ideal and parasitics are estimated from placement.

| Variant | Slow setup, overall | Slow setup, internal | Fast hold, overall | Fast hold, internal | Slow placed area |
|---|---:|---:|---:|---:|---:|
| `OPT=3` Retry-only control | −3.377 ns | −2.934 ns | −0.205 ns | −0.055 ns | 384,680 µm² |
| `OPT=5` Separate writeback and host handshakes | −0.732 ns | −0.732 ns | −0.204 ns | −0.054 ns | 385,377 µm² |
| `OPT=6` Also predecode at fetch | −1.061 ns | −1.061 ns | −0.205 ns | −0.055 ns | 387,832 µm² |

`OPT=5` improved slow internal setup by 2.202 ns at a cost of 697 µm². Its instruction-to-queue and instruction-to-capture groups also pass placement setup. Predecode improved on the control, but did not improve on the smaller local writeback change.

## Clock tree and timing repair

For `OPT=5`, built one clock tree with both corners loaded. Used the PDK clock buffer list, propagated the clock, repaired setup and then hold, legalized placement, and re-estimated parasitics. No routing or extraction ran. Kept the same probe I/O constraints throughout; no timing exceptions were added.

| Stage | Slow setup, overall | Slow setup, internal | Fast hold, overall | Fast hold, internal | Cell area |
|---|---:|---:|---:|---:|---:|
| Placed | −0.732 ns | −0.732 ns | −0.204 ns | −0.054 ns | 385,377 µm² |
| After clock tree | −0.762 ns | −0.762 ns | −0.572 ns | −0.087 ns | 438,637 µm² |
| After setup and hold repair | +0.040 ns | +0.040 ns | −0.014 ns | +0.081 ns | 510,284 µm² |

The repaired setup and internal hold paths pass in the probe. Overall hold still misses, with the worst path starting at `entry1[6]`, a synthetic host configuration port constrained as an input with zero minimum delay. In production it comes from BLK-HOST; this result neither proves nor waives its timing. The repaired probe occupies about 42% of the 8×4 row area in cells, up about 32% from placement. It excludes the host, physical interface, and routing, so it does not establish full-chip fit. The setup margin is only 40 ps before routing.

## Verification

Directed Icarus checks passed in all three variants, including wraparound retry, expired retry with no credit, guarded waits, fault F/F+1 ordering, arithmetic writeback and a malformed host instruction with an available input word. For the two new variants the test compares writeback enable and data with the original retirement logic on each exercised execute or retry edge. All 89 existing Python model tests passed separately. These are exploratory tests, not registered verification results.

The expired-retry test also releases a blocked host read in the other context on edge F, after retry selection. It confirms that the other context is runnable on F but does not issue or transfer payload, and both contexts stop on F+1. This checks fault ordering for the measured schedule, not equivalence to the same-cycle scheduler.

`OPT=5` and `OPT=6` each passed 124/124 RTL replay cases with EVAL-020's independent monitors: 14 Fast-mode I2C alone, 14 Fast-mode I2C with SPI, and 96 UART RX with SPI. The retry-only schedule previously passed the same matrix. The replays use RTL, not the repaired netlist.

## Recommendation

Use `OPT=5` as the leading implementation candidate, not as an adopted pipeline or timing sign-off. It avoids adding a cycle to every instruction, passed the replay, and was smaller and faster than predecode at placement. Before adoption, review the one-cycle change to expired-retry detection against the block contract. Verify the real host-to-core boundary, setup margin, hold and cell area on the integrated routed design. Do not change the ISA, block contracts or clock target based on this probe.

## Reproduce

Run from WSL at the repository root. The summaries record source hashes. The Git command identifies the archived model revision.

```bash
source scripts/env.sh
pdk="$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l"
tiles="$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def"
for v in 3 5 6; do
  work="test/sim_build/EVAL-021/v$v"
  out="design/evals/EVAL-021/v$v"
  python3 -B -m models.physical.run_full_core_probe --opt "$v" --work "$work" --out "$out" \
    --pdk "$pdk" --def "$tiles" || exit 1
  iverilog -g2005 -s full_core_probe_tb -Pfull_core_probe_tb.OPT="$v" -o "$work/probe.vvp" \
    models/physical/full_core_probe_tb.v models/physical/full_core_probe.v \
    models/physical/full_core_drive.v models/physical/full_core_capture.v \
    models/physical/probe_store.v models/physical/regfile_probe.v || exit 1
  vvp "$work/probe.vvp" || exit 1
done
for v in 5 6; do
  python3 -B -m models.physical.run_full_core_replay --opt "$v" --out "design/evals/EVAL-021/v$v/replay.json" || exit 1
done
python3 -B -m models.physical.run_full_core_cts --work test/sim_build/EVAL-021/v5 --out design/evals/EVAL-021/v5 \
  --pdk "$pdk" --def "$tiles"
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-021/v5/summary.json
```
