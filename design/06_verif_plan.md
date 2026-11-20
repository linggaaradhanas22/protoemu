# 06 — Verification plan

How each level of the V is checked. TEST items live in this file.

## Levels

| V-level (left) | Test level (right) | Test ID | Typical tools |
|---|---|---|---|
| REQ | acceptance | `TEST-ACC-NNN` | Check the submission artifacts and demonstrate required behavior. Save review records, simulation results, or precheck reports. |
| SPEC | system | `TEST-SYS-NNN` | Run the full chip with a host and independent protocol models. Record decoded data and timing. Use static timing reports and formal proofs where specified. |
| ARCH / DEC | integration | `TEST-INT-NNN` | Use cocotb to check interactions between blocks during program load and execution. Compare observable behavior with the reference model. |
| BLK | unit | `TEST-UNIT-NNN` | Use cocotb and SymbiYosys to check block behavior, boundary cases, and invariants. |

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
- `- Run:` the cocotb test function name(s) for simulation (the checker matches these with
  `test/results.xml`). For a review or external tool, record the procedure and evidence in the item text.
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

### TEST-ACC-008 — Concurrent UART and SPI
- Status: planned
- Level: acceptance
- Verifies: REQ-PROTO-004
- Run: test_concurrent_uart_spi
On one loaded configuration at 60 MHz, receive consecutive UART frames at 115200 baud while the chip runs two-byte mode-0 SPI exchanges at 1 MHz. Use independent UART and SPI fixtures on distinct pins. Place at least two complete SPI exchanges within the UART stream, each overlapping a UART data-bit transition.
Pass if the UART receives the full byte sequence exactly once and in order, both SPI directions exchange the expected bytes, and the SPI timing and UART stimulus remain within their baseline limits. Do not pause a protocol or reload the chip to switch between them.

### TEST-ACC-009 — Controller and target roles
- Status: planned
- Level: acceptance
- Verifies: REQ-PROTO-005
- Run: test_spi_i2c_target_roles
Use the SPI and I2C baseline controller tests as evidence for the outgoing roles. In separate runs, use independent external controllers to exercise the chip as a target.
- SPI: Exchange two distinct bytes in each direction under one chip-select assertion. Use modes 0 through 3 at 100 kHz and 1 MHz. Check that the chip releases MISO when it is not selected.
- I2C: Use 100 and 400 kHz. Write and read multiple bytes at the chip's 7-bit address, including a repeated-START read. Check that the chip ACKs its address, ignores an unmatched address, and releases SDA after the controller NACKs the final read byte.

Pass if the baseline controller tests pass and the target cases match the expected data, timing, and bus ownership. UART transmit and receive are already covered by their system tests and do not have separate controller and target roles.

### TEST-ACC-010 — Submission repository contents
- Status: planned
- Level: acceptance
- Verifies: REQ-DEL-001
Check out the candidate submission commit. Resolve any versioned artifacts using the repository's documented retrieval steps.
Pass if the checkout contains the RTL and test sources, and the repository supplies the final Tiny Tapeout GDS and passing precheck report. Verify that the report refers to the delivered GDS using the artifact hash or recorded build ID. Reuse the build and precheck evidence from `TEST-ACC-005` when it matches the candidate.

### TEST-ACC-011 — Architecture and programming documentation
- Status: planned
- Level: acceptance
- Verifies: REQ-DEL-002
Compare the documentation with the release RTL and toolchain. Check the architecture overview, visible resources, instruction set or equivalent programming model, pin behavior, and loader interface.
Pass if a reviewer can follow the documented steps to build, load, and run a baseline example with the expected result without undocumented commands or settings.

### TEST-ACC-012 — Design and verification write-up
- Status: planned
- Level: acceptance
- Verifies: REQ-DEL-003
Review `WRITEUP.md` against the architecture decisions, verification plan, and reports. Check that it explains the design choices, how the checks were run, their results and limitations, and any new techniques or flows used.
Pass if the write-up covers those topics and each claimed verification result points to evidence for the stated revision.

### TEST-ACC-013 — AI use disclosure
- Status: planned
- Level: acceptance
- Verifies: REQ-DEL-004
Compare the AI use section in `WRITEUP.md` with the project journal. Ask Lingga to check the account of the work and decisions.
Pass if the section identifies the AI tools used, describes what they produced or checked, and distinguishes AI work from human decisions and review.

### TEST-ACC-014 — Final gate-level regression
- Status: planned
- Level: acceptance
- Verifies: REQ-DEL-005
Run `bash scripts/gl_sim.sh` with the final gate-level netlist from the submitted hardening run. Exercise host load and reload and the UART, SPI, and I2C baseline functional cases. Run the reset simulation without the formal proof. Use the same external fixtures and pass criteria as for the corresponding RTL simulations.
Pass if every required case runs and passes on the final netlist, with no skipped required case. Save the netlist identifier, command, log, and results. This check does not replace the routed static timing review in `TEST-SYS-001`.

### TEST-ACC-015 — Traceability audit
- Status: planned
- Level: acceptance
- Verifies: REQ-GOAL-002
Regenerate `design/trace.md` for the candidate submission. Compare the RTL files and runnable tests with the `BLK` and `TEST` records. Review the traceability explanation in `WRITEUP.md`.
Pass if every RTL block and each project test has a valid path to an agreed requirement, the checker finds no errors or suspect items, and the write-up shows a real trace from requirement to result.

### TEST-ACC-016 — RTL freeze date
- Status: planned
- Level: acceptance
- Verifies: REQ-GOAL-005
Check the dated freeze record for the final RTL revision and compare that revision's RTL with the submitted RTL. Use the freeze record date, not the date of an earlier test snapshot used for `SPEC-PROG-002`.
Pass if Lingga recorded the final RTL freeze no later than January 10, 2027, and the submission uses that RTL unchanged.

## Conditional acceptance checks for Could items

These checks apply only to features selected for submission. The G7 checker requires every registered acceptance test to pass, so add a numbered test when Lingga selects a feature and approves its scope. A deferred feature is not verified.

| Requirement | Acceptance check if selected |
|---|---|
| `REQ-PROTO-006` | Complete the agreed low-speed USB transaction with an independent peer. Match the expected packets and timing. Document which parts of line coding, CRC, and clock recovery run on-chip. |
| `REQ-PROTO-007` | Exchange the agreed 10BASE-T test frames with a reference peer through the documented Pmod. Check payload, frame integrity, and timing. |
| `REQ-PROTO-008` | Run the agreed transaction for each selected protocol from JTAG, SWD, PS/2, and CAN. Check both decoded data and pin timing against an independent peer or monitor. Record any options not selected. |
| `REQ-DEL-006` | Open the submitted demo video and check that it shows what runs on the chip or in simulation and labels the setup correctly. |
| `REQ-GOAL-003` | Build the release design for the selected FPGA and run the documented demo with real peripherals. Check expected input and output on the board. |
| `REQ-GOAL-004` | Use the documented host interface to inspect named state and issue one step in a known program. Check that the step advances the documented unit of execution and that the chip is paused again afterward. |

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
Drive the documented RP2350 SPI0 transactions at a 60 MHz chip clock. For each baseline image, measure from its first load transfer to the complete-image reply after `COMMIT`. Confirm that `READY` alone is not a complete-image indication. Issue a separate `START` and check the expected result.
In a separate trial, send only part of an image and stop before completion. Check that the host observes no successful load indication and that the image does not execute. Reset and load a full image.
Repeat the full load and start after a cold restart that models deselection and reselection. Use two images with different pin behavior to check that the second run uses the new image.
Pass if each full load reports success within 1 s, starts on request, and runs the expected image without relying on prior state.
Force the request-frame, reply-ready and reply-frame timeouts from BLK-HOST in separate runs. Check that the driver aborts without automatically replaying a command. Hold `READY` high through the reset recovery deadline and check that the driver reports recovery failure. With a qualified reset, check that a fresh load works and protocol traffic resumes only on an explicit `START`.

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
Run the WS2812, 1-Wire, and RC5 benchmarks at 60 MHz on the same RTL revision. Load each program through the documented host interface. Use the [TASK-009 benchmark profiles](../models/benchmarks/README.md) as the source for stimulus and limits.
Pass if independent fixtures check the two RGB values and latch interval, the 1-Wire presence and full ROM value, and the RC5 address, command, and toggle for both frames. All three benchmarks must meet their timing limits.
Use the same RC5 program at all benchmark rates. Repeat the frame pair with the counter wrapping between the calibration edges. Check that the program reports both frames exactly once and does not require host service during capture.

## Integration tests

### TEST-INT-001 — Shared issue under timed-I/O contention
- Status: planned
- Level: integration
- Verifies: ARCH-B, DEC-001, BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-PADS, BLK-TIMER
- Run: test_shared_issue_deadlines
Replay concurrent UART RX and 1 MHz SPI, and 10 µs stretched Fast-mode I2C, with the G4 issue and pad-observation timing. Sweep relative start phase and repeat near timestamp wrap. Force queue-full, same-cycle due events, and simultaneous captures in directed cases. Pass if independent monitors match payload and pin timing, every accepted nonflushed update hits its deadline exactly once, and neither context loses its capture. Record peak queue occupancy, longest runnable-to-issue wait, and minimum slack from acceptance to deadline. In an intentional overcommit case require a reported fault and no late pad update.
Use the BLK-PADS overlap pin map. Preload host payload, then run without host service during the transactions; check preserved result order for each context.
Load the SPI transmit words through host `WRITE`. The program must consume them with `host_get` and send its results with `host_put`. Drain the results with host `READ` after the run. Change a preloaded word in a directed trial and check that the SPI peer observes the new word on the pins.
Exercise capture-derived deadlines in the encoded programs near wrap. Check that an output delayed by queue pressure still targets the original observation time plus the programmed offset, or faults without a late drive.
Mix compact and vector instructions in one loaded image. Schedule a vector that drives some pads and releases others when only one queue slot is free. Check that it occupies one slot and all selected pads update together at its deadline.

### TEST-INT-002 — Load, run and stop across the pad boundary
- Status: planned
- Level: integration
- Verifies: ARCH-B, BLK-HOST, BLK-PROGRAM, BLK-PADS, BLK-CORE, BLK-DRIVE, BLK-CAPTURE
- Run: test_load_run_stop_boundary
Load a short program over the dedicated SPI pins, check the `READY`-gated reply, then start it. Stop with a pad update due on the edge after the validated `STOP` frame closes. Repeat around synchronized deselect, reset and core fault with a capture pending. Also try malformed and truncated reloads. Pass if partial images cannot fetch, accepted starts fetch only committed words, and safe/flush wins on each specified safe edge. A subsequent shorter image must not execute residual words or complete old operations.
Lose a valid `START` reply after execution and corrupt a valid payload-write reply in separate runs. Check that the host does not repeat either request. Assert recovery reset with a pad update due, check safe outputs and cleared work, then reload and start explicitly.
Save a timestamp before stopping. After reload, check that a timed instruction cannot use the old saved timestamp before a new capture has saved a time.
Repeat with `edge_delta` waiting on a transition. Stop and reload. Check that the pending capture does not retire and the old timestamp cannot be used.
Stop with a payload instruction blocked. Check that reload cannot complete the old transfer or expose stale FIFO words.

## Unit tests

### TEST-UNIT-001 — Shared issue and context isolation
- Status: planned
- Level: unit
- Verifies: BLK-CORE
- Run: test_issue_context_isolation
Stub the program and timed-I/O endpoints. Check issue slots with both contexts runnable, then block one context on drive credit, result availability and payload in separate runs. Pass if the other context issues at the next free selection boundary, context state stays isolated, and the blocked instruction retires once with its saved operands. A deadline that expires while blocked must fault even if credit never returns. Also check redirect cost and non-retirement on reject.
Save different observation times in the two contexts. Delay a consume, then check it saves the observation time, not the consume time. Check that a consume without a save preserves the saved time. Exercise carry across bit 15 and wrap across bit 23 in deadline arithmetic. After reset, start or global flush, an instruction that uses the invalid timestamp must fault without issuing a drive or sample.
Check mask, values and enables from each drive format. Include pad 7 in both shift positions and reject duplicate pins, an empty vector mask and nonzero reserved bits. Block a shift request, then accept it and check its register shifts once. In a separate trial, reject the retry and check the register stays unchanged.
Run `host_get` on empty ingress and `host_put` on full egress. Check that the other context can issue. Release each stall and check for one transfer without refetch. A blocked read must not change its destination. A blocked write must retain its source word.
Check `edge_delta` across wrap and with an interval greater than 65,535 cycles. Check both destination words, timestamp replacement and offset clear. Inject an invalid saved time or destination and confirm no arm request. Reject an out-of-range interval without a partial register write. Confirm that one context cannot replace the other's timestamp.

### TEST-UNIT-002 — Registered fetch and image bounds
- Status: planned
- Level: unit
- Verifies: BLK-PROGRAM
- Run: test_program_store_visibility
Write 1-word and 128-word images, read endpoints and reload a shorter image over a longer one. Present reads before commit and writes during run; perturb unwritten memory across resets. Pass if fetch latency is one registered slot, only committed in-range words become instructions, invalid running PCs return fault, and illegal writes cannot alter live code.
Include a CRC failure after tentative words reached the array. Keep `image_valid` low for that trial; no fetch may return those words.

### TEST-UNIT-003 — Exact due cycles and queue backpressure
- Status: planned
- Level: unit
- Verifies: BLK-DRIVE
- Run: test_timed_drive_queue
Fill all four slots. Enqueue out of deadline order, retire disjoint masks together, and accept into a slot on its retirement edge. Try an overlapping mask, an unowned pin, a zero deadline delta and an expired retry. Cross wrap and assert flush on a due edge. Pass if the scoreboard sees each accepted, nonflushed masked update once on its programmed edge, no rejected update reaches a pad, and merged value/OE fields match the masks.
With one slot free, admit a full-width mask and retire its mixed values and enables as one event. Repeat with one unowned bit and check that the whole request is rejected.

### TEST-UNIT-004 — Context capture ownership and observation edge
- Status: planned
- Level: unit
- Verifies: BLK-CAPTURE
- Run: test_capture_slot_ownership
Arm both contexts and arrange two results on one edge. Cover a transition on the arm edge, a subsequent edge, a level already present, a timed sample across wrap, stalled consumption and an attempted overwrite. Pass if captured values and pre-edge timestamps match the observation rule, only owners consume results, reads never bypass completion, and reset or flush discards all live slots.
Exercise falling, rising and either-edge arms. Hold a result across counter wrap before consuming it. The result must keep the original observation time, not the consume time.

### TEST-UNIT-005 — Timebase, half range and wrap
- Status: planned
- Level: unit
- Verifies: BLK-TIMER
- Run: test_cycle_timer_wrap
Start from reset, run a reduced-width instance through wrap, and exercise the shared deadline rule with deltas 0, 1, half-range minus one, half range and all ones. Pass if the counter advances exactly once per cycle regardless of run state, the first active edge sees zero, and the accepted deltas are exactly the valid future half range.
Check pre-wrap and post-wrap observations as an interval input to the core. Confirm that resetting or stalling one context does not introduce a second timebase or change the counter's cycle sequence.

### TEST-UNIT-006 — Pad synchronization and safe drive
- Status: planned
- Level: unit
- Verifies: BLK-PADS
- Run: test_pad_sync_and_safe_drive
Change inputs away from clock edges and check the two-flop path. Apply partial pin updates, open-drain low and release, and coincident reset or safe assertion. Pass if pad outputs change only on sampling edges, open drain never drives high, unmasked pins retain state, and reset or safe overrides any competing update. This logic test does not measure metastability or pad timing.
Check dedicated host pin mapping and registered `MISO`/`READY`. Toggle host inputs without changing the protocol pad ownership or enables.
Apply one update with both driven and released pads. Check that an enable of zero releases a masked pad even if its value bit is high. Also check open-drain high releases with enable set, and unmasked pads retain their state.

### TEST-UNIT-007 — Complete image before run
- Status: planned
- Level: unit
- Verifies: BLK-HOST
- Run: test_loader_commit_and_start
Drive valid, truncated, overlong and bad-CRC SPI frames; try invalid entry PCs and overlapping write allocations. Check little-endian word writes and `READY` for a separate reply with the first bit preloaded. Attempt start before and after commit, loading while running, and deselection or fault while work is active. Check per-context FIFO order, full and empty handling, and a clean reload after each stop path. Pass if only validated settings become active, completion precedes start, and stop clears timed work, payload and image validity as specified.
End requests one bit early, one byte early and one bit late. Stall SCK with `CS` low. Check that no command executes before exact frame validation. Interrupt or overclock a reply to a payload read, then start a new reply frame and check bit-zero restart with exactly one FIFO pop. Reset during a request and with a pending reply in separate runs. Check that no stale reply remains and that the next request needs a fresh `CS` falling edge after synchronized `CS` high.
Check one word per core handshake and preserve FIFO order and context isolation under stalls. Check that host `READ` and `WRITE` still use their existing framing, including empty and full replies.
