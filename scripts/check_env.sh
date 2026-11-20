#!/usr/bin/env bash
# Check that every tool the flow needs is installed. Prints OK / MISSING per tool.
# Usage: bash scripts/check_env.sh
source "$(dirname "$0")/env.sh"
fail=0
check() {  # name, command to print version
  local name="$1" out; shift
  if out="$("$@" 2>&1)"; then
    printf "  %-12s OK       %s\n" "$name" "${out%%$'\n'*}"
  else
    printf "  %-12s MISSING  (%s)\n" "$name" "$*"
    fail=1
  fi
}
echo "Tools:"
check git        git --version
check make       make --version
check rsync      rsync --version
check python3    python3 --version
check iverilog   "${ICARUS_BIN_DIR:+$ICARUS_BIN_DIR/}iverilog" -V
check yosys      yosys -V
check verilator  verilator --version
check sby        sby --version
check docker     docker --version
check opencode   opencode --version
echo "Python packages (venv: ${VIRTUAL_ENV:-none}):"
check cocotb     python3 -c "import cocotb; print('cocotb', cocotb.__version__)"
check librelane  python3 -c "import importlib.metadata as m; print('librelane', m.version('librelane'))"
echo "Python version must be 3.11 or newer:"
python3 -c 'import sys; v=sys.version_info; print("  OK" if v>=(3,11) else "  TOO OLD", sys.version.split()[0]); sys.exit(v<(3,11))' || fail=1
echo "Docker running:"
if docker info >/dev/null 2>&1; then echo "  OK"; else echo "  NOT RUNNING (start Docker Desktop / dockerd)"; fail=1; fi
echo "Settings: PDK=$PDK PDK_ROOT=$PDK_ROOT BUILD_DIR=$BUILD_DIR"
case "$PROTOEMU_ROOT" in
  /mnt/*) echo "Repo is on the Windows drive ($PROTOEMU_ROOT) - fine for docs/sim; harden.sh uses BUILD_DIR." ;;
esac
if [ "$fail" -ne 0 ]; then echo "Some items are missing - see SETUP.md (librelane is only needed for harden.sh)."; fi
exit "$fail"
