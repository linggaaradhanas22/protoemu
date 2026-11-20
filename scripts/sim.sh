#!/usr/bin/env bash
# Run the cocotb RTL tests in test/ (the Tiny Tapeout template's Makefile).
# Extra arguments go straight to make. Examples:
#   bash scripts/sim.sh
#   bash scripts/sim.sh COCOTB_TEST_FILTER=test_uart_tx     # cocotb 2.x
#   bash scripts/sim.sh TESTCASE=test_uart_tx               # cocotb 1.x
# Results: test/results.xml (read by check_trace.py), waves in test/.
set -eo pipefail
source "$(dirname "$0")/env.sh"
cd "$PROTOEMU_ROOT/test"
make -B "$@"
