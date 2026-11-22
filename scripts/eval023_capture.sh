#!/bin/bash
# Rebuild and run the EVAL-023 capture timeout comparison.
set -e
mkdir -p test/sim_build/EVAL-023
out=design/evals/EVAL-023/capture-directed.txt
iverilog -g2005 -Wall -s capture_expiry_probe_tb -o test/sim_build/EVAL-023/capture.vvp \
  models/physical/capture_expiry_probe_tb.v models/physical/capture_expiry_probe.v \
  models/physical/full_core_capture.v
vvp test/sim_build/EVAL-023/capture.vvp | tee "$out"
