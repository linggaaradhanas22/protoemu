# CHG-004 — Carry compact and vector pad operations into the ISA draft
- Status: proposed
- Size: medium
- Affects: BLK-CORE, BLK-PROGRAM, BLK-DRIVE, BLK-PADS, TEST-UNIT-001, TEST-UNIT-003, TEST-UNIT-006, TEST-INT-001

## Reason

The earlier benchmark encoding could not address all eight pads for timed drive. [DEC-004](../04_decisions/DEC-004-hybrid-pad-isa.md) recommends using compact instructions for routine updates and one vector event for wider updates.

## Proposed change

Carry `pad` and `pad2` for one- and two-pad updates, and `drivev` for a masked update of up to eight pads with independent enables. Both produce the same timed queue request. Keep the two shift formats so pad 7 remains usable at either output position. Use the proposed fields in the [ISA review draft](../05_microarch/isa-draft.md) when writing the next model, not as a release freeze.

## Impact and approval

The block widths, pin map, requirements and architecture do not change. The programmer-visible operations do change. On approval, update the block drafts and test plans to check decode, mask and enable generation, vector admission with one free slot, and no register shift before admission. Keep generic payload, edge/time access and fault timing open as listed in the [G4 review](../05_microarch/g4-review.md). Lingga must approve before applying this proposal. Approval does not agree the block records or pass G4.
