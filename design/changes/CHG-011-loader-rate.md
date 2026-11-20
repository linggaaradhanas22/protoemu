# CHG-011 — 1 MHz loader with 4-word payload transfers
- Status: done
- Size: medium
- Affects: DEC-002, BLK-HOST, BLK-PADS, TEST-UNIT-007, TEST-SYS-005, TEST-SYS-010

## Reason

At 250 kHz the host moves one payload word per 468 µs, so UART streams above 19,200 baud stop after 10–17 bytes ([EVAL-014](../evals/EVAL-014-payload-fifo.md)). [EVAL-015](../evals/EVAL-015-host-rate.md) modeled faster clocks and multi-word transfers.

## Proposed change

- **DEC-002 → DEC-005.** Keep the dedicated SPI0 transport and pins. Run SCK at 1 MHz instead of 250 kHz. DEC-002 becomes `replaced`.
- **`READN ctx, n`** (n = 1–4): reply `OK` with `min(n, count)` egress words, or `EMPTY` if there are none. The words stay in the FIFO while the reply is sent. Free them only on an exact-length reply close, so an interrupted reply restarts from bit zero with the same words. Reset, deselect and `STOP` clear the FIFO as before.
- **`WRITEN ctx, words`** (1–4 words): write the words tentatively into free ingress slots beyond the tail while the request arrives. On validation, commit the leading words that fit and reply with the accepted count (`OK` if all, `FULL` if fewer). A bad length or CRC commits nothing. The core never reads tentative slots.
- Keep single-word `READ` and `WRITE`. Numeric opcode values stay draft.
- Guards, inter-frame budget, `READY` behavior and recovery deadlines are unchanged.

## Impact

No SPEC or REQ change; SPEC-HOST-001 leaves the rate open. The host pins and BLK-HOST's payload interface to the core are unchanged. FIFO area rises by 305 µm² at depth 8 (EVAL-015); the framing logic is not measured. 1 MHz SPI must be checked on the board. Items below DEC-002 in `trace.md`: BLK-HOST, BLK-PADS, BLK-PROGRAM, SPEC-HOST-001, SPEC-RST-002 and REQ-PROTO-004 are its upward links; nothing traces up to DEC-002.

## Approval

Lingga approved option D from EVAL-015 on 2026-11-20 ("follow your recommendations").

## Close-out

Created DEC-005 and marked DEC-002 `replaced`. Updated BLK-HOST (clock, commands, tentative ingress writes, rates), BLK-PADS, the micro-architecture README, the G4 review list, TEST-UNIT-007, TEST-SYS-005 and TEST-SYS-010. Re-checked BLK-PROGRAM, SPEC-HOST-001 and SPEC-RST-002: their text does not depend on the clock rate. Nothing stays `suspect`. Blocks remain draft and tests remain planned.
