# RC5: decode two frames from a demodulated input

Basis: `SPEC-PROG-003`, `TEST-SYS-013`. Timing and input polarity follow [ST AN3174, section 3](https://www.st.com/resource/en/application_note/an3174-implementing-receivers-for-infrared-remote-control-protocols-using-stm32f10xxx-microcontrollers-stmicroelectronics.pdf). The fixture models the output of an active-low demodulator, not the 36 kHz carrier. Between frames the line is high. A logical 0 is low then high. A logical 1 is high then low.

Send legacy 14-bit frames: two start bits (`11`), one toggle bit, five address bits, and six command bits. Send address and command most significant bit first.

| Frame | Bits on the wire before bi-phase encoding | Expected address | Expected command | Expected toggle |
|---|---|---:|---:|---:|
| 1 | `11 0 00101 110101` | `0x05` | `0x35` | 0 |
| 2 | `11 1 11010 001100` | `0x1A` | `0x0C` | 1 |

| Timing | Nominal | Nominal clocks at 60 MHz |
|---|---:|---:|
| Half-bit | 889 µs | 53,340 |
| Full bit | 1.778 ms | 106,680 |
| Frame envelope (28 half-bits) | 24.892 ms | 1,493,520 |
| Idle between frame envelopes (100 half-bits) | 88.900 ms | 5,334,000 |

Run the two frames at nominal timing, then repeat with all half-bits at 50,673 clocks (−5%) and 56,007 clocks (+5%). Keep 100 half-bits of idle between envelopes in each run and observe the output for that same interval after the second frame. The ±5% replay range is a benchmark choice. The first half of each frame is idle-level, so its first edge occurs one half-bit after the envelope starts. Equal-level halves may merge across bit boundaries.

Pass if the program reports those two tuples in order, once each and before the corresponding idle interval ends. It must not report a frame during initial idle. Use the same decoder program at all three replay rates.
