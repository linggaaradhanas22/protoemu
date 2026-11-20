# 03 — Architecture options

Candidate architectures that could meet the spec. Stage G3.
The choice between them is made in a DEC (`04_decisions/`) using EVAL evidence (`evals/`).

**Each option must describe**
1. The idea in 3–5 sentences, and a block sketch (text diagram is fine).
2. How it would run each benchmark in `models/benchmarks/` (or why it can't).
3. Rough area (cells / tiles) and the biggest timing risk.
4. Toolchain effort (assembler? bitstream?).
5. Main risks and unknowns → each unknown becomes an EVAL.

Status: `candidate` → `chosen` or `rejected`. Keep rejected options here — they explain the
decision in the write-up. Aim for at least 3 options; the gate needs at least 2.

Example:

```markdown
### ARCH-A — PIO-style state machines with a small ALU
- Status: candidate
- Traces to: REQ-FLEX-001, REQ-PROTO-001, REQ-PROTO-002, REQ-PROTO-003
Idea: 4 small engines, 1 instruction per cycle, side-set + delay fields, plus XOR/shift ops ...
Benchmarks: UART/SPI/I2C easy; USB-LS in software (~30 cycles/bit est.); 10BASE-T not possible.
Area guess: ~4 tiles per engine incl. 32x16 instruction memory in flops.
Risks: instruction memory size; START/STOP detection for I2C target. -> EVAL needed.
```

**Starting ideas** (from `design/reference/` — not decisions, just seeds):
- PIO-style state machines, extended (ALU, bigger memory, richer wait conditions).
- PRU-style deterministic RISC core with timed I/O ports (XMOS idea).
- Small sequencer + configurable "bit-layer" pipeline (line coder → stuffer → CRC → shifter).
- Tiny eFPGA + sequencer hybrid.

---

All three candidates use the same host contract: load while halted, report a complete image, then start. Reset clears the load-valid and run state, output enables and any queued work. Instruction storage cannot affect pins before a complete load; no candidate assumes power-up contents. The host may queue payload and configuration but cannot service protocol deadlines. Models include two input synchronizer stages and registered pad outputs. A pin allocation must fit the Tiny Tapeout interface with the loader and all five concurrent UART/SPI pins in use.

### ARCH-A — Two independent PIO-style engines
- Status: candidate
- Traces to: REQ-RULE-002, REQ-RULE-004, REQ-FLEX-001, REQ-FLEX-002, REQ-FLEX-003, REQ-PROTO-001, REQ-PROTO-002, REQ-PROTO-003, REQ-PROTO-004, REQ-GOAL-001

Two engines each fetch from a private program bank. An instruction can update pins and perform a shift, ALU operation, branch, or wait; only explicit waits and delays stall the engine. Pin ownership is configured before start, so neither engine can delay the other's I/O. Open-drain mode maps a pin update to drive-low or release.

```text
host loader -> banks A/B -> engine A/B -> pin ownership -> registered pad outputs
pad inputs -> 2-flop synchronizers -> both engines
```

Initial sizing point: two 64×32-bit program banks, or 4,096 flop storage sites, before decode, bank read muxes, engines, I/O and loader. The likely critical path is bank read through decode to a registered action. Use a small assembler with labels, pin aliases and delay literals; count bank duplication and instruction packing in [EVAL-002](evals/EVAL-002-area-timing.md). Check whether programs fit and whether either engine can lose a back-to-back input edge in [EVAL-001](evals/EVAL-001-protocol-comparison.md).

### ARCH-B — One deterministic ALU core with timed I/O
- Status: candidate
- Traces to: REQ-RULE-002, REQ-RULE-004, REQ-FLEX-001, REQ-FLEX-002, REQ-FLEX-003, REQ-PROTO-001, REQ-PROTO-002, REQ-PROTO-003, REQ-PROTO-004, REQ-GOAL-001

A small ALU core runs one shared program and schedules masked pin updates and samples against a free-running cycle counter. The I/O unit has a short timestamped output queue and a separate edge/sample capture queue. The core handles protocol decisions and replenishes queues; it must schedule conditional continuations after captures without CPU stalls that miss deadlines. The I/O unit has no protocol-specific operations.

```text
host loader -> shared program -> deterministic core -> timed output queue -> pad regs
pad inputs -> 2-flop synchronizers -> capture queue -> core
cycle counter -> timed output and capture units
```

Initial sizing point: one 128×24-bit program bank, or 3,072 flop storage sites, before the register file, queues, timestamp logic, I/O and loader. Check program fetch and the timestamp/queue-to-pin path in [EVAL-002](evals/EVAL-002-area-timing.md). The assembler needs labels and timed I/O operations; programs must manage deadlines explicitly. [EVAL-001](evals/EVAL-001-protocol-comparison.md) measures queue occupancy and the worst time to act on a captured edge when two protocols overlap.

### ARCH-C — Sequencer with two configurable bit lanes
- Status: candidate
- Traces to: REQ-RULE-002, REQ-RULE-004, REQ-FLEX-001, REQ-FLEX-002, REQ-FLEX-003, REQ-PROTO-001, REQ-PROTO-002, REQ-PROTO-003, REQ-PROTO-004, REQ-GOAL-001

A shared control sequencer sets up two generic lanes and branches on their events. Each lane repeats a configured bit operation with two timed phases, shifting and sampling on selected phases. A lane can also capture edge timestamps or run a one-shot pin action. Per-lane events are latched until consumed; the sequencer is still responsible for branches across words or transaction phases.

```text
host loader -> descriptor store + sequencer -> lane A/B -> registered pad outputs
pad inputs -> 2-flop synchronizers -> lane A/B -> latched events -> sequencer
```

Initial sizing point: 64×24-bit control store plus two 16×24-bit descriptor banks, or 2,304 flop storage sites, before lane counters, shifters, capture state, sequencer, I/O and loader. The big timing risk is timer/event arbitration when both lanes fire together. The image builder must pack lane descriptors and assemble the control program. [EVAL-001](evals/EVAL-001-protocol-comparison.md) checks whether the lane primitives let programs implement all transactions without adding hardware per protocol. [EVAL-002](evals/EVAL-002-area-timing.md) checks whether the lanes erase the storage savings.

### How the candidates would run the benchmarks

These are implementation hypotheses, not test results. The model decides whether each one fits; no candidate may change hardware between cases.

| Profile | Independent engines | Timed I/O core | Configurable lanes |
|---|---|---|---|
| UART TX/RX | Count bit periods; detect start, wait to mid-bit, then shift one sample per bit. | Schedule TX levels; capture RX start and schedule mid-bit samples. | Sequence start/stop around repeated shifts; arm RX lane for a start edge and a timed sample phase. |
| SPI controller | Loop with clock/data pin updates and programmed half-period delays. Move the sample to the correct half-cycle for CPHA. | Queue clock/MOSI transitions and MISO samples at the selected edge phase. | Set idle polarity and sample/drive phase; run a 16-bit transfer under one CS assertion. |
| I2C controller | Use open-drain pin updates and wait for synchronized SCL high. Branch on ACK/NACK and explicitly program START/STOP. | Schedule low/release transitions. After a release, schedule the rest of the bit only after observing the SCL rise. | Gate the high phase on observed SCL; sequence START/STOP and branch on ninth-clock samples. |
| Concurrent UART RX and SPI | Give each protocol its own engine and pin group. | Reserve capacity for both in the capture queue; refill SPI output events without delaying UART samples. | Assign one lane to each protocol; test whether shared event handling can keep up. |
| WS2812 | Shift bits and select one of two high times, then hold low for latch. | Fill the queue with bit-dependent pulse widths; refill before it underruns. | Select the high phase from the shifted bit; sequence the final low interval. |
| 1-Wire | Drive low/release and test the presence and read windows in software. | Schedule reset and read slot pulses; capture presence and sample each read slot. | Run one-shot open-drain pulses and timed samples; assemble the 64-bit readout in the control program. |
| RC5 | Timestamp intervals with a counter loop, then classify edges and decode fields. | Capture both edge polarities and decode half-bit intervals in software. | Use edge timestamp mode and decode intervals with the sequencer. Check capture loss and counter wrap. |

Storage counts above count only proposed program/descriptor bits, assuming flop implementation. Even the storage cell area alone depends on the mapped IHP library; it excludes read muxes and routing. Convert mapped area to a rough utilization of the 8×4 core in the physical evaluation. The 1×1 template smoke run cannot supply a timing or area result for these candidates.
