# 02 — Specification

Requirements turned into **exact, testable statements**. Stage G2.

**How to write a SPEC**
- One measurable statement per item, using "shall" and numbers with units
  (e.g. "within ±1.0 %", "at 100 kHz and 400 kHz", "≤ 2 clock cycles").
- `- Traces to:` at least one REQ.
- Say how it will be checked (simulation, formal, measurement, review) in the text.
- Every SPEC needs at least one TEST in `06_verif_plan.md` that verifies it (checked at gate G2).
- A SPEC describes behaviour seen from outside the chip (pins, host, timing), not the design.
  Design choices come later (ARCH/DEC/BLK).

Example (inside a code fence, so the checker ignores it):

```markdown
### SPEC-UART-001 — UART TX bit timing
- Status: draft
- Traces to: REQ-PROTO-001, REQ-RULE-004
The TX bit period shall be within ±1.0 % of nominal for 9600, 19200, 38400, 57600 and 115200
baud with a 60 MHz clock. Checked by system simulation: measure edge times on the TX pin.
```

---

## Pins and electrical
<!-- SPEC-PIN-NNN -->

## Clock, reset and power-down
<!-- SPEC-RST-NNN -->

### SPEC-RST-001 — Reset convergence
- Status: draft
- Traces to: REQ-RULE-005
With a 60 MHz clock, the chip shall reach a deterministic reset state by the fourth rising edge of `clk` with `rst_n` held low.
The state before reset shall not affect pin behavior or host responses after reset under the same inputs.
Check reset convergence in system simulation and prove independence from initial state with formal analysis.

### SPEC-RST-002 — Reload after reselection
- Status: draft
- Traces to: REQ-RULE-006
After reselection, the chip shall accept and run a new program through the documented host loader without relying on any state from before deselection.
Check in system simulation at 60 MHz. Model the loss of state by starting a fresh DUT before the second load.
The host transfer format and timing limits belong to TASK-007.

## Host interface and program loading
<!-- SPEC-HOST-NNN -->

## Programmability
<!-- SPEC-PROG-NNN -->

## Protocols
<!-- SPEC-UART-NNN, SPEC-SPI-NNN, SPEC-I2C-NNN, ... -->

## Area and timing
<!-- SPEC-PHY-NNN -->

### SPEC-PHY-001 — Timing at 60 MHz
- Status: draft
- Traces to: REQ-RULE-004
At the board clock of 60 MHz, the routed design shall meet setup and hold timing at every corner required by the shuttle flow.
Check `project.clock_hz` in `info.yaml` and run static timing analysis on the routed design.
The `clk` constraint shall use a period no longer than 50/3 ns.

## Deliverables
<!-- SPEC-DEL-NNN -->
