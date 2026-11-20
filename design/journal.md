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
