#!/usr/bin/env bash
# Run the cocotb tests on the gate-level netlist produced by scripts/harden.sh.
# harden.sh copies the netlist to test/gate_level_netlist.v.
set -eo pipefail
source "$(dirname "$0")/env.sh"
cd "$PROTOEMU_ROOT/test"
if [ ! -f gate_level_netlist.v ]; then
  echo "No test/gate_level_netlist.v - run: bash scripts/harden.sh"
  exit 1
fi
make -B GATES=yes "$@"
