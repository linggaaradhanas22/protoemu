# Tasks

Units of work. Agents pick the first `todo` task of the current stage that is not blocked, set it
to `doing`, and to `done` when finished (or `blocked` with the reason).
Add new tasks at the bottom with the next free number. Keep tasks small (one session each).

Format:

```markdown
### TASK-NNN — <title>
- Status: todo
- Owner: agent | Lingga
- Works on: <IDs>
- Blocked by: <TASK IDs or gate>
Done when: <clear finish condition>
```

---

## Stage G1 — Requirements

### TASK-001 — Review and agree requirements
- Status: done
- Owner: Lingga
- Works on: REQ-RULE-001, REQ-FLEX-001, REQ-PROTO-001, REQ-DEL-001, REQ-GOAL-001
Done when: every REQ in `01_requirements.md` is `agreed` or `rejected` (decide the REQ-GOAL
proposals and stretch-protocol priorities), `check_trace.py --gate G1` says MET, tag `g1-req`.

### TASK-002 — Set up the WSL tool environment
- Status: done
- Owner: Lingga
- Works on: REQ-RULE-001
Done when: `bash scripts/check_env.sh` shows OK for every tool except possibly librelane
(installed later by `harden.sh --setup`).

### TASK-003 — Prove the simulation flow
- Status: done
- Owner: agent
- Works on: REQ-RULE-001
- Blocked by: TASK-002 (simulation prerequisites only)
Done when: `bash scripts/sim.sh` runs the template's example test and it passes; result noted
in the journal.

### TASK-004 — Prove the hardening flow
- Status: done
- Owner: agent
- Works on: REQ-RULE-008
- Blocked by: TASK-003
Result: hardening and gate-level simulation passed. See the [smoke-test report](../reports/harden/20261120_1602/README.md) for the steps used to resume the setup wrapper in the WSL copy.
Done when: the local flow started by `bash scripts/harden.sh --setup` hardens the stock RTL, `gl_sim.sh` passes on the resulting netlist, and the journal records the runtime and any workarounds. (Ask Lingga before installing Docker.)

## Stage G2 — Specification (start after G1)

### TASK-005 — Spec for rules and constraints
- Status: done
- Owner: agent
- Works on: REQ-RULE-002, REQ-RULE-003, REQ-RULE-004, REQ-RULE-005, REQ-RULE-006, REQ-RULE-007
- Blocked by: G1
Done when: each agreed REQ-RULE item has SPEC(s) or an acceptance TEST; all drafts proposed to Lingga.

### TASK-006 — Spec for UART, SPI and I2C
- Status: done
- Owner: agent
- Works on: REQ-PROTO-001, REQ-PROTO-002, REQ-PROTO-003
- Blocked by: G1
Done when: measurable SPECs exist for baud rates/accuracy, SPI modes/clock rates, I2C speeds,
clock stretching and ACK handling, each with a planned system TEST.

### TASK-007 — Spec for programmability and host interface
- Status: done
- Owner: agent
- Works on: REQ-FLEX-001, REQ-FLEX-002, REQ-FLEX-003, REQ-RULE-006, REQ-GOAL-001
- Blocked by: G1
Done when: SPECs say how "unplanned protocol" support is judged (benchmark list), what the
toolchain must provide, and how programs are loaded/reloaded; each has a planned TEST.

### TASK-008 — Acceptance tests and verification plan
- Status: done
- Owner: agent
- Works on: REQ-PROTO-004, REQ-PROTO-005, REQ-DEL-001, REQ-DEL-002, REQ-DEL-003, REQ-DEL-004, REQ-DEL-005, REQ-GOAL-002, REQ-GOAL-005
- Blocked by: G1
Done when: each agreed Must or Should requirement without a SPEC has an acceptance TEST,
the remaining Could requirements have conditional checks, and `06_verif_plan.md` lists methods per level.

### TASK-009 — Benchmark suite for architecture evaluation
- Status: done
- Owner: agent
- Works on: REQ-FLEX-001, REQ-GOAL-001, REQ-PROTO-001, REQ-PROTO-002, REQ-PROTO-003, REQ-PROTO-004
- Blocked by: G1
Done when: `models/benchmarks/` lists each benchmark protocol (targets + non-targets) with its
timing numbers at 60 MHz, ready for stage G3 EVALs.

## Stage G3: Architecture

### TASK-010 — Draft architecture candidates and comparison plans
- Status: done
- Owner: agent
- Works on: EVAL-001, EVAL-002
Historical scope: drafted ARCH-A, ARCH-B, and ARCH-C before the selection.
Done when: three candidates cover all benchmark profiles and the evaluation plans define comparable evidence for protocol fit, physical risk and toolchain effort.

### TASK-011 — Build and run the shared protocol benchmark models
- Status: done
- Owner: agent
- Works on: EVAL-001
- Blocked by: TASK-010
Done when: each candidate has reproducible per-case results, starting with SPI, I2C stretching and concurrency. The exploratory models and traces are in EVAL-001; image and latency checks remain open.

### TASK-012 — Compare mapped area, timing risk and image tooling
- Status: done
- Owner: agent
- Works on: EVAL-002
- Blocked by: TASK-013
Done when: mapped size and timing evidence, input assumptions and image build steps are recorded for each viable design point.

### TASK-013 — Check encodings and rerun the critical protocol cases
- Status: done
- Owner: agent
- Works on: EVAL-001, EVAL-002
- Blocked by: TASK-011
Done when: candidate images for 1 MHz SPI, stretched Fast-mode I2C and UART/SPI overlap can be built, their sizes can be compared to the proposed stores, and the clock-level reruns account for fetch, branch and event latency. Record any candidate needing a revised design point.

### TASK-014 — Draft the architecture decision
- Status: done
- Owner: agent
- Works on: DEC-001
- Blocked by: TASK-012, TASK-013
Done when: the draft compares all three options using both evaluations, recommends an option, and records proposed weights and risks for Lingga to review.

### TASK-015 — Score the architecture decision
- Status: done
- Owner: agent
- Works on: DEC-001
- Blocked by: TASK-014
Done when: DEC-001 records Lingga's approved weights, the scores from both evaluations, and the six sensitivity tests. The architecture remains unselected until Lingga approves it.

### TASK-016 — Record the architecture selection
- Status: done
- Owner: agent
- Works on: DEC-001, ARCH-B
- Blocked by: TASK-015
Done when: Lingga's selection is recorded in DEC-001 and the architecture options, and the G3 checker is run before asking for sign-off.

### TASK-017 — Record G3 sign-off
- Status: done
- Owner: agent
- Works on: DEC-001, ARCH-B
- Blocked by: TASK-016
Done when: Lingga approves closing G3, the gate check reports MET, the sign-off commit is tagged `g3-arch`, and the status board moves to G4.

## Stage G4: Micro-architecture

### TASK-018 — Outline ARCH-B blocks and unit-test coverage
- Status: done
- Owner: agent
- Works on: ARCH-B, DEC-001
- Blocked by: G3
Done when: draft block records define responsibilities and interface boundaries. Each block has a planned unit test. Record open decisions for the timed-I/O queue, capture ownership, timestamp wrap, shared issue path, loader, and pin allocation.

## Repository maintenance

### TASK-019 — Set up GitHub SSH in WSL
- Status: done
- Owner: agent
Done when: WSL Git can reach the repository over SSH and a dry-run push succeeds without a Windows credential helper.

## Stage G4: Evidence and review

### TASK-020 — Check timed-I/O and issue contracts against the critical profiles
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-TIMER, TEST-INT-001, EVAL-003
- Blocked by: TASK-018
Done when: a reproducible cycle-level replay reports issue wait, admission slack, slot use and wrap behavior, and supports a recommendation on queue, capture and issue rules.

### TASK-021 — Compare RP2350 transports and pin maps
- Status: done
- Owner: agent
- Works on: BLK-HOST, BLK-PADS, BLK-PROGRAM, TEST-INT-002, EVAL-004, DEC-002, CHG-001
- Blocked by: TASK-018
Done when: the transport comparison accounts for synchronized handshakes, image loading within the specified limit, concurrent pin use, host payload buffering, and stop/reload timing.

### TASK-022 — Distinguish data and control in the ARCH-B diagram
- Status: done
- Owner: agent
- Works on: ARCH-B
Done when: the editable diagram and SVG distinguish solid data from dashed control, and the project records that convention for future revisions.

### TASK-023 — Review the loader transport proposal
- Status: done
- Owner: Lingga
- Works on: DEC-002, CHG-001
- Blocked by: TASK-021
Done when: Lingga approves the SPI proposal or records which option or interfaces to revise.

### TASK-024 — Specify loader recovery
- Status: done
- Owner: agent
- Works on: CHG-002, BLK-HOST, BLK-PADS, TEST-UNIT-007, TEST-INT-002, TEST-SYS-010
- Blocked by: TASK-023
Done when: the draft defines host timeouts and safe recovery from interrupted requests, interrupted or corrupted replies, and reset. The proposed checks cover these cases without assuming the host can safely repeat a command with side effects.

### TASK-025 — Review SPI loader recovery
- Status: done
- Owner: Lingga
- Works on: CHG-002
- Blocked by: TASK-024
Done when: Lingga approves the recovery proposal or records what to revise.

### TASK-026 — Compare ISA timestamp representations
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-TIMER, TEST-UNIT-001, TEST-INT-001, EVAL-005, DEC-003, CHG-003
- Blocked by: TASK-025
Done when: a reproducible exploration compares paired 16-bit registers with a dedicated timestamp operand. Check 24-bit wrap and report instruction count and timing impact for scheduling from an input capture.

### TASK-027 — Review the captured timestamp proposal
- Status: done
- Owner: Lingga
- Works on: DEC-003, CHG-003
- Blocked by: TASK-026
Done when: Lingga approves the proposed timestamp operand or records which option or behavior to revise.

### TASK-028 — Prototype timestamp instruction encoding
- Status: done
- Owner: agent
- Works on: DEC-003, BLK-CORE, BLK-PROGRAM, TEST-INT-001, EVAL-006
- Blocked by: TASK-027
Done when: a draft 24-bit encoding covers capture saves and timed operations, including a plan for offsets that do not fit one instruction. Re-encode and replay stretched I2C and concurrent UART/SPI programs. Report program size and deadline slack without changing RTL.

### TASK-029 — Compare timed drive encodings for eight pads
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-PADS, EVAL-006, EVAL-007, TEST-INT-001
- Blocked by: TASK-028
Done when: compare encodings that can address all eight pads and control output enable. Check instruction count and deadline slack for the critical programs, and identify the operations that need a 60 MHz timing probe before ISA sign-off.

### TASK-030 — Probe eight-pad issue and retirement timing
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-PADS, SPEC-PHY-001, EVAL-007, EVAL-008
- Blocked by: TASK-029
Done when: an exploratory physical model compares the compact and vector issue paths and measures the deadline/admission and due-to-pad paths at 60 MHz. Report timing and area limits before proposing final opcodes. Do not change production RTL.

### TASK-031 — Draft the ISA and block review package
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-TIMER, BLK-PROGRAM, BLK-HOST, BLK-PADS, EVAL-007, EVAL-008, DEC-004, CHG-004
- Blocked by: TASK-030
Done when: present the proposed instruction formats and block contracts for review. Record outstanding encoding, execution and timing risks. Do not change the approval status of any block.

### TASK-032 — Review the timed pad formats
- Status: done
- Owner: Lingga
- Works on: DEC-004, CHG-004
- Blocked by: TASK-031
Done when: Lingga approves carrying both pad formats into the ISA draft or records what to revise. This is not G4 approval.

### TASK-033 — Prototype generic host payload instructions
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-HOST, TEST-UNIT-001, TEST-INT-001, EVAL-009, CHG-005
- Blocked by: TASK-032
Done when: propose context-local instructions for reading and writing payload. Replace fixture-specific reports in a replay of concurrent UART/SPI. Check that FIFO backpressure blocks only the requesting context and that each payload operation retires once.

### TASK-034 — Review the generic host payload operations
- Status: done
- Owner: Lingga
- Works on: CHG-005, EVAL-009
- Blocked by: TASK-033
Done when: Lingga approves the proposed draft operations or records what to revise.

### TASK-035 — Prototype edge capture and elapsed-time instructions
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-CAPTURE, BLK-TIMER, SPEC-PROG-003, TEST-UNIT-004, EVAL-010, CHG-006
- Blocked by: TASK-034
Done when: propose how a program captures rising and falling edges and measures intervals across timer wrap. Replay a non-target input workload such as RC5 and report timing and program size. Do not freeze opcodes or change production RTL.

### TASK-036 — Review the edge and elapsed-time operations
- Status: done
- Owner: Lingga
- Works on: CHG-006, EVAL-010
- Blocked by: TASK-035
Done when: Lingga approves the proposed behavior for the draft ISA or records what to revise.

### TASK-037 — Specify modular wait and fence behavior
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-CAPTURE, BLK-TIMER, TEST-UNIT-001, TEST-UNIT-004, EVAL-011, CHG-007
- Blocked by: TASK-036
Done when: propose how timed waits and fences handle already-reached targets, future targets and timer wrap. Check the boundaries in the model and keep final opcodes and production RTL unchanged.

### TASK-038 — Review the modular guard rule
- Status: done
- Owner: Lingga
- Works on: CHG-007, EVAL-011, BLK-CORE, BLK-CAPTURE, BLK-TIMER, TEST-UNIT-001, TEST-UNIT-004, TEST-UNIT-005
- Blocked by: TASK-037
Done when: Lingga approves the proposed fence and wait guard behavior for the draft ISA or records what to revise. After approval, apply CHG-007 to the block, test and ISA records.

### TASK-039 — Specify global fault, flush and pending-operation ordering
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-PADS, TEST-UNIT-001, TEST-UNIT-003, TEST-UNIT-004, EVAL-012, CHG-008
- Blocked by: TASK-038
Done when: propose what happens on the edge where one context faults, halts or is flushed while drives, captures, guards or payload transfers are pending. Settle the order against `safe` pad overrides. Check in the model that no operation commits twice or half-commits. Keep opcodes and production RTL unchanged.

### TASK-040 — Review the fault, stop and halt ordering
- Status: done
- Owner: Lingga
- Works on: CHG-008, EVAL-012, BLK-CORE, BLK-HOST, BLK-DRIVE, BLK-CAPTURE, BLK-PADS, TEST-UNIT-001, TEST-UNIT-003, TEST-UNIT-004, TEST-UNIT-006, TEST-UNIT-007, TEST-INT-002
- Blocked by: TASK-039
Done when: Lingga approves the proposed ordering and run states for the draft ISA, including the two listed choices, or records what to revise. After approval, apply CHG-008 to the block and test records.

### TASK-041 — Settle the two-word elapsed-time writeback
- Status: done
- Owner: agent
- Works on: BLK-CORE, TEST-UNIT-001, EVAL-013, CHG-009
- Blocked by: TASK-040
Done when: compare register-file write options for `edge_delta` (one write port over two retirement cycles against two write ports in one) by issue cost in the RC5 and overlap replays and by synthesized area. Propose one. Keep opcodes and production RTL unchanged.

### TASK-042 — Settle payload FIFO depth and same-edge host/core access
- Status: done
- Owner: agent
- Works on: BLK-HOST, BLK-CORE, TEST-UNIT-007, EVAL-014, CHG-010
- Blocked by: TASK-041
Done when: define what happens when the host and a context access the same payload FIFO on one edge, including full and empty boundaries. Size the FIFO depth from the baseline and non-target replays and from synthesized area. Propose one rule and depth. Keep opcodes and production RTL unchanged.

### TASK-043 — Replay all baseline and non-target programs on the draft ISA
- Status: done
- Owner: agent
- Works on: SPEC-PROG-001, SPEC-PROG-003, BLK-CORE, EVAL-016, CHG-012
- Blocked by: TASK-044
Done when: assemble UART TX/RX, every baseline SPI and I2C case and the non-target examples with only draft-ISA operations and host payload. Replay them under the CHG-007 and CHG-008 rules and report pass/fail, words and timing margins.

### TASK-044 — Review the payload FIFO rule and depth
- Status: done
- Owner: Lingga
- Works on: CHG-010, EVAL-014, CHG-011, DEC-005, BLK-HOST, BLK-CORE, BLK-PADS, TEST-UNIT-001, TEST-UNIT-007, TEST-SYS-005, TEST-SYS-010
- Blocked by: TASK-045
Done when: Lingga approves the same-edge rule and depth 8 for the draft, or records what to revise, and decides whether to pursue a faster loader or multi-word `READ`. After approval, apply CHG-010 to the block and test records.

### TASK-045 — Model faster loader clock and multi-word payload transfers
- Status: done
- Owner: agent
- Works on: BLK-HOST, SPEC-UART-001, SPEC-UART-002, EVAL-015
- Blocked by: TASK-042
Done when: sweep loader SCK rate, per-frame overhead, words per transaction and FIFO depth for UART receive and transmit bursts at 38,400 to 115,200 baud. Check which SCK rates the synchronizer timing model allows, and measure the area of multi-word FIFO support. Report data for Lingga's TASK-044 decision; change no agreed record.

### TASK-046 — Review the LSB-first shift option
- Status: done
- Owner: Lingga
- Works on: CHG-012, EVAL-016, BLK-CORE, TEST-UNIT-001
- Blocked by: TASK-043
Done when: Lingga approves the LSB-first `shift_pin` option or chooses documented host bit reversal. After approval, apply CHG-012 to the ISA draft, BLK-CORE and TEST-UNIT-001.

### TASK-047 — Evaluate a timeout for input waits (I2C clock stretching)
- Status: done
- Owner: agent
- Works on: EVAL-017, SPEC-I2C-003, BLK-CORE, BLK-CAPTURE, CHG-013
- Blocked by: TASK-046
Done when: run the EVAL-017 plan: model software polling, a timed wait and a per-context watchdog against all I2C cases plus stuck-SCL cases, with area for the hardware options. Recommend one option to Lingga; change no agreed record.

### TASK-048 — Review the timed wait
- Status: done
- Owner: Lingga
- Works on: CHG-013, EVAL-017, BLK-CORE, BLK-CAPTURE, TEST-UNIT-001, TEST-UNIT-004, TEST-SYS-009
- Blocked by: TASK-047
Done when: Lingga approves `wait_to` (C2) or keeps host `STOP` as the only recovery. After approval, apply CHG-013 to the ISA draft, BLK-CORE, BLK-CAPTURE and the tests.

### TASK-049 — Prepare the G4 block review
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-CAPTURE, BLK-DRIVE, BLK-HOST, BLK-PADS, BLK-PROGRAM, BLK-TIMER
- Blocked by: TASK-048
Done when: for each block, check that its record is consistent after CHG-005 to CHG-013, lists its interface, behavior and open items, and has at least one unit TEST that covers it. Produce a short review sheet per block for Lingga (g4-review step 2). Change no agreed record.

### TASK-050 — Review and agree the seven blocks
- Status: done
- Owner: Lingga
- Works on: BLK-CORE, BLK-CAPTURE, BLK-DRIVE, BLK-HOST, BLK-PADS, BLK-PROGRAM, BLK-TIMER
- Blocked by: TASK-049
Done when: Lingga has read the [block review sheets](05_microarch/g4-block-review.md) and agreed each block or recorded what to change. When all seven are agreed, run the G4 gate check and ask Lingga to pass G4.

Lingga approved all seven block contracts on 2026-11-22. This did not approve the G4 gate or freeze the ISA encoding.

### TASK-051 — Full-core timing probe
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-PROGRAM, BLK-DRIVE, BLK-CAPTURE
- Blocked by: TASK-049
Done when: synthesize and place a probe of the core with the saved-request path, the real register file and the timed-I/O interfaces, and report setup, hold and area against 60 MHz (g4-review step 3). Tracked separately from G4 agreement.

[EVAL-018](evals/EVAL-018-full-core-timing.md) records the completed probe. The measured baseline misses 60 MHz; no design change was applied.

### TASK-053 — Compare a split issue path at 60 MHz
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, SPEC-PHY-001
- Blocked by: TASK-051
Done when: compare the baseline and a version that moves validation ahead of saved-request selection without adding an issue cycle. Measure setup, hold and area with the same flow, and check that retry, capture and fault ordering still work. Do not adopt a pipeline change or modify production RTL.

[EVAL-019](evals/EVAL-019-split-issue-timing.md) records the comparison. Both variants improved worst slow setup but failed 60 MHz. No production implementation was selected.

### TASK-054 — Test registered issue boundaries
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, SPEC-PHY-001, SPEC-I2C-003
- Blocked by: TASK-053
Done when: place staged probes at 60 MHz, check safe-edge and deadline behavior, and replay timing-sensitive Fast-mode I2C and concurrent UART/SPI on the staged RTL. Keep production RTL and agreed contracts unchanged.

[EVAL-020](evals/EVAL-020-staged-issue-timing.md) records the comparison. The retry-only variant passed 124/124 replay cases but missed setup. The deeper variant passed internal setup but failed contended I2C and shifted the UART/SPI fixture's chip-select schedule. No production pipeline was selected.

### TASK-055 — Shorten fresh writeback without adding issue cycles
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-PROGRAM, BLK-DRIVE, BLK-PADS, SPEC-PHY-001
- Blocked by: TASK-054
Done when: measure changes to the fresh instruction path against the retry-only control, replay the protocol cases on the leading candidate, and test clock-tree synthesis and hold repair on that candidate. Record limits without changing production RTL or contracts.

[EVAL-021](evals/EVAL-021-fresh-writeback-timing.md) records both candidates. Separate writeback passed 124/124 replay cases and met internal setup and hold after physical repair. Overall hold and routed timing remain open. No production implementation was selected.

### TASK-056 — Measure expired-retry fault ordering
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-PADS, SPEC-PHY-001
- Blocked by: TASK-055
Done when: compare the current fault schedules and an immediate-expiry variant at a free issue boundary. Test pin effects, arbitration and timing. Record evidence and remaining G4 decisions without changing an agreed contract.

[EVAL-022](evals/EVAL-022-expired-retry.md) records the timing, protocol replays and directed cases. [CHG-014](changes/CHG-014-expired-retry-selection.md) is proposed only. Both registered variants lose the final legal admission edge in one directed case.

### TASK-052 — Document ISA traceability and system sequences
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-PROGRAM, BLK-DRIVE, BLK-CAPTURE, BLK-TIMER, BLK-PADS, BLK-HOST
Done when: the ISA draft links its programming model to the relevant G2 specs, and an editable chip-level sequence links to one detailed sequence per block. Cross-link the existing block records and structural diagrams. Do not change any behavior or approval status.

### TASK-057 — Gather evidence for the reopened G4 decisions
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-HOST, SPEC-PHY-001
- Blocked by: TASK-056
Done when: compare retry policies that preserve the last legal edge, compare guarded timeout storage, and check the candidate ISA and host encodings against their models. Record recommendations and limits without adopting changes.

[EVAL-023](evals/EVAL-023-retry-and-timeout-alternatives.md) and [EVAL-024](evals/EVAL-024-encoding-check.md) record the evidence. [CHG-014](changes/CHG-014-expired-retry-selection.md) is rejected in favour of the existing same-cycle retry schedule.

### TASK-058 — Record the G4 decision approvals
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-HOST
- Blocked by: TASK-057
Done when: the four decision records carry Lingga's approval and the trace checker reports no new error.

Lingga approved all four [G4 decision recommendations](05_microarch/g4-decision-review.md) on 2026-11-22. CHG-014 is rejected. No block contract changed.

### TASK-059 — Place the agreed schedule with and without a host boundary
- Status: done
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-PADS, SPEC-PHY-001
- Blocked by: TASK-058
Done when: place the same-cycle retry with the separate writeback, run clock-tree synthesis and repair, and repeat with registered host configuration. Report setup, hold and area, and keep production RTL unchanged.

[EVAL-025](evals/EVAL-025-agreed-schedule-timing.md) records the runs. After repair the agreed schedule is within 23 to 37 ps of 60 MHz setup and passes hold. That is not closure margin.

### TASK-060 — Implement the timebase and program store
- Status: done
- Owner: agent
- Works on: BLK-TIMER, BLK-PROGRAM
- Blocked by: none
Done when: `src/cycle_timer.v` and `src/program_store.v` implement the agreed blocks, lint clean, and their cocotb tests (TEST-UNIT-005, TEST-UNIT-002) pass. Record the TEST status only after the test ran.

Both modules passed Verilator lint. `bash scripts/sim.sh` passed both unit tests and the template smoke test. The unit tests instantiate the blocks directly, without the host, core, or chip wrapper.

### TASK-061 — Shorten the core run-control cloud
- Status: todo
- Owner: agent
- Works on: BLK-CORE, BLK-DRIVE, BLK-PADS
- Blocked by: none
Done when: propose and measure a partitioning of the `started`, `active`, `done` and payload-eligibility logic that keeps the agreed host-visible timing. Record the result in an EVAL and apply it only in the BLK-CORE RTL. Any change that moves a host-visible edge needs a CHG first.

### TASK-062 — Draft the external pin specification
- Status: done
- Owner: agent
- Works on: BLK-PADS, REQ-RULE-003, REQ-RULE-007
- Blocked by: none
Done when: record the proposed pin specs and system test in a CHG for Lingga's review. Leave the agreed specs and RTL unchanged.

[CHG-015](changes/CHG-015-pin-specification.md) records the draft. TASK-063 applies the approved change.

### TASK-063 — Add the approved pin specs to the baseline
- Status: done
- Owner: agent
- Works on: CHG-015, SPEC-PIN-001, SPEC-PIN-002, SPEC-PIN-003, BLK-PADS, TEST-SYS-014, TEST-INT-001, TEST-INT-002, TEST-UNIT-006
- Blocked by: none
Done when: add the approved specs and planned system test, recheck the pad contract and dependent test plans, and regenerate the trace. No RTL changes.

### TASK-064 — Match the top-level diagram to the block records
- Status: done
- Owner: agent
- Works on: ARCH-B, BLK-CORE, BLK-PROGRAM, BLK-DRIVE, BLK-CAPTURE, BLK-TIMER, BLK-PADS, BLK-HOST
- Blocked by: none
Done when: label each block with its record ID and exact title. Publish a new editable diagram and SVG, and update the overview links. Keep the architecture and earlier diagrams unchanged.

Published [revision 3](05_microarch/diagrams/arch-b_v3.svg) and its [editable source](05_microarch/diagrams/arch-b_v3.drawio). All seven labels match their block records. The diagram geometry and wiring are unchanged.
