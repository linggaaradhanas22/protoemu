# SPI: two-byte controller exchange

Basis: `SPEC-SPI-001`, `TEST-SYS-006`.

At each rate and mode, the candidate sends `96 4B` on MOSI. The fixture returns `3A D2` on MISO. Send most significant bit first. Hold active-low chip select across both bytes. Use four protocol pins: chip select, SCLK, MOSI, and MISO.

| Mode | Clock idle | Sample edge | Data change edge |
|---:|---|---|---|
| 0 | Low | Rising | Falling |
| 1 | Low | Falling | Rising |
| 2 | High | Falling | Rising |
| 3 | High | Rising | Falling |

| Rate | Nominal half-period | Allowed half-period in clocks |
|---:|---:|---:|
| 100 kHz | 5 µs | 299–301 |
| 1 MHz | 0.5 µs | 29–31 |

The fixture makes its first bit valid before the first sample edge for modes 0 and 2. For later bits and for the first bit in modes 1 and 3, change MISO one quarter of a nominal half-period after the data change edge. This is a fixed benchmark peer setting, not a general MISO setup requirement.

Pass if both directions receive the expected data on the specified edges, the idle polarity is correct, and chip select stays low for exactly 16 sample edges. Check every half-period between consecutive SCLK edges inside the transaction.
