# I2C: 7-bit controller transactions

Basis: `SPEC-I2C-001` through `SPEC-I2C-003` and `TEST-SYS-007` through `TEST-SYS-009`. Timing source: [NXP UM10204, Table 11](https://www.nxp.com/docs/en/user-guide/UM10204.pdf).

The candidate controls SDA and SCL using low or release only. The fixture uses ideal pull-ups and one target at 7-bit address `0x50`. Address bytes on the wire are `A0` (write) and `A1` (read).

| Timing check on resolved pins | Standard, nominal 100 kHz | Fast, nominal 400 kHz |
|---|---:|---:|
| Unstretched SCL bit period in whole clocks | 600–631 | 150–157 |
| SCL low minimum | 282 | 78 |
| SCL high minimum | 240 | 36 |
| Data setup minimum | 15 | 6 |
| START and repeated START hold minimum | 240 | 36 |
| Repeated START setup minimum | 282 | 36 |
| STOP setup minimum | 240 | 36 |
| STOP-to-START bus free minimum | 282 | 78 |

The last seven rows are clock counts. Apply the bit-period window only to consecutive cycles in unstretched bit transfers, not across START or STOP.

At each rate, run these cases:

1. Write `96 4B` to `0x50` and STOP. Start a separate read and get `3A D2`, then STOP. Check the bus-free interval between transactions.
2. Write `96 4B` and issue a repeated START. Read `3A D2`, then STOP. Do not insert a STOP before the repeated START.
3. Repeat the multibyte write twice: NACK its address on the first run. On the second run, ACK its address and NACK `96`. Require STOP and a failure result with no further byte after either NACK.
4. Repeat the combined transfer from case 2 with target stretch during the first data bit of `96` and its ninth clock. Run separately with holds of 1, 5, and 10 µs (60, 300, and 600 clocks) after the candidate releases SCL. Do not count the target's hold as high time. Require the specified minimum high time from the actual SCL rise.

Pass if decoded bytes and START/STOP events match, the controller ACKs `3A` and NACKs `D2` in each read, and both lines meet timing and open-drain checks. Stretched runs must complete without data errors or extra SCL edges.
