# 00 — Project status

Progress board. Agents update "Next tasks", "Open questions" and the gate table at the end of
every session. Only Lingga marks a gate ✅.

**Last updated:** 2026-11-20 (TASK-008 acceptance coverage complete)
**Current stage:** G2 (Specification)

## Gates

| Gate | Name | Status | Tag | Check |
|---|---|---|---|---|
| G1 | Requirements agreed | ✅ Approved by Lingga | `g1-req` | `check_trace.py --gate G1` |
| G2 | Spec agreed | 🔄 all Must and Should items covered; 13 draft specs | `g2-spec` | `--gate G2` |
| G3 | Architecture decided | ⏳ | `g3-arch` | `--gate G3` |
| G4 | Micro-architecture agreed | ⏳ | `g4-uarch` | `--gate G4` |
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
1. TASK-009: Define benchmark stimuli and timing limits at 60 MHz for comparing architectures.
2. TASK-004: Run local hardening and gate-level simulation on the unchanged template. This can proceed in parallel with G2.

## Open questions for Lingga
- Review the TASK-005 specs at G2. Keep four rising edges as the provisional reset limit in `SPEC-RST-001`.
- Review the TASK-006 protocol specs at G2, especially the UART baud list and error limits, the 100 kHz and 1 MHz SPI targets, and the 10 µs I2C stretch limit.
- Review the proposed 1 s limit for each RP2350 program load and the plan to choose one new protocol after freezing the RTL for verification. The three named benchmarks do not count as that new protocol.
- Review the proposed acceptance cases for concurrent UART reception with SPI and for SPI and I2C target roles (`TEST-ACC-008` and `TEST-ACC-009`). The Could items remain optional.
