#!/usr/bin/env bash
# Lint the RTL with Verilator.
# Usage: bash scripts/lint.sh [top_module]   (default: top_module from info.yaml)
set -eo pipefail
source "$(dirname "$0")/env.sh"
cd "$PROTOEMU_ROOT"
top="${1:-}"
if [ -z "$top" ]; then
  top="$(sed -nE 's/^[[:space:]]*top_module:[[:space:]]*"?([A-Za-z0-9_]+)"?.*/\1/p' info.yaml | head -n1)"
fi
if [ -z "$top" ]; then
  echo "Could not find top_module in info.yaml; pass it as an argument."
  exit 1
fi
shopt -s nullglob
files=(src/*.v)
verilator --lint-only -Wall -Wno-DECLFILENAME -Isrc --top-module "$top" "${files[@]}"
echo "lint: OK ($top)"
