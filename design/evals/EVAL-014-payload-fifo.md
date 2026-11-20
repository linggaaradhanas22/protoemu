# EVAL-014 — Payload FIFO depth and same-edge host/core access
- Status: done
- Traces to: BLK-HOST, BLK-CORE, SPEC-UART-002, SPEC-PROG-003, SPEC-HOST-001
- Compares: registered status vs bypass; depths 2, 4, 6, 8, 16
- Model: `models/physical/fifo_probe.v`, `models/benchmarks/g4_fifo_depth.py`

## Question

Each context has an ingress FIFO (host to core, `host_get`) and an egress FIFO (core to host, `host_put`) of 16-bit words. The trial depth is 8. Two points were open: what happens when the host and the core touch the same FIFO on one edge, and how deep the FIFOs must be.

## Rules compared

| Rule | Full queue, push and pop on one edge | Empty queue, push and pop on one edge |
|---|---|---|
| **Registered status** | Pop happens; push waits | Push happens; pop waits |
| Bypass | Both happen | The word passes straight through |

Under both rules, a push and a pop on one edge both happen when the queue is neither full nor empty. Registered status decides acceptance from the count before the edge, so no host-side signal reaches the core's issue decision in the same cycle.

## Method

- **Function:** an Icarus testbench pushes and pops at random for 20,000 cycles against a reference queue at each depth (2, 4, 6, 8, 16) and rule. The load alternates between filling and draining, so the boundary cases occur often. A bypass FIFO with its full-boundary term removed must be detected.
- **Area:** map four queues (two contexts × two directions) to IHP `sg13cmos5l` cells at `typ_1p20V_25C`, as in EVAL-013.
- **Host rate:** use the EVAL-004 SPI transport model (250 kHz, 2 µs guards, 24 µs inter-frame budget) to time one payload `READ` and `WRITE`.
- **Demand:** count the words each specified test must hold with no host service. Take the counts from the TEST text and the EVAL-009/010 replays.
- **Streaming:** for back-to-back UART frames, with the host polling `READ` continuously, find the longest burst that never meets a full egress queue.

## Results

**Function:** all ten configurations matched the reference with 0 errors. At depth 8 there were about 1,200 full and 1,200 empty edges with both sides active under registered status. The mutation produced 1,191 errors.

**Area (four queues):**

| Depth | Registered status (µm²) | Share of tile | Bypass (µm²) |
|---:|---:|---:|---:|
| 2 | 11,523.3 | 0.95 % | 12,689.8 |
| 4 | 22,810.5 | 1.89 % | 24,158.7 |
| 6 | 35,157.3 | 2.91 % | 35,672.2 |
| **8** | **45,196.7** | **3.74 %** | 46,381.5 |
| 16 | 87,620.9 | 7.25 % | 90,732.4 |

Bypass costs 1,185 µm² more at depth 8. Depth 8 uses 50 % of BLK-HOST's 0.090 mm² planning allowance.

**Host rate:** a `READ` that returns a word takes 468 µs, and an `EMPTY` reply 404 µs. The FIFO is accessed 196 µs into the transaction, on the edge that validates the request. A `WRITE` also takes 468 µs. The host can therefore move about 2,100 words per second in each direction.

**Demand without host service:**

| Test | Direction | Words, one byte each | Words, two bytes each |
|---|---|---:|---:|
| TEST-SYS-005 UART RX (6 frames) | egress | 6 | 3 |
| TEST-SYS-006 SPI | each | 2 | 1 |
| EVAL-009 overlap (UART / SPI) | egress / ingress | 3 / 4 | 2 / 2 |
| TEST-SYS-013 WS2812 (two RGB values) | ingress | 6 | 3 |
| TEST-SYS-013 1-Wire (presence + ROM) | egress | 9 | 5 |
| TEST-SYS-013 RC5 | egress | 2 | 2 |

The draft ISA has no left shift or register OR. Packing two received UART bytes into a word would need `cap` mode 1, which leaves each byte bit-reversed for the host to undo. Treat the unpacked column as the sizing case.

**Longest back-to-back UART burst without a stall (bytes, one per word):**

| Baud | Depth 2 | 4 | 6 | 8 | 16 |
|---:|---:|---:|---:|---:|---:|
| 9,600 and 19,200 | host keeps up | host keeps up | host keeps up | host keeps up | host keeps up |
| 38,400 | 3 | 8 | 12 | 17 | 35 |
| 57,600 | 4 | 7 | 10 | 13 | 26 |
| 115,200 | 3 | 5 | 8 | 10 | 20 |

## Conclusion

- **Rule:** use registered status. Losing the boundary case costs the core at most one 60 MHz cycle, and the host at most one `FULL` or `EMPTY` reply. Both are negligible next to a 404–468 µs transaction. It is also smaller and keeps the host path out of the issue decision.
- **Depth:** keep 8. It holds every specified test's unpacked demand except 1-Wire (9 words). 1-Wire produces a byte more slowly than the host reads one, so the host must poll during the ROM read, or the program can pack presence into a ROM word. Depth 6 would save 10,039 µm², but it holds the WS2812 and UART cases with no spare word and absorbs only 8 bytes at 115,200 baud.
- [CHG-010](../changes/CHG-010-payload-fifo.md) proposes both.

**Known limit:** above 19,200 baud, the 250 kHz loader cannot drain a continuous UART stream at any practical depth. At depth 8, the receiver absorbs 10 to 17 back-to-back bytes, depending on rate. A longer burst fills egress and stalls the receiving context, which then misses frames. The agreed test uses 6 bytes, so SPEC-UART-002 is met, but the limit belongs in the user documentation. A faster loader clock or a multi-word `READ` would raise it; both would change DEC-002 or BLK-HOST.

## Limits

- Typical-corner area after synthesis only; no placement or timing. The probe stores words in flops and does not include the SPI framing that feeds it.
- Demand is counted from test text and earlier replays. TASK-043 must confirm it with the assembled programs.
- The streaming model assumes the host does nothing but poll `READ`, with the EVAL-004 timing. Real firmware may be slower.
- No production RTL or registered tests changed.

## Reproduce

```bash
source scripts/env.sh
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-014/area.json
python3 -B -m models.physical.run_fifo_probe \
  --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
  --out design/evals/EVAL-014/area.json
for d in 2 4 6 8 16; do for b in 0 1; do
  iverilog -g2005 -s fifo_probe_tb -P fifo_probe_tb.DEPTH=$d -P fifo_probe_tb.BYPASS=$b \
    -o test/sim_build/EVAL-014/f$d$b.vvp models/physical/fifo_probe.v models/physical/fifo_probe_tb.v
  vvp test/sim_build/EVAL-014/f$d$b.vvp
done; done
python3 -B -m models.benchmarks.g4_fifo_depth --out design/evals/EVAL-014/streaming.json
python3 -B -m unittest models.benchmarks.test_g4_fifo_depth
```

[`area.json`](EVAL-014/area.json) records the areas, Yosys version and Liberty hash. [`streaming.json`](EVAL-014/streaming.json) holds the host timing, demand and burst tables.
