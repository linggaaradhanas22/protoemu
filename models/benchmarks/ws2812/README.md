# WS2812: two pixels on one output

Basis: `SPEC-PROG-003`, `TEST-SYS-013`. Use the timing table in the [Worldsemi WS2812B-2020 V1.0 data sheet, page 4](https://www.mouser.com/pdfDocs/WS2812B-2020_V10_EN_181106150240761.pdf). Other revisions can have different limits.

Request RGB pixels `(12, A5, 3C)` then `(E7, 40, 81)`, all values hexadecimal. Expect wire bytes `A5 12 3C 40 E7 81` in GRB order, most significant bit first. Start with the line low. After 48 pulses, leave the line low for the latch interval.

| Interval | Data sheet limit | Whole clocks at 60 MHz | Benchmark nominal |
|---|---:|---:|---:|
| 0 high | 220–380 ns | 14–22 | 18 clocks |
| 0 low | 580–1000 ns | 35–60 | 57 clocks |
| 1 high | 580–1000 ns | 35–60 | 51 clocks |
| 1 low | 220–420 ns | 14–25 | 24 clocks |
| Latch low | >280 µs | ≥16,801 | 18,000 clocks |

The nominal bit period is 75 clocks (1.25 µs). Decode each bit from its high pulse. Check the following low width for the first 47 bits. After the last high pulse, check the continuous latch interval instead of applying a data low maximum. Pass if the monitor sees exactly the six expected bytes and the pulse and latch checks pass. This is a digital timing profile, not a claim that a 3.3 V output can drive a physical 5 V pixel directly.
