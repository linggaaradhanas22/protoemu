# Tiny Tapeout template smoke test

- Source revision: `1d433c2e48a826d7716f4e3fe67db1ddc9af964c`. The 1×1 template RTL, flow config and testbench were unchanged. Only the WSL scratch copy had a title, author and description added.
- Toolchain: Tiny Tapeout support tools `0922544e`, LibreLane `3.1.0.dev4`, IHP `ihp-sg13cmos5l` PDK `89d42ee6d2fd9b50b86a1aada6fee6673c3e6008`, Icarus Verilog `12.0`, cocotb `2.0.1`.
- Hardening: **passed**, 348.85 s wall time on the first Docker run. LibreLane wrote the GDS and non-powered netlist and reported a unique LVS match.
- Functional gate-level simulation: **1 passed, 0 failed**, 1.65 s wall time. `test.test_project` completed at 100,000 ns of simulated time. Icarus warned that it does not support the cell models' timing checks.

The resulting GDS and netlist are under `~/protoemu-build/runs/wokwi/final/`. SHA-256:

```text
a3c34427abebf9f2553c0f440dcc6081f5a67cf182fdd06c8778507912c12213  gds/tt_um_example.gds
4974433fc176edbe889374ec091709673c3a00483990b16cd2a1fb7a89bc0779  nl/tt_um_example.nl.v
```

[LibreLane metrics](metrics.json) are saved with this report.

## Rerun notes

The setup wrapper copied the repo and installed dependencies but stopped at the blank project metadata. In `~/protoemu-build`, fill only the three approved metadata fields (`Protoemu template smoke test`, `Protoemu`, `Unchanged Tiny Tapeout RTL hardening smoke test`). From the scratch copy, initialize local Git metadata and fetch the source revision from the local repository without checking it out: the wrapper excludes `.git`, but `tt_tool.py --harden` reads the commit for provenance. Do not rerun the wrapper over the metadata override, as its sync would copy the blank fields back.

From the scratch copy:

```bash
source scripts/env.sh
./tt/tt_tool.py --pdk ihp-sg13cmos5l --create-user-config
/usr/bin/time -p ./tt/tt_tool.py --pdk ihp-sg13cmos5l --harden
```

From the source repository in WSL, copy the generated netlist and point simulation at the exact Ciel PDK version used by hardening:

```bash
cp ~/protoemu-build/runs/wokwi/final/nl/tt_um_example.nl.v test/gate_level_netlist.v
PDK_ROOT="$HOME/ttsetup/pdk/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008" \
  /usr/bin/time -p bash scripts/gl_sim.sh COCOTB_RESULTS_FILE=sim_build/gl/results.xml
```

LibreLane warned about fallback SDC files, no clock sinks in the combinational example, and missing KLayout DRC metrics. This is a flow smoke test, not evidence of 60 MHz timing closure, Tiny Tapeout precheck, or final-project verification.
