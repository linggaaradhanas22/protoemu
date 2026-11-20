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
- Works on: ARCH-A, ARCH-B, ARCH-C, EVAL-001, EVAL-002
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
