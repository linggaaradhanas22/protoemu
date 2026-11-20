# CHG-003 — Add a dedicated capture timestamp operand
- Status: done
- Size: medium
- Affects: BLK-CORE, BLK-CAPTURE, BLK-TIMER, BLK-DRIVE, TEST-UNIT-001, TEST-INT-001

## Reason

The proposed 24-bit timebase does not fit in one 16-bit general register. [EVAL-005](../evals/EVAL-005-isa-timestamps.md) compares three ways to carry captured time. The [draft decision](../04_decisions/DEC-003-isa-timestamps.md) recommends a dedicated operand.

## Proposed change

- Give each context one 24-bit captured timestamp and a valid bit. Clear validity on reset, start and global flush. An explicit capture consume can save the pre-edge timestamp; ordinary level samples need not overwrite it. An instruction that requests an invalid timestamp faults rather than using stale time.
- Allow timed drive and timed sample operations to form an absolute deadline from the saved timestamp plus an offset, modulo 24 bits. Keep the existing half-range admission rule. Do not silently schedule a late event for the current cycle.
- If a drive request waits for queue space, hold its computed absolute deadline and operands. Do not recompute from the current time. Revalidate the saved deadline on retry.
- Keep the timer, capture and drive interface widths unchanged. This proposal adds programmer-visible core state and operation semantics. It does not freeze opcodes, offset field sizes, support for longer offsets, or instructions to save multiple timestamps.

## Impact and approval

Lingga approved DEC-003 and CHG-003 on 2026-11-20. Before agreeing the block records, re-encode representative programs and test I2C stretching and UART/SPI overlap. Check area and the adder and admission path at 60 MHz.

## Close-out

Updated the affected block drafts and verification plan. Reviewed EVAL-003 and EVAL-005 against the approved behavior. The earlier model results do not verify a final encoding or physical timing. The block records remain draft and the registered tests remain planned.
