# CHG-001 — Define the RP2350 loader interface
- Status: done
- Size: medium
- Affects: BLK-HOST, BLK-PADS, BLK-PROGRAM, TEST-UNIT-007, TEST-INT-002

## Reason

The block drafts leave transport and pin mapping open. [EVAL-004](../evals/EVAL-004-g4-loader.md) supports the [SPI recommendation](../04_decisions/DEC-002-loader-transport.md). No requirement change is proposed.

## Proposed change

- Define dedicated SPI mode 0 host pins and the separate reply-ready signal. Use the protocol pin map in EVAL-004. The ASIC samples the synchronized host clock and data; it does not use the host clock as an ASIC clock domain.
- Put one command in each request frame. Keep `CS` high between frames. Only issue a reply read when `READY` is high; during that frame the loader sends the pending reply and ignores MOSI. Preload the first reply bit before the next rising SCK. Hold the pending reply until a complete reply read. Define timeout/abort and retry behavior before agreeing BLK-HOST; the probe assumes complete reply reads and does not guarantee a retry after a corrupted reply.
- Use opcode, 16-bit little-endian body length, body and CRC-16/CCITT-FALSE (initial `0xFFFF`, little-endian CRC bytes). `BEGIN` carries word count, context enables, entry PCs, ownership masks and open-drain mask. `DATA` carries exactly that many 24-bit words, in little-endian byte order. Stream tentative words into the halted store; do not add a duplicate image buffer. Reject malformed or incomplete loads; report image completion only on a separate valid `COMMIT`. `START` remains separate. The probe's numeric command and status codes are draft.
- Try per-context ingress and egress buffers with eight 16-bit words each. A full host write reports full without an overwrite; an empty host read reports empty. A full core result buffer blocks the reporting context only. Preload host payload and drain results outside timing-critical transactions. Measure area and replay baseline programs before locking buffer depth.
- Give reset, deselect and stop priority over a coincident pad update on the safe edge. Propose that a validated explicit `STOP` makes the protocol pads safe and invalidates the running image on the next ASIC edge. Deselect acts on the edge that sees synchronized `ena` low. Always reset and reload after reselection. Test safe-edge timing, including core fault propagation, during integration.

## Impact and approval

Lingga approved DEC-002 and CHG-001 on 2026-11-20. Recheck the affected records and downstream tests, including `TEST-SYS-010`; no project test has passed on the strength of this probe. Check measured loader/FIFO area and routed input timing before physical sign-off.

## Close-out

Applied the approved interface to BLK-HOST, BLK-PADS and BLK-PROGRAM, then reviewed the affected verification records. The EVAL-004 rerun reproduced all 192 modeled loads; all 25 Python model checks passed. The block records remain draft and hardware tests remain planned. Timeout, abort and retry are tracked in TASK-024, not approved by this change.
