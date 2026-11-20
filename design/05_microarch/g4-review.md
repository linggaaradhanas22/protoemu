# G4 review: instruction formats and block contracts

**Approved for the draft:** [DEC-004](../04_decisions/DEC-004-hybrid-pad-isa.md) and [CHG-004](../changes/CHG-004-hybrid-pad-isa.md) carry both timed pad formats forward. Use compact instructions for one or two pads and a vector instruction for a wider update. Both feed the same four-entry queue. See the [draft instruction fields](isa-draft.md).

This is not a request to approve G4. The blocks below remain draft. This decision does not freeze a binary interface for software or authorize production RTL.

## What the evidence supports

- [EVAL-003](../evals/EVAL-003-g4-timed-io.md): four output slots, one capture slot per context and shared issue work for the tested UART/SPI and stretched I2C workloads. This does not prove admission under arbitrary load.
- [EVAL-005](../evals/EVAL-005-isa-timestamps.md) and [EVAL-006](../evals/EVAL-006-isa-encoding.md): one saved timestamp per context works in the tested schedules. Offsets can span more than one instruction's immediate field. [DEC-003](../04_decisions/DEC-003-isa-timestamps.md) already approves the timestamp representation, not the offset register assignment.
- [EVAL-007](../evals/EVAL-007-eight-pad-encoding.md): each format passed 116 modeled cases. Compact used 63 words for stretched I2C versus 74 for the unoptimized vector translation. Vector used one queue entry for an eight-pad update versus four for compact.
- [EVAL-008](../evals/EVAL-008-eight-pad-timing.md): hybrid placed setup slack was +4.566 ns at 60 MHz at the slow corner. Fast hold missed by 0.199 ns overall and 0.037 ns on internal register paths. The slice excludes the full core and loader. No routed timing or tile fit claim follows.
- [DEC-002](../04_decisions/DEC-002-loader-transport.md) and [CHG-002](../changes/CHG-002-loader-recovery.md) already approve the SPI loader pin split and reset/reload recovery policy. Board timing and final payload FIFO depth remain open.
- [CHG-005](../changes/CHG-005-host-payload.md) approves generic `host_get` and `host_put` for the draft ISA. [EVAL-009](../evals/EVAL-009-host-payload.md) replayed 96 overlap cases with the host model.
- [CHG-006](../changes/CHG-006-edge-interval.md) approves edge capture and elapsed-time behavior for the draft ISA. [EVAL-010](../evals/EVAL-010-edge-interval.md) replayed six RC5 cases, including wrap. The model does not settle two-register writeback timing.

## Block contracts for review

The linked records define the interfaces. The checks below are planned, not passing tests.

| Block | Contract to preserve | Planned unit check |
|---|---|---|
| [Core](BLK-CORE.md) | Two contexts share one fetch and execute path. A blocked context retains its request and does not stop the other context from issuing. Saved time belongs to the context. | `TEST-UNIT-001`: isolation, retry identity and faults |
| [Program store](BLK-PROGRAM.md) | One 128-word, 24-bit store with registered fetch. Tentative and out-of-image words do not execute. | `TEST-UNIT-002`: commit, bounds and shorter reload |
| [Drive](BLK-DRIVE.md) | Four unordered deadline slots. Disjoint due masks merge. A late or conflicting update faults rather than driving a pad late. | `TEST-UNIT-003`: collision, wrap and slot reuse |
| [Capture](BLK-CAPTURE.md) | One arm/result slot per context. The result contains the original synchronized observation time. | `TEST-UNIT-004`: ownership, simultaneous observations and rearm |
| [Timer](BLK-TIMER.md) | One 24-bit cycle counter. Check the future half range on admission. | `TEST-UNIT-005`: counter wrap and range bounds |
| [Pads](BLK-PADS.md) | Register pad values and enables. Open drain drives low or releases. Safe overrides a coincident update. | `TEST-UNIT-006`: map, registered changes and safe precedence |
| [Host](BLK-HOST.md) | SPI load, commit, then explicit start. No automatic command replay after an uncertain transfer. | `TEST-UNIT-007`: frame validation, FIFO handling and restart |

## Before asking for block approval

1. Resolve global fault timing and elapsed-time writeback. [CHG-007](../changes/CHG-007-modular-guards.md) settled modular wait/fence behavior. Replay baseline and non-target programs, including ones that need these operations.
2. Review each block with its unit test. Keep provisional host timeout and FIFO sizing assumptions visible. If a draft interface changes, record the change before agreement.
3. Check full-core timing with the saved-request path and actual register file. Track fast hold, routed setup and tile fit separately from G4 agreement. The slice does not substitute for sign-off.
