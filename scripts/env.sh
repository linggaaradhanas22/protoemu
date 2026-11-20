# shellcheck shell=bash
# Shared environment for all scripts. Use it with:  source scripts/env.sh
# Every value can be overridden by exporting it before sourcing this file.
# Edit the defaults below if your install paths differ (see SETUP.md).

PROTOEMU_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROTOEMU_ROOT

export OSS_CAD_DIR="${OSS_CAD_DIR:-$HOME/tools/oss-cad-suite}"   # Yosys, Icarus, Verilator, SBY
export TT_VENV="${TT_VENV:-$HOME/ttsetup/venv}"                   # Python venv (cocotb, LibreLane)
export PDK_ROOT="${PDK_ROOT:-$HOME/ttsetup/pdk}"
export PDK="${PDK:-ihp-sg13cmos5l}"
export LIBRELANE_TAG="${LIBRELANE_TAG:-3.1.0.dev4}"               # check Tiny Tapeout's guide for newer
export BUILD_DIR="${BUILD_DIR:-$HOME/protoemu-build}"             # hardening runs here (WSL disk, fast)
export STD_LIB="${STD_LIB:-}"                                     # optional .lib for synth_area.sh

# OSS CAD Suite first, then the venv on top so its python/pip win.
if [ -d "$OSS_CAD_DIR/bin" ]; then
  case ":$PATH:" in
    *":$OSS_CAD_DIR/bin:"*) ;;
    *) export PATH="$OSS_CAD_DIR/bin:$PATH" ;;
  esac
fi
if [ -f "$TT_VENV/bin/activate" ] && [ "${VIRTUAL_ENV:-}" != "$TT_VENV" ]; then
  # shellcheck disable=SC1091
  source "$TT_VENV/bin/activate"
fi

# The OSS CAD Suite vvp wrapper forces its own Python home, which breaks venv cocotb.
if [ -z "${ICARUS_BIN_DIR:-}" ] && [ -x /usr/bin/iverilog ] && [ -x /usr/bin/vvp ]; then
  export ICARUS_BIN_DIR=/usr/bin
fi
