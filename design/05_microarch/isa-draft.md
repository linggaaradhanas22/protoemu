# ARCH-B instruction encoding for review

This is the draft encoding for the tested subset, not a release ISA. Lingga approved carrying both timed drive formats forward in [DEC-004](../04_decisions/DEC-004-hybrid-pad-isa.md) and [CHG-004](../changes/CHG-004-hybrid-pad-isa.md). The open instructions below and all block approvals are still pending.

## Traceability to the G2 specification

The main trace runs through [BLK-CORE](BLK-CORE.md). The G2 specs define behavior visible to the host or on the pins. The instruction names, bit fields and register layout below are ARCH-B design choices, not G2 requirements.

| G2 spec | What the ISA contributes |
|---|---|
| [`SPEC-PROG-001`](../02_spec.md#spec-prog-001--build-the-baseline-program-images): build loadable baseline programs | A 24-bit word format for the assembler and a programming model for UART TX/RX, SPI and I2C. The released toolchain is still open. |
| [`SPEC-PROG-002`](../02_spec.md#spec-prog-002--protocol-selected-after-rtl-freeze): support a new protocol after RTL freeze | Branches, arithmetic, timed I/O and generic host payload let the loaded program make protocol decisions. The post-freeze demonstration has not run. |
| [`SPEC-PROG-003`](../02_spec.md#spec-prog-003--non-target-benchmark-suite): run WS2812, 1-Wire and RC5 on the same design | Timed drive and sampling cover pulse generation and 1-Wire reads. `edge_save` and `edge_delta` give the RC5 program edge times and intervals. |
| [`SPEC-UART-001`](../02_spec.md#spec-uart-001--uart-transmit-timing) and [`002`](../02_spec.md#spec-uart-002--uart-receive-tolerance) | LSB-first `shift_pin` schedules outgoing bits. A saved observation time and `cap` let the receiver place samples relative to the start bit. |
| [`SPEC-SPI-001`](../02_spec.md#spec-spi-001--spi-controller-modes-and-clock-rate) | `shift_pair`, timed drive and `cap` let the program coordinate data transitions and samples with the selected SPI mode. |
| [`SPEC-I2C-001`](../02_spec.md#spec-i2c-001--i2c-clock-and-bus-timing), [`002`](../02_spec.md#spec-i2c-002--i2c-transfers-and-acknack) and [`003`](../02_spec.md#spec-i2c-003--i2c-target-clock-stretching) | Timed pad updates work with the pad adapter's open-drain mode. Sampling and branches handle ACK/NACK. Guarded waits let the program use the observed SCL rise as its timing reference. `wait_to` also lets software handle a stuck line; the spec requires bounded stretch support, not that opcode or its timeout policy. |
| [`SPEC-HOST-001`](../02_spec.md#spec-host-001--load-and-start-from-the-rp2350): load and start complete images | The loader delivers 24-bit words to [BLK-PROGRAM](BLK-PROGRAM.md). [BLK-HOST](BLK-HOST.md) defines the SPI framing and `COMMIT`/`START` rules, which are outside the ISA. `host_get` and `host_put` move runtime payload, not program words. |

[EVAL-016](../evals/EVAL-016-program-suite.md) gives model evidence for the baseline and non-target programs. It is not RTL verification. See the [system and block sequences](sequences.md) for the fetch, timed I/O and host handoffs.

## Word layout

Each instruction is one 24-bit word in little-endian byte order. Bits `[4:0]` hold the opcode. In the table, the first operand starts at bit 5, and each next operand starts above the previous one. Require zero in unused upper bits. Pin indices 0 through 7 refer to `uio[0]` through `uio[7]`. A branch or call target is a word index, not a byte address.

| Opcode (decimal) | Instruction | Operands in bit order, low to high |
|---:|---|---|
| 0 | `halt` | None |
| 1 | `set` | Register (3), value (16) |
| 2 | `add` | Register (3), signed immediate (15) |
| 5 | `cap` | Pin (3), destination (3), sample mode (2), offset (9) |
| 6 | `wait_to` | Pin (3), level (1), earliest offset (9), timeout register (3) |
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
| 20 | `shift_pin` | Source (3), pin (3), offset (9), order (1) |
| 21 | `shift_pair` | Source (3), data pin (3), extra pin (3), extra value (1), offset (9) |
| 22 | `drivev` | Source (3), output enable bits (8), offset (8) |
| 23 | `host_get` | Destination (3) |
| 24 | `host_put` | Source (3) |
| 25 | `edge_save` | Pin (3), edge mode (2) |
| 26 | `edge_delta` | Pin (3), edge mode (2), low destination (3) |
| 27 | `shr` | Destination (3), shift count (4) |
| 28 | `addoff_r` | Source (3) |
| 29 | `xor` | Destination (3), source (3) |
| 30 | `ult` | Destination (3), unsigned immediate (16) |
| 31 | `mov` | Destination (3), source (3) |

Opcode 12 (`report`) belongs to the earlier benchmark decoder and is invalid in this draft. The earlier five-pad `out` and sentinel-based `shift_out` (3 and 4) are superseded. Do not assign unlisted opcodes until the instruction gaps are resolved.

## Programmer-visible behavior

- **Registers and control:** Eight 16-bit registers and a two-entry return stack per context. `set` writes a value. `add` adds a signed immediate modulo `2^16`. `loop` decrements modulo `2^16` and branches if the result is nonzero. `jnz` branches without changing the register. `call` saves the next PC. `ret` pops it. Out-of-image fetch, stack overflow and underflow fault. `halt` finishes only the current context. Already admitted pad events can still retire. A fault takes effect on the next edge: everything else due on the fault edge completes, then both contexts stop, queued work is discarded and the pads go safe. See [CHG-008](../changes/CHG-008-stop-ordering.md).
- **Time:** `wait_save` saves the observation timestamp of a synchronized level, not the time of consume. `save_now` saves the counter on its execute edge. Each clears the offset pair in the model. The tested convention uses `R0` for the low 16 offset bits and `R6` for the high seven. `addoff` performs checked signed addition across that pair. Load both halves for offsets that do not fit an immediate. Reject effective relative offsets outside `0` through `2^23−1`. The final register assignment and its reset effect still need review.
- **Scheduling:** Add the saved time, register offset and immediate modulo `2^24`. Apply the half-range rule at drive or sample admission. An invalid saved time faults, except that `wait_save` can wait with zero offset and no saved time. `wait_save` treats its time as an earliest observation, and `fence` waits until its time before completing. Neither queues a pad update.
- **Time guards:** When a `fence` first executes or a guarded `wait_save` arms, compute `delta = (target − cycle) mod 2^24`. `1` through `2^23−1` waits until `cycle == target`. Zero or `2^23` and above means already reached: continue without a fault. An open guard stays open until the instruction retires. Arm a guard within `2^23−1` cycles (~140 ms) of its target; an older target looks like a future one. See [CHG-007](../changes/CHG-007-modular-guards.md).
- **Sampling:** `cap` observes the synchronized pin on the target cycle. Mode 0 replaces the destination with the bit. Mode 1 shifts the destination left and inserts the bit at bit 0. Mode 2 shifts right and ORs the bit into bit 7, as used for UART bytes in the probe. Mode 3 is invalid. These modes do not overwrite saved time. Mode 2 is not a general 16-bit right-insert operation.
- **Driving:** `pad` and `pad2` carry explicit value and enable bits. `drivev` reads a mask from source bits `[7:0]` and values from `[15:8]`. Its instruction carries one enable per pad. A zero mask faults. `shift_pin` and `shift_pair` schedule the source MSB and shift the source left only after admission. With order `1`, `shift_pin` schedules the source LSB and shifts right with zero fill instead ([CHG-012](../changes/CHG-012-shift-lsb.md)); `shift_pair` is MSB-first only. They request enable for their pads. Use the explicit-enable instructions to release a push-pull pad. Open-drain mode converts high to release. A pair cannot repeat a pin. A request waiting for a queue slot retains its deadline and payload. The queue admits a vector as one event. Splitting a wide update into pairs does not guarantee admission of all pairs.

- **Host payload:** `host_get Rd` pops one 16-bit word from the issuing context's ingress FIFO and writes `Rd`. `host_put Rs` appends the source word to that context's egress FIFO. Empty ingress or full egress stalls only the issuing context. Retain the destination or source word and retry without refetching. Transfer once when the instruction retires. See [CHG-005](../changes/CHG-005-host-payload.md). The opcodes shown are provisional.
- **Timed waits:** `wait_to` waits like `wait_save` with a saved time, guarded at its target. It expires `Rt × 64` cycles after that target. The expiry must be in the future half at the first execute, or the instruction faults. `Rt = 0` disables expiry. On a match it saves the observation time and clears the offset pair. On expiry it writes `Rt = 0` and changes nothing else; the program branches with `jnz Rt`. Expiry is not a fault. See [CHG-013](../changes/CHG-013-timed-wait.md).
- **Edges and elapsed time:** `edge_save` and `edge_delta` wait for falling (`0`), rising (`1`) or either (`2`) edge. Mode `3` is invalid. On success, save the synchronized observation timestamp and clear the offset pair. `edge_delta` requires a valid previous timestamp and returns the modular difference in `Rd` (low 16 bits) and `Rd+1` (zero-extended high bits). `Rd` is `R1` through `R4` in the trial layout. A difference of zero or at least `2^23` faults. These operations have no built-in timeout. See [CHG-006](../changes/CHG-006-edge-interval.md).
- **Arithmetic for measured intervals:** `shr` shifts right with zero fill. `addoff_r` adds an unsigned register value to the offset pair and faults if the result exceeds its range. `xor` updates the destination with its XOR against the source. `ult` replaces the destination with `1` if its previous value is less than the immediate, or `0` otherwise. `mov` copies a register. Opcodes 25–31 are provisional.

## Gaps before RTL or a release encoding

| Gap | Evidence needed |
|---|---|
| Payload FIFO and status | [EVAL-009](../evals/EVAL-009-host-payload.md) replays the approved operations through the host model. [CHG-010](../changes/CHG-010-payload-fifo.md) settles the same-edge rule and depth 8 ([EVAL-014](../evals/EVAL-014-payload-fifo.md)). [CHG-011](../changes/CHG-011-loader-rate.md) adds four-word host transfers at 1 MHz. |
| Edge capture and time inspection | [CHG-006](../changes/CHG-006-edge-interval.md) adopts edge and elapsed-time behavior for the draft. [EVAL-010](../evals/EVAL-010-edge-interval.md) covers RC5. [CHG-009](../changes/CHG-009-delta-writeback.md) writes both result words on one edge. Final opcodes and any separate timestamp inspection remain open. |
| Arithmetic and offset register use | Check bit operations, register pressure and split offsets in real programs. The replay reserves `R0`/`R6` by convention, while the vector translator uses `R7` as scratch. The latter is not an architectural reservation. |
| Execution corner cases | [CHG-007](../changes/CHG-007-modular-guards.md) settles the modular guard/fence rule ([EVAL-011](../evals/EVAL-011-modular-guards.md)). [CHG-008](../changes/CHG-008-stop-ordering.md) settles fault, stop and halt ordering ([EVAL-012](../evals/EVAL-012-stop-ordering.md)). Check isolated contexts and that no failed output, payload or shift operation commits twice. |
| Program coverage | [EVAL-016](../evals/EVAL-016-program-suite.md) runs every baseline and non-target test case on the draft ISA (914 of 914 pass, at most 70 words). [CHG-012](../changes/CHG-012-shift-lsb.md) adds LSB-first `shift_pin`, so UART TX no longer needs host bit reversal. A released assembler and toolchain build are still missing. |

The [eight-pad replay](../evals/EVAL-007-eight-pad-encoding.md) checks both formats with the approved pad map. The [physical slice](../evals/EVAL-008-eight-pad-timing.md) does not include the full core, shift instructions, pending-operation register or routed clocks.
