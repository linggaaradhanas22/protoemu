# DEC-001 — Select the protocol emulator architecture
- Status: draft
- Traces to: REQ-FLEX-001, REQ-FLEX-002, REQ-RULE-002, REQ-RULE-003, REQ-PROTO-004, SPEC-HOST-001, SPEC-PHY-001, SPEC-PROG-002
- Chooses: ARCH-B
- Evidence: EVAL-001, EVAL-002

This draft recommends B. It does not select an architecture or pass G3.

## Options

- **A:** Two independent PIO-style engines. Separate instruction banks and issue paths isolate workloads.
- **B:** One deterministic core with timed I/O. Two execution contexts share one instruction store and one issue path.
- **C:** A sequencer with two configurable bit lanes. The lanes handle repeated bit timing without issuing each pin operation through the sequencer.

## Step 1: Feasibility screen

| Criterion | A | B | C | Evidence |
|---|---|---|---|---|
| Critical UART/SPI/I²C cases at 60 MHz | 11/11 encoded cases passed | 11/11 | 11/11 | [EVAL-001](../evals/EVAL-001-protocol-comparison.md) |
| Fits within 8×4 tiles | Probe used 33.6% of the row area after repair | 26.1% | 22.0% | [EVAL-002](../evals/EVAL-002-area-timing.md); full design fit is open |
| Meets 60 MHz routed setup and hold | Probe setup +3.339 ns; hold −0.224 ns | +2.934 ns; −0.232 ns | +2.289 ns; −0.226 ns | EVAL-002, placed slow-corner estimates only; none demonstrated routed closure |
| Host reload, pin allocation and post-freeze protocol | Open | Open | Open | EVAL-001 and EVAL-002 do not test these requirements |

No candidate was ruled out by the model runs. The probe hold violations are on inputs to the first synchronizer, with zero minimum input delay and no clock-tree synthesis or hold repair. Do not mark full-fit, routed timing or the untested requirements as passing.

## Step 2: Proposed weights and measured inputs

These weights are for Lingga to approve before scoring. The suggested 1–5 rubric scales each metric between the worst and best measured candidate, with the preferred end scoring 5. If all candidates tie on a metric, score them equally. Do not use the unverified post-freeze protocol or unsupported effort estimates as scores.

| Metric | Proposed weight | A | B | C | Preferred direction |
|---|---:|---:|---:|---:|---|
| Free code words in the bank that runs the Fast-mode I²C image (EVAL-001) | 50% | 2 | 66 | 2 | More is better |
| Repaired probe area (EVAL-002) | 30% | 0.406 mm² | 0.316 mm² | 0.266 mm² | Less is better |
| Slow-corner setup slack after placement and repair (EVAL-002) | 20% | +3.339 ns | +2.934 ns | +2.289 ns | More is better |

Code headroom indicates room to extend one measured program. It is not a direct measure of protocol coverage. A's spare engine bank and C's descriptor banks are not interchangeable with the code bank used by this I²C image. No weighted totals are assigned in this draft.

## Step 3: Sensitivity

After the weights are agreed, vary each weight by ±10 percentage points in turn and rescale the other two proportionally to keep the total at 100%. Area-first priorities favor C; a hard requirement for independent issue paths would favor A. If B cannot preserve deadlines when one context is backpressured, revisit the recommendation before relying on its program-space advantage.

## Recommendation

Carry **B** into microarchitecture if Lingga approves. Its shared store leaves 66 of 128 instruction words free after the Fast-mode I²C exchange, and the placed probe used 26.1% of the row area. Compared with C, the probe costs about 0.050 mm² more. Compared with A, B gives up independent issue paths.

Start from the evaluated design point: a 128×24-bit flop program store, two contexts, four timed output slots and two context-owned capture slots. These are starting parameters, not an approved ISA or a frozen block interface. The encoded tests used all four output entries in the 10 µs stretch case and both capture slots in the UART/SPI overlap case.

Before implementation, specify what happens when the output queue fills, when a timestamp wraps, and when events in different contexts become due on the same cycle. Test that backpressure cannot lose a write or capture or make the other context miss a deadline. Separately define the RP2350 loader and pin allocation, verify reset/reload behavior, and check 60 MHz setup and hold after CTS and routing. The protocol chosen after RTL freeze remains a separate acceptance test.

Approval: pending Lingga review of the decision criteria and recommendation.
