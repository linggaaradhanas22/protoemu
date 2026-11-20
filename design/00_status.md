# 00 — Project status

Progress board. Agents update "Next tasks", "Open questions" and the gate table at the end of
every session. Only Lingga marks a gate ✅.

**Last updated:** 2026-11-20 (tools installed; Docker first-run setup pending)
**Current stage:** G1 — Requirements

## Gates

| Gate | Name | Status | Tag | Check |
|---|---|---|---|---|
| G1 | Requirements agreed | 🔄 in progress | `g1-req` | `check_trace.py --gate G1` |
| G2 | Spec agreed | ⏳ | `g2-spec` | `--gate G2` |
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
| 2027-01-10 | RTL freeze (proposed, REQ-GOAL-005) |
| 2027-01-18 | Submission deadline (REQ-RULE-010) |

## Next tasks
1. TASK-001 — Lingga reviews requirements (G1).
2. TASK-002 — Finish Docker Desktop's first-run setup, then verify Docker from Ubuntu. SymbiYosys and LibreLane are installed.
3. TASK-004 — Prove the hardening flow once Docker is available.

## Open questions for Lingga
- Which `REQ-GOAL-*` proposals do you want to keep, and with which priority?
- How ambitious on stretch protocols (USB-LS / Ethernet / CAN): target, or only "could"?
