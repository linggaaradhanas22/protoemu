# EVAL-004 — RP2350 loader transport and pin split
- Status: done
- Traces to: BLK-HOST, BLK-PADS, BLK-PROGRAM, SPEC-HOST-001, SPEC-RST-002, REQ-RULE-003, REQ-RULE-007, REQ-PROTO-004
- Compares: ARCH-B
- Model: `models/benchmarks/g4_loader.py`

## Timing comparison

Both options use dedicated Tiny Tapeout input and output pins and leave `uio[7:0]` free for protocol I/O. The nibble option uses four bits in each direction plus request, acknowledge, frame and ready. The serial option uses SPI mode 0 at 250 kHz, with separate request and reply transfers and a reply-ready pin. Both use the same length and CRC checks in the probe.

Sweep 16 host edge phases against the 60 MHz chip clock. The serial probe has 2 µs low and high half periods, 2 µs guards before the first bit and after the last, and a 20 µs inter-frame budget after the end guard. The nibble probe gives data 1 µs of setup before toggling request, samples it one chip clock after the synchronized request, polls the acknowledge every 5 µs and waits 1 µs before the next nibble. The stress run adds a 25 µs delay to every nibble acknowledgement poll. These are model settings, not RP2350 firmware measurements.

| Transport | `ui_in` / `uo_out` used | G3 SPI / I2C / overlap load time (ms) | 128-word load (ms) |
|---|---:|---:|---:|
| Nibble, nominal poll | 6 / 6 | 1.430 / 3.278 / 2.144 | 6.050 |
| Nibble, delayed poll | 6 / 6 | 5.980 / 14.428 / 9.244 | 27.100 |
| SPI, 250 kHz | 3 / 2 | 3.068 / 7.292 / 4.700 | 13.628 |

All 192 modeled loads returned a valid completion before the start command. Times include the replies and the last inter-frame budget, but not startup/reset. The 128-word case is the capacity bound (384 bytes of code), not a released program. No baseline firmware ran. The probe checks the timing of synchronization and reconstructs symbols with ideal settled levels. It does not implement a full serial receiver with arbitrary edge timing or analog metastability. The 20 µs budget must be checked with target firmware, including host dispatch and polling delays.

## Proposed board allocation

The [ETR demo PCB RP2350 pin table](https://github.com/TinyTapeout/tt-demo-pcb#rp2-pinout) maps the serial pins to SPI0. This is a pin-table comparison, not a bench test. For the nibble option use `ui_in[3:0]` and `uo_out[3:0]` for data; use bit 4 on each for request and acknowledge, and bit 5 on each for frame select and ready.

| Function | ASIC pin | ETR RP2350 connection or drive rule |
|---|---|---|
| Host frame, clock, MOSI | `ui_in[0]`, `ui_in[1]`, `ui_in[2]` | GPIO17, GPIO18, GPIO19; RP2350 drives |
| Host MISO and reply-ready | `uo_out[3]`, `uo_out[4]` | GPIO36, GPIO37; RP2350 reads |
| Protocol SPI CS, MOSI, MISO, SCK | `uio[0]`, `uio[1]`, `uio[2]`, `uio[3]` | SPI top row per [TT pinout guidance](https://tinytapeout.com/specs/pinouts/#spi); ASIC drives CS/MOSI/SCK; peer drives MISO |
| Protocol UART RX for overlap | `uio[6]` | Peer drives RX; follows the recommended bottom-row UART RX pin. Standalone UART may also drive TX on `uio[5]`. |
| Protocol I2C SCL and SDA, separate image | `uio[6]`, `uio[7]` | Bottom-row pin roles; use external pull-ups to 3.3 V and never drive high. Not concurrent with the UART example. |

The overlap case uses five distinct protocol pins and no loader pins. SPI's write mask is `0x0B`; UART RX owns no output in the overlap image. For I2C, both the write mask and open-drain mask are `0xC0`. Configure the RP2350 bidirectional-pin drivers and pulls off when external peers are attached. Check the actual board revision, Pmod wiring, electrical levels and turnaround before board sign-off.

## Payload and restart findings

- As a starting point, model eight 16-bit entries per context, per direction. In the overlap workload, two SPI payload words can be queued before start, and three UART results plus two SPI results fit without any mid-transfer host service. The probe checks full and empty responses and verifies that one full result buffer does not prevent reporting to the other. It does not rerun the timed core with this endpoint or size buffers for other workloads. Four queues at this depth use 512 data bits before pointers and control; measure area before freezing the depth.
- A complete `BEGIN`, `DATA`, `COMMIT` sequence makes the image visible. Only a later `START` allows a fetch. The model rejects short, overlong, truncated and bad-CRC images, invalid configuration, and writes during execution. A short reload cannot expose old words.
- `STOP` takes effect one modeled chip edge after the validated frame close; reset takes effect on the first sampled low edge, and deselect on the first decision edge that sees the synchronized selection low (two to less than three chip cycles after the pin changes in this model). Each suppresses a pad update due on the safe edge and requires a fresh load. The model assumes the chip still receives clocks for those edges; it does not model the board mux or power-off sequencing. Test the real deselect/reselect behavior with reset before any new load.

**Recommendation:** start with framed SPI. It does not win nominal load speed, but the modeled maximum is well below the 1 s bound, it frees three dedicated inputs and four outputs versus nibble, and the ETR routes its four SPI signals to hardware SPI0. RTL area and firmware timing are not yet measured. See the [draft decision](../04_decisions/DEC-002-loader-transport.md) for the proposal.

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-004/results.json
python3 -B -m unittest -v models.benchmarks.test_g4_loader
python3 -B -m models.benchmarks.run_g4_loader --out design/evals/EVAL-004/results.json
```

See the [per-case results](EVAL-004/results.json). The six Python checks are exploration tests, not `TEST-INT-002` or `TEST-SYS-010`.
