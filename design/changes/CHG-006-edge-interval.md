# CHG-006 — Add edge capture and elapsed-time operations to the ISA draft
- Status: proposed
- Size: medium
- Affects: BLK-CORE, BLK-CAPTURE, BLK-TIMER, TEST-UNIT-001, TEST-UNIT-004, TEST-UNIT-005, TEST-SYS-013

## Reason

`wait_save` observes a level and cannot require a transition. Programs such as RC5 need to measure time between edges. [EVAL-010](../evals/EVAL-010-edge-interval.md) exercises two generic operations with the existing capture slot and timer.

## Proposed change

| Operation | Behavior |
|---|---|
| `edge_save pin, mode` | Arm the owning context's slot for a falling (`0`), rising (`1`) or either (`2`) edge. Save the observation timestamp when consuming the result. Do not match a transition on the arm edge. Do not modify the other context. |
| `edge_delta pin, mode, Rd` | Require a valid saved timestamp. Wait for the selected edge, then calculate `(observation − saved) mod 2^24`. Reject zero or a result at or above `2^23`. On success, return the low 16 bits in `Rd` and the zero-extended high bits in `Rd+1`. Update saved time to the observation. |

In this probe, both operations clear the offset pair on success, as `wait_save` does. To avoid writing the same register twice, `edge_delta` permits destinations `R1` through `R4` only. Mode `3` is invalid. Clear or replace the saved time under the existing context reset/flush rules. Do not add another capture slot, edge FIFO or timebase. A program must bound elapsed time because a modulo result cannot detect extra full counter wraps.

The probe uses `shr`, `addoff_r`, `xor`, `ult` and `mov` to decode the RC5 waveform in software. `addoff_r` adds an unsigned general register to the offset pair with a half-range check. `shr` shifts right with zero fill. `xor` and `mov` use a register source, and `ult` replaces a register with `1` or `0` after an unsigned immediate comparison. See `FORMATS` in [`g4_edges.py`](../../models/benchmarks/g4_edges.py) for the trial field sizes. Do not freeze the opcode or register assignments yet.

## Impact and approval

Lingga must approve before the draft blocks and test plan adopt the behavior. Check the two-register writeback schedule, half-range boundaries, rearm, reset/flush and context isolation before block approval. This does not change the requirements or pass G4.
