# G4 decision review

Lingga withdrew G4 approval after the first core timing experiments. The seven block agreements still stand. This page separates decisions that affect the design contract from checks that need production RTL or hardware. No recommendation here changes an agreed item.

## Decisions to resolve before reapproval

| Decision | Evidence | What still needs a decision or a check |
|---|---|---|
| Core retry schedule and expired-request fault edge | [EVAL-020](../evals/EVAL-020-staged-issue-timing.md) compares added issue stages. [EVAL-021](../evals/EVAL-021-fresh-writeback-timing.md) compares writeback paths. [EVAL-022](../evals/EVAL-022-expired-retry.md) checks the observable fault-edge difference when another context becomes ready. | Decide whether fault detection should occur on selection or commit. Decide whether the bound is relative to round-robin selection or the absolute deadline. Preserve F+1 safe handling, and do not allow a late pad update. |
| ISA opcode map and offset pair | The [ISA draft](isa-draft.md) lists the implemented model encoding. [EVAL-016](../evals/EVAL-016-program-suite.md) exercises the baseline programs. [EVAL-013](../evals/EVAL-013-delta-writeback.md) measures the narrow writeback port with R0/R6 reserved for the offset. | Check encoder and decoder agreement, invalid encodings, and the R0/R6 convention. Decide explicitly whether to freeze the current binary map or keep it provisional until that check passes. |
| Capture timeout interface | [CHG-013](../changes/CHG-013-timed-wait.md) selects guarded timeout behavior. [EVAL-017](../evals/EVAL-017-wait-timeout.md) estimates the slot cost of storing `Rt`. The EVAL-021 full-core probe includes that implementation. | Compare retaining `Rt` in the slot with passing a precomputed expiry. Measure both against the same model and constraints. Check guard opening, already-passed targets, wrap, `Rt = 0`, and a match on the expiry edge. |
| Host command and status encoding | [BLK-HOST](BLK-HOST.md#spi-and-load-sequence) defines frame and command behavior. [EVAL-015](../evals/EVAL-015-host-rate.md) measures the transport model and FIFO area. | Check the command, status, fault and reserved values in one replayable table. Test good and bad encodings, including `READN`/`WRITEN` and interrupted replies. Review the area of the framing and run-control logic separately. |

## Checks after the decisions

- Check the host and core together at slow and fast corners after routing. The core-only repair probe does not establish setup margin, hold, or full-chip tile fit.
- Measure 1 MHz RP2350 SPI and the host timeouts on the board. If the board requires the 500 kHz fallback, document the reduced sustained payload rate.
- Run the planned block and integration tests against the agreed schedules. Update any affected block record and its sequence diagram after Lingga selects the schedule.

These checks remain open. A `MET` result from the trace checker does not replace Lingga's review or reapproval.
