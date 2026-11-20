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
- Status: todo
- Owner: Lingga
- Works on: CHG-006, EVAL-010
- Blocked by: TASK-035
Done when: Lingga approves the proposed behavior for the draft ISA or records what to revise.
