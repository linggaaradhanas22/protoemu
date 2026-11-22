# G4 decision review

Lingga withdrew G4 approval after the first core timing experiments. The seven block agreements still stand. This page separates decisions that affect the design contract from checks that need production RTL or hardware. No recommendation here changes an agreed item.

## Approval

Lingga approved all four recommendations below on 2026-11-22. The block contracts therefore need no change. Micro-architecture gate approval is a separate step and is not given by this page.

## Decisions to resolve before reapproval

| # | Decision | Evidence now | Recommendation | Still needs a human decision or a check |
|---|---|---|---|---|
| 1 | Core retry schedule and fault edge | [EVAL-020](../evals/EVAL-020-staged-issue-timing.md), [EVAL-021](../evals/EVAL-021-fresh-writeback-timing.md), [EVAL-022](../evals/EVAL-022-expired-retry.md), [EVAL-023](../evals/EVAL-023-retry-and-timeout-alternatives.md) | Keep the agreed same-cycle retry contract as the behavior baseline. It is the only schedule that already matches the agreed fault and admission edges. Do not replace it with a registered variant that changes when a fault is detected and when a freed slot can be reused. | Confirm the fault edge and F+1 safe rule against the model. Add a directed expired-retry test to TEST-UNIT-001 for the same-cycle design. |
| 2 | ISA opcode map and offset pair | [EVAL-024](../evals/EVAL-024-encoding-check.md), [EVAL-016](../evals/EVAL-016-program-suite.md), [EVAL-013](../evals/EVAL-013-delta-writeback.md) | Keep the current map provisional. All 26 opcodes are unique, the boundary corpus round-trips, and the R0/R6 convention is exercised by the baseline programs. The production encoder is not written. | Decide whether to freeze the map now or after the assembler exists. Check the production decoder against the same corpus before freezing. |
| 3 | Capture timeout storage | [EVAL-023](../evals/EVAL-023-retry-and-timeout-alternatives.md), [CHG-013](../changes/CHG-013-timed-wait.md) | Keep storing `Rt` for now. The precomputed-expiry probe is 1,338 µm² smaller but adds 18 flops, and it has not been placed with the real capture block. | Decide whether the 18 extra flops and smaller combinational depth are worth an interface change after a placed comparison. |
| 4 | Host command and status encoding | [EVAL-024](../evals/EVAL-024-encoding-check.md), [EVAL-015](../evals/EVAL-015-host-rate.md), [BLK-HOST](BLK-HOST.md#spi-and-load-sequence) | Freeze the command behavior described in BLK-HOST, not the numeric status values. `BEGIN`, `DATA`, `COMMIT`, `START`, `WRITE`, `READ`, `WRITEN`, `READN` and `STOP` all behave as documented in the loader model, and an interrupted `READN` restarts without losing words. | Choose numeric opcode and status values before the RTL decoder exists, or explicitly keep them provisional into G5. Measure the RTL framing area. |

## Decision 1 detail

The same-cycle control passed every replay and directed case. Pattern 5, the registered design closest to a deliverable, missed slow setup by 0.636 ns before clock-tree synthesis and missed hold repair at the buffer cap. That is not 60 MHz closure, and the same-cycle control is not available for a direct comparison.

The registered variants change two observable edges:

- An expired retry can fault one cycle later, so an older admitted update can become visible before safe.
- A slot that first frees on the last legal edge cannot be used by a registered retry.

Neither difference is acceptable for the agreed CHG-008 ordering without a change request. The bypass designs that restore the last edge miss slow setup by 7 to 9 ns, because the bypass sits on the shared fetch path. That makes them worse than the control for timing.

There is no evidence that a registered retry schedule can keep the agreed fault edge and admission edge. Further work on 60 MHz timing should look at the fresh instruction execute and writeback path, or at a different fetch/execute organization, not at retry admission. That is an implementation question, and it does not change the block contracts.

## Checks after the decisions

- Check the host and core together at slow and fast corners after routing. The core-only repair probe does not establish setup margin, hold, or full-chip tile fit.
- Measure 1 MHz RP2350 SPI and the host timeouts on the board. If the board requires the 500 kHz fallback, document the reduced sustained payload rate.
- Run the planned block and integration tests against the agreed schedules. Update any affected block record and its sequence diagram after Lingga selects a schedule.

These checks remain open. A `MET` result from the trace checker does not replace Lingga's review or reapproval.

## Follow-up for the production work

Decisions 2 and 4 stay provisional into G5. The open follow-ups are:

- Freeze the opcode map when the assembler and decoder exist, after the boundary corpus passes on the RTL decoder.
- Freeze the host numeric values when the RTL command decoder exists, alongside the framing area measurement.
- Revisit capture timeout storage only if a placed capture block shows the 18-flop version is clearly better.

Add a directed expired-retry test to TEST-UNIT-001 so the same-cycle fault edge is verified explicitly, not only by the model.
