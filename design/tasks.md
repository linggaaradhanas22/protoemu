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
- Status: todo
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
- Status: todo
- Owner: agent
- Works on: REQ-RULE-008
- Blocked by: TASK-003
Done when: `bash scripts/harden.sh --setup` hardens the unchanged template, `gl_sim.sh` passes,
and the runtime + any problems are noted in the journal. (Ask Lingga before installing Docker.)

## Stage G2 — Specification (start after G1)

### TASK-005 — Spec for rules and constraints
- Status: todo
- Owner: agent
- Works on: REQ-RULE-002, REQ-RULE-003, REQ-RULE-004, REQ-RULE-005, REQ-RULE-006, REQ-RULE-007
- Blocked by: G1
Done when: each agreed REQ-RULE item has SPEC(s) or an acceptance TEST; all drafts proposed to Lingga.

### TASK-006 — Spec for UART, SPI and I2C
- Status: todo
- Owner: agent
- Works on: REQ-PROTO-001, REQ-PROTO-002, REQ-PROTO-003
- Blocked by: G1
Done when: measurable SPECs exist for baud rates/accuracy, SPI modes/clock rates, I2C speeds,
clock stretching and ACK handling, each with a planned system TEST.

### TASK-007 — Spec for programmability and host interface
- Status: todo
- Owner: agent
- Works on: REQ-FLEX-001, REQ-FLEX-002, REQ-FLEX-003, REQ-RULE-006
- Blocked by: G1
Done when: SPECs say how "unplanned protocol" support is judged (benchmark list), what the
toolchain must provide, and how programs are loaded/reloaded; each has a planned TEST.

### TASK-008 — Acceptance tests and verification plan
- Status: todo
- Owner: agent
- Works on: REQ-DEL-001, REQ-DEL-002, REQ-DEL-003, REQ-DEL-004, REQ-DEL-005
- Blocked by: G1
Done when: every agreed REQ without a SPEC has an acceptance TEST, and `06_verif_plan.md`
lists methods per level.

### TASK-009 — Benchmark suite for architecture evaluation
- Status: todo
- Owner: agent
- Works on: REQ-FLEX-001, REQ-GOAL-001
- Blocked by: G1
Done when: `models/benchmarks/` lists each benchmark protocol (targets + non-targets) with its
timing numbers at 60 MHz, ready for stage G3 EVALs.
