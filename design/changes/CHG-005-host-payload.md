# CHG-005 — Add generic host payload operations to the ISA draft
- Status: done
- Size: medium
- Affects: BLK-CORE, BLK-HOST, TEST-UNIT-001, TEST-UNIT-007, TEST-INT-001

## Reason

The earlier instruction model hard-coded report channels for specific protocols and a constant SPI transmit word. [EVAL-009](../evals/EVAL-009-host-payload.md) replays the overlap case using generic FIFO operations instead.

## Proposed change

- Add `host_get Rd` and `host_put Rs` to the draft ISA. Use provisional opcodes 23 and 24 with one three-bit register operand after the five opcode bits. Require zero in unused bits. Keep the old fixture opcode 12 out of the draft decoder.
- Transfer one 16-bit word through the issuing context's ingress or egress FIFO. A blocked operation does not retire. Retain its destination or source word until that context gets an issue slot with FIFO credit. Transfer once on retirement without refetching. The other context can continue.
- Keep SPI framing, pin allocation and the host `READ`/`WRITE` contract unchanged. Use the existing context-local queues. Leave final depth and same-edge host/core arbitration for block review. Do not assign protocol meanings to payload words in hardware.

## Impact and approval

Lingga approved the draft operations on 2026-11-20. The architecture, requirements and host framing did not change. The opcodes remain provisional. No block or gate was approved.

## Close-out

Updated the ISA, core and host drafts and the affected verification plans. Reviewed the linked decisions and evaluations. The selected loader, timestamp and timed pad formats are unchanged. The registered tests remain planned. FIFO depth and simultaneous host/core access remain open.
