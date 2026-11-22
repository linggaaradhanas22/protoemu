# EVAL-024 — Encoding checks for the draft ISA and host protocol
- Status: done
- Traces to: BLK-CORE, BLK-HOST, BLK-PROGRAM
- Compares: ARCH-B
- Model: `models/physical/run_encoding_probe.py`

## Results

The model opcode map assigns 26 distinct opcodes with no duplicates. Only codes 3, 4, 12 and 13 are unused and unassigned. The eight-word boundary corpus (`pad`, `pad2`, `shift_pin` MSB and LSB, `shift_pair`, `drivev`) encoded and decoded back to the same operands at both minimum and maximum field values.

Host command results on the loader model, in the required order:

| Command | Request bytes | Reply status |
|---|---:|---|
| `BEGIN` (valid) | 12 | `OK` |
| `DATA` (3 words) | 8 | `OK` |
| `COMMIT` | 5 | `COMPLETE` |
| `START` | 5 | `OK` |
| `WRITE` | 8 | `OK` |
| `READ` (empty FIFO) | 6 | `EMPTY` |
| `WRITEN` (1 word) | 8 | `OK` + accepted count |
| `READN` (empty FIFO) | 7 | `EMPTY` |
| `STOP` | 5 | `OK` |
| Unknown opcode 0 | 5 | `BAD` |
| Unknown opcode 255 | 5 | `BAD` |
| `COMMIT` while running | 5 | `BAD` |

The model opcode map has 26 distinct opcodes with no duplicates. Codes 3, 4, 12 and 13 are unused. The boundary corpus covered minimum and maximum values where the operand has both, except `pad2`, `shift_pair` and `drivev`, which have one entry each.

An interrupted `READN` reply restarted from bit zero with an identical reply, and the egress FIFO still held both words. The first reply was cut after five bytes.

## Limits

This checks the model and the documented framing, not an RTL implementation. The RTL SPI receiver, CRC engine and command decoder are still unwritten. The reply status values are the model's numbering and stay provisional until the production decoder is tested. No timing, electrical or board behavior was measured.
