# DEC-004 — Select timed pad formats for the draft ISA
- Status: draft
- Traces to: BLK-CORE, BLK-DRIVE, BLK-PADS, SPEC-PHY-001, SPEC-I2C-001, REQ-PROTO-004
- Evidence: EVAL-007, EVAL-008

| Option | Instruction and queue cost | Slow-corner placed setup slack |
|---|---|---:|
| Compact only | Stretched I2C: 63 words. An eight-pad edge needs four queue entries. | +4.332 ns |
| Vector only for non-shift writes | Stretched I2C: 74 words in the unoptimized translation. An eight-pad edge needs one queue entry. | +5.434 ns |
| Hybrid | Use compact for the measured 63-word I2C program. Keep vector for wide updates in one entry. | +4.566 ns |

The timing measurements are for exploratory slices. All three missed fast hold. The hybrid slice adds 8,747 µm² versus the compact slice, but synthesis removes the unused register bank from compact. This area difference is not the cost of adding vector to the full core.

**Recommendation:** Carry both formats into the draft ISA. Compact keeps frequent pin updates short. Vector admits a wide update as one event. The [instruction draft](../05_microarch/isa-draft.md) describes the measured subset and the gaps. No weighted score or release opcode freeze is proposed. No production RTL or block approval follows from this decision alone.
