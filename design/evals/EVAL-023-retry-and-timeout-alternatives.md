# EVAL-023 — Retry policy and capture timeout alternatives
- Status: done
- Traces to: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, SPEC-PHY-001
- Compares: ARCH-B
- Model: `models/physical/full_core_probe.v`, `models/physical/capture_expiry_probe.v`, `models/physical/run_capture_expiry_probe.py`

## Variants

Four retry policies use the same separate-writeback core. Each one adds and removes only the admission exception described below.

- Pattern 2: same-cycle retry control.
- Pattern 7: rejected. This is the earlier commit-only retry with a selection-edge fault for an expired drive. It loses the final legal admission edge.
- Pattern 8: bypass the retry register only when the selected drive's original deadline is one cycle ahead. The queue still revalidates the deadline at admission. Expiry then faults on selection as in pattern 7.
- Pattern 9: bypass the retry register whenever a waiting drive wins selection and the queue has credit. This restores the same-cycle admission path for every valid drive retry. An expired drive still faults at selection.

The capture alternative stores the guard target and a precomputed expiry from the core instead of storing `Rt` and reloading the expiry when the guard opens. It changes no pin behavior in the directed comparison.

## Placement at 60 MHz

Same placement flow and corners as EVAL-022.

| Pattern | Slow worst setup | Slow internal setup | Fast internal hold | Slow placed cell area |
|---|---:|---:|---:|---:|
| 7, commit-only with selection fault | −0.264 ns | −0.264 ns | −0.055 ns | 385,359 µm² |
| 8, last-edge bypass | −9.221 ns | −8.413 ns | −0.045 ns | 387,362 µm² |
| 9, full drive bypass | −7.994 ns | −5.462 ns | −0.055 ns | 385,765 µm² |

Both bypass variants miss slow setup by several nanoseconds. The bypass multiplexer is on the fetch and register-read path, and the result is worse than pattern 7. This is the cost of same-cycle drive admission on top of registered selection. It does not follow from the area or the protocol result. Pattern 8 also misses the saved-request-to-queue group by 3.834 ns. Pattern 9 misses it by 2.942 ns.

## Directed and protocol checks

| Pattern | Last legal edge at D−1 | Older update at D+1 with fault at D | Protocol replays |
|---|---|---|---|
| 2 | admitted | suppressed | 124/124 |
| 7 | lost | no | 124/124 ([log](EVAL-023/v7/replay.json)) |
| 8 | admitted | no | 124/124 ([log](EVAL-023/v8/replay.json)) |
| 9 | admitted | no | 124/124 ([log](EVAL-023/v9/replay.json)) |

For pattern 9, an expired drive that wins selection faults at D, before any drive credit or pin effect. Patterns 8 and 9 pass the same directed expiry checks. Pattern 9's expiry test covers both ready-at-D and ready-at-D+1 cases.

Capture comparison: 29 directed cases and 2,379 checked edges. The test compares slot occupancy, result, timestamp and expiry on every edge. It covers both contexts, wrap and non-wrap, guarded targets before, at and after the deadline, already-passed targets, `Rt = 0`, same-edge match and expiry, and two simultaneous expiries. Both implementations match on every edge.

## Capture timeout storage

The existing slot stores `Rt` and reloads its deadline when the guard opens. The alternative stores the guard target and a precomputed 24-bit expiry.

| Implementation | Typical map area | Flops | Delta |
|---|---:|---:|---:|
| Store `Rt`, reload at guard open | 17,680.6 µm² | 162 | — |
| Store precomputed expiry | 16,342.1 µm² | 180 | −1,338.5 µm² |

The precomputed version adds 18 flops and is smaller after mapping, because it removes the 16-bit incrementer and comparator path. This is a typical-corner probe, not a placed block. The result contradicts the earlier assumption that the extra register would cost area; it needs a second look in the integrated capture block. Neither option changes the block interface if the core supplies the expiry value.

## Recommendation for the G4 review

Do not use a bypass to recover the last legal admission edge. Both bypass variants lose several nanoseconds of slow-corner setup on the shared fetch path. Treat the final-edge loss as a software constraint for the registered schedule. A program that arms a drive must leave at least one more cycle of queue credit than the same-cycle model required. Recheck that bound against the baseline programs before adopting the schedule.

Keep storing `Rt` for now. The precomputed-expiry probe is smaller and uses more flops, but it has not been placed with the real capture block. Measure it there before changing the interface.
