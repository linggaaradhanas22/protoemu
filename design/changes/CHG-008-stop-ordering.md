# CHG-008 — Define fault, stop and halt ordering
- Status: proposed
- Size: medium
- Affects: BLK-CORE, BLK-HOST, BLK-DRIVE, BLK-CAPTURE, BLK-PADS, TEST-UNIT-001, TEST-UNIT-003, TEST-UNIT-004, TEST-UNIT-006, TEST-UNIT-007, TEST-INT-002

## Reason

BLK-HOST says core fault propagation to the safe edge still needs review. BLK-CORE says both contexts lose pending operations on "global fault, flush, or halt", which conflicts with `halt` ending only one context. The records don't define what the host sees after a fault or a normal finish. [EVAL-012](../evals/EVAL-012-stop-ordering.md) checks one ordering on 12,520 stopped runs.

## Proposed change

**Run states seen by the host:**

| State | Entered by | Pads | Image and payload FIFOs |
|---|---|---|---|
| `HALTED` | Reset, deselect, `STOP` | Safe | Invalid / cleared (as today) |
| `RUNNING` | `START` with a committed image | Programmed | In use |
| `DONE` | Every enabled context has halted and the drive queue is empty | **Hold their last values** | Kept, so the host can drain results |
| `FAULTED` | A core fault | Safe | Kept, so the host can drain results and read the fault record |

`START` is accepted only from `HALTED` with a committed image, as today. Leave `DONE` or `FAULTED` with `STOP`, which keeps its current meaning: safe, flush, clear payload, invalidate the image. A fresh load is then needed, as the records already require. The `STOP` reply carries the latched run status and fault record.

**Fault ordering:**
1. A fault is detected on the edge F where a context tries to execute an operation. That operation does not retire: no PC advance, register write, FIFO transfer, queue entry or arm. No other operation issues on F.
2. Everything else due on F completes. Updates due on F retire, and capture observations on F are recorded.
3. Register the fault. **F + 1 is the safe edge.** Assert `flush` and `safe` for that edge. Suppress updates due on it, discard all queue entries, clear both capture slots and guard bits, discard both contexts' pending operations and stop issue. Release every protocol pad.
4. Latch one fault record: context, PC and cause class. Cause codes stay provisional.

**`STOP`, reset and deselect:** unchanged. The safe edge is the edge after the validated frame close, or the first edge that samples reset or deselect. Nothing issues, captures or retires on it. If a fault safe edge and a `STOP` safe edge fall on the same edge, there is one safe edge and the status reports `FAULTED`. Priority on any edge: reset, then deselect, then the safe edge, then due updates.

**`halt`:** ends only its own context. Its queued updates still retire and its egress words stay readable. The other context continues. A later fault or `STOP` flushes any updates the halted context still has queued. Replace "global fault, flush, or halt" in BLK-CORE with "global fault, `STOP`, reset or deselect".

**No duplicate or partial effects:** each queue entry retires completely or not at all; a `pad2` or `drivev` entry is one entry. A shift source register changes only on admission. `host_get` pops and writes its register in the same retirement, and `host_put` pushes only on retirement. Registers are not visible after a stop, and `START` clears them. So a stop between the two `edge_delta` writes is not observable.

**Known limit:** a stop can release a pad one cycle after its last programmed change, which can truncate a peer's frame. Released pads take their board pull levels. The host must reset or resynchronize peers after `STOP` or a fault.

Item updates after approval:
- **BLK-CORE:** fault detection, the F + 1 safe edge, the fault record, and the `halt` wording.
- **BLK-HOST:** the run-state table, the fault record in the `STOP` reply, and `DONE`/`FAULTED` keeping payload. Replace "core fault propagation still needs integration review".
- **BLK-DRIVE, BLK-CAPTURE, BLK-PADS:** the F + 1 safe edge and the priority list. Interfaces are unchanged.
- **Tests:** TEST-UNIT-001 (no retirement on F, nothing issues after F), TEST-UNIT-003 and 004 (due on F retires or is recorded, due on F + 1 is suppressed), TEST-UNIT-006 (priority list), TEST-UNIT-007 (`DONE`/`FAULTED` payload and `START` rejection), TEST-INT-002 (fault with drive, capture, guard and payload pending; halted context's updates).
- **Model:** keep `g4_stop.py` as the reference for these checks.

## Impact

No SPEC or REQ changes; SPEC-HOST-001 already allows a separate start request and reload. Block interfaces are unchanged except that `run_status` carries the run state and fault record, which BLK-HOST already latches. All blocks are still draft, so nothing becomes `suspect`. Area and fault-to-pad timing are not measured.

Rejected alternative: a same-edge safe (`same`). It behaves differently in only 3 of 3,212 fault points and needs a combinational path from decode to flush and the pads.

Choices for Lingga (the defaults are proposed above):
- `DONE` holds the pads instead of making them safe. A UART TX line stays idle high without relying on a pull-up.
- `DONE` and `FAULTED` keep the payload FIFOs until `STOP`.

## Approval

medium: waiting for Lingga.

## Close-out

Not started.
