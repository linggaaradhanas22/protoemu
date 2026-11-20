# 06 — Verification plan

How each level of the V is checked. TEST items live in this file.

## Levels

| V-level (left) | Test level (right) | Test ID | Typical tools |
|---|---|---|---|
| REQ | acceptance | `TEST-ACC-NNN` | precheck result, review of docs, end-to-end demo, FPGA |
| SPEC | system | `TEST-SYS-NNN` | cocotb on the full chip, protocol models, reference model |
| ARCH / DEC | integration | `TEST-INT-NNN` | cocotb on groups of blocks, program-level tests |
| BLK | unit | `TEST-UNIT-NNN` | cocotb on one block, SymbiYosys formal |

## Methods we plan to use
- **Reference model comparison**: the chosen architecture's Python model and the RTL run the
  same program; pin activity must match cycle by cycle (see `models/README.md`).
- **Random programs**: random legal instruction streams compared against the reference model.
- **Protocol checks**: real UART/SPI/I2C/... programs against protocol models (bus-functional
  models in cocotb).
- **Formal** (SymbiYosys): FIFOs, counters, no unwanted `uio_oe`, deterministic timing.
- **Gate-level simulation**: the same tests on the hardened netlist (`scripts/gl_sim.sh`).
- **Coverage**: every instruction × condition × stall case; every pin-mapping corner.

## How to write a TEST
- `- Level:` unit / integration / system / acceptance.
- `- Verifies:` the SPEC, BLK, REQ, ARCH or DEC it checks.
- `- Run:` the cocotb test function name(s) once written (the checker matches these with
  `test/results.xml`).
- Status: `planned` → `written` → `passing` / `failing`. Only set `passing` after running it.
- Text: what is stimulated, what is checked, pass criterion.

Example:

```markdown
### TEST-SYS-000 — UART TX baud accuracy
- Status: planned
- Level: system
- Verifies: SPEC-UART-001
- Run: test_uart_tx_baud
Load the UART TX example program, send 0x55 at each listed baud rate, measure every TX edge.
Pass: all bit periods within ±1.0 %.
```

---

## Acceptance tests

### TEST-ACC-001 — IHP process and template
- Status: planned
- Level: acceptance
- Verifies: REQ-RULE-001
Check the template origin in the submission's history or provenance record.
Check the hardening report for the process used to produce the submitted GDS.
Pass if the submission starts from the Tiny Tapeout IHP Verilog template's `main` branch and uses `sg13cmos5l`.

### TEST-ACC-002 — Tiny Tapeout tile budget
- Status: planned
- Level: acceptance
- Verifies: REQ-RULE-002
Check `project.tiles` in `info.yaml` and compare the final GDS boundary with the flow's assigned slot.
Pass if the setting is `8x4` and the final layout, including any SRAM macros, fits that slot.
If the design uses SRAM macros, also check that the layout with the macros passes precheck.

### TEST-ACC-003 — Tiny Tapeout port interface
- Status: planned
- Level: acceptance
- Verifies: REQ-RULE-003
Compare the top-level RTL ports and documented pinout with the Tiny Tapeout template.
Pass if the project uses only the 8 dedicated inputs, 8 dedicated outputs, 8 bidirectional pads, `clk`, and `rst_n`.
At the RTL boundary, check the directions and widths of `ui_in`, `uo_out`, `uio_in`, `uio_out`, and `uio_oe`.
Check that `ena` is the standard wrapper input and that the project uses no analog pads.

### TEST-ACC-004 — Demo board I/O and Pmod parts
- Status: planned
- Level: acceptance
- Verifies: REQ-RULE-007
Compare each documented connection with the demo board schematic and the electrical limits of the connected parts.
Check the allowed voltages, logic levels, and drive direction for each connection.
Pass if each connection works with the board's 3.3 V I/O and the docs list all external parts and their Pmod connections.

### TEST-ACC-005 — GDS build and precheck
- Status: planned
- Level: acceptance
- Verifies: REQ-RULE-008
Run the Tiny Tapeout hardening flow from the submission commit. Run precheck on the resulting GDS.
Pass if the build produces the GDS without errors and all required precheck checks pass for that artifact.
Record the commit, flow version, and precheck report.

### TEST-ACC-006 — Public source release
- Status: planned
- Level: acceptance
- Verifies: REQ-RULE-009
Clone the submission commit without repository credentials. Check the files against the design file list and license notices.
Pass if anyone can retrieve all design files from the public repository under the documented open-source terms at submission.

### TEST-ACC-007 — Submission deadline
- Status: planned
- Level: acceptance
- Verifies: REQ-RULE-010
Check the organizer's submission confirmation for the complete entry.
Pass if the recorded submission time meets the organizer's cutoff for January 18, 2027.

## System tests

### TEST-SYS-001 — Routed timing at the board clock
- Status: planned
- Level: system
- Verifies: SPEC-PHY-001
Check that `project.clock_hz` is `60000000` and the timing constraint for `clk` is no longer than 50/3 ns.
Review the final setup and hold reports at each corner required by the shuttle flow.
Pass if all required corners have nonnegative setup and hold slack and no synchronous path lacks an intended timing constraint.

### TEST-SYS-002 — Reset from different prior states
- Status: planned
- Level: system
- Verifies: SPEC-RST-001
Run cold-start and warm-start cases at 60 MHz. Use two different legal programs to reach distinct states before warm reset.
Hold `rst_n` low for four rising edges. Apply the same pin inputs and host transactions to each case after release.
Pass if the output enables, driven pin values, and host responses are known and identical for the checked sequence.
For the formal check, start two copies from independent arbitrary states with the same inputs.
Check that their observable behavior matches after reset for every common legal input sequence.

### TEST-SYS-003 — Reload without retained state
- Status: planned
- Level: system
- Verifies: SPEC-RST-002
Load and run program A at 60 MHz. Check its expected pin output to confirm that A ran.
Start a fresh DUT to model power loss. Apply reset, then load and run program B through the documented host interface.
Pass if B loads without saved chip state and produces its expected pin output, which differs from A's.
Toggling `ena` alone does not model this test's power loss.

## Integration tests

## Unit tests
