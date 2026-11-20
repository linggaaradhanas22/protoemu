# CHG-012 — Least-significant-bit-first option for `shift_pin`
- Status: proposed
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

medium: waiting for Lingga.

## Close-out

Not started.
