# DEC-002 — RP2350 loader transport
- Status: draft
- Traces to: BLK-HOST, BLK-PADS, BLK-PROGRAM, SPEC-HOST-001, SPEC-RST-002, REQ-PROTO-004
- Evidence: EVAL-004

## Options and evidence

| Criterion | Framed SPI | Dedicated nibble handshake |
|---|---|---|
| 1 s image load target | 13.628 ms for 128 words in the model | 6.050 ms nominal; 27.100 ms with delayed polling in the model |
| Concurrent UART RX and SPI pin use | Five separate protocol pins, no host overlap | Same |
| ETR wiring and implementation | 3 inputs / 2 outputs; ETR routes SPI0 | 6 inputs / 6 outputs; requires GPIO or PIO handshake driver |
| RTL fit and board operation | Not measured | Not measured |

## Recommendation, pending approval

Use dedicated SPI0 host wiring, mode 0 at 250 kHz. Keep host traffic off the protocol pads. Both candidates meet the modeled time budget, so the explicit tradeoff is to give up nominal nibble speed for fewer pins and a hardware SPI driver. No weighted scoring or selection has been approved. The [interface change proposal](../changes/CHG-001-loader-interface.md) describes the block updates to apply after approval.
