# DEC-003 — Represent captured time in the instruction set
- Status: draft
- Traces to: BLK-CORE, BLK-TIMER, BLK-CAPTURE, BLK-DRIVE, SPEC-I2C-003, SPEC-PROG-003, REQ-PROTO-004
- Evidence: EVAL-005

## Options

| Option | Instructions in measured capture-to-schedule sequence | Tradeoff |
|---|---:|---|
| Split register pair | 4 | Uses two general registers. Separate add and carry instructions take extra issue slots. |
| Fused register pair | 2 | Uses two general registers for a live timestamp. Can use other pairs to keep older timestamps. |
| Dedicated timestamp | 2 | Keeps general registers available. Adds one 24-bit timestamp and a valid bit per context. Holds only one captured timestamp per context. |

## Recommendation, pending approval

Use the dedicated timestamp as the starting point for the ISA. The split pair met both representative delays in the probe but left less time for other work. The fused pair matched the dedicated option's modeled speed. The dedicated operand keeps the evaluated eight general registers available without requiring a double write into the general register file on capture.

The [interface proposal](../changes/CHG-003-isa-timestamps.md) leaves opcodes, long-offset support and saved-timestamp access open. Confirm encoding, area and timing before agreeing BLK-CORE. Do not treat the cycle counts as routed timing evidence.
