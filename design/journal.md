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
