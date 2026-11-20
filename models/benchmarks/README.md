# Architecture benchmarks at 60 MHz

These profiles define stimulus and pass criteria for G3 architecture evaluations. They are not measured results. Use the same profile for every candidate. Protocol checks use independent peer models or pin monitors, not the candidate's own decoder.

| Profile | Scope | Main constraint |
|---|---|---|
| [UART](uart/README.md) | Target, TX and RX | 520.83 clocks per bit at 115200 baud |
| [SPI](spi/README.md) | Target, controller modes 0–3 | 30 clocks per half-period at 1 MHz |
| [I2C](i2c/README.md) | Target, controller read/write and stretching | 150–157 clocks per unstretched bit in Fast-mode |
| [Concurrent UART and SPI](concurrent/README.md) | Target combination, Should | SPI exchanges overlap incoming UART frames |
| [WS2812](ws2812/README.md) | Non-target, pulse-width output | Nominal 75 clocks per bit, with separate pulse width limits |
| [1-Wire](onewire/README.md) | Non-target, bidirectional single-drop bus | Read sample by 900 clocks after the slot starts |
| [RC5](rc5/README.md) | Non-target, bi-phase input | Nominal 53,340 clocks per half-bit |

The three non-target profiles provide the evidence planned in `SPEC-PROG-003`. They do not qualify as the protocol chosen after RTL freeze under `SPEC-PROG-002`. There is no holdout profile in this suite. The optional stretch protocols have not been selected for evaluation.

## Common rules

- At 60 MHz, one clock period is exactly 50/3 ns. Convert a time window to whole clocks by rounding the lower bound up and the upper bound down. For a strict bound, exclude any clock count exactly on the bound. Use exact times for external stimuli if edges need not align with `clk`.
- Count from the first protocol edge through the last required operation, including required bus waits and latch intervals. Measure program load separately. List the clock phase, test case, and fixture revision in the evaluation.
- Keep protocol decisions and pin timing in the candidate. The host may supply configuration and payload, but must not service individual protocol edges. Use ideal digital inputs and pull-ups. Do not infer board-level electrical compliance.
- Report pass or fail per case, the worst timing margin in clocks over all measured edges, program image size in bytes, and the pins and execution resources used. Give the model commit, command, and raw traces with the evaluation. A timing miss or a payload mismatch is a failure even if all other cases pass.

The profiles use the current draft G2 limits. If Lingga changes a limit during review, update the affected profile and rerun it on all candidates before comparing results.
