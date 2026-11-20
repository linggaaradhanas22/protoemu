# EVAL-012 — Fault, stop and halt ordering with pending work
- Status: done
- Traces to: BLK-CORE, BLK-HOST, BLK-DRIVE, BLK-CAPTURE, BLK-PADS, SPEC-HOST-001
- Compares: fault safe edge on F + 1 (next), fault safe edge on F (same)
- Model: `models/benchmarks/g4_stop.py`

## Question

The records say a fault or `STOP` makes the pads safe and clears pending work, and that `safe` and `flush` win over a coincident update. They do not say on which edge a core fault takes effect. They also don't say what happens to updates, captures, waits and payload transfers that are due on or near that edge, or how this relates to `halt`. Does a simple rule avoid duplicate or partial effects on real programs?

## Rules compared

A fault is detected when the issue path tries to execute an operation, on edge F. The faulting operation does not retire.

| Rule | Safe edge | Work due on F |
|---|---|---|
| `next` (proposed) | F + 1. The fault is registered first. | Completes normally: due updates retire and observations are recorded |
| `same` | F | Suppressed. Needs a combinational path from decode to flush and pads |

On the safe edge X, the model suppresses updates due on X, discards queued updates, clears both capture slots, releases every owned pad and stops issue. A host `STOP` uses its own safe edge S with the same actions.

## Method

Three draft-ISA benchmarks, two of them across timer wrap:

| Scenario | Run (cycles) | Issues | Updates admitted | Captures | Payload transfers |
|---|---:|---:|---:|---:|---:|
| UART RX + SPI overlap with `host_get`/`host_put` | 15,378 | 690 | 70 | 62 | 7 |
| I2C combined write/read, 1 µs clock stretch, open drain | 8,790 | 1,576 | 171 | 76 | 0 |
| RC5 receive with `edge_delta`, long fences and `host_put` | 13,841,714 | 946 | 0 | 56 | 2 |

- **Fault:** fault the issue attempt after each possible issue count, under both rules.
- **Host stop:** put S on every edge with an issue, retirement or capture, the edge after each, and evenly spaced edges.
- Compare each stopped run with the same run without a stop. Before the stop, the issue, admission, retirement, capture, sample, payload and pad-write traces must match exactly. Each admitted update must retire exactly once if due before X, and be flushed and never retire otherwise. No pad may be written on or after X except the release. No owned pad may still be driven afterwards.

Five directed tests also run. They check that a fault keeps a drive due on F and flushes one due on F + 1, and that a `STOP` suppresses an update and a capture due on S. They also check that a halted context's updates retire until the other context faults. A deliberately faulty stop rule must make the checker report an error.

## Results

| Scenario | Faults, `next` | Faults, `same` | Host stops | Most updates flushed | Longest flushed lead (cycles) | Shortest held pad value (cycles) |
|---|---:|---:|---:|---:|---:|---:|
| UART + SPI | 690 / 690 | 690 / 690 | 963 / 963 | 3 | 4,226 (70 µs) | 1 |
| I2C | 1,576 / 1,576 | 1,576 / 1,576 | 2,073 / 2,073 | 4 | 157 | 1 |
| RC5 | 946 / 946 | 946 / 946 | 3,060 / 3,060 | 0 | – | – |

- **All 12,520 stopped runs met every check.** No update retired twice. No update was lost without being flushed. No pad changed after its safe edge.
- The rules differ in only **3 of 3,212** fault points. In those cases a drive or capture was due exactly on F. `next` lets it happen; `same` suppresses it. Neither leaves partial state.
- A stop can release a pad **one cycle** after its last programmed change, in every scenario that drives pads. A peer can see a 17 ns pulse or a truncated frame. This is the same under both rules, because a `STOP` can arrive at any edge.
- Up to four queued updates are discarded. The furthest was 70 µs ahead.
- All 64 Python model checks passed (5 new). EVAL-003 through EVAL-011 regenerate byte-identical results. The new safe-edge hook is off by default.

## Conclusion

Recommend `next`. Behavior differs only on the rare edge where work is due exactly when the fault is detected, and both rules are clean there. `next` registers the fault like the existing `STOP` path, so no decode result reaches the pad or queue flush in the same cycle. That timing benefit is a **guess**: it has not been measured. [CHG-008](../changes/CHG-008-stop-ordering.md) proposes the full ordering, including halt and the host-visible run states.

## Limits

- The model raises some faults one cycle early: on the fetch that precedes the bad operation, not on its execute. The ordering checks are relative to the fault edge, so this does not change the results.
- Injected faults stand for every fault cause. Programs that fault for real are not replayed.
- Registers are not checked after a stop, because they are not visible to the host and `START` clears them. The two-word `edge_delta` writeback schedule is still open.
- Simultaneous host and core access to one payload FIFO is not modeled.
- Fault-to-pad timing and area are not measured. No production RTL or registered tests changed.

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-012/results.json
python3 -B -m models.benchmarks.g4_stop --out design/evals/EVAL-012/results.json
python3 -B -m unittest models.benchmarks.test_g4_stop models.benchmarks.test_g4_guards models.benchmarks.test_g4_edges models.benchmarks.test_g4_payload models.benchmarks.test_g4_pad_encoding models.benchmarks.test_g4_isa models.benchmarks.test_g4_timestamp models.benchmarks.test_g4_loader models.benchmarks.test_g4_timing models.benchmarks.test_compare models.benchmarks.test_encoded
```

The sweep takes about 2.5 minutes. The [results](EVAL-012/results.json) store the per-scenario summary and any failing rows.
