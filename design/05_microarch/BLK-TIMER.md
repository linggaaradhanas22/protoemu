# BLK-TIMER — Cycle timebase
- Status: draft
- Traces to: DEC-001, SPEC-PHY-001, SPEC-RST-001, SPEC-I2C-003, SPEC-PROG-003

## Purpose

Provide a common cycle number for scheduling output changes and timestamping input observations. The counter does not stop when execution or either context stalls.

## Interface

| Signal | Dir | Width | Meaning |
|---|---|---:|---|
| `clk`, `rst_n` | In | 1 each | Single 60 MHz domain, synchronous active-low reset |
| `cycle` | Out | 24 proposed | Current cycle for issue, output deadlines and capture timestamps |

All consumers use the value of `cycle` immediately **before** the sampling edge. It equals zero before the first edge after reset release and increments on that edge. Start, halt and fault do not rewind time. An event with `deadline == cycle` acts on that edge.

For a new timed request, compute `(deadline - cycle) mod 2^W`. Accept only values from 1 through `2^(W-1)-1`. Zero, half range and values above half range are invalid, not a request to fire now. Software must obey the same half-range rule: a far-out absolute timestamp can alias a near-future one. Accepted requests are compared by equality, not unsigned timestamp order.

The shared timebase does not change under DEC-003. BLK-CORE's saved timestamps are copies of observation times, not separate running counters. A deadline derived from one of those copies obeys the same admission rule.

## Implementation options and budget

Compare 24 bits with 16 bits or a split coarse/fine counter. At 60 MHz the proposed 24-bit half range is about 140 ms; 16 bits gives about 546 µs, less than a 1-Wire reset followed by recovery. Check the carry path and fanout in the next timing probe. Planning allowance: 0.025 mm² of cell area; not measured for this block.

## Unit-test plan and RTL

Exercise reset, exact increment, half-range boundaries and wrap. Planned file: `src/cycle_timer.v`.
