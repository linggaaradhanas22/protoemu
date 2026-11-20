#!/usr/bin/env bash
# Run the Tiny Tapeout hardening flow (LibreLane) locally.
# The repo is copied to $BUILD_DIR on the WSL disk first, because running the
# flow on the Windows drive (/mnt/c) is very slow. Needs Docker running.
#
# Usage: bash scripts/harden.sh            normal run
#        bash scripts/harden.sh --setup    first run: also installs tt-support-tools + LibreLane
#
# After the run:
#   - full outputs:        $BUILD_DIR/runs/   (not in git)
#   - small summaries:     reports/harden/<date>/  (in git)
#   - gate-level netlist:  test/gate_level_netlist.v  (for scripts/gl_sim.sh)
# Commands follow https://tinytapeout.com/guides/local-hardening - check it if a step fails.
set -eo pipefail
source "$(dirname "$0")/env.sh"

setup=0
if [ "${1:-}" = "--setup" ]; then setup=1; fi

mkdir -p "$BUILD_DIR"
rsync -a --delete \
  --exclude .git --exclude runs --exclude tt \
  --exclude test/sim_build --exclude '*.vcd' --exclude '*.fst' \
  "$PROTOEMU_ROOT"/ "$BUILD_DIR"/
cd "$BUILD_DIR"

if [ ! -d tt ]; then
  git clone https://github.com/TinyTapeout/tt-support-tools tt
  setup=1
fi
if [ "$setup" -eq 1 ]; then
  git -C tt pull --ff-only || true
  pip install -r tt/requirements.txt
  pip install "librelane==$LIBRELANE_TAG"
fi

./tt/tt_tool.py --pdk "$PDK" --create-user-config
./tt/tt_tool.py --pdk "$PDK" --harden
./tt/tt_tool.py --pdk "$PDK" --print-warnings > runs/warnings.txt 2>&1 || true

stamp="$(date +%Y%m%d_%H%M)"
dest="$PROTOEMU_ROOT/reports/harden/$stamp"
mkdir -p "$dest"
cp runs/warnings.txt "$dest/"
if [ -f runs/wokwi/final/metrics.json ]; then
  cp runs/wokwi/final/metrics.json "$dest/"
fi
top="$(./tt/tt_tool.py --pdk "$PDK" --print-top-module)"
nl="runs/wokwi/final/nl/$top.nl.v"
if [ -f "$nl" ]; then
  cp "$nl" "$PROTOEMU_ROOT/test/gate_level_netlist.v"
  echo "Gate-level netlist copied to test/gate_level_netlist.v"
fi
echo "Done. Summaries in reports/harden/$stamp. Full run in $BUILD_DIR/runs."
echo "View layout: cd $BUILD_DIR && ./tt/tt_tool.py --pdk $PDK --open-in-klayout"
