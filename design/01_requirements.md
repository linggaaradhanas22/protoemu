# 01 — Requirements

What the chip and the project must achieve. Everything else in `design/` traces back to these.

**Sources**
- Competition announcement + FAQ (updated 9 Nov 2026):
  <https://blog.janestreet.com/protocol-emulator-asic-competition/>
- Tiny Tapeout docs: <https://www.tinytapeout.com/>
- IHP Verilog template: <https://github.com/TinyTapeout/ttihp-verilog-template>
- Lingga's own goals (the `REQ-GOAL-*` items are proposals — Lingga decides).

**Rules for this file**
- Only Lingga sets a requirement to `agreed`, changes its text, or adds/removes one.
- Agents may propose a new requirement as `draft` with a CHG record.
- Requirements say **what**, not **how**. Exact numbers go in `02_spec.md`.
- All items start as `draft`. Gate G1 = Lingga reviews and sets each to `agreed` or `rejected`.

---

## Competition rules and constraints

### REQ-RULE-001 — Process and template
- Status: agreed
- Priority: Must
- Source: competition rules (Process); IHP template README
The design shall be built for IHP 130 nm `sg13cmos5l` through Tiny Tapeout, starting from the
`ttihp-verilog-template` main branch.

### REQ-RULE-002 — Area
- Status: agreed
- Priority: Must
- Source: competition rules (Area); FAQ
The design shall fit in at most 8×4 Tiny Tapeout tiles (about 1.0 mm²), with `tiles: 8x4` set in
`info.yaml`. IHP SRAM macros may be used if they fit and pass precheck.

### REQ-RULE-003 — Pin interface
- Status: agreed
- Priority: Must
- Source: FAQ (Pins)
The design shall use only the Tiny Tapeout project interface: 8 inputs, 8 outputs, 8
bidirectional pins, plus clock and reset. No analog pads.

### REQ-RULE-004 — Clock
- Status: agreed
- Priority: Must
- Source: FAQ (Clock: 60 MHz confirmed acceptable); our target choice
The design shall work at a 60 MHz clock supplied by the demo board.

### REQ-RULE-005 — Reset to a known state
- Status: agreed
- Priority: Must
- Source: FAQ (Reset)
All state that affects behaviour shall reach a known value through `rst_n`. The design shall not
rely on flip-flop power-up values.

### REQ-RULE-006 — Reload after power-down
- Status: agreed
- Priority: Must
- Source: FAQ (Reset: deselected designs lose state)
The design shall support reloading its program after being deselected and reselected.

### REQ-RULE-007 — Electrical environment
- Status: agreed
- Priority: Must
- Source: FAQ (External parts)
The design shall work with the demo board's 3.3 V I/O. Any external parts (pull-ups,
transceivers, level shifters) shall be on a Pmod and documented.

### REQ-RULE-008 — Clean flow and precheck
- Status: agreed
- Priority: Must
- Source: competition rules (Submission, Sign-off)
The design shall produce a GDS with a clean Tiny Tapeout flow and pass precheck.

### REQ-RULE-009 — Open source
- Status: agreed
- Priority: Must
- Source: competition rules (Open source)
All design files shall be open source and in a public repository at submission time.

### REQ-RULE-010 — Deadline
- Status: agreed
- Priority: Must
- Source: competition rules (Deadline)
The complete submission shall be made by 18 January 2027.

## Flexibility and programmability

### REQ-FLEX-001 — Unplanned protocols
- Status: agreed
- Priority: Must
- Source: competition brief (main judging criterion)
After fabrication, the chip shall be programmable to support protocols that were not planned
during design, within its timing and I/O limits.

### REQ-FLEX-002 — Software toolchain
- Status: agreed
- Priority: Must
- Source: FAQ (Architecture)
The project shall include the software side: an assembler/toolchain (or bitstream flow) and
example programs.

### REQ-FLEX-003 — Program loading
- Status: agreed
- Priority: Must
- Source: FAQ (Program loading)
The chip shall accept programs from a host. The demo board's microcontroller (RP2350) is the
default host. The loading method shall be documented.

## Protocols

### REQ-PROTO-001 — UART
- Status: agreed
- Priority: Must
- Source: competition brief; FAQ (common baud rates)
The chip shall transmit and receive UART at common baud rates.

### REQ-PROTO-002 — SPI
- Status: agreed
- Priority: Must
- Source: competition brief; FAQ (SPI modes 0–3)
The chip shall support SPI in modes 0, 1, 2 and 3.

### REQ-PROTO-003 — I2C
- Status: agreed
- Priority: Must
- Source: competition brief; FAQ (100 and 400 kHz)
The chip shall support I2C at 100 kHz and 400 kHz.

### REQ-PROTO-004 — Concurrent protocols
- Status: agreed
- Priority: Should
- Source: FAQ (concurrency is a plus)
The chip should run more than one protocol at the same time.

### REQ-PROTO-005 — Controller and target roles
- Status: agreed
- Priority: Should
- Source: FAQ (controller/target roles are a plus)
The chip should act as both controller and target for the supported protocols.

### REQ-PROTO-006 — Low-speed USB
- Status: agreed
- Priority: Could
- Source: competition brief (stretch goal); FAQ (more on-chip protocol work is better)
The chip could support low-speed USB, doing as much line coding, CRC and clock recovery on-chip
as possible.

### REQ-PROTO-007 — 10 Mbit Ethernet
- Status: agreed
- Priority: Could
- Source: competition brief (stretch goal)
The chip could support 10BASE-T Ethernet (with external analog parts on a Pmod).

### REQ-PROTO-008 — Other suggested protocols
- Status: agreed
- Priority: Could
- Source: competition brief (JTAG, SWD, PS/2, CAN suggested)
The chip could support JTAG, SWD, PS/2 and CAN.

## Deliverables

### REQ-DEL-001 — Repository contents
- Status: agreed
- Priority: Must
- Source: FAQ (Submit)
The repository shall contain the RTL, the tests and a passing GDS/precheck from the Tiny Tapeout
flow.

### REQ-DEL-002 — Architecture and ISA documentation
- Status: agreed
- Priority: Must
- Source: FAQ (Submit)
The project shall document the architecture and the instruction set (or programming model).

### REQ-DEL-003 — Verification write-up
- Status: agreed
- Priority: Must
- Source: FAQ (Submit; write-up weighted heavily)
The project shall include a clear write-up of the design and verification approach, explaining
any new techniques or flows.

### REQ-DEL-004 — Description of AI use
- Status: agreed
- Priority: Must
- Source: FAQ (AI tools allowed if described)
The write-up shall describe how AI tools were used.

### REQ-DEL-005 — Gate-level simulation
- Status: agreed
- Priority: Should
- Source: FAQ (Sign-off: strongly recommended)
The design should pass gate-level simulation of the final netlist.

### REQ-DEL-006 — Demo video
- Status: agreed
- Priority: Could
- Source: FAQ (video optional)
The project could include a demo video.

## Lingga's goals (proposals — please decide)

### REQ-GOAL-001 — Evidence of flexibility
- Status: agreed
- Priority: Should
- Source: proposal for Lingga (supports REQ-FLEX-001)
The project should demonstrate, at least in simulation, three or more protocols that were not
design targets (candidates: WS2812, 1-Wire, MIDI, DMX512, RC5 infrared).

### REQ-GOAL-002 — Traceable design process
- Status: agreed
- Priority: Should
- Source: proposal for Lingga (supports REQ-DEL-003)
Every block of RTL and every test should trace back to a requirement, and the write-up should
explain this process.

### REQ-GOAL-003 — FPGA prototype
- Status: agreed
- Priority: Could
- Source: proposal for Lingga
The design could be demonstrated on an FPGA with real peripherals before tapeout.

### REQ-GOAL-004 — Debug access
- Status: agreed
- Priority: Could
- Source: proposal for Lingga (helps silicon bring-up)
The host could inspect and single-step the chip's internal state.

### REQ-GOAL-005 — Schedule margin
- Status: agreed
- Priority: Should
- Source: proposal for Lingga (part-time project)
The RTL should be frozen by 10 January 2027, leaving a week for sign-off and the write-up.
