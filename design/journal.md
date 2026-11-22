# Journal

Dated log of every work session, newest at the bottom. It is the handover between sessions and
the raw material for the write-up.

Format (keep it short):

```markdown
## 2026-11-21 — <agent or Lingga> — TASK-003
Did: what was done, with IDs.
Results: numbers, pass/fail, links to reports.
AI vs human: what the AI produced; what Lingga decided or changed.
Problems: anything that went wrong or surprised us.
Next: the next step and any question for Lingga.
```

---

## 2026-11-20 — Lingga + Claude — project start
Did: set up the V-model process: AGENTS.md, SETUP.md, design/ records, check_trace.py and
WSL scripts. Wrote the first requirements from the competition rules (all `draft`).
AI vs human: Claude drafted the process and requirement text; Lingga chose the method
(V-model with full traceability), the tools (OpenCode, Verilog + cocotb, WSL for tools,
Windows for files) and will decide the requirements at G1.
Next: Lingga reviews requirements (TASK-001) and sets up WSL (TASK-002).

## 2026-11-20 — Lingga + OpenCode: TASK-002, TASK-003
Did: Created `~/ttsetup/venv` in WSL, installed the pinned packages from `test/requirements.txt`, and ran `bash scripts/sim.sh` against the unchanged template.
Results: `test.test_project` passed on Icarus Verilog 12.0 with cocotb 2.0.1 (1 passed, 0 failed; 100 µs simulated). Local result: `test/results.xml`.
AI vs human: Lingga asked for help with setup. OpenCode installed the simulation dependencies and ran the test. No design decisions were made.
Problems: `check_env.sh` can print `OK` for missing commands or packages because it checks the exit status of `head`. SymbiYosys and Docker remain unavailable in WSL.
Next: Lingga reviews requirements (TASK-001) and decides when to finish TASK-002. LibreLane can wait until the hardening run (TASK-004).

## 2026-11-20 — Lingga + OpenCode — TASK-002
Did: Installed the OSS CAD Suite (2026-11-19) and LibreLane 3.1.0.dev4 in WSL. Installed Docker Desktop 4.99.0 in per-user mode with the WSL 2 backend. Fixed `check_env.sh` so a failed version command no longer prints `OK`.
Results: SymbiYosys v0.71-7-gb21f778 passed a small Z3 proof. The RTL template passed again (1 passed, 0 failed). Docker Desktop opened its welcome window; Docker is not yet available from Ubuntu.
AI vs human: Lingga approved installing the remaining tools. OpenCode installed and checked them. No design decisions were made.
Problems: The suite's `vvp` wrapper overrides the Python home. `env.sh` now prefers system Icarus for cocotb when both system binaries are present.
Next: Lingga completes Docker Desktop's first-run setup. Then verify `docker run --rm hello-world` from Ubuntu to finish TASK-002 before starting TASK-004.

## 2026-11-20 — OpenCode — TASK-002
Did: Rechecked the WSL setup from Ubuntu.
Results: `bash scripts/check_env.sh` reported all tools and packages OK. Docker 29.9.3 pulled and ran `hello-world` from Ubuntu. TASK-002 is done.
AI vs human: Lingga asked for the recheck. OpenCode ran both checks. No design decisions were made.
Problems: None in the setup checks.
Next: Run local hardening and gate-level simulation in TASK-004.

## 2026-11-20: Lingga + OpenCode (TASK-001)
Did: Recorded approval of all 32 requirements without changing their text or priorities.
Results: `check_trace.py --gate G1 --write-trace` reported `GATE G1: MET`, with 0 errors and 0 warnings.
AI vs human: Lingga approved the requirements. OpenCode recorded the decisions and ran the checker.
Problems: None.
Next: Ask Lingga for G1 sign-off before tagging `g1-req` or moving to G2.

## 2026-11-20: Lingga + OpenCode (G1 sign-off)
Did: Recorded G1 sign-off, closed TASK-001, and set G2 as the current stage.
Results: `GATE G1: MET`. All 32 requirements are agreed. The checker reported 0 errors and 0 warnings.
AI vs human: Lingga approved closing G1 and requested a push. OpenCode updated the project records and ran the checker.
Problems: None in the G1 check.
Next: Draft the rules and constraints specification (TASK-005). The template hardening check (TASK-004) is still open.

## 2026-11-20: OpenCode (TASK-005)
Did: Drafted `SPEC-RST-001`, `SPEC-RST-002`, and `SPEC-PHY-001`. Planned seven acceptance tests and three system tests.
Results: All ten `REQ-RULE-*` items now have a draft specification or a planned acceptance test. The trace checker reported 0 errors and 0 warnings. No design tests ran.
AI vs human: OpenCode drafted the checks and proposed the four-edge reset window. Lingga approved the underlying requirements at G1. The specifications remain drafts.
Problems: None in the trace check. G2 remains open pending the remaining coverage and specification review.
Next: Draft UART, SPI, and I2C specifications and tests (TASK-006). Keep the template unchanged for TASK-004.

## 2026-11-20: Lingga + OpenCode (TASK-006)
Did: Drafted two UART, one SPI, and three I2C specifications for `REQ-PROTO-001` through `REQ-PROTO-003`. Added one planned system test per spec.
Results: Checked the I2C timing values against NXP UM10204. The trace checker reported 0 errors and 0 warnings. No design tests ran.
AI vs human: Lingga asked to proceed after discussing the reset window. OpenCode kept four edges as a provisional limit and drafted the protocol targets for review. No spec was marked agreed.
Problems: None in the trace check. G2 still needs the remaining coverage and approval of the drafts.
Next: Draft the programmability and host interface specifications (TASK-007). Local template hardening (TASK-004) remains open.

## 2026-11-20: Lingga + OpenCode (TASK-007)
Did: Drafted `SPEC-HOST-001` and `SPEC-PROG-001` through `SPEC-PROG-003`, with four planned system tests. Linked the existing reselection draft to the loader contract.
Results: Specified load and start behavior, baseline toolchain outputs, three non-target benchmarks, and a separate protocol selected after an RTL revision is frozen for verification. The checker reported 0 errors and 0 warnings. G2 still has 9 uncovered Must or Should requirements and 13 draft specs. No design tests ran.
AI vs human: Lingga asked to proceed with TASK-007. OpenCode drafted the contract and proposed the 1 s load limit and the benchmark list. No spec was marked agreed.
Problems: Pin assignments, transfer format, and exact benchmark timings remain open. The benchmark profiles belong to TASK-009.
Next: Draft the remaining acceptance tests and review coverage (TASK-008). Local template hardening (TASK-004) remains open.

## 2026-11-20: Lingga + OpenCode (TASK-008)
Did: Added nine planned acceptance tests (`TEST-ACC-008` through `TEST-ACC-016`). Recorded conditional checks for all six Could requirements without registering them as G7 tests.
Results: All 20 Must and 6 Should requirements now have a specification or acceptance test. The G2 checker found 0 errors and 0 warnings. Only the 13 draft specs remain on its open-point list. No design tests ran.
AI vs human: Lingga asked to proceed with the next task. OpenCode proposed the acceptance scenarios. No requirement priority or spec approval changed.
Problems: None in the trace check. The checker requires all registered acceptance tests to pass at G7, so the optional checks stay conditional until selected.
Next: Prepare the benchmark profiles at 60 MHz (TASK-009). Local template hardening (TASK-004) remains open.

## 2026-11-20: Lingga + OpenCode (TASK-009)
Did: Defined seven benchmark profiles at 60 MHz with stimuli, pass criteria, and timing budgets. Linked the three non-target profiles to `TEST-SYS-013` and left the post-freeze protocol unselected.
Results: Checked timing conversions, the synthetic 1-Wire ROM CRC, RC5 frame fields, and UART/SPI overlap. The trace checker found 0 errors and 0 warnings. No architecture models or RTL tests ran.
AI vs human: Lingga asked to proceed. OpenCode chose the proposed fixture variants and documented their sources. Lingga has not yet approved the G2 specs.
Problems: WS2812B revisions have different pulse widths. The benchmark uses the V1.0 data sheet instead of assuming one limit applies to all variants.
Next: Lingga reviews the 13 G2 drafts. Local template hardening (TASK-004) remains open.

## 2026-11-20: Lingga + OpenCode (G2 specification approval)
Did: Recorded approval of all 13 specs without changing their wording.
Results: The trace checker reported `GATE G2: MET`, with 0 errors and 0 warnings. No design tests ran.
AI vs human: Lingga approved the specs. OpenCode recorded the approval and ran the checker.
Problems: None in the trace check.
Next: Ask Lingga to sign off on G2 before tagging `g2-spec` or starting G3.

## 2026-11-20: Lingga + OpenCode (G2 sign-off)
Did: Recorded G2 sign-off and set G3 as the current stage.
Results: `GATE G2: MET`. All 13 specs are agreed, and all 26 Must and Should requirements have planned checks. No design tests ran.
AI vs human: Lingga approved closing G2 and requested a push. OpenCode verified the gate and updated the project records.
Problems: None in the trace check.
Next: Draft architecture candidates and plan their benchmark evaluations. Template hardening (TASK-004) remains open.

## 2026-11-20: OpenCode (TASK-010)
Did: Drafted ARCH-A (independent engines), ARCH-B (one core with timed I/O), and ARCH-C (sequencer with configurable lanes). Planned the common pin-level protocol comparison (EVAL-001) and the area, timing and toolchain comparison (EVAL-002).
Results: Three candidates and two planned evaluations. The trace check found no errors or warnings. No candidate benchmark ran, and G3 remains open.
AI vs human: Lingga requested G3 work in parallel with the template smoke test. OpenCode drafted the options and methods; Lingga has not selected an architecture.
Next: Build the shared benchmark fixtures and candidate cycle models in TASK-011.

## 2026-11-20: OpenCode (TASK-004)
Did: Confirmed Docker was already running. Ran `/usr/bin/time -p bash scripts/harden.sh --setup` on the unchanged Tiny Tapeout template using LibreLane `3.1.0.dev4` and Tiny Tapeout support tools `0922544`.
Results: The setup attempt stopped after 32.08 s (wall time), exit 1. No hardening started, no gate-level netlist was produced, and gate-level simulation did not run. This does not verify REQ-RULE-008.
AI vs human: Lingga requested this smoke test in parallel with G3. OpenCode ran the setup and left the template files unchanged.
Problems: `tt_tool.py --create-user-config` rejects the empty title, author and description in the stock `info.yaml`.
Next: Ask Lingga to approve a metadata-only override in the WSL smoke-test copy, then rerun hardening and simulate the generated netlist.

## 2026-11-20: Lingga + OpenCode (TASK-004 complete)
Did: Filled only the three approved metadata fields in the WSL copy, added local Git provenance for `tt_tool.py`, and finished hardening. Ran `gl_sim.sh` on the generated netlist using the exact Ciel PDK revision from the flow.
Results: Hardening passed in 348.85 s wall time. Gate-level `test_project` passed (1/1, 1.65 s wall time). See the [smoke-test report](../reports/harden/20261120_1602/README.md). No project acceptance tests ran.
AI vs human: Lingga approved the scratch-copy metadata. OpenCode ran the flow and verified that the repository template files were unchanged.
Problems: The wrapper excludes Git metadata that `tt_tool.py --harden` needs. Gate-level simulation also needed `PDK_ROOT` pointed at Ciel's version directory. The report documents both workarounds and the warnings.
Next: TASK-011, shared benchmark fixtures and candidate cycle models. G3 remains open.

## 2026-11-20: OpenCode (TASK-011)
Did: Built three exploratory scheduling models, shared pin-level peers and monitors for all seven profiles, and archived the per-case results and traces under EVAL-001.
Results: All 2,262 cases passed across the three candidates. Eight model sanity tests passed. B filled its four-entry output queue in the overlap case; C used both configurable lanes. No RTL or acceptance tests ran.
AI vs human: Lingga authorized the benchmark work. OpenCode implemented and ran the comparison. Lingga has not selected an architecture.
Problems: The first idle-skipping implementation skipped the cycle that made a synchronized input visible. Fixed it and checked sparse and dense traces for all three models on the stretched Fast-mode I2C case. The models do not yet measure binary image size or fetch and branch latency.
Next: TASK-013 to encode programs and rerun the critical cases before sizing and timing probes in TASK-012.

## 2026-11-20: OpenCode (TASK-013)
Did: Built packed instruction and lane images and reran 1 MHz SPI modes 0–3, UART/SPI overlap, and Fast-mode I2C with clock stretching and NACKs. The interpreter enforces bank capacities and charges issue slots for fetch, execution, taken branches and descriptor reads.
Results: All 33 encoded cases and 12 model sanity tests passed. A and C used 62 of 64 code words for the Fast-mode I2C exchange. B reached four output entries during the 10 µs I2C stretch case. Results, images and traces are under EVAL-001.
AI vs human: Lingga authorized the encoded comparison. OpenCode wrote and ran the provisional images and model. Lingga has not selected an architecture or approved an ISA.
Problems: These cases do not measure host loading, timestamp rollover, or the mapped area and timing of the actual hardware.
Next: TASK-012 to map area and timing probes on IHP for each viable candidate.

## 2026-11-20: OpenCode (TASK-012)
Did: Mapped representative flop stores, datapaths, I/O timing logic and loader front ends for all three architectures. Ran unplaced timing at three IHP corners and slow-corner timing after placement and design repair using the 8×4 row geometry.
Results: Placed area was 0.406, 0.316 and 0.266 mm² for A, B and C. All passed estimated slow-corner setup at 60 MHz; all showed about −0.23 ns hold slack at a synchronizer input. See EVAL-002. These are probe measurements, not final design sign-off.
AI vs human: Lingga authorized the comparison. OpenCode built and ran the probes. No architecture or decision weights have been approved.
Problems: Unbuffered control loads made unplaced timing much worse than placed timing. The probe does not include clock-tree synthesis, routed parasitics or the full host interface.
Next: Ask Lingga which tradeoff should drive the draft architecture decision. Keep G3 open.

## 2026-11-20: OpenCode (TASK-014)
Did: Drafted DEC-001 around B's shared program capacity. Compared the measured code space, area and timing across EVAL-001 and EVAL-002, with the remaining validation risks listed separately.
Results: The draft recommends B and proposes weights. It does not assign scores or change candidate or gate status. No tests ran in this task.
AI vs human: Lingga authorized drafting the decision. OpenCode wrote the recommendation and proposed weights. Lingga has not approved the weights or selected an architecture.
Next: Ask Lingga to confirm or revise the proposed weights before scoring the decision.

## 2026-11-20: Lingga + OpenCode (TASK-015)
Did: Scored DEC-001 from the archived EVAL-001 and EVAL-002 data. Changed each approved weight up and down by 10 percentage points, rescaling the others for each test.
Results: B scored 4.264/5, C 2.200/5, and A 1.800/5. B ranked first in all six sensitivity tests. No architecture status changed, and no design tests ran.
AI vs human: Lingga approved the 50% program space, 30% area, and 20% setup slack weights. OpenCode calculated and recorded the scores. Lingga has not yet approved the selection.
Next: Ask Lingga to select ARCH-B. Leave G3 open until approval and the gate check.

## 2026-11-20: Lingga + OpenCode (TASK-016)
Did: Recorded ARCH-B as chosen in DEC-001 and retained A and C as rejected alternatives.
Results: `check_trace.py --gate G3` reported MET with zero errors and zero warnings. No design tests ran; final fit and routed timing are unverified.
AI vs human: Lingga approved selecting ARCH-B. OpenCode recorded the selection and ran the gate checker. G3 sign-off has not been requested or recorded yet.
Next: Ask Lingga to sign off G3. After approval, tag the gate and start G4 block and unit-test planning.

## 2026-11-20: Lingga + OpenCode (TASK-017, G3 sign-off)
Did: Recorded G3 sign-off for ARCH-B and set G4 as the current stage. Kept DEC-001 and its evaluation evidence unchanged.
Results: `check_trace.py --gate G3` reported MET with zero errors and zero warnings. No design tests ran. Final fit and routed setup and hold remain unverified.
AI vs human: Lingga approved closing G3. OpenCode ran the gate check and updated the project records.
Next: TASK-018, draft the hardware block boundaries and plan unit-test coverage for ARCH-B.

## 2026-11-20: Lingga + OpenCode (TASK-019)
Did: Configured this checkout to use WSL Git and SSH with a dedicated key. No global Git or SSH settings changed.
Results: GitHub authentication, remote lookup, and a dry-run push succeeded. No remote refs changed and no design tests ran.
AI vs human: Lingga registered the public key. OpenCode verified the account and configured the checkout.
Next: TASK-018 remains the next design task.

## 2026-11-20: Lingga + OpenCode (TASK-018)
Did: Drafted seven ARCH-B block contracts, provisional area allowances and a candidate pin split. Added `TEST-UNIT-001` through `TEST-UNIT-007`, `TEST-INT-001` and `TEST-INT-002`, and an editable hardware overview.
Results: Trace checker found zero errors and warnings. G4 remains open with seven draft blocks. The draw.io validator found zero errors and warnings, and the PNG review checked routing and label placement. No hardware tests ran and no RTL changed.
AI vs human: Lingga asked to proceed with G4 and asked about diagram rules. OpenCode drafted the interfaces and planned tests. Lingga has not approved the block contracts or the gate.
Next: TASK-020 for deadline replay; TASK-021 for loader and pin allocation. Tile fit and routed timing remain open.

## 2026-11-20: Lingga + OpenCode (TASK-020)
Did: Built a cycle-level exploration of G4 issue, capture and timed output. Reused the G3 programs and independent peer monitors. Archived the sweep in EVAL-003.
Results: Four slots passed 58/58 cases at each of two counter starts, including wrap. Three slots passed 58/58 but had up to 16 queue-blocked cycles per case. All 19 Python checks and 33 G3 encoded cases passed. No RTL tests ran.
AI vs human: Lingga authorized the replay. OpenCode wrote and ran the probe and recommends retaining four output slots and one capture slot per context. Lingga has not agreed any block or gate.
Next: TASK-021, compare the loader transports and validate the pin split. Final timestamp/ISA encoding and routed timing remain open.

## 2026-11-20: Lingga + OpenCode (TASK-022)
Did: Published version 2 of the ARCH-B overview with separate data and control arrows. Kept version 1 and recorded the project diagram convention.
Results: The validator and visual review checked the revised drawing. No hardware contracts or gate status changed.
AI vs human: Lingga chose solid for data and dashed for control. OpenCode updated the drawing and documented the convention.
Next: TASK-021, compare loader transports and validate the pin split.

## 2026-11-20: Lingga + OpenCode (TASK-021)
Did: Compared nibble and dedicated SPI transports, checked the ETR RP2350 pin table, and modeled payload and stop/reload. Archived EVAL-004 and drafted DEC-002 and CHG-001.
Results: All 192 modeled loads and 25 Python checks passed. The full 128-word image took 13.628 ms over modeled SPI, versus 6.050 ms on the nominal nibble link and 27.100 ms with delayed polling. Both layouts leave eight bidirectional pads for protocol use. No firmware, RTL or board test ran.
AI vs human: Lingga requested the next task. OpenCode produced the probe and recommends SPI. Lingga has not approved the transport or block interfaces.
Next: TASK-023, ask Lingga to approve or revise DEC-002 and CHG-001. The gate stays open.

## 2026-11-20: Lingga + OpenCode (TASK-023)
Did: Recorded Lingga's approval of DEC-002 and CHG-001. Updated the loader, pad adapter, program store and affected test plans. No blocks were approved.
Results: EVAL-004 reproduced all 192 modeled loads and all 25 Python checks passed. Traceability was clean. No RTL or firmware changed, and no board or project verification tests ran.
AI vs human: Lingga approved the SPI transport, pin map and proposed interface. OpenCode applied the change and rechecked the affected records.
Next: TASK-024, draft timeout and recovery behavior. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-024)
Did: Drafted CHG-002 for SPI timeouts, interrupted frames and corrupted replies. Added proposed cases for loader, integration and system checks.
Results: The proposal keeps the approved pin map and frame format. It calls for reset and reload instead of automatically repeating an operation with unknown outcome. No recovery tests ran and no block contract changed.
AI vs human: Lingga authorized drafting recovery. OpenCode proposed the behavior and provisional timeouts. Lingga has not approved CHG-002.
Next: TASK-025, review CHG-002. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-025)
Did: Recorded Lingga's approval of CHG-002. Updated the loader and pad drafts and added recovery cases to the verification plan.
Results: Traceability was clean. No RTL or firmware changed and no recovery verification tests ran. The timeout values still need board measurements.
AI vs human: Lingga approved resetting and reloading after an uncertain transfer without automatic command replay. OpenCode applied the change and reviewed affected records.
Next: TASK-026, compare ISA timestamp representations. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-026)
Did: Ran the EVAL-005 exploration for split and fused register pairs and a dedicated timestamp. Archived the wrap, contention and queue cases. Drafted DEC-003 and CHG-003.
Results: The fused pair and dedicated operand used two words and admitted in 3–7 cycles without queue stalls in the representative cases. The split pair used four words and took 7–17 cycles. The probe ran 222 cases, including expected late rejections. All 29 Python checks passed. No RTL changed.
AI vs human: Lingga authorized the comparison. OpenCode wrote the model and recommends the dedicated operand. Lingga has not approved the decision or change.
Next: TASK-027, review DEC-003 and CHG-003. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-027)
Did: Recorded approval of DEC-003 and CHG-003. Updated the core, capture, drive and timer drafts and the affected test plans.
Results: The shared timer and timed-I/O interfaces are unchanged. The new test cases cover saved-time validity, context isolation, wrap and stable deadlines under retries. No RTL changed and no registered tests ran.
AI vs human: Lingga approved one saved timestamp per context. OpenCode applied the change and reviewed the affected records.
Next: TASK-028, prototype the instruction encoding. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-028)
Did: Ran EVAL-006 as an exploration. Assembled 24-bit instruction words that use saved timestamps and replayed the existing SPI, stretched I2C and concurrent UART/SPI fixtures.
Results: All 116 modeled cases and 33 Python checks passed. I2C used 63 words with eight cycles of minimum drive and sample slack. The overlap used 36 words with 13 cycles of minimum drive slack. The prototype does not cover all eight pads or establish physical timing. No RTL changed.
AI vs human: Lingga authorized the prototype. OpenCode wrote and ran the exploration. No final encodings or blocks were approved.
Next: TASK-029, compare drive encodings for eight pads. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-029)
Did: Ran EVAL-007 as an exploration. Compared compact one- and two-pad instructions with an eight-pad vector. Replayed the critical protocol fixtures on the approved pin map.
Results: Each format passed 116 modeled cases. All 38 Python checks passed. Compact I2C used 63 words with 8 cycles of minimum drive slack, versus 74 words and 6 cycles for vector. An eight-pad edge used four queue entries with compact and one with vector. No production RTL changed.
AI vs human: Lingga authorized the comparison. OpenCode wrote and ran it and recommends compact for routine updates and a vector timing probe for wide updates. No final encoding or block was approved.
Next: TASK-030, probe issue and retirement timing at 60 MHz. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-030)
Did: Built and placed the EVAL-008 exploratory issue and pad-retirement slice for compact, vector and hybrid decoding. Simulated a directed hybrid queue and pad sequence.
Results: Hybrid placed setup slack was +4.566 ns at the slow corner. Fast hold slack was −0.199 ns overall and −0.037 ns for internal register paths. Hybrid placed slice area was 55,542 µm². The smoke check and all 38 Python model checks passed. No production RTL changed.
AI vs human: Lingga authorized the probe. OpenCode ran it and recommends carrying both formats into review. No final encoding or block was approved.
Next: TASK-031, draft the ISA and block review package. Full-chip fit and routed timing remain open.

## 2026-11-20: Lingga + OpenCode (TASK-031)
Did: Drafted the G4 review, candidate ISA table, DEC-004 and CHG-004. Linked every block to its planned unit check and recorded the remaining ISA and timing gaps.
Results: The draft carries compact and vector operations into review using EVAL-007 and EVAL-008 as evidence. No RTL, model or registered test changed.
AI vs human: Lingga authorized the review package. OpenCode drafted it. No pad format, block or gate was approved in this task.
Next: TASK-032, review DEC-004 and CHG-004. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-032)
Did: Recorded approval of DEC-004 and CHG-004. Updated the core, program store, drive and pad drafts and added decode, shift and output enable cases to the verification plan.
Results: Traceability was clean and all 38 Python model checks passed. Block interfaces and pin mapping did not change. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga approved keeping both timed pad formats in the draft ISA. OpenCode recorded the decision and applied the change. Neither the release opcodes nor G4 were approved.
Next: TASK-033, prototype generic host payload instructions.

## 2026-11-20: Lingga + OpenCode (TASK-033)
Did: Ran EVAL-009 as an exploration. Replaced benchmark reports and the fixed SPI transmit word with FIFO instructions in the overlap program. Drafted CHG-005.
Results: All 96 concurrent UART/SPI model cases and 41 Python checks passed. A directed check stalled one context on empty ingress and full egress without blocking the other. The program used 37 words with 13 cycles of minimum output admission slack. No production RTL changed.
AI vs human: Lingga authorized the prototype. OpenCode wrote and ran it. Lingga has not approved the payload operations or G4.
Next: TASK-034, review CHG-005.

## 2026-11-20: Lingga + OpenCode (TASK-034)
Did: Recorded approval of CHG-005. Added `host_get` and `host_put` to the ISA, core and host drafts. Planned checks for stalls, context isolation and reload with a pending payload operation.
Results: Traceability was clean and all 41 Python model checks passed. Host framing and pin mapping are unchanged. The opcodes, FIFO depth and simultaneous access rules are not frozen. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga approved the draft payload operations. OpenCode applied the change and reviewed the linked records. No block or gate was approved.
Next: TASK-035, prototype edge capture and elapsed-time instructions. G4 remains open.

## 2026-11-20: Lingga + OpenCode (TASK-035)
Did: Explored encoded edge save and interval arithmetic in EVAL-010. Replayed the RC5 benchmark and drafted CHG-006.
Results: All six modeled RC5 cases passed, including wrap at each rate. The 39-word program returned both expected frames. All 45 Python model checks passed. No production RTL or registered tests changed.
AI vs human: Lingga authorized the prototype. OpenCode modeled the instructions, wrote the RC5 program and proposed the behavior for review. Lingga has not approved the change or G4.
Next: TASK-036, review CHG-006. Two-register writeback and opcode allocation are not frozen.

## 2026-11-20: Lingga + OpenCode (TASK-036)
Did: Recorded approval of CHG-006. Updated the draft ISA and the core, capture and timer records. Added planned checks for edge polarity, wrap, interval writeback and reset.
Results: Traceability reported no errors or warnings. All 45 Python checks and all six RC5 model cases passed. The capture and timer interfaces did not change. The two-register writeback schedule and opcodes remain open. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga approved the edge capture and elapsed-time behavior for the draft ISA. OpenCode applied the change and reviewed the linked records. No block or gate was approved.
Next: TASK-037, specify timed wait and fence behavior across wrap.

## 2026-11-20: Lingga + Claude (TASK-037)
Did: Added a 24-bit guard model (`g4_guards.py`) and 13 directed checks. Compared four rules for `fence` and `wait_save` targets in EVAL-011 and proposed the `sticky` rule in CHG-007. `wait_save` without a saved time is now marked as unguarded in the model. `g4_edges.run_case` accepts a probe class.
Results: `sticky` passed 122/122 replays with cycle traces identical to the earlier model. `compare` also passed the replays but missed a level that arrived 2^23 + 1000 cycles after its guard opened. `strict` failed all 96 UART cases because the receiver arms a wait whose target has already passed. All 58 Python model checks passed. EVAL-006, EVAL-009 and EVAL-010 regenerate byte-identical results. Traceability reported no errors or warnings. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga asked Claude to start TASK-037. Claude chose the candidate rules, built the model, ran the replays and drafted EVAL-011 and CHG-007. Lingga has not yet reviewed the proposal. No block, CHG or gate was approved.
Problems: The earlier model's fence and wait checks used unbounded elapsed time and would misbehave after 2^24 model cycles. Guard hardware cost is not measured.
Next: TASK-038, Lingga reviews CHG-007.

## 2026-11-20: Lingga + Claude (TASK-038)
Did: Recorded approval of CHG-007. Added the guard rule to BLK-CORE, BLK-CAPTURE, BLK-TIMER and the ISA draft. Added boundary, wrap and late-level checks to TEST-UNIT-001, TEST-UNIT-004 and TEST-UNIT-005. Moved the guard model into `g4_timing.py` and made `sticky` the default for `ISAProbe` and its subclasses. Added TASK-039.
Results: All 59 Python model checks passed. EVAL-003 through EVAL-011 regenerate byte-identical results. Traceability reported no errors or warnings. Block interfaces and SPECs did not change. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga approved the `sticky` guard rule for the draft ISA. Claude applied it and reviewed the linked records. No block or gate was approved.
Next: TASK-039, specify global fault, flush and pending-operation ordering.

## 2026-11-20: Lingga + Claude (TASK-039)
Did: Added an inert safe-edge hook to `g4_timing.py`, the stop model `g4_stop.py` and 5 directed checks. Compared a fault safe edge on F + 1 against one on F in EVAL-012. Proposed the fault, stop and halt ordering and host run states in CHG-008. Added TASK-040.
Results: 12,520 stopped runs (every issue point in three benchmarks under both rules, plus 6,096 host stop edges) met every check: no duplicate retirement, no lost update, no pad change after the safe edge, and matching traces before the stop. The two rules differ in 3 of 3,212 fault points. A stop can release a pad one cycle after its last change. All 64 Python model checks passed. EVAL-003 through EVAL-011 regenerate byte-identical results. Traceability reported no errors or warnings. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga asked Claude to continue with TASK-039. Claude chose the rules to compare, built the model, ran the sweep and drafted EVAL-012 and CHG-008, including the proposed `DONE` and `FAULTED` behavior. Lingga has not reviewed the proposal. No block, CHG or gate was approved.
Problems: The first results file was 5.8 MB, so it now stores only summaries and failing rows. The timing benefit of the F + 1 rule is a guess; it is not measured.
Next: TASK-040, Lingga reviews CHG-008.

## 2026-11-20: Lingga + Claude (TASK-040)
Did: Recorded approval of CHG-008. Added the fault, stop and halt ordering and the `HALTED`/`RUNNING`/`DONE`/`FAULTED` run states to BLK-CORE, BLK-HOST, BLK-DRIVE, BLK-CAPTURE, BLK-PADS, the ISA draft and the G4 review list. Added fault-edge, priority and run-state checks to TEST-UNIT-001, 003, 004, 006, 007 and TEST-INT-002. Added TASK-041.
Results: Traceability reported no errors or warnings. Block interfaces and SPECs did not change apart from the run state and fault record in `run_status`. No model code, production RTL or registered verification tests changed.
AI vs human: Lingga approved the ordering and both proposed choices: `DONE` holds the pads, and `DONE`/`FAULTED` keep payload FIFOs until `STOP`. Claude applied the change and reviewed the linked records. No block or gate was approved.
Next: TASK-041, settle the two-word `edge_delta` writeback.

## 2026-11-20: Lingga + Claude (TASK-041)
Did: Built a two-context register-file probe (`models/physical/regfile_probe.v`) with three ways to write the `edge_delta` high word, plus a random testbench and an IHP mapping runner. Added an optional extra writeback slot to the ISA model and an issue-cost study (`g4_writeback.py`) with 4 checks. Wrote EVAL-013 and applied CHG-009 (small) to BLK-CORE and TEST-UNIT-001. Added TASK-042 and TASK-043.
Results: All variants matched the reference over 4,000 random instructions; a seeded address bug gave 7,931 errors. Mapped areas: held word 25,098.7 µm², narrow port 24,437.4 µm², full second port 27,647.2 µm². The held word cost one extra issue per `edge_delta` and 1 cycle of RC5 sample slack, with no change to the other context's drive slack. All 68 Python model checks passed. EVAL-003 through EVAL-012 regenerate byte-identical results. Traceability reported no errors or warnings. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga asked Claude to do TASK-041. Claude chose the options, built the probes and applied CHG-009 as a small change under AGENTS.md §7, without asking first; Lingga has not reviewed it yet. No block or gate was approved.
Problems: The generic Yosys cell count ranked the options differently from the mapped IHP area; the EVAL uses the mapped result. Register-file timing is not measured.
Next: TASK-042, payload FIFO depth and same-edge host/core access. Lingga to review CHG-009.

## 2026-11-20: Lingga + Claude (TASK-042)
Did: Built a payload FIFO probe with two same-edge rules (`models/physical/fifo_probe.v`), a random reference testbench, an IHP area runner and a shared mapping helper (`ihp_map.py`, now also used by the EVAL-013 runner). Added a host-rate, demand and UART-burst study (`g4_fifo_depth.py`) with 4 checks. Wrote EVAL-014 and proposed CHG-010. Added TASK-044 and made TASK-043 wait for it.
Results: Both rules matched the reference at depths 2–16; a seeded boundary bug gave 1,191 errors. Four depth-8 queues map to 45,196.7 µm² (3.74 % of the tile); bypass adds 1,184.8 µm². A payload READ takes 468 µs on the 250 kHz loader. Depth 8 holds every specified test's unpacked demand except 1-Wire (9 words). Continuous UART RX is sustainable only up to 19,200 baud; at 115,200 a depth-8 receiver absorbs 10 back-to-back bytes. The refactored EVAL-013 runner reproduces its areas exactly. All 72 Python model checks passed. Traceability reported no errors or warnings. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga asked Claude to continue with TASK-042. Claude chose the rules and depths to compare, built the probes, counted the demand and drafted EVAL-014 and CHG-010. Lingga has not reviewed them. No block, CHG or gate was approved.
Problems: The UART burst limit is a real product limit, not a spec failure; Lingga must decide whether to document it or change the loader. The draft ISA cannot pack two received bytes per word without bit reversal.
Next: TASK-044, Lingga reviews CHG-010 and the burst-limit question.

## 2026-11-20: Lingga + Claude (TASK-045)
Did: Lingga asked for data before deciding the UART burst limit. Made the loader transport's SCK and frame overhead adjustable (defaults unchanged). Added provisional `READN`/`WRITEN` commands to the host model, a rate sweep (`g4_host_rate.py`) with 6 checks, a multi-word FIFO probe with a random testbench, and an area runner. Wrote EVAL-015 and linked it from CHG-010.
Results: At 115,200 baud and depth 8: 250 kHz single-word stops after 10 bytes; 2 MHz single-word after 47; 4 MHz single-word and 1 MHz with 4-word transfers sustain the stream in both directions. Multi-word transfers alone do not help at 250 kHz. The synchronizer model passes up to 4 MHz (59 ns reply margin) and fails at 8 MHz; 1 MHz leaves 434 ns. Multi-word FIFO access adds 304.8 µm² at depth 8. The 250 kHz load time matches EVAL-004 (13.6 ms); 1 MHz loads in 3.5 ms. All 78 Python model checks passed. EVAL-003 through EVAL-014 regenerate byte-identical results. Traceability reported no errors or warnings. No production RTL, agreed record or registered test changed.
AI vs human: Lingga asked Claude to model the options first. Claude chose the sweep ranges, designed the provisional commands, ran the models and recommended 1 MHz with 4-word transfers. The tight-overhead case is Claude's guess. Lingga has not chosen an option.
Problems: The first multi-word testbench reported a count mismatch caused by a testbench race; quiescing the core before the final check fixed it, and a seeded bug still gives 5,879 errors. Board and pad delays are not modeled.
Next: TASK-044, Lingga decides CHG-010 and the loader option.

## 2026-11-20: Lingga + Claude (TASK-044)
Did: Recorded Lingga's approval of CHG-010 and of option D from EVAL-015. Applied CHG-010 (registered-status FIFO rule, depth 8) to BLK-HOST, BLK-CORE, TEST-UNIT-001 and TEST-UNIT-007. Wrote CHG-011 and DEC-005, which replaces DEC-002: same SPI0 transport and pins, 1 MHz SCK, and `READN`/`WRITEN` with up to four words. Marked DEC-002 `replaced`. Updated BLK-HOST, BLK-PADS, the micro-architecture README, the G4 review list, the ISA draft, TEST-UNIT-007, TEST-SYS-005 and TEST-SYS-010.
Results: Traceability reported 0 errors and 2 warnings: finished TASK-021 and TASK-023 still point to the replaced DEC-002, which is correct history. Re-checked BLK-PROGRAM, SPEC-HOST-001 and SPEC-RST-002; none depends on the clock rate. No model code, production RTL or registered verification tests changed.
AI vs human: Lingga told Claude to follow its recommendations: approve CHG-010 and choose the 1 MHz, four-word option. Claude wrote DEC-005 and CHG-011 from EVAL-015 and applied both changes. No block or gate was approved.
Next: TASK-043, replay all baseline and non-target programs on the draft ISA. Board check of 1 MHz SPI remains open.

## 2026-11-20: Lingga + Claude (TASK-043)
Did: Recorded that Lingga accepted CHG-009 as applied and that the two trace-checker warnings stay as correct history (no tool change). Wrote native draft-ISA programs for UART TX/RX, SPI, I2C, WS2812 and 1-Wire with host payload (`g4_suite.py`), and replayed them with RC5 and the overlap case against the independent G3 monitors. Added a prototype `shift_lsb` operation (exploration only) and 3 checks. Wrote EVAL-016 and proposed CHG-012. Added TASK-046.
Results: 914 of 914 cases passed, including the full UART RX baud-error and start-phase sweep (740 cases), all SPI modes at 100 kHz and 1 MHz, all I2C variants at both rates, and timer wrap. Images use 15 to 70 words. The monitors reject UART TX without bit reversal, a wrong I2C address and a short WS2812 pulse. All 81 Python model checks passed. EVAL-003 through EVAL-015 regenerate byte-identical results. Traceability reported 0 errors and the 2 accepted warnings. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga asked Claude to close the open decisions and do TASK-043. Claude wrote the programs and the prototype, chose to sample 1-Wire presence instead of waiting, and proposed CHG-012. Lingga has not reviewed CHG-012.
Problems: The draft ISA cannot send LSB first without host bit reversal. The first 1-Wire program waited for presence with no timeout and copied a write-0 pulse at the 60 µs minimum; both were changed (sampled presence, 65 µs pulse, worst margin 62 clocks).
Next: TASK-046, Lingga reviews CHG-012. Then the G4 block review and full-core timing check.

## 2026-11-20: Lingga + Claude (TASK-046)
Did: Recorded Lingga's approval of CHG-012. Applied it: `shift_pin` bit 20 selects LSB-first output in the ISA draft, BLK-CORE and TEST-UNIT-001. Replaced the prototype `shift_lsb` in the model with the order bit and added an encoding check. At Lingga's request, wrote the EVAL-017 plan for a wait timeout (I2C clock stretching) and added TASK-047.
Results: Order 0 encodes bit-identically to the old `shift_pin`. EVAL-003 through EVAL-016 regenerate byte-identical results, and all 82 Python model checks passed. Traceability reported 0 errors and the 2 accepted warnings. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga approved CHG-012 and asked for a plan for the I2C stall. Claude applied the change and wrote the plan with four options (host stop, software polling, timed wait, watchdog). Lingga has not reviewed the plan.
Next: TASK-047, run the EVAL-017 plan, then the G4 block review.

## 2026-11-20: Lingga + Claude (TASK-047)
Did: Ran the EVAL-017 plan. Added `g4_timeout.py` (I2C program variants with a status register, a stuck-SCL peer, a two-context I2C+SPI runner, host-stop and watchdog models) and a prototype `wait_to` in the ISA model. Added area probes for timed wait slots and a watchdog with a directed testbench, and 5 checks. Wrote the EVAL-017 results and proposed CHG-013. Added TASK-048.
Results: The timed wait passed 14/14 I2C regression and 8/8 stuck-bus cases, detected stuck SCL at the limit (18 cycles early from 64-cycle units) and never disturbed the SPI context. Host stop and the watchdog detected every stuck bus but stopped SPI after 4–5 of 6 exchanges. Software polling failed: at 16 cycles it faulted under contention; at 32–64 cycles it stretched the next SCL clock to 161–193 clocks (window 150–157) and once starved SPI. Guarded timed slots cost +5,479 µm², unguarded ones less than synthesis noise, the watchdog 6,753 µm². All 87 Python model checks passed. Earlier affected EVALs regenerate byte-identical results. Traceability reported 0 errors and the 2 accepted warnings. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga approved running the plan. Claude built the models and probes and recommends the unguarded timed wait (C2). Lingga has not reviewed CHG-013.
Problems: The first two-context runs faulted because the I2C program's 16-cycle start lead was too short with another context issuing; it now uses 64 cycles. The first unguarded area probe forced every wait unguarded and gave a misleadingly small area; it was fixed. The repeated-START stuck case first used the wrong clock count. Several summary-print bugs cost reruns.
Next: TASK-048, Lingga reviews CHG-013. Then the G4 block review and full-core timing check.

## 2026-11-20: Lingga + Claude (TASK-048)
Did: Lingga approved CHG-013 (unguarded timed wait). While applying it, the model showed it fails every I2C case: programs run ahead of the pins, so the wait sees SCL still high before the queued fall. Claude stopped and reported. The EVAL-017 claim that the guard was unnecessary was wrong; the earlier passing prototype had kept the guard. Claude measured the alternatives under SPI contention. Lingga then approved the guarded version, which Claude applied to the ISA draft, BLK-CORE, BLK-CAPTURE, TEST-UNIT-001, TEST-UNIT-004 and TEST-SYS-009. EVAL-017 was rewritten with a correction note. Added TASK-049.
Results: Guarded `wait_to` passed 14/14 regression, 9/9 stuck-bus cases and 154/154 runs with SPI busy, with a worst I2C margin of 2 clocks (same as `wait_save`). The unguarded version with a fence passed with 0 clocks of margin and fails without the fence. Both timed versions first faulted under contention with SDA sampled 14 cycles after the rise; sampling at 28 fixed it. All 89 Python model checks passed. Affected earlier EVALs regenerate byte-identical results. Traceability reported 0 errors and the 2 accepted warnings. No production RTL changed and no registered verification tests ran.
AI vs human: Lingga approved CHG-013 twice: first the unguarded version on Claude's wrong recommendation, then the guarded version after Claude reported the error with data. Claude made the error, found it while applying the change and corrected the records.
Problems: A recommendation went to Lingga based on a prototype that did not match the proposed semantics. Future CHGs should be checked against a model of the exact proposed behavior before asking for approval.
Next: TASK-049, prepare the G4 block review sheets.

## 2026-11-20: Lingga + Claude (TASK-049)
Did: Read all seven block records against CHG-005 to CHG-013 and fixed stale text: BLK-CORE (run status, ISA and encoding sentences, re-fetch option, paragraph order), BLK-CAPTURE (CHG-013 interface fields, edge timeout wording, options text), BLK-TIMER (24-bit width settled) and BLK-DRIVE (options text). At Lingga's request, drew one internal diagram per block in the ARCH-B style. Lingga pointed Claude to the OpenCode drawio skill: Claude followed its hardware-architecture house style and preset, generated the `.drawio` files with `scripts/block_diagrams.py`, checked them with the skill's `validate.py`, inspected draft PNG exports, and exported SVGs through the Windows draw.io install. Wrote the G4 block review sheets and added TASK-050 and TASK-051.
Results: Seven `blk-*_v1` diagram pairs (SVG 20–49 KB, vector text only); after two layout passes no edge crosses another or passes through a block except the expected enclosure warnings. Every block has a unit test; the G4 gate's only open points are the seven block agreements. Traceability reported 0 errors and the 2 accepted warnings. No model code, production RTL or registered tests changed.
AI vs human: Lingga asked for the review and for diagrams if the implementations were fixed, and redirected Claude to the drawio skill. Claude judged all seven structures fixed enough to draw, marking the core's pipeline as subject to the timing check, and recommends agreeing all seven blocks. Lingga has not agreed any block yet.
Problems: The first diagram pass had edges through blocks, crossings and labels on the enclosure; a second layout pass fixed them. The review sheet's first headings duplicated block IDs and broke the trace check; they were renamed.
Next: TASK-050, Lingga reviews and agrees the blocks; TASK-051, full-core timing probe.

## 2026-11-22: Lingga + OpenCode (TASK-052)
Did: Added the G2 spec links to the ISA draft and distinguished required behavior from draft instruction choices. Made one editable draw.io book with a chip sequence and seven linked block sequences. Exported SVG views and linked them from the block records, G4 review sheets and micro-architecture index.
Results: All eight diagrams passed structural validation with no warnings. Checked draft renders, all eight SVG exports, 69 Markdown links and 36 internal page targets. No RTL, model, block contract or approval status changed.
AI vs human: Lingga approved the documentation work and asked for chip and block levels. OpenCode chose how to split the sequence views and wrote the ISA traceability table. Lingga has not agreed the blocks.
Problems: The first layout triggered false overlap warnings where phase bands crossed lifelines. A separate annotation layer removed those warnings. Shortened a note that ran past its band.
Next: TASK-050, Lingga reviews and agrees the blocks; TASK-051, full-core timing probe.

## 2026-11-22: Lingga + OpenCode (TASK-050)
Did: Recorded Lingga's approval of all seven block contracts.
Results: The seven block records are agreed. The ISA encoding and the formal G4 gate remain open.
AI vs human: Lingga approved TASK-050 and asked OpenCode to run TASK-051. OpenCode updated the records without changing behavior or marking G4 passed.
Problems: The full-core timing and area check is still outstanding.
Next: Run TASK-051 and present the G4 gate check for approval.

## 2026-11-22: Lingga + OpenCode (TASK-051, EVAL-018 exploration)
Did: Built a full-core placement probe in `models/physical/` with the loadable store, both contexts, real register file, saved-request retry, guarded capture and timed pad drive. Ran Icarus, Yosys and OpenROAD. No production RTL or agreed contract changed.
Results: The placed probe used about 0.381 mm². At 60 MHz, slow setup missed by 10.226 ns overall and 8.939 ns internally. Fast hold missed by 0.198 ns overall and 0.055 ns internally. The directed probe simulation and all 89 Python model checks passed. Registered project tests did not run.
AI vs human: Lingga requested the probe. OpenCode built it and recommends isolating retry selection from validation and commit before considering more stages. Lingga has not approved a follow-up or passed G4 formally.
Problems: The full issue and retry paths missed setup although the earlier pad slice met it. The probe excludes the host and has no CTS or routing. Python test discovery by folder failed because the tests use relative imports; loading the fully qualified test modules passed.
Next: Ask Lingga for formal G4 approval and whether to run the follow-up probe. Do not freeze the core pipeline on this result.

## 2026-11-22: Lingga + OpenCode (G4 approval)
Did: Recorded Lingga's approval of G4 and moved the project to G5.
Results: The G4 checker reported MET, zero errors and the two accepted historical warnings. The gate records the block contracts, not physical timing or an ISA freeze.
AI vs human: Lingga approved G4 and authorized the timing follow-up. OpenCode recorded the approval and did not change the block contracts.
Problems: EVAL-018 did not meet 60 MHz.
Next: Run the exploratory follow-up without changing production RTL.

## 2026-11-22: Lingga + OpenCode (TASK-053, EVAL-019 exploration)
Did: Compared a rerun control, a split saved-request validator and a split validator with carry-save deadline sums. Kept the issue schedule and production RTL unchanged.
Results: The best variant improved slow internal setup slack from −7.445 ns to −5.265 ns and added 5,369 µm² of placed cells. It still missed 60 MHz. All variants passed the Icarus checks with identical 228-sample traces; all 89 existing Python benchmark checks passed. No registered project tests ran.
AI vs human: Lingga authorized the follow-up. OpenCode implemented and measured the probes. Lingga has not chosen a pipeline or approved a staged probe.
Problems: The cycle-to-register-file path still dominates slow setup. Fast hold still fails between the pin synchronizer stages. The first parameterized placement run failed because Yosys renamed the top; giving the parameterized top its original name fixed it.
Next: Ask whether to try a registered select/commit boundary. Replay the timing-sensitive workloads if issue latency changes.

## 2026-11-22: Lingga + OpenCode (TASK-054, EVAL-020 exploration)
Did: Placed three issue variants and replayed Fast-mode I2C and concurrent UART RX/SPI on each probe RTL. Compared pin activity and payload against the existing independent monitors.
Results: Registered retry selection passed 124/124 cases and had +9.615 ns slow setup slack from saved request to queue, but missed internal setup by 1.499 ns overall. Adding a stage to each fresh instruction met internal setup by 0.302 ns. It passed 20/124 replay cases: eight contended I2C cases faulted and 96 UART/SPI cases missed only the expected chip-select schedule. Directed smoke checks and all 89 Python benchmark tests passed. No registered project tests ran.
AI vs human: Lingga approved the experiment. OpenCode built and measured the probes and recommends keeping the retry boundary as a candidate, not adopting the global extra stage. No production RTL or agreed contract changed.
Problems: The first replay harness discarded pin bits because it reused an iterator for membership tests. Materializing the pin set fixed it before the archived runs. Fast internal hold and overall setup still fail on both staged variants.
Next: Ask whether to narrow the fresh instruction-to-writeback path while keeping the tested retry boundary. Replay the timed workloads before selecting any new schedule.
