# CHG-012 — Least-significant-bit-first option for `shift_pin`
- Status: done
- Size: medium
- Affects: BLK-CORE, TEST-UNIT-001

## Reason

[EVAL-016](../evals/EVAL-016-program-suite.md) found that the draft ISA cannot send a byte least significant bit first. `shift_pin` and `shift_pair` always send bit 15 and shift left. There is no left shift, register AND or register add that could isolate bit 0 in a bit loop. UART TX passes only if the host bit-reverses every byte. That moves protocol formatting to the host, against the benchmark rule that protocol decisions stay in the program. It also affects other LSB-first protocols the chip may need after RTL freeze.

## Proposed change

- Use bit 20 of the `shift_pin` word, now reserved zero, as an order flag. `0`: send bit 15, then shift the source left (today). `1`: send bit 0, then shift the source right with zero fill.
- Admission, blocking and retry rules are unchanged: the source register still changes only when the request is admitted.
- `shift_pair` uses all 24 bits and stays MSB-first.
- Update the ISA draft table (`shift_pin`: source (3), pin (3), offset (9), order (1)) and the shift rules in BLK-CORE.
- Add to TEST-UNIT-001: both orders, a blocked LSB-first request that shifts once on admission, and a rejected retry that leaves the register unchanged.

## Impact

No SPEC or REQ change. No new opcode. In EVAL-016 the prototype matched the host-reversed program on all 10 UART TX cases, with the same margins. Area is not measured; the expected cost (a **guess**) is a 2:1 select for the pad bit and a 16-bit shift-direction mux in the core. All blocks are draft, so nothing becomes `suspect`.

Alternative: keep the ISA and document host bit reversal for LSB-first output.

## Approval

Lingga approved the LSB-first `shift_pin` option on 2026-11-20.

## Close-out

Updated the ISA draft (format and driving rules), BLK-CORE, TEST-UNIT-001 and the G4 review list. The model now decodes the order bit in `shift_pin`, and the prototype `shift_lsb` was removed. Order 0 encodes bit-identically to the old `shift_pin`, so EVAL-003 to EVAL-016 regenerate byte-identical results. All 82 Python model checks passed. Area is still not measured. Blocks remain draft and tests remain planned; nothing stays `suspect`.
