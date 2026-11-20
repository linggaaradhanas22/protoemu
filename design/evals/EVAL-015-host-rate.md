# EVAL-015 — Loader clock and multi-word payload transfers
- Status: done
- Traces to: BLK-HOST, SPEC-UART-001, SPEC-UART-002, SPEC-HOST-001
- Compares: SCK 0.25–8 MHz; 1, 4 or 8 words per transaction; FIFO depth 4, 8, 16
- Model: `models/benchmarks/g4_host_rate.py`, `models/physical/fifo_multi_probe.v`

## Question

[EVAL-014](EVAL-014-payload-fifo.md) found that the 250 kHz loader moves only one payload word per 468 µs. Above 19,200 baud, UART streams therefore stop after 10 to 17 bytes. Would a faster loader clock, multi-word transfers, or both remove the limit, and at what cost?

## Options modeled

- **Loader SCK** 0.25, 0.5, 1, 2, 4 and 8 MHz. Everything else follows the EVAL-004 transport model: 2 µs lead guard, plus a 24 µs tail for the lag guard and host dispatch.
- **Frame overhead sensitivity:** a "tight" case with 1 µs guards and 4 µs dispatch. This is a **guess** for optimized RP2350 firmware; it is not measured.
- **Multi-word commands (provisional opcodes for this study only):**
  - `READN ctx, n` returns up to `n` egress words. The words stay in the FIFO while the reply is sent and are freed when the reply frame closes. An interrupted reply can therefore restart without losing data.
  - `WRITEN ctx, words` writes words tentatively into free slots and commits as many as fit when the request is validated. The reply returns the accepted count.
- **Streams:** back-to-back UART bytes, one byte per word, for up to 2,000 bytes. Receive (RX): the host polls continuously. Transmit (TX): the FIFO starts full and the host refills it continuously.

## Results

**Longest burst at 115,200 baud, depth 8, EVAL-004 overhead (RX / TX bytes; "all" = no stall in 2,000 bytes):**

| SCK | 1 word (µs per word) | 4 words (µs per word) | 8 words (µs per word) |
|---:|---|---|---|
| 250 kHz | 10 / 10 (468) | 10 / 12 (173) | 10 / 8 (118.5) |
| 500 kHz | 12 / 12 (260) | 40 / 71 (93) | all (62.5) |
| **1 MHz** | 17 / 18 (156) | **all (53)** | all (34.5) |
| 2 MHz | 47 / 47 (104) | all (33) | all (20.5) |
| 4 MHz | all (78) | all (23) | all (13.5) |

At 38,400 and 57,600 baud every configuration from 500 kHz up sustains the stream, except 500 kHz with single words at 57,600 baud (23 bytes).

- Multi-word transfers **alone do not help at 250 kHz**. A long reply holds its words in the FIFO, so a depth-8 receiver still fills after about 10 bytes.
- A faster clock alone works: 4 MHz sustains 115,200 baud with today's single-word commands. With the tight-overhead guess, 2 MHz does too, and 1 MHz absorbs 30 bytes.

**Effect of depth at 115,200 baud (RX / TX bytes):**

| Configuration | Depth 4 | Depth 8 | Depth 16 |
|---|---|---|---|
| 250 kHz, 1 word | 5 / 5 | 10 / 10 | 20 / 19 |
| 2 MHz, 1 word | 23 / 23 | 47 / 47 | 95 / 95 |
| 1 MHz, 4 words | all | all | all |

**Clock limits and load time:**

| SCK | Synchronizer check, all 16 host phases | Reply-path margin before pad and board delays | 128-word image load |
|---:|---|---:|---:|
| 250 kHz | pass | 1,934 ns | 13.6 ms |
| 1 MHz | pass | 434 ns | 3.5 ms |
| 2 MHz | pass | 184 ns | 1.8 ms |
| 4 MHz | pass | 59 ns | 1.0 ms |
| 8 MHz | **fail** | −3 ns | – |

The margin is the time between the chip registering a reply bit (after two synchronizer flops and one output register) and the host sampling it. Pad, board and RP2350 input delays are not modeled and must fit inside it. The 250 kHz load time matches EVAL-004's 13.628 ms.

**Area of four FIFOs (IHP, typical corner):**

| Depth | Single-word (µm²) | Multi-word host access (µm²) | Extra |
|---:|---:|---:|---:|
| 4 | 22,810.5 | 22,946.7 | +136.2 |
| 8 | 45,196.7 | 45,501.5 | +304.8 |
| 16 | 87,620.9 | 88,687.9 | +1,067.0 |

The multi-word FIFOs matched reference queues in random tests at depths 4, 8 and 16, with the core pushing or popping on the same edges. A seeded pointer bug gave 5,879 errors. The SPI framing changes for `READN`/`WRITEN` (word counter, accepted-count reply) are not included in the area.

All 78 Python model checks passed (6 new). EVAL-003 through EVAL-014 regenerate byte-identical results after the transport model was parametrized.

## Options for the decision

| Option | 115,200-baud stream | Changes | Cost and risk |
|---|---|---|---|
| A. Keep 250 kHz, single word, depth 8 | 10 bytes | None; document the limit | None |
| B. 2 MHz, single word | 47 bytes | Loader clock in DEC-002 | 184 ns margin; firmware and board check |
| C. 4 MHz, single word | Sustained | Loader clock in DEC-002 | 59 ns margin; thin once pad and board delays are added |
| **D. 1 MHz, 4-word commands, depth 8** | **Sustained, both directions** | Loader clock in DEC-002; `READN`/`WRITEN` in BLK-HOST | 434 ns margin; +305 µm² FIFO plus unmeasured framing logic |
| E. As D, depth 4 | Sustained | As D | Saves 22,555 µm² against D, but a transfer that must run without host service holds only 4 words per direction |

## Conclusion

Recommend **D**. It is the only option that sustains every common baud rate in both directions while keeping a wide timing margin. It also cuts image load time from 13.6 ms to 3.5 ms. Depth 8 keeps room for transfers that must complete without host service: TEST-SYS-012 asks the chip to handle the transaction without host assistance, and RC5 must not need host service during capture. E saves area if those transfers fit in 4 words. B is the smallest change if a 47-byte burst limit is acceptable.

## Limits

- The transport model has no pad, board or RP2350 input delays. Check any SCK above 250 kHz on the real board before relying on it.
- The tight-overhead case is a guess. The main tables use the EVAL-004 assumption.
- The streams assume the host does nothing but poll or refill one context. Two busy contexts share the link.
- `READN`/`WRITEN` are provisional. Their framing logic, error replies and interaction with `STOP` are not specified or measured.
- No production RTL, agreed record or registered test changed.

## Reproduce

```bash
source scripts/env.sh
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-015/rates.json
python3 -B -m models.benchmarks.g4_host_rate --out design/evals/EVAL-015/rates.json
python3 -B -m models.physical.run_fifo_multi_probe \
  --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
  --out design/evals/EVAL-015/area.json
for d in 4 8 16; do
  iverilog -g2005 -s fifo_multi_probe_tb -P fifo_multi_probe_tb.DEPTH=$d \
    -o test/sim_build/EVAL-015/m$d.vvp models/physical/fifo_multi_probe.v models/physical/fifo_multi_probe_tb.v
  vvp test/sim_build/EVAL-015/m$d.vvp
done
python3 -B -m unittest models.benchmarks.test_g4_host_rate
```

[`rates.json`](EVAL-015/rates.json) holds every configuration, including the tight-overhead case. [`area.json`](EVAL-015/area.json) records the areas, Yosys version and Liberty hash.
