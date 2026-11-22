#!/bin/bash
# Rebuild and run the EVAL-023 directed retry tests.
set -e
mkdir -p test/sim_build/EVAL-023
out=design/evals/EVAL-023/expiry-overlap.txt
: > "$out"
for v in 2 7 8 9; do
  iverilog -g2005 -s full_core_probe_tb -Pfull_core_probe_tb.OPT="$v" \
    -o "test/sim_build/EVAL-023/check-$v.vvp" models/physical/full_core_probe_tb.v \
    models/physical/full_core_probe.v models/physical/full_core_drive.v \
    models/physical/full_core_capture.v models/physical/probe_store.v models/physical/regfile_probe.v
  vvp "test/sim_build/EVAL-023/check-$v.vvp" >> "$out"
done
cat "$out"
