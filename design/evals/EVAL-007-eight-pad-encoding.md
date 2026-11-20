# EVAL-007 — Compare timed drive formats for eight pads
- Status: done
- Traces to: BLK-CORE, BLK-DRIVE, BLK-PADS, SPEC-SPI-001, SPEC-I2C-001, SPEC-I2C-003, REQ-PROTO-004
- Compares: ARCH-B
- Model: `models/benchmarks/g4_pad_encoding.py`

## Options

Both formats use 24-bit words with a five-bit opcode. The scheduler, saved timestamp and register offset follow EVAL-006. The probe checks pad ownership before queue admission. A pad with output enable cleared is released. Open-drain high also releases the pad.

| Format | Operands after the opcode | Queue entries |
|---|---|---:|
| Compact `pad` / `pad2` | One or two groups of 3-bit pin, value bit and enable bit. Both groups share a 9-bit immediate offset. | One per instruction |
| Vector `drivev` | 3-bit register index, 8-bit enable mask and 8-bit immediate offset. The register supplies the 8-bit write mask and 8-bit values. | One for up to eight pads |

Both candidates share the same shift instructions. Separate `shift_pin` and `shift_pair` opcodes remove the need for a sentinel pin. Both pins in `shift_pair` can address pad 7. These shift operations request a drive on their selected pins. Use `pad`, `pad2` or `drivev` for explicit enable changes.

In the vector replay, each translated constant output uses `set` and `drivev`. The scratch register holds the mask and values. Programs can load a reusable vector earlier. The replay does not optimize register allocation or hoist repeated constants.

## Results

Each format passed **116/116** monitored cases, including the run starting 500 cycles before timestamp wrap. The fixture uses the approved protocol mapping: SPI on pads 0–3, UART RX on pad 6 in overlap, and I2C on pads 6–7 in its own image. The peer models and protocol checks are unchanged.

| Program | Image words, compact / vector | Max executed words, compact / vector | Min drive slack, compact / vector | Min sample slack, compact / vector |
|---|---:|---:|---:|---:|
| Standalone 1 MHz SPI | 18–19 / 21–23 | 94 / 113 | 18 / 16 cycles | 48 / 46 cycles |
| Fast-mode I2C | 63 / 74 | 610 / 749 | 8 / 6 cycles | 8 / 8 cycles |
| Concurrent UART RX and SPI | 36 / 40 | 284 / 322 | 13 / 11 cycles | 48 / 46 cycles |

Slack is the number of cycles from queue admission or sample arm to the target edge. Neither format stalled on a full queue in the protocol replay. Both reached four pending output entries and two pending captures across those cases.

A separate directed test schedules all eight pad updates on one edge, then releases four and drives four high together on a later edge. Compact uses four entries per edge. Vector uses one per edge, so it can queue the second update before the first retires in this test. This matters when queue entries are already occupied. The directed checks also exercise open-drain release, the extra shift output on pad 7, invalid masks and opcode packing. All 38 Python checks passed.

## Recommendation and next evidence

Use compact operations for routine one- and two-pad updates. Carry the vector operation into a timing probe for wide updates. Do not freeze either encoding yet. Compact uses fewer instructions and leaves more slack in the tested programs. Vector preserves queue capacity for wide updates. Splitting a wide update into compact instructions is not an atomic admission: each pair needs its own slot even if all pairs target the same edge.

At 60 MHz, compare these paths before proposing a freeze:

1. Instruction decode and pin expansion or vector register read through mask, value and enable assembly.
2. Saved timestamp and offsets through deadline calculation, half-range check and queue admission. Include late retry, collision checks, and an entry that retires and becomes available on the same edge.
3. Queue deadline compare through the merge of disjoint due entries and pad output/enable registers. Include four simultaneous due entries and open-drain release.

The model assumes the execute slot and pad timing rules from EVAL-006. It checks driven versus released behavior, not the value of the data latch while output enable is low. It does not establish area or routed timing. No production RTL or registered project tests changed.

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-007/results.json
python3 -B -m models.benchmarks.g4_pad_encoding --out design/evals/EVAL-007/results.json
python3 -B -m unittest models.benchmarks.test_g4_pad_encoding models.benchmarks.test_g4_isa models.benchmarks.test_g4_timestamp models.benchmarks.test_g4_loader models.benchmarks.test_g4_timing models.benchmarks.test_compare models.benchmarks.test_encoded
```

The Git command identifies the model revision for the archived [per-case results](EVAL-007/results.json).
