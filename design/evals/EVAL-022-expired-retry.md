# EVAL-022 — Observe the expired-retry fault edge
- Status: done
- Traces to: BLK-CORE, BLK-DRIVE, BLK-PADS, SPEC-PHY-001
- Compares: ARCH-B
- Model: `models/physical/full_core_probe.v`, `models/physical/full_core_probe_tb.v`

## Method

The probe fills four drive slots. A fifth request waits until its original deadline `D`, across counter wrap. An older admitted update is due at `D+1`. The other context has a blocked host read, which becomes ready either on `D` or on `D+1`. Check the fault record, original request retirement count, host reads, visible pad update, and global safe edge.

- Pattern 2: select and execute a retry on one edge. This is the same-cycle control.
- Pattern 5: select a runnable retry on one edge and execute on the next. This is the separate-writeback candidate from EVAL-021.
- Pattern 7: retain pattern 5's retry path for non-expired requests. For an expired drive request that wins round-robin selection, record the fault on the selection edge. This does not preempt another context that wins selection.

## Directed results

| Other context ready | Pattern | Fault F | Safe edge | Older update due at D+1 visible? | Other context host reads |
|---|---|---|---|---|---:|
| D+1 | 2 | D | D+1 | No | 0 |
| D+1 | 5 | D+1 | D+2 | Yes | 0 |
| D+1 | 7 | D | D+1 | No | 0 |
| D | 2 | D+1 | D+2 | Yes | 1 |
| D | 5 | D+3 | D+4 | Yes | 1 |
| D | 7 | D+2 | D+3 | Yes | 1 |

No variant admitted the expired fifth request. All variants stopped both contexts and released the pads on F+1. The delayed fault can make an already-admitted update visible even though it never applies the expired request itself. Pattern 7 restores the same edge when the expired request wins selection at `D`. It is not cycle-equivalent when the other context wins first: its registered host retry uses an additional edge.

In a separate test, a slot frees on `D−1`, the last legal admission edge. Pattern 2 admits the saved request on `D−1` and drives on `D`. Patterns 5 and 7 select on `D−1`, reject at commit on `D`, and go safe on `D+1`. Selecting an already-expired request earlier does not recover the lost issue cycle for a request that was still valid on selection.

This distinguishes three possible commitments. A selection-relative rule can preserve round robin and F+1 without promising a fault at `D`. A commit-relative registered rule needs explicit acceptance of the extra edge and the `D+1` pad update in the first case. An absolute `D` guarantee would require a separate priority or fault mechanism not tested here. Even the same-cycle control does not guarantee `D` under arbitration.

## 60 MHz placement

Same PDK, timing assumptions and 8×4 rows as EVAL-021. Both variants run from the same source revision. The clock is ideal and the flow estimates wire delays from placement.

| Pattern | Slow worst setup | Fast internal hold | Slow placed cell area |
|---|---:|---:|---:|
| 5, fault on registered retry commit | −0.636 ns | −0.056 ns | 385,150 µm² |
| 7, fault on selection for an expired drive | −0.468 ns | −0.054 ns | 385,250 µm² |

The selection check adds 100 µm² of placed cells in this run. It does not make the worst setup path worse, but neither unrepaired variant closes timing. The difference is not evidence that the added logic speeds up the core. Small mapping and placement differences affect these numbers.

Pattern 7's separate clock-tree experiment reported −0.479 ns worst setup and −0.086 ns internal hold after CTS, before timing repair. OpenROAD stopped during hold repair at its 4,032-buffer cap and reported −0.071 ns overall hold at that point. It did not produce a final legalized timing report. Pattern 5's EVAL-021 repair result is not transferable to pattern 7. See the [CTS log](EVAL-022/v7/cts.txt).

## Result for G4

Pattern 7 passed [124/124 protocol replays](EVAL-022/v7/replay.json). The directed checks exposed a difference the protocol suite did not exercise. All 89 Python model checks passed separately. See the [directed simulation output](EVAL-022/expiry-overlap.txt).

Keep the current G4 contracts and do not adopt a registered retry schedule yet. Preserve the final legal admission edge when the retry wins arbitration, unless Lingga explicitly accepts losing it. If the edge must remain usable, compare a fast admission path for selected drives on that edge against same-cycle retries. [CHG-014](../changes/CHG-014-expired-retry-selection.md) describes the narrower option if the extra lead time is acceptable. This evaluation does not establish 60 MHz timing closure.

## Reproduce

From the repository root in WSL:

```bash
source scripts/env.sh
pdk="$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l"
tiles="$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def"
mkdir -p test/sim_build/EVAL-022
for v in 2 5 7; do
  iverilog -g2005 -s full_core_probe_tb -Pfull_core_probe_tb.OPT="$v" \
    -o "test/sim_build/EVAL-022/check-$v.vvp" models/physical/full_core_probe_tb.v \
    models/physical/full_core_probe.v models/physical/full_core_drive.v \
    models/physical/full_core_capture.v models/physical/probe_store.v models/physical/regfile_probe.v || exit 1
  vvp "test/sim_build/EVAL-022/check-$v.vvp" || exit 1
done
for v in 5 7; do
  python3 -B -m models.physical.run_full_core_probe --opt "$v" \
    --work "test/sim_build/EVAL-022/v$v" --out "design/evals/EVAL-022/v$v" \
    --pdk "$pdk" --def "$tiles" || exit 1
done
python3 -B -m models.physical.run_full_core_replay --opt 7 --out design/evals/EVAL-022/v7/replay.json
python3 -B -m models.physical.run_full_core_cts --work test/sim_build/EVAL-022/v7 --out design/evals/EVAL-022/v7 \
  --pdk "$pdk" --def "$tiles"
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-022/v7/summary.json
```
