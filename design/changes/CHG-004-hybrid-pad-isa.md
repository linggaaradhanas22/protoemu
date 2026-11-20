# CHG-004 — Carry compact and vector pad operations into the ISA draft
- Status: done
- Size: medium
- Affects: BLK-CORE, BLK-PROGRAM, BLK-DRIVE, BLK-PADS, TEST-UNIT-001, TEST-UNIT-003, TEST-UNIT-006, TEST-INT-001

## Reason

The earlier benchmark encoding could not address all eight pads for timed drive. [DEC-004](../04_decisions/DEC-004-hybrid-pad-isa.md) recommends using compact instructions for routine updates and one vector event for wider updates.

## Proposed change

Carry `pad` and `pad2` for one- and two-pad updates, and `drivev` for a masked update of up to eight pads with independent enables. Both produce the same timed queue request. Keep the two shift formats so pad 7 remains usable at either output position. Use the proposed fields in the [ISA review draft](../05_microarch/isa-draft.md) when writing the next model, not as a release freeze.

## Impact and approval

Lingga approved the change on 2026-11-20. Block widths, pin map, requirements and architecture did not change. This approval does not agree the block records or pass G4.

## Close-out

Updated the four block drafts and the planned decode, shift, vector admission and pad tests. Reviewed the linked decisions, evaluations and downstream test plans. The loader, timestamp and fetch contracts are unchanged. Generic payload, edge/time access and fault timing remain open in the [G4 review](../05_microarch/g4-review.md). No production RTL or project verification tests changed.
