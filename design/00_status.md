# 00 — Project status

Progress board. Agents update "Next tasks", "Open questions" and the gate table at the end of
every session. Only Lingga marks a gate ✅.

**Last updated:** 2026-11-20 (G4 loader comparison)
**Current stage:** G4 (Micro-architecture)

## Gates

| Gate | Name | Status | Tag | Check |
|---|---|---|---|---|
| G1 | Requirements agreed | ✅ Approved by Lingga | `g1-req` | `check_trace.py --gate G1` |
| G2 | Spec agreed | ✅ Approved by Lingga | `g2-spec` | `--gate G2` |
| G3 | Architecture decided | ✅ Approved by Lingga; ARCH-B selected in DEC-001 | `g3-arch` | `--gate G3` |
| G4 | Micro-architecture agreed | 🔄 loader options evaluated; interface decision, ISA and block approval pending | `g4-uarch` | `--gate G4` |
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
1. TASK-023: Review the proposed SPI loader and pin map in DEC-002 and CHG-001.

Use the [project diagram convention](05_microarch/diagrams/README.md): solid for data, dashed for control and status.

## Open questions for Lingga
- Approve [CHG-001](changes/CHG-001-loader-interface.md) and [DEC-002](04_decisions/DEC-002-loader-transport.md)? [EVAL-004](evals/EVAL-004-g4-loader.md) supports using dedicated SPI0 pins for loading and leaving the eight bidirectional pads for protocol I/O. Board and firmware timing remain unmeasured.
- [EVAL-003](evals/EVAL-003-g4-timed-io.md) supports keeping four output slots and one capture slot per context. Exact ISA/timestamp representation remains open. No block is agreed yet.
- Final tile fit and routed 60 MHz timing remain unverified. The placed probes met slow-corner setup but missed input hold before clock-tree synthesis.
