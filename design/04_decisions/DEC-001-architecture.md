# DEC-001 — Select the protocol emulator architecture
- Status: agreed
- Traces to: REQ-FLEX-001, REQ-FLEX-002, REQ-RULE-002, REQ-RULE-003, REQ-PROTO-004, SPEC-HOST-001, SPEC-PHY-001, SPEC-PROG-002
- Chooses: ARCH-B
- Evidence: EVAL-001, EVAL-002

Lingga selected B on 2026-11-20. G3 sign-off is separate from architecture selection.

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

## Step 2: Weighted scores

Lingga approved the weights on 2026-11-20. Each metric scores 1 at the worst measured value and 5 at the best, with linear interpolation between them. For area, use the negative of the measured value so smaller is better. For an all-candidate tie, use 3 for every candidate. Multiply each score by its weight, then sum without rounding. The unverified post-freeze protocol and unsupported effort estimates are not scored.

| Metric | Weight | A: value / score | B: value / score | C: value / score | Evidence |
|---|---:|---:|---:|---:|---|
| Free code words in the bank running Fast-mode I²C | 50% | 2 / 1.000 | 66 / 5.000 | 2 / 1.000 | [EVAL-001 encoded results](../evals/EVAL-001/encoded/results.json), 10 µs stretch case |
| Repaired probe area | 30% | 405,518 µm² / 1.000 | 315,550 µm² / 3.575 | 265,768 µm² / 5.000 | [EVAL-002 summary](../evals/EVAL-002/summary.json), slow placed area |
| Slow-corner setup slack after placement and repair | 20% | +3.339 ns / 5.000 | +2.934 ns / 3.457 | +2.289 ns / 1.000 | EVAL-002 summary, slow placed setup slack |
| **Weighted total (out of 5)** | **100%** | **1.800** | **4.264** | **2.200** | EVAL-001 and EVAL-002, as above |

Code headroom indicates room to extend one measured program. It is not a direct measure of protocol coverage. A's spare engine bank and C's descriptor banks are not interchangeable with the code bank used by this I²C image.

## Step 3: Sensitivity

Each row changes one weight by 10 percentage points and rescales the other two proportionally so the total stays at 100%. Weights and scores are displayed rounded; the calculations used unrounded values.

| Weight varied | Headroom / area / setup | A | B | C |
|---|---:|---:|---:|---:|
| Headroom −10 pp | 40% / 36% / 24% | 1.960 | 4.117 | 2.440 |
| Headroom +10 pp | 60% / 24% / 16% | 1.640 | 4.411 | 1.960 |
| Area −10 pp | 57.14% / 20% / 22.86% | 1.914 | 4.362 | 1.800 |
| Area +10 pp | 42.86% / 40% / 17.14% | 1.686 | 4.166 | 2.600 |
| Setup −10 pp | 56.25% / 33.75% / 10% | 1.400 | 4.365 | 2.350 |
| Setup +10 pp | 43.75% / 26.25% / 30% | 2.200 | 4.163 | 2.050 |

B ranks first in every test. Its narrowest lead is 1.566 points over C when area rises to 40%. A hard requirement for independent issue paths would favor A. If B cannot preserve deadlines when one context is backpressured, revisit the recommendation before relying on its program-space advantage.

## Decision

Carry **B** into microarchitecture after G3 sign-off. Its shared store leaves 66 of 128 instruction words free after the Fast-mode I²C exchange, and the placed probe used 26.1% of the row area. Compared with C, the probe costs about 0.050 mm² more. Compared with A, B gives up independent issue paths. A and C were not selected on the approved scoring criteria; neither failed the encoded cases.

Start from the evaluated design point: a 128×24-bit flop program store, two contexts, four timed output slots and two context-owned capture slots. These are starting parameters, not an approved ISA or a frozen block interface. The encoded tests used all four output entries in the 10 µs stretch case and both capture slots in the UART/SPI overlap case.

Before implementation, specify what happens when the output queue fills, when a timestamp wraps, and when events in different contexts become due on the same cycle. Test that backpressure cannot lose a write or capture or make the other context miss a deadline. Separately define the RP2350 loader and pin allocation, verify reset/reload behavior, and check 60 MHz setup and hold after CTS and routing. The protocol chosen after RTL freeze remains a separate acceptance test.

Approval: Lingga approved the weights and the selection of ARCH-B on 2026-11-20.
