# DEC-002 — RP2350 loader transport
- Status: agreed
- Traces to: BLK-HOST, BLK-PADS, BLK-PROGRAM, SPEC-HOST-001, SPEC-RST-002, REQ-PROTO-004
- Chooses: Dedicated SPI0 with reply-ready
- Evidence: EVAL-004

## Options and evidence

| Criterion | Framed SPI | Dedicated nibble handshake |
|---|---|---|
| 1 s image load target | 13.628 ms for 128 words in the model | 6.050 ms nominal; 27.100 ms with delayed polling in the model |
| Concurrent UART RX and SPI pin use | Five separate protocol pins, no host overlap | Same |
| ETR wiring and implementation | 3 inputs / 2 outputs; ETR routes SPI0 | 6 inputs / 6 outputs; requires GPIO or PIO handshake driver |
| RTL fit and board operation | Not measured | Not measured |

## Decision

Use dedicated RP2350 SPI0 host wiring, mode 0 at 250 kHz, with a separate `READY` output. Keep host traffic off the protocol pads. Both candidates meet the modeled load-time target. SPI gives up nominal nibble speed for fewer pins and support from the RP2350 hardware SPI controller. No weighted scoring was used.

Lingga approved the transport and [interface change](../changes/CHG-001-loader-interface.md) on 2026-11-20. This approval does not freeze the pending details in BLK-HOST or close G4.
