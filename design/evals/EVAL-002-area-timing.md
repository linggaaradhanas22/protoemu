# EVAL-002 — What area and timing risks differentiate the candidates?
- Status: planned
- Traces to: REQ-RULE-002, SPEC-PHY-001, SPEC-HOST-001, SPEC-PROG-001, REQ-GOAL-005
- Compares: ARCH-A, ARCH-B, ARCH-C
- Model: storage inventory, executable image builders and exploratory synthesis probes under `models/` (not yet implemented)

## Method

1. Size each candidate to the largest image and runtime state observed in the protocol comparison. Count instruction/descriptor bits, read ports, muxes, queue and register bits, pad logic and the loader. Keep the same flop storage assumption and common loader/pad accounting. If a candidate needs an SRAM macro to fit, record that as a separate, unproven variant.
2. Synthesize representative storage and critical-path probes against the same IHP cell library. Use the same mapping settings and a `50/3 ns` clock target. Record mapped cell count and area, estimate 8×4 core utilization using the flow's core dimensions, and report the worst path. Keep synthesis/STA estimates separate from routed measurements. If a probe cannot settle the comparison, run a representative physical experiment before treating that risk as retired.
3. Assemble the baseline images and record which configuration, encoding and loader stages they need. Describe the remaining effort and trace any untested deliverable, rather than scoring effort from the number of assembly lines alone.
4. Record the exact commands, model commit, PDK/library revision and corners. Store raw reports under `design/evals/EVAL-002/`. No number from the unchanged template counts as candidate evidence.

## Decision use

Prefer results with documented area headroom and a credible 60 MHz implementation path. Neither synthesis probes nor analytical area estimates satisfy routed timing, precheck or system acceptance.

## Results

Not run. The inventory in the options document counts storage bits, not mapped cell area.
