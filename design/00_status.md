# 00 — Project status

Progress board. Agents update "Next tasks", "Open questions" and the gate table at the end of
every session. Only Lingga marks a gate ✅.

**Last updated:** 2026-11-20 (payload FIFO rule and depth proposed in CHG-010)
**Current stage:** G4 (Micro-architecture)

## Gates

| Gate | Name | Status | Tag | Check |
|---|---|---|---|---|
| G1 | Requirements agreed | ✅ Approved by Lingga | `g1-req` | `check_trace.py --gate G1` |
| G2 | Spec agreed | ✅ Approved by Lingga | `g2-spec` | `--gate G2` |
| G3 | Architecture decided | ✅ Approved by Lingga; ARCH-B selected in DEC-001 | `g3-arch` | `--gate G3` |
| G4 | Micro-architecture agreed | 🔄 ISA execution corner cases settled (CHG-007 to CHG-009); block approvals pending | `g4-uarch` | `--gate G4` |
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
1. TASK-044 (Lingga): Review [CHG-010](changes/CHG-010-payload-fifo.md), the payload FIFO rule and depth. Then apply it.
2. TASK-043: Replay all baseline and non-target programs on the draft ISA.

Use the [project diagram convention](05_microarch/diagrams/README.md): solid for data, dashed for control and status.

## Open questions for Lingga
- **Approve [CHG-010](changes/CHG-010-payload-fifo.md)?** [EVAL-014](evals/EVAL-014-payload-fifo.md): decide FIFO acceptance from the count before the edge (no pass-through), and keep depth 8 (45,197 µm², 3.7 % of the tile, half of BLK-HOST's allowance).
- **UART burst limit.** The 250 kHz loader drains about 2,100 words/s. Continuous UART RX works up to 19,200 baud. At depth 8, bursts of 17 / 13 / 10 bytes fit at 38,400 / 57,600 / 115,200 baud. The agreed 6-byte test fits. Should we document the limit, or raise it with a faster loader clock (DEC-002) or a multi-word `READ` (BLK-HOST)?
- **Review [CHG-009](changes/CHG-009-delta-writeback.md) (small, already applied).** [EVAL-013](evals/EVAL-013-delta-writeback.md): a narrow second write port (R2–R5 only) writes both `edge_delta` words on one edge. It is the smallest option (24,437 µm², 2.0 % of the tile) and needs no extra issue slot. Say if you want it reverted or widened to a full second port (+3,210 µm²).
- Lingga approved [CHG-008](changes/CHG-008-stop-ordering.md) with both proposed choices: `DONE` holds the pads, and `DONE`/`FAULTED` keep payload FIFOs until `STOP`. Fault-to-pad timing is not measured.
- Lingga approved [CHG-007](changes/CHG-007-modular-guards.md) (24-bit guard rule). Guard area is not measured; check it in the BLK-CORE timing probe.
- Lingga approved [CHG-002](changes/CHG-002-loader-recovery.md). Recovery cases are planned. Timeout values remain provisional, and payload FIFO depth plus board and firmware timing remain open.
- Lingga approved [CHG-006](changes/CHG-006-edge-interval.md) for the draft ISA. CHG-009 settled the writeback and CHG-008 the fault behavior; final opcodes remain open. No block is agreed yet.
- Lingga approved [CHG-005](changes/CHG-005-host-payload.md) for the draft ISA. Simultaneous host/core FIFO access remains open.
- [EVAL-003](evals/EVAL-003-g4-timed-io.md) supports keeping four output slots and one capture slot per context.
- Final tile fit and routed 60 MHz timing remain unverified. The hybrid [timing slice](evals/EVAL-008-eight-pad-timing.md) met placed setup but missed fast hold, including on internal register paths.
