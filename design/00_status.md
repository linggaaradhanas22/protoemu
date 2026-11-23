# 00 — Project status

Progress board. Agents update "Next tasks", "Open questions" and the gate table at the end of
every session. Only Lingga marks a gate ✅.

**Last updated:** 2026-11-23 (TASK-064 complete, diagram labels match block records)
**Current stage:** G5 (RTL + unit tests)

## Gates

| Gate | Name | Status | Tag | Check |
|---|---|---|---|---|
| G1 | Requirements agreed | ✅ Approved by Lingga | `g1-req` | `check_trace.py --gate G1` |
| G2 | Spec agreed | ✅ Approved by Lingga | `g2-spec` | `--gate G2` |
| G3 | Architecture decided | ✅ Approved by Lingga; ARCH-B selected in DEC-001 | `g3-arch` | `--gate G3` |
| G4 | Micro-architecture agreed | ✅ Reapproved by Lingga after the decision review and EVAL-025 | `g4-uarch-r2` (prior `g4-uarch`) | `--gate G4` |
| G5 | RTL + unit tests | 🔄 2 of 7 blocks implemented, 2 of 7 unit tests passing | `g5-rtl` | `--gate G5` |
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
1. TASK-061: measure a shorter BLK-CORE run-control and payload-eligibility path before core RTL.
2. Close the two provisional encodings when the RTL decoder and assembler exist.

Use the [top-level diagram](05_microarch/README.md) to find block records by ID. The [diagram convention](05_microarch/diagrams/README.md) uses solid arrows for data and dashed arrows for control and status.

## Open questions for Lingga
- **Pin verification:** The [pin specs](02_spec.md#pins-and-electrical) are agreed. TEST-SYS-014 is planned for system simulation. TEST-ACC-004 still covers the board wiring and electrical checks.
- **Provisional encodings:** The ISA map and host numeric values stay provisional into G5 by decision 2 and decision 4. Freeze them when the RTL decoder and assembler exist.
- **Capture timeout storage:** Keep storing `Rt`. Revisit only after a placed capture-block comparison.
- **60 MHz margin:** [EVAL-025](evals/EVAL-025-agreed-schedule-timing.md) places the agreed schedule with the faster writeback. After clock-tree synthesis and repair, setup is −0.023 ns bare and +0.037 ns with a registered host boundary, and hold passes. That is 23 to 37 ps, too little for routing. The limiter is the run-control and payload-eligibility cloud, not the writeback or timed I/O. Optimize that cloud in G5 and check the routed design.
- Lingga approved [CHG-012](changes/CHG-012-shift-lsb.md) (LSB-first `shift_pin`). Its area is not measured.
- Lingga approved the guarded timed wait [CHG-013](changes/CHG-013-timed-wait.md) after the unguarded version failed in the model (EVAL-017 corrected). It costs 5,479 µm² in the capture slots; the core-side adder operand is not measured.
- Lingga approved [CHG-010](changes/CHG-010-payload-fifo.md) (no pass-through, depth 8) and the 1 MHz loader with four-word transfers ([CHG-011](changes/CHG-011-loader-rate.md), [DEC-005](04_decisions/DEC-005-loader-rate.md) replacing DEC-002). 1 MHz SPI must be checked on the board; the fallback is 500 kHz. `READN`/`WRITEN` framing area is not measured.
- The trace checker warns that finished TASK-021 and TASK-023 point to the replaced DEC-002. Accepted as correct history; the checker is unchanged.
- Lingga accepted [CHG-009](changes/CHG-009-delta-writeback.md) (narrow second register write port) as applied.
- Lingga approved [CHG-008](changes/CHG-008-stop-ordering.md) with both proposed choices: `DONE` holds the pads, and `DONE`/`FAULTED` keep payload FIFOs until `STOP`. The probe's registered fault-to-pad path meets placed setup; routed timing remains open.
- Lingga approved [CHG-007](changes/CHG-007-modular-guards.md) (24-bit guard rule). Guard area is not measured; check it in the BLK-CORE timing probe.
- Lingga approved [CHG-002](changes/CHG-002-loader-recovery.md). Recovery cases are planned. Timeout values remain provisional, and board and firmware timing remain open.
- Lingga approved [CHG-006](changes/CHG-006-edge-interval.md) for the draft ISA. CHG-009 settled the writeback and CHG-008 the fault behavior; final opcodes remain open.
- Lingga approved [CHG-005](changes/CHG-005-host-payload.md) for the draft ISA; CHG-010 settled simultaneous host/core FIFO access.
- [EVAL-003](evals/EVAL-003-g4-timed-io.md) supports keeping four output slots and one capture slot per context.
- Final tile fit and routed 60 MHz timing remain unverified. The repaired core probe used about 0.510 mm² of cells, without the host loader and FIFOs.
- BLK-TIMER and BLK-PROGRAM pass standalone simulation. Their cell area, routed timing, and integration with the host and core remain unverified.
