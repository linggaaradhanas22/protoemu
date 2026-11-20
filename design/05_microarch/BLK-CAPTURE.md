# BLK-CAPTURE — Context-owned input capture
- Status: draft
- Traces to: DEC-001, SPEC-UART-002, SPEC-SPI-001, SPEC-I2C-003, SPEC-PROG-003, REQ-PROTO-004

## Purpose

Capture synchronized input levels or edges independently of the issue path. Retain a result until its owning context consumes it.

## Interface

| Signal group | Dir | Width | Meaning |
|---|---|---|---|
| `cycle`, `pin_sample` | In | `W`, `P` | Cycle timebase and second-stage pad samples |
| `capture_req` | In | `valid`, 1-bit context, pin index, mode, `W`-bit deadline | Arm a timed level sample or selected edge/level condition, or request consume |
| `capture_status` | Out | `ready`, `reject`, 2 result-ready bits; result bit and `W`-bit timestamp for selected owner | No result is returned from the other context's slot |
| `flush` | In | 1 | Clear slots and suppress captures on that edge |

Draft contract: one slot per context (`EMPTY`, `ARMED`, `RESULT`). Arm only from `EMPTY`; a second arm to an occupied slot is a programming fault, not an overwrite. Consume only from `RESULT`; a premature consume waits without issuing repeatedly. Neither context can modify or consume the other's slot. The pad-to-owner restriction applies to output writes, not reads.

Sample `pin_sample` as seen before the decision edge and timestamp it with the pre-edge `cycle`, not the asynchronous pad transition time. With continuously updated sample history, an edge arm considers transitions on decision edges **after** its acceptance edge. A level arm can detect a level already present on its first observation edge. A guarded level arm (`wait_save` with a saved time) classifies its earliest target once at the arm edge under the [CHG-007](../changes/CHG-007-modular-guards.md) rule. A future target (`1` through `2^23 − 1` cycles ahead) opens the guard on the edge where `cycle == target`; an observation on that edge counts. A reached or passed target opens it at once, without a fault. Hold one guard-open bit per slot until the slot is consumed, flushed or reset. An open guard does not close again, however long the level takes. Timed arms obey BLK-TIMER admission. A due sample sees the pre-edge synchronized value even if an output changes on that edge. Capture becomes readable on the next cycle; no consume/capture bypass. Both slots may finish on the same edge. Further edges while a result is held are not buffered. Reset disarms both slots; execution cannot arm before input synchronization has settled after reset. After a core fault on edge F, an observation on F is still recorded; `flush` on F + 1 clears both slots and guard bits and suppresses observations on that edge ([CHG-008](../changes/CHG-008-stop-ordering.md)).

At consume, return the original observation timestamp even if the result waited for issue. BLK-CORE can save it in the owning context's timestamp register. This does not change the slot format or ownership rules.

For `edge_save` and `edge_delta`, arm for falling, rising or either polarity. Neither instruction consumes an edge observed on the arm edge. Return the same observation timestamp and sampled level for both. The core computes intervals. The capture slot does not add a timeout, buffer extra edges, or allow one context to read the other slot.

## Implementation options and budget

Evaluate fixed mailboxes against a tagged shared FIFO. Fixed ownership prevents a slow consumer from using both slots. Measure observation-to-consume latency and check whether rearm gaps lose UART/RC5 edges at the required rates. Planning allowance: 0.040 mm² of cell area; not measured for this block.

## Unit-test plan and RTL

Check simultaneous capture, stable results, capture/consume ordering, wrap, arm/rearm boundaries, and reset in every slot state. Planned file: `src/timed_capture.v`.
