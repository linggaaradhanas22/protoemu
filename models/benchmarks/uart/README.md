# UART: 8N1 transmit and receive

Basis: `SPEC-UART-001`, `SPEC-UART-002`, `TEST-SYS-004`, `TEST-SYS-005`.

Use separate TX and RX pins. The line idles high. A frame starts low, carries 8 data bits least significant bit first, and ends with one high stop bit.

| Baud | Nominal clocks per bit | TX window in whole clocks (±1% time) |
|---:|---:|---:|
| 9600 | 6250 | 6188–6312 |
| 19200 | 3125 | 3094–3156 |
| 38400 | 1562.5 | 1547–1578 |
| 57600 | 1041.667 | 1032–1052 |
| 115200 | 520.833 | 516–526 |

- TX: Send `55 55 55 80 01` with no extra idle between frames. Check each measurable bit interval in the alternating `55` sequence, including stop-to-start intervals. Check that a UART monitor decodes every byte as listed.
- RX: Drive `00 FF 55 AA 80 01` with no extra idle between frames. For each nominal baud, test peer baud error from −2% to +2% in 0.5 percentage point steps. Use an exact fixture bit period of `1 / (nominal baud × (1 + fractional error))`. Sweep the first start edge across one `clk` period in steps of 1/16 of a clock, including phases on either side of a rising edge.
- Pass if TX meets period and frame checks at all rates and RX reports exactly the expected sequence for every fixture case.
