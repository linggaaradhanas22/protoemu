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

### TEST-SYS-004 — UART TX framing and bit periods
- Status: planned
- Level: system
- Verifies: SPEC-UART-001
Load the UART TX example and send consecutive `0x55` bytes at each listed rate. Measure the bit periods between transitions, including the stop-to-start transition.
Send `0x80` and `0x01` to check bit order. Pass if an independent UART monitor decodes the expected bytes and all measured periods meet the tolerance.

### TEST-SYS-005 — UART RX baud mismatch and start phase
- Status: planned
- Level: system
- Verifies: SPEC-UART-002
At each listed rate, use an independent UART source to send `0x00`, `0xFF`, `0x55`, `0xAA`, `0x80`, and `0x01` without extra idle bits.
Sweep peer baud error from −2% to +2% in 0.5 percentage point steps. Sweep the initial start edge in steps of one sixteenth of a `clk` period, including just before and after a clock edge.
Pass if the receive output contains exactly the expected sequence for every case.

### TEST-SYS-006 — SPI mode and rate matrix
- Status: planned
- Level: system
- Verifies: SPEC-SPI-001
Run each of the four modes at both rates with an independent target model. Send two bytes in each direction under one chip-select assertion. Use different asymmetric data in the two directions.
Pass if both directions receive the expected bytes and the pin trace meets the idle polarity, sample edge, clock timing, and chip-select criteria.

### TEST-SYS-007 — I2C timing and open-drain drive
- Status: planned
- Level: system
- Verifies: SPEC-I2C-001
Connect an I2C target model and resolve SDA and SCL with ideal pull-ups. Run unstretched traffic in both modes.
Include consecutive transactions and a repeated START. Measure every applicable interval in the timing table at the resolved signals.
Pass if all measured intervals meet the limits and the chip never drives either line high.

### TEST-SYS-008 — I2C read/write and ACK handling
- Status: planned
- Level: system
- Verifies: SPEC-I2C-002
At both rates, run a multibyte write, a multibyte read, and a write followed by a repeated-START read. Inject an address NACK and a nonfinal write-byte NACK in separate trials.
Pass if successful transfers match the expected data and START/STOP sequence. Check that the controller ACKs each nonfinal read byte and NACKs the last one.
In each injected NACK trial, require STOP and a reported failure before the controller sends any further byte.

### TEST-SYS-009 — I2C clock stretch
- Status: planned
- Level: system
- Verifies: SPEC-I2C-003
At both rates, have the target stretch SCL during a data bit and an ACK bit. Repeat with 1 µs, 5 µs, and 10 µs holds after controller release.
Pass if the controller waits for each delayed SCL rising edge, preserves the required high time, and finishes with the expected data and ACK sequence.

### TEST-SYS-010 — RP2350 load, start, and reload
- Status: planned
- Level: system
- Verifies: SPEC-HOST-001
- Run: test_host_load_start_reload
Drive the documented RP2350 loader transactions at a 60 MHz chip clock. For each baseline image, measure from its first load transfer to the successful load indication. Start the image and check for its expected result.
In a separate trial, send only part of an image and stop before completion. Check that the host observes no successful load indication and that the image does not execute. Reset and load a full image.
Repeat the full load and start after a cold restart that models deselection and reselection. Use two images with different pin behavior to check that the second run uses the new image.
Pass if each full load reports success within 1 s, starts on request, and runs the expected image without relying on prior state.

### TEST-SYS-011 — Toolchain clean build and load
- Status: planned
- Level: system
- Verifies: SPEC-PROG-001
- Run: test_baseline_examples_from_source
Use the documented tool versions and commands in a clean checkout. Remove any generated images before the build. Build every baseline example and load each result through the simulated host interface without preloading chip memory.
Pass if the commands produce all expected images and those images pass the applicable UART, SPI, and I2C baseline tests.

### TEST-SYS-012 — Post-freeze protocol on unchanged RTL
- Status: planned
- Level: system
- Verifies: SPEC-PROG-002
- Run: test_post_freeze_protocol
Record the frozen RTL revision and compare the chosen transaction against the documented pin, electrical, timing, and program resource limits. Record the expected payload, pin sequence, and timing tolerances before authoring the program.
Build and load the program through the released tools. Run it on the frozen revision against an independent peer model or pin-trace checker.
Pass if the payload and pin timing match and the hardware and programming model remain unchanged. Check that the emulator handles protocol timing and decisions without host assistance during the transaction.

### TEST-SYS-013 — Non-target program benchmarks
- Status: planned
- Level: system
- Verifies: SPEC-PROG-003
- Run: test_non_target_benchmarks
Run the WS2812, 1-Wire, and RC5 benchmarks at 60 MHz on the same RTL revision. Load each program through the documented host interface. Use the TASK-009 profiles as the source for stimulus and limits.
Pass if independent fixtures check the two RGB values and latch interval, the 1-Wire presence and full ROM value, and the RC5 address, command, and toggle for both frames. All three benchmarks must meet their timing limits.

## Integration tests

## Unit tests
