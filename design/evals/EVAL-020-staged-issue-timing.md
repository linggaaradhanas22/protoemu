# EVAL-020 — Place and replay registered issue boundaries
- Status: done
- Traces to: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, SPEC-PHY-001, SPEC-I2C-003
- Compares: ARCH-B
- Model: `models/physical/full_core_probe.v`, `models/physical/run_full_core_replay.py`

## Variants

- `OPT=2`: same-cycle EVAL-019 control, remapped from the current source. Placement slack can differ from the historical run because Yosys mapped the refactored selection logic differently.
- `OPT=3`: register the context selected for a retry, then commit on the next edge. Fresh instructions still use fetch and execute. Retry uses its saved operands, not a fresh decode; the drive queue rechecks the original deadline at commit.
- `OPT=4`: also register the freshly calculated relative offset, deadline and expiry before execute. This costs one edge on every fresh instruction, not only instructions that use the timer. `SAVE_NOW` observes the actual execute edge, not the preparation edge.

Neither staged variant overlaps issue slots. A waiting drive with no credit can be selected when its deadline arrives; the staged versions report the fault on retry commit one edge later. They do not apply a late pad update. Fault safe handling is still F+1 relative to detection. These are experimental schedules, not changes to the agreed blocks.

## Placement at 60 MHz

Same corners, placement assumptions and stubbed host interface as EVAL-019. These numbers exclude CTS, hold repair, routing and the production loader.

| Variant | Slow setup, overall | Slow setup, internal | Saved request to drive queue, slow setup | Fast hold, internal | Slow placed area |
|---|---:|---:|---:|---:|---:|
| `OPT=2` Same-cycle control | −4.889 ns | −3.778 ns | −1.451 ns | −0.053 ns | 385,640 µm² |
| `OPT=3` Register retry selection | −2.025 ns | −1.499 ns | +9.615 ns | −0.053 ns | 384,009 µm² |
| `OPT=4` Also register fresh timing operands | −1.530 ns | +0.302 ns | +8.963 ns | −0.056 ns | 388,824 µm² |

Registering retry selection removes the measured deficit on the saved-request-to-queue path. The worst internal path then runs from the fetched instruction to a general register write. `OPT=4` meets slow internal setup by 0.302 ns but misses overall setup on an instruction-to-`ingress_pop` path under the probe's I/O assumptions. Fast internal hold still misses between the pad synchronizer stages.

## RTL replay

The Icarus harness loads the existing program images into the actual probe store. It supplies preloaded payload with the planned eight-word FIFO bounds and connects the registered pins to the independent Python peers and monitors. It does not model the SPI loader or gate delays. The matrix is 28 Fast-mode I2C cases (the seven EVAL-017 scenarios with and without SPI traffic, repeated near wrap) and 96 UART RX plus 1 MHz SPI overlap cases (16 UART phases, three SPI start offsets and two epochs). The I2C plus SPI sweep uses one fixed inter-exchange gap of 400 clocks, not the full EVAL-017 gap sweep.

The directed smoke checks passed for all variants, including retry across wrap, a missed deadline with no credit, guarded waits, and the F/F+1 distinction. The 89 existing Python benchmark tests passed separately. These exploratory runs do not update registered test status.

| Variant | Fast-mode I2C alone | Fast-mode I2C with SPI | UART RX with SPI | Total |
|---|---:|---:|---:|---:|
| `OPT=2` Same-cycle control | 14/14 | 14/14 | 96/96 | 124/124 |
| `OPT=3` Register retry selection | 14/14 | 14/14 | 96/96 | 124/124 |
| `OPT=4` Also register fresh timing operands | 14/14 | 6/14 | 0/96 | 20/124 |

The eight contended Fast-mode I2C failures in `OPT=4` are core faults. The first reaches PC 63 (`shift_pin` on SDA with a 20-cycle offset) and reports a drive rejection. The 96 UART/SPI failures are exact chip-select schedule mismatches only: the monitors found no other SPI timing, UART or payload errors in those cases.

## Decision boundary

Do not adopt the extra execute edge globally. Keep the registered retry boundary as a candidate. To close the remaining setup gap, target the fresh instruction-to-writeback path without extending every instruction, or overlap preparation with independent work. Any new schedule must pass the same pin replay and preserve safe-edge behavior. Hold still needs separate physical work.

## Reproduce

Run from WSL at the repo root with the same local LibreLane image and PDK as EVAL-019:

```bash
source scripts/env.sh
for v in 2 3 4; do
  work="test/sim_build/EVAL-020/v$v"
  out="design/evals/EVAL-020/v$v"
  python3 -B -m models.physical.run_full_core_probe --opt "$v" --work "$work" --out "$out" \
    --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
    --def "$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def" || exit 1
  iverilog -g2005 -s full_core_probe_tb -Pfull_core_probe_tb.OPT="$v" -o "$work/probe.vvp" \
    models/physical/full_core_probe_tb.v models/physical/full_core_probe.v \
    models/physical/full_core_drive.v models/physical/full_core_capture.v \
    models/physical/probe_store.v models/physical/regfile_probe.v || exit 1
  vvp "$work/probe.vvp" || exit 1
  python3 -B -m models.physical.run_full_core_replay --opt "$v" --out "$out/replay.json" || exit 1
done
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-020/v2/summary.json
```
