# CHG-013 — Guarded timed level wait (`wait_to`)
- Status: done
- Size: medium
- Affects: BLK-CORE, BLK-CAPTURE, TEST-UNIT-001, TEST-UNIT-004, TEST-SYS-009

## Reason

Input waits have no time limit. An I2C target that holds SCL low stalls the controller context until the host sends `STOP`, which also stops the other context and needs a reload. [EVAL-017](../evals/EVAL-017-wait-timeout.md) compared host stop, software polling, timed waits and a watchdog. Only a guarded timed wait detected every stuck bus, kept all I2C cases passing with the same margins as `wait_save` under load, and left the other context untouched.

## Change

**Instruction** `wait_to pin, level, offset, Rt` (provisional opcode 6; fields: pin 3, level 1, offset 9, Rt 3; 21 bits):
- **Guard:** exactly as `wait_save` with a saved time. The target is `saved time + offset pair + offset`, classified once under CHG-007.
- **Wait:** for the synchronized pin to equal `level`.
- **Expiry cycle:** `target + Rt × 64 (mod 2^24)`. At the first execute it must be 1 to `2^23 − 1` cycles in the future, or the instruction faults, as for timed samples. `Rt = 0` means no expiry. `Rt` up to 65,535 gives up to about 70 ms. A saved time is required.
- **On a match:** save the observation timestamp and clear the offset pair, as `wait_save` does. `Rt` is unchanged.
- **On expiry:** the slot ends the wait on the expiry edge. The core writes `Rt = 0` and leaves the saved time and offset unchanged. The program tests `Rt` with `jnz`. A match and expiry on the same edge count as a match. Expiry is not a fault. Stops, faults and flushes follow CHG-008.

**BLK-CAPTURE:** a guarded level arm may be timed. As modeled in EVAL-017, the slot stores `Rt` and, when the guard opens, reloads its deadline register with target + `Rt × 64`. It then compares with its existing equality check. It adds an expired flag. An alternative to compare in RTL is to receive the precomputed expiry from the core and store it in a second 24-bit register.

**BLK-CORE:** decode `wait_to`. Check the expiry at the first execute with the deadline adder (`Rt × 64` as an extra operand), and write `Rt = 0` on expiry. Retry rules are unchanged.

**Programs:** the I2C example uses `wait_to` for every SCL rise. On expiry it releases both lines and reports status 2. It samples SDA 28 cycles after the observed rise. The limit is host-supplied, for example 25 ms.

**Tests:**
- TEST-UNIT-004: a timed guarded arm with a match before expiry, expiry with no match, a match and expiry on one edge, `Rt = 0`, an already-passed guard target, and wrap.
- TEST-UNIT-001: expiry writes only `Rt`; a past expiry faults at the first execute; the other context keeps issuing during a long wait.
- TEST-SYS-009: a stuck-SCL case must report a timeout while the other context completes, and a 10 µs stretch must still pass.

## Impact

No SPEC or REQ change; legitimate stretches are unaffected. Capture-slot area +5,479 µm² for two slots (0.45 % of the tile); the core adder operand is not measured. Uses one of the three free opcodes. All blocks are draft, so nothing becomes `suspect`.

Rejected: the unguarded variant fails I2C because programs run ahead of the pins, and with a fence it has 0 clocks of Fast-mode margin. The watchdog (+6,753 µm²) stops the whole chip, and software polling breaks I2C timing after a stretch. Host `STOP` stays the fallback for any stuck wait.

## Approval

Lingga first approved an unguarded version on 2026-11-20. While applying it, the model showed that version fails I2C. EVAL-017's claim that the guard was unnecessary was wrong. Lingga then approved this guarded version on 2026-11-20.

## Close-out

Updated the ISA draft, BLK-CORE, BLK-CAPTURE, TEST-UNIT-001, TEST-UNIT-004, TEST-SYS-009 and the G4 review list. The model implements `wait_to` as guarded; the rejected unguarded form remains only as an EVAL-017 exploration op. All 89 Python model checks passed. Blocks remain draft and tests remain planned; nothing stays `suspect`.
