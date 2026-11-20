# 00 — Project status

Progress board. Agents update "Next tasks", "Open questions" and the gate table at the end of
every session. Only Lingga marks a gate ✅.

**Last updated:** 2026-11-20 (fault, stop and halt ordering approved and applied, CHG-008)
**Current stage:** G4 (Micro-architecture)

## Gates

| Gate | Name | Status | Tag | Check |
|---|---|---|---|---|
| G1 | Requirements agreed | ✅ Approved by Lingga | `g1-req` | `check_trace.py --gate G1` |
| G2 | Spec agreed | ✅ Approved by Lingga | `g2-spec` | `--gate G2` |
| G3 | Architecture decided | ✅ Approved by Lingga; ARCH-B selected in DEC-001 | `g3-arch` | `--gate G3` |
| G4 | Micro-architecture agreed | 🔄 stop ordering approved and applied (CHG-008); block approvals pending | `g4-uarch` | `--gate G4` |
| G5 | RTL + unit tests | ⏳ | `g5-rtl` | `--gate G5` |
| G6 | System verified | ⏳ | `g6-verified` | `--gate G6` |
| G7 | Sign-off: precheck + write-up | ⏳ | `g7-submit` | `--gate G7` |

What each gate needs (the checker tests these; Lingga also reviews the content):
- **G1**: every REQ is `agreed` or `rejected`.
- **G2**: every Must/Should REQ has a SPEC or an acceptance TEST; every SPEC is agreed and has a TEST.
- **G3**: ≥ 2 ARCH options; exactly 1 `chosen`; an agreed DEC chooses it, backed by finished EVALs, no guesses.
- **G4**: every BLK agreed and has at least one unit TEST.
- **G5**: every BLK implemented; all unit tests passing.
- **G6**: all integration and system tests passing; every SPEC verified.
- **G7**: all acceptance tests passing; every Must REQ verified; `WRITEUP.md` exists; precheck clean.
- Every gate: zero checker errors, zero `suspect` items.

## Key dates

| Date | Milestone |
|---|---|
| 2027-01-10 | RTL freeze target (REQ-GOAL-005, Should) |
| 2027-01-18 | Submission deadline (REQ-RULE-010) |

## Next tasks
1. TASK-041: Settle the two-word `edge_delta` writeback (register-file write ports).

Use the [project diagram convention](05_microarch/diagrams/README.md): solid for data, dashed for control and status.

## Open questions for Lingga
- Lingga approved [CHG-008](changes/CHG-008-stop-ordering.md) with both proposed choices: `DONE` holds the pads, and `DONE`/`FAULTED` keep payload FIFOs until `STOP`. Fault-to-pad timing is not measured.
- Lingga approved [CHG-007](changes/CHG-007-modular-guards.md) (24-bit guard rule). Guard area is not measured; check it in the BLK-CORE timing probe.
- Lingga approved [CHG-002](changes/CHG-002-loader-recovery.md). Recovery cases are planned. Timeout values remain provisional, and payload FIFO depth plus board and firmware timing remain open.
- Lingga approved [CHG-006](changes/CHG-006-edge-interval.md) for the draft ISA. Two-register writeback, final opcodes and exact fault behavior remain open. No block is agreed yet.
- Lingga approved [CHG-005](changes/CHG-005-host-payload.md) for the draft ISA. Simultaneous host/core FIFO access remains open.
- [EVAL-003](evals/EVAL-003-g4-timed-io.md) supports keeping four output slots and one capture slot per context.
- Final tile fit and routed 60 MHz timing remain unverified. The hybrid [timing slice](evals/EVAL-008-eight-pad-timing.md) met placed setup but missed fast hold, including on internal register paths.
