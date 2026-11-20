# EVAL-016 — Baseline and non-target programs on the draft ISA
- Status: done
- Traces to: SPEC-PROG-001, SPEC-PROG-003, SPEC-UART-001, SPEC-UART-002, SPEC-SPI-001, SPEC-I2C-001, SPEC-I2C-002, SPEC-I2C-003, BLK-CORE
- Model: `models/benchmarks/g4_suite.py`

## Question

Earlier replays used programs translated from the G3 probe code. They covered SPI at 1 MHz, Fast-mode I2C (combined transfer), UART RX inside the overlap case, and RC5. Can the draft ISA, with the rules settled in CHG-005 to CHG-011, run every baseline and non-target test case with protocol decisions in the program and only payload from the host?

## Method

New programs written directly in draft-ISA operations, without the superseded `out`/`shift_out`. Payload enters through `host_get`, and results leave through `host_put`. Guards use the CHG-007 rule. The pins follow the BLK-PADS map. Each case is checked by the independent G3 peers and monitors, as the benchmark profiles require. Most cases run at epoch 0 and again with the timer wrapping early in the run.

| Test | Cases |
|---|---|
| TEST-SYS-004 UART TX `55 55 55 80 01` | 5 rates × 2 epochs, two variants (below) |
| TEST-SYS-005 UART RX `00 FF 55 AA 80 01` | 5 rates × 9 baud errors (−2 % to +2 %) × 16 start phases, plus 20 wrap runs |
| TEST-SYS-006 SPI, two bytes each way | 4 modes × 100 kHz and 1 MHz × 2 epochs |
| TEST-SYS-007 to 009 I2C | 100 and 400 kHz × separate, combined, address NACK, data NACK, stretch 1/5/10 µs × 2 epochs |
| TEST-SYS-013 WS2812, 1-Wire, RC5 | WS2812 and 1-Wire (normal and delayed presence, plus no device) × 2 epochs; RC5 6 cases from EVAL-010 |
| UART RX + SPI overlap | 96 cases from EVAL-009 |

**UART TX variants.** The draft `shift_pin` sends bit 15 first and shifts left. UART sends the least significant bit first, and the draft ISA has no left shift, register AND or register add that could isolate bit 0 in the bit loop. The `host-reversed` variant therefore has the host send each byte bit-reversed in the upper byte of the word. The `lsb` variant uses a prototype `shift_lsb` that sends bit 0 and shifts right. `shift_lsb` is exploration only and not part of the draft ISA.

**1-Wire presence.** `wait_save` has no timeout, so waiting for a presence pulse would hang with no device on the bus. The program samples the line 70 µs after reset release instead, as 1-Wire masters do, and reports `0xFFFF` if no device answers.

## Results

**914 of 914 cases passed.**

| Program | Cases passed | Image (words of 128) | Worst monitor margin (clocks) | Least issue slack (clocks) |
|---|---:|---:|---:|---:|
| UART TX, host-reversed | 10 / 10 | 15 | 5.0 at 115,200 baud | 58 |
| UART TX, `shift_lsb` prototype | 10 / 10 | 15 | 5.0 at 115,200 baud | 58 |
| UART RX | 740 / 740 | 16 | 156 at 115,200 baud, ±2 % | 513 |
| SPI | 16 / 16 | 15–16 | 1 (half-period exact; window ±1) | 10 |
| I2C Standard-mode | 14 / 14 | 69–70 | 12 | 5 |
| I2C Fast-mode | 14 / 14 | 69–70 | 2 (bit period 152 in 150–157) | 5 |
| WS2812 | 2 / 2 | 15 | 1 (window ±1 around nominal) | 8 |
| 1-Wire, incl. no device | 6 / 6 | 34 | 62 | 12 |
| RC5 | 6 / 6 | 39 | 25,336 | 25,308 |
| UART RX + SPI overlap | 96 / 96 | 37 | 1 | 13 |

"Issue slack" is the smallest time between admitting a drive or arming a sample and its deadline. It shows how far ahead of the pins the program runs.

**Payload layout used** (all within the depth-8 FIFOs of CHG-010):

| Program | Ingress words | Egress words |
|---|---|---|
| UART TX | count, then one byte per word | – |
| UART RX | count | one byte per word; `0x1xx` on a bad stop bit |
| SPI | one 16-bit word per transaction | one 16-bit word per transaction |
| I2C | two data bytes in one word | two read bytes in one word, then a status word (0 = OK, 1 = NACK) |
| WS2812 | count, then two pixel bytes per word | – |
| 1-Wire | – | one ROM byte per word (8), or `0xFFFF` if no device |

The suite runs in about 25 s. All 81 Python model checks passed, including 3 new ones. Those include negative checks: UART TX without the bit reversal, I2C with a wrong address and WS2812 with a 12-clock pulse are all rejected by the monitors. EVAL-003 through EVAL-015 regenerate byte-identical results.

## Conclusions

- The draft ISA runs every baseline and non-target test case in at most 70 words. The host supplies payload only, never individual protocol edges.
- **Gap: least-significant-bit-first output.** UART TX works today only if the host bit-reverses each byte. That moves protocol formatting to the host and would also affect other LSB-first protocols, such as 1-Wire commands from the host, DMX512 or MIDI. An LSB-first option for `shift_pin` gives identical results with natural byte order. [CHG-012](../changes/CHG-012-shift-lsb.md) proposes it.
- **Limit: waits have no timeout.** 1-Wire presence avoids the problem by sampling. I2C clock stretching still waits on SCL indefinitely, so a target holding SCL low stalls the context until the host sends `STOP`. Document this, or consider a timeout later.

## Limits

- These are model programs, not output of a released assembler; `sw/` has no toolchain yet (SPEC-PROG-001, TEST-SYS-011).
- Stops and faults (CHG-008) and the new `READN`/`WRITEN` host commands are not exercised in this suite. The 64-byte UART stream in TEST-SYS-005 is covered only by the EVAL-015 rate model.
- One program runs at a time, except the overlap case. Area and timing are not measured.
- No production RTL, agreed record or registered test changed.

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-016/results.json
python3 -B -m models.benchmarks.g4_suite --out design/evals/EVAL-016/results.json
python3 -B -m unittest models.benchmarks.test_g4_suite
```

[`results.json`](EVAL-016/results.json) holds the summary and every case.
