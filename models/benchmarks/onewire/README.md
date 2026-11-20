# 1-Wire: single-drop Read ROM

Basis: `SPEC-PROG-003`, `TEST-SYS-013`. Use a [DS2401](https://www.analog.com/media/en/technical-documentation/data-sheets/DS2401.pdf) peer in standard speed mode. The one bidirectional pin resolves low if either side drives low. Otherwise the ideal pull-up resolves it high. Neither side may actively drive high.

The chip drives reset low, releases the bus, and detects the peer's presence pulse. After reset recovery, it writes `33` (Read ROM) and starts 64 read slots. Use least significant bit first in every byte. The synthetic ROM is `01 23 45 67 89 AB CD E9` in wire order. `01` is the family code and `E9` is the CRC byte. The program must report all eight bytes. It need not calculate the CRC for this benchmark.

| Interval | Benchmark limit | Whole clocks at 60 MHz | Nominal fixture or controller target |
|---|---:|---:|---:|
| Controller reset low | 480–960 µs | 28,800–57,600 | 500 µs |
| Reset release to first command slot | ≥480 µs | ≥28,800 | 500 µs |
| Peer presence delay from reset release | 15–60 µs | 900–3,600 | 30 µs |
| Peer presence low | 60–240 µs | 3,600–14,400 | 120 µs |
| Write-1 or read initiation low | 1–15 µs | 60–900 | 6 µs |
| Write-0 low | 60–120 µs | 3,600–7,200 | 60 µs |
| Start-to-start data slot, including recovery | 65–120 µs | 3,900–7,200 | 70 µs |
| Resolved bus high before next data slot | ≥1 µs | ≥60 | Depends on bit and driver release |
| Read sample from slot start | After controller release and within 15 µs | ≤900 | 14 µs |

For the command, the peer samples at 30 µs into each slot. For a ROM zero bit, the peer starts pulling low 1 µs after the slot starts and releases the line at 30 µs. For a one bit, it leaves the line released. Run with the nominal presence timing and again with presence delayed 60 µs and held for 60 µs. The slot window is a benchmark choice within the standard speed limits. The monitor checks observable timing, drive ownership, and the eight returned bytes. A model can also report the internal read sample time to show its margin.
