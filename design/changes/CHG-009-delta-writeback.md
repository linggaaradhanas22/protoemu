# CHG-009 — Write both `edge_delta` words through a narrow second port
- Status: done
- Size: small
- Affects: BLK-CORE, TEST-UNIT-001

## Reason

CHG-006 left the hardware writeback schedule for the two-word `edge_delta` result open. [EVAL-013](../evals/EVAL-013-delta-writeback.md) compares three register-file write structures.

## Proposed change

- On the `edge_delta` retirement edge, write `Rd` through write port A and `Rd+1` through a narrow port. The narrow port reaches only R2–R5 and writes `{9'b0, interval[22:16]}`. Clear the offset pair on the same edge through its dedicated path. All three writes hit different registers.
- Do not add a held-word register or an extra issue slot.
- Keep `Rd` restricted to R1–R4, as CHG-006 already does.

## Impact

Inside BLK-CORE only. No change to block interfaces, SPECs, the ISA draft's behavior or opcodes; the model already retires both words together. Area: 24,437 µm² for the two-context register file after mapping; the held-word option is 661 µm² larger and the full second port 3,210 µm² larger. Timing is not measured. If `Rd` is later allowed to be any register, or the offset pair moves, the narrow port must be widened.

## Approval

small: the agent may apply it under AGENTS.md §7. Applied on 2026-11-20 and reported to Lingga for review. Lingga accepted it as applied on 2026-11-20.

## Close-out

Updated BLK-CORE, TEST-UNIT-001, the ISA draft gap table and the G4 review list. BLK-CORE stays draft and TEST-UNIT-001 stays planned. Nothing became `suspect`.
