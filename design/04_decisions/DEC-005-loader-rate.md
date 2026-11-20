# DEC-005 — RP2350 loader transport, clock and payload transfers
- Status: agreed
- Traces to: BLK-HOST, BLK-PADS, BLK-PROGRAM, SPEC-HOST-001, SPEC-RST-002, SPEC-UART-002, REQ-PROTO-004
- Chooses: Dedicated SPI0 at 1 MHz with reply-ready and 4-word payload transfers
- Evidence: EVAL-004, EVAL-014, EVAL-015
- Replaces: DEC-002

## Options and evidence

DEC-002's transport choice stands: dedicated RP2350 SPI0 with a separate `READY`, not the nibble handshake ([EVAL-004](../evals/EVAL-004-g4-loader.md)). This decision changes the clock and adds multi-word payload commands, because the 250 kHz link limited UART streams ([EVAL-014](../evals/EVAL-014-payload-fifo.md)).

| Option ([EVAL-015](../evals/EVAL-015-host-rate.md)) | 115,200-baud stream, depth 8 | Reply-path margin before pad and board delays | 128-word load | Change |
|---|---|---:|---:|---|
| 250 kHz, single word (DEC-002) | 10 bytes | 1,934 ns | 13.6 ms | None |
| 2 MHz, single word | 47 bytes | 184 ns | 1.8 ms | Clock |
| 4 MHz, single word | Sustained | 59 ns | 1.0 ms | Clock |
| **1 MHz, 4-word transfers** | **Sustained, both directions** | **434 ns** | **3.5 ms** | Clock and two commands |

No weighted scoring was used. All numbers come from the model; pad, board and RP2350 delays are not included.

## Decision

Use dedicated RP2350 SPI0, mode 0 at **1 MHz**, with a separate `READY` output, on the DEC-002 pins. Add `READN` and `WRITEN`, which move up to **four** payload words per frame (behavior in [CHG-011](../changes/CHG-011-loader-rate.md)). It is the only modeled option that sustains UART at every common baud rate in both directions with a wide timing margin. It also cuts load time by a factor of four. We give up some simplicity: two more commands and their framing logic, whose area is not yet measured. The FIFO part costs 305 µm².

Follow-up: check 1 MHz SPI on the real board and RP2350 firmware before relying on it. If the board fails, fall back to 500 kHz: at depth 8 that still sustains 38,400 and 57,600 baud with 4-word transfers, and keeps 40 bytes (receive) or 71 bytes (transmit) at 115,200.

Lingga approved this option on 2026-11-20 ("follow your recommendations" after EVAL-015). This does not close G4.
