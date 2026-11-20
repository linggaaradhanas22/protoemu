# Concurrent UART RX and SPI controller

Basis: `TEST-ACC-008`, with the [UART](../uart/README.md) and [SPI](../spi/README.md) fixtures.

Use one loaded configuration at 60 MHz. Run nominal 115200 baud UART RX and 1 MHz mode-0 SPI on five distinct protocol pins. Let clock 0 be the first UART start edge. Send `55 55 A3` as consecutive 8N1 frames.

Start the two SPI exchanges at clocks 360 and 5550 (6 µs and 92.5 µs). Each should exchange `96 4B` on MOSI and `3A D2` on MISO. These starts are benchmark triggers, not a project-wide latency requirement. The candidate schedules its work from the preloaded configuration.

Pass if each entire SPI exchange is contained in the UART stream and crosses at least one UART data-bit transition. Check both SPI exchanges against the standalone data and timing criteria. Require the exact UART byte sequence. Do not pause either protocol or reload between exchanges.
