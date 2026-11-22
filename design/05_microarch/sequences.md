# ARCH-B sequence diagrams

[Editable draw.io book](diagrams/arch-b-sequences_v1.drawio) · [Chip block diagram](diagrams/arch-b_v2.svg) · [ISA draft](isa-draft.md)

The block diagrams show what connects. The sequences show when each block acts and what it hands off. In draw.io, follow a linked block header to its sequence page. Each detail page links back to the chip page. The SVGs below are static views.

## Chip sequence

![Four phases: the RP2350 loads and commits an image, the core starts and fetches, timed I/O exchanges signals with a protocol peer, and the host reads back results.](diagrams/seq-chip_v1.svg)

The host loads an image with `BEGIN`, `DATA` and `COMMIT`. Only a separate `START` enables fetch. The core issues instructions ahead of the pins: drive and capture use the same free-running cycle count and do not need an issue slot when an event comes due. One context can stall while the other issues. The program sends results through `host_put`; the RP2350 can drain them while running or after `DONE` or `FAULTED`.

Read the diagrams top to bottom. Spacing is not cycle count. Arrows show logical handoffs, not extra signals or mandatory wait cycles. Operations labeled for the same edge happen in parallel. The [block records](g4-block-review.md) define the full draft contracts.

| Chip phase | Block sequence pages |
|---|---|
| 01 Load and commit | [Host](#host), [Program store](#program-store), [Pad adapter](#pad-adapter) |
| 02 Start and fetch | [Host](#host), [Program store](#program-store), [Issue core](#issue-core) |
| 03 Timed I/O | [Issue core](#issue-core), [Timebase](#timebase), [Timed output](#timed-output), [Input capture](#input-capture), [Pad adapter](#pad-adapter) |
| 04 Readback | [Host](#host), [Issue core](#issue-core), [Pad adapter](#pad-adapter) |

## Host

[BLK-HOST](BLK-HOST.md) · [Block diagram](diagrams/blk-host_v1.svg) · [Back to chip sequence](#chip-sequence)

![Host sequence: validate SPI frames, commit the image, start contexts, transfer payload, preserve interrupted replies and stop on the safe edge.](diagrams/seq-host_v1.svg)

## Program store

[BLK-PROGRAM](BLK-PROGRAM.md) · [Block diagram](diagrams/blk-program_v1.svg) · [Back to chip sequence](#chip-sequence)

![Program-store sequence: tentative writes stay hidden. After start, a fetch returns a registered instruction or bounds fault.](diagrams/seq-program_v1.svg)

## Issue core

[BLK-CORE](BLK-CORE.md) · [Block diagram](diagrams/blk-core_v1.svg) · [Back to chip sequence](#chip-sequence)

![Core sequence: select, fetch and execute. A blocked instruction retries the saved request. Halt drains admitted output; fault stops both contexts on the next edge.](diagrams/seq-core_v1.svg)

## Timebase

[BLK-TIMER](BLK-TIMER.md) · [Block diagram](diagrams/blk-timer_v1.svg) · [Back to chip sequence](#chip-sequence)

![Timebase sequence: on each edge, core, drive and capture see the same pre-edge count as the counter advances.](diagrams/seq-timer_v1.svg)

## Timed output

[BLK-DRIVE](BLK-DRIVE.md) · [Block diagram](diagrams/blk-drive_v1.svg) · [Back to chip sequence](#chip-sequence)

![Drive sequence: validate the request, enqueue it, then merge and apply due updates without core involvement. Fault cleanup flushes remaining work.](diagrams/seq-drive_v1.svg)

## Input capture

[BLK-CAPTURE](BLK-CAPTURE.md) · [Block diagram](diagrams/blk-capture_v1.svg) · [Back to chip sequence](#chip-sequence)

![Capture sequence: arm the owning context's slot, observe synchronized input or expire, then hold the result until that context consumes it.](diagrams/seq-capture_v1.svg)

## Pad adapter

[BLK-PADS](BLK-PADS.md) · [Block diagram](diagrams/blk-pads_v1.svg) · [Back to chip sequence](#chip-sequence)

![Pad sequence: synchronize host and protocol inputs, register outputs, and give reset, deselect and safe priority over a due update.](diagrams/seq-pads_v1.svg)
