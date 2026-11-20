# ARCH-B instruction encoding for review

This is the draft encoding for the tested subset, not a release ISA. Lingga approved carrying both timed drive formats forward in [DEC-004](../04_decisions/DEC-004-hybrid-pad-isa.md) and [CHG-004](../changes/CHG-004-hybrid-pad-isa.md). The open instructions below and all block approvals are still pending.

## Word layout

Each instruction is one 24-bit word in little-endian byte order. Bits `[4:0]` hold the opcode. In the table, the first operand starts at bit 5, and each next operand starts above the previous one. Require zero in unused upper bits. Pin indices 0 through 7 refer to `uio[0]` through `uio[7]`. A branch or call target is a word index, not a byte address.

| Opcode (decimal) | Instruction | Operands in bit order, low to high |
|---:|---|---|
| 0 | `halt` | None |
| 1 | `set` | Register (3), value (16) |
| 2 | `add` | Register (3), signed immediate (15) |
| 5 | `cap` | Pin (3), destination (3), sample mode (2), offset (9) |
| 7 | `call` | Target (7) |
| 8 | `ret` | None |
| 9 | `loop` | Register (3), target (7) |
| 10 | `jnz` | Register (3), target (7) |
| 11 | `jump` | Target (7) |
| 14 | `fence` | Offset (9) |
| 15 | `save_now` | None |
| 16 | `addoff` | Signed displacement (15) |
| 17 | `wait_save` | Pin (3), level (1), earliest offset (9) |
| 18 | `pad` | Pin (3), value (1), enable (1), offset (9) |
| 19 | `pad2` | Pin A (3), value A (1), enable A (1), pin B (3), value B (1), enable B (1), offset (9) |
| 20 | `shift_pin` | Source (3), pin (3), offset (9) |
| 21 | `shift_pair` | Source (3), data pin (3), extra pin (3), extra value (1), offset (9) |
| 22 | `drivev` | Source (3), output enable bits (8), offset (8) |
| 23 | `host_get` | Destination (3) |
| 24 | `host_put` | Source (3) |

Opcode 12 (`report`) belongs to the earlier benchmark decoder and is invalid in this draft. The earlier five-pad `out` and sentinel-based `shift_out` (3 and 4) are superseded. Do not assign unlisted opcodes until the instruction gaps are resolved.

## Programmer-visible behavior

- **Registers and control:** Eight 16-bit registers and a two-entry return stack per context. `set` writes a value. `add` adds a signed immediate modulo `2^16`. `loop` decrements modulo `2^16` and branches if the result is nonzero. `jnz` branches without changing the register. `call` saves the next PC. `ret` pops it. Out-of-image fetch, stack overflow and underflow fault. `halt` finishes only the current context. Already admitted pad events can still retire. The exact global fault/stop ordering remains open.
- **Time:** `wait_save` saves the observation timestamp of a synchronized level, not the time of consume. `save_now` saves the counter on its execute edge. Each clears the offset pair in the model. The tested convention uses `R0` for the low 16 offset bits and `R6` for the high seven. `addoff` performs checked signed addition across that pair. Load both halves for offsets that do not fit an immediate. Reject effective relative offsets outside `0` through `2^23−1`. The final register assignment and its reset effect still need review.
- **Scheduling:** Add the saved time, register offset and immediate modulo `2^24`. Apply the half-range rule at drive or sample admission. An invalid saved time faults, except that `wait_save` can wait with zero offset and no saved time. `wait_save` treats its time as an earliest observation, and `fence` waits until its time before completing. Neither queues a pad update. The finite replay does not settle ordering for guards or fences that span more than the half range.
- **Sampling:** `cap` observes the synchronized pin on the target cycle. Mode 0 replaces the destination with the bit. Mode 1 shifts the destination left and inserts the bit at bit 0. Mode 2 shifts right and ORs the bit into bit 7, as used for UART bytes in the probe. Mode 3 is invalid. These modes do not overwrite saved time. Mode 2 is not a general 16-bit right-insert operation.
- **Driving:** `pad` and `pad2` carry explicit value and enable bits. `drivev` reads a mask from source bits `[7:0]` and values from `[15:8]`. Its instruction carries one enable per pad. A zero mask faults. `shift_pin` and `shift_pair` schedule the source MSB and shift the source left only after admission. They request enable for their pads. Use the explicit-enable instructions to release a push-pull pad. Open-drain mode converts high to release. A pair cannot repeat a pin. A request waiting for a queue slot retains its deadline and payload. The queue admits a vector as one event. Splitting a wide update into pairs does not guarantee admission of all pairs.

- **Host payload:** `host_get Rd` pops one 16-bit word from the issuing context's ingress FIFO and writes `Rd`. `host_put Rs` appends the source word to that context's egress FIFO. Empty ingress or full egress stalls only the issuing context. Retain the destination or source word and retry without refetching. Transfer once when the instruction retires. See [CHG-005](../changes/CHG-005-host-payload.md). The opcodes shown are provisional.

## Gaps before RTL or a release encoding

| Gap | Evidence needed |
|---|---|
| Payload FIFO and status | [EVAL-009](../evals/EVAL-009-host-payload.md) replays the approved operations through the host model. Final FIFO depth, same-edge host/core access and status behavior remain open. |
| Edge capture and time inspection | Define an opcode or mode for edge capture, and how a program reads elapsed time or preserves an old timestamp. The tested `wait_save` waits for a level. It does not encode RC5 edge interval measurement. |
| Arithmetic and offset register use | Check bit operations, register pressure and split offsets in real programs. The replay reserves `R0`/`R6` by convention, while the vector translator uses `R7` as scratch. The latter is not an architectural reservation. |
| Execution corner cases | Define modular guard/fence behavior, exact fault and `safe`/`flush` ordering, and pending-operation state. Check isolated contexts and that no failed output, payload or shift operation commits twice. |
| Program coverage | Assemble UART TX/RX, all baseline SPI/I2C cases and the non-target examples using the proposed release operations. The current modeled replay does not verify the full program set or the post-freeze protocol. |

The [eight-pad replay](../evals/EVAL-007-eight-pad-encoding.md) checks both formats with the approved pad map. The [physical slice](../evals/EVAL-008-eight-pad-timing.md) does not include the full core, shift instructions, pending-operation register or routed clocks.
