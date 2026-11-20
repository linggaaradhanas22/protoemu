#!/usr/bin/env bash
# Quick synthesis to estimate size. Use it in EVALs and to check block area budgets.
# Usage: bash scripts/synth_area.sh <top_module> [verilog files...]   (default files: src/*.v)
# Output: reports/synth/<top>_<date>.txt
#   - STD_LIB empty  -> generic Yosys cells (good for comparing options)
#   - STD_LIB set    -> mapped to the IHP standard cells, with real area (see SETUP.md)
set -eo pipefail
source "$(dirname "$0")/env.sh"
cd "$PROTOEMU_ROOT"
if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/synth_area.sh <top_module> [files...]"
  exit 1
fi
top="$1"; shift
shopt -s nullglob
if [ $# -gt 0 ]; then files=("$@"); else files=(src/*.v); fi
mkdir -p reports/synth
out="reports/synth/${top}_$(date +%Y%m%d_%H%M).txt"
if [ -n "$STD_LIB" ]; then
  script="read_verilog ${files[*]}; synth -top $top -flatten; dfflibmap -liberty $STD_LIB; abc -liberty $STD_LIB; opt_clean; stat -liberty $STD_LIB"
else
  script="read_verilog ${files[*]}; synth -top $top -flatten; stat"
fi
yosys -p "$script" > "$out"
echo "Full log: $out"
sed -n '/Printing statistics/,$p' "$out" | head -n 60
