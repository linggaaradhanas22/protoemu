# EVAL-026 — Split core payload eligibility by context
- Status: running
- Traces to: BLK-CORE, BLK-DRIVE, BLK-PADS, SPEC-PHY-001
- Compares: ARCH-B
- Model: `models/physical/full_core_probe.v`, `models/physical/full_core_host.v`

## Question

Can the core shorten the path to the host payload handshake without adding a cycle? [EVAL-025](EVAL-025-agreed-schedule-timing.md) measured +0.037 ns setup and +0.080 ns hold after clock-tree synthesis and repair with a registered host boundary. Its worst repaired setup path ran from the core's redirect register to the egress-push logic.

## Variants

- `OPT=10`: same-cycle retry baseline from EVAL-025.
- `OPT=11`: build GET and PUT eligibility from each context's saved wait kind and FIFO readiness. Keep the same round-robin selection. At a free issue boundary, qualify the selected context's transfer with its active bit and local eligibility. For a fresh instruction, qualify the transfer with the fetch context and the existing execute and decode checks.

There is no new state or retry cycle. `started`, `active`, `DONE`, and fault state updates are unchanged. Pending drive, capture, and fence requests use the existing paths. These changes are in the probe, not production RTL.

## Behavior checks

[Directed results](EVAL-026/directed.txt): Icarus Verilog 12.0 passed the directed cases for both variants. All 362 directed trace records matched. The cases check arbitration against an expiring request, retry on the last legal edge, fault release on F+1, guarded waits, and malformed instructions. New cases check egress contention, `STOP` when credit returns, and ingress becoming visible on the edge after a host write. The testbench models the registered FIFO flags. It does not test the real host FIFO.

[Protocol replay](EVAL-026/replay.json): Both variants passed all 124 Fast-mode I²C and UART/SPI cases. The result files matched byte for byte. This includes each case's digest of the per-cycle pad values and enables, FIFO transfers and words, `DONE`, faults, and sample observations. The replay drives the bare probe, not the registered host wrapper.

## Physical results so far

Mapped both variants with `full_core_host` as top and the same Yosys and `sg13cmos5l` typical library.

| Variant | Mapped cells | Mapped cell area |
|---|---:|---:|
| [`OPT=10`](EVAL-026/v10h-mapping.json) | 15,985 | 365,625.792 µm² |
| [`OPT=11`](EVAL-026/v11h-mapping.json) | 15,839 | 365,790.298 µm² |

The candidate uses 146 fewer cells but 164.506 µm² more mapped area (+0.045%). The current `OPT=10` mapped netlist differs from the archived EVAL-025 netlist. Use the current baseline and candidate together for placement. The older +0.037 ns result is context, not a new measurement.

Docker Desktop's Linux engine was unavailable. No placement, clock-tree synthesis, or setup and hold repair ran for this evaluation. Mapped area does not show whether the rewrite improves timing. Do not adopt it in production RTL until the timing comparison runs.

## Reproduce

Use the probe sources in the commit that adds this record, based on `69cdd1c`. Run from the repository root in WSL.

```sh
source scripts/env.sh
work=test/sim_build/EVAL-026
mkdir -p "$work"
for opt in 10 11; do
  /usr/bin/iverilog -g2005 -s full_core_probe_tb -Pfull_core_probe_tb.OPT="$opt" \
    -o "$work/directed-$opt.vvp" \
    models/physical/{full_core_probe_tb,full_core_probe,full_core_drive,full_core_capture,probe_store,regfile_probe}.v
  /usr/bin/vvp "$work/directed-$opt.vvp" +trace > "$work/v$opt-directed.txt"
  PATH=/usr/bin:/bin python3 -B -m models.physical.run_full_core_replay \
    --opt "$opt" --out "$work/v$opt-replay.json"
done
diff -u <(grep '^TRACE' "$work/v10-directed.txt") <(grep '^TRACE' "$work/v11-directed.txt")
cmp "$work/v10-replay.json" "$work/v11-replay.json"
```

Set `pdk_dir` to the installed `ihp-sg13cmos5l` PDK directory that contains `libs.ref`. The existing runner supports `--map-only` to reproduce the area comparison without Docker. Omit that flag and run the CTS command when Docker is available. Use the same image and 8×4 DEF for both variants.

```sh
tiles="$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def"
for opt in 10 11; do
  variant="$work/v${opt}h"
  python3 -B -m models.physical.run_full_core_probe --opt "$opt" --host-reg \
    --pdk "$pdk_dir" --def "$tiles" --work "$variant" --out "$variant"
  python3 -B -m models.physical.run_full_core_cts --top full_core_host \
    --pdk "$pdk_dir" --def "$tiles" --work "$variant" --out "$variant"
done
```
