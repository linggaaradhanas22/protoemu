# EVAL-026 — Split core payload eligibility by context
- Status: done
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

## Physical results

Mapped both variants with `full_core_host` as top and the same Yosys and `sg13cmos5l` typical library.

| Variant | Mapped cells | Mapped cell area |
|---|---:|---:|
| [`OPT=10`](EVAL-026/v10h-mapping.json) | 15,985 | 365,625.792 µm² |
| [`OPT=11`](EVAL-026/v11h-mapping.json) | 15,839 | 365,790.298 µm² |

The candidate uses 146 fewer cells but 164.506 µm² more mapped area (+0.045%). The current `OPT=10` mapped netlist differs from the archived EVAL-025 netlist. Compare the two runs below rather than subtracting the older +0.037 ns result.

Both runs used the registered host boundary, the same 8×4 floorplan, and the same LibreLane image and repair script as EVAL-025. The clock period was 50/3 ns with 0.25 ns uncertainty. Setup is from the slow corner and hold from the fast corner. All numbers use placement-estimated parasitics, not routed extraction.

| Variant | Stage | Worst setup slack | Worst hold slack | Cell area |
|---|---|---:|---:|---:|
| `OPT=10` | Placed | −3.671 ns | −0.208 ns | 387,960 µm² |
| `OPT=10` | After clock tree | −3.697 ns | −0.575 ns | 440,997 µm² |
| `OPT=10` | After repair | **−0.004 ns** | **+0.080 ns** | 516,728 µm² |
| `OPT=11` | Placed | −5.046 ns | −0.205 ns | 388,274 µm² |
| `OPT=11` | After clock tree | −5.078 ns | −0.573 ns | 441,311 µm² |
| `OPT=11` | After repair | **−0.019 ns** | **+0.080 ns** | 515,687 µm² |

Timing reports and provenance: `OPT=10` [CTS log](EVAL-026/v10h/cts.txt), [CTS summary](EVAL-026/v10h/cts.json), [placement summary](EVAL-026/v10h/summary.json); `OPT=11` [CTS log](EVAL-026/v11h/cts.txt), [CTS summary](EVAL-026/v11h/cts.json), [placement summary](EVAL-026/v11h/summary.json). Both mapped netlist hashes match the corresponding mapping-only runs.

## Conclusion

The rewrite preserved the tested cycle behavior but did not improve worst setup slack. It lost 1.375 ns at placement and 0.015 ns after repair. Repaired cell area decreased by 1,041 µm² (0.20%). Hold passed for both variants, but neither met setup at 60 MHz. In both repaired runs, the worst setup path starts at a cycle-counter bit and ends at a register-file bit. The worst path does not establish whether the FIFO-specific path improved.

Keep `OPT=11` as probe evidence only. Recommend keeping the agreed schedule and measuring the integrated RTL before choosing another optimization. This probe excludes the real loader, FIFOs and pad ring. It cannot establish final tile fit or routed timing.

## Reproduce

Use the probe sources from `bef4fa4`. Run from the repository root in WSL.

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

Set `pdk_dir` to the installed `ihp-sg13cmos5l` PDK directory that contains `libs.ref`. Use the same LibreLane image and 8×4 DEF for both variants. For mapping alone without Docker, add `--map-only` to the first command and skip the second.

```sh
tiles="$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def"
for opt in 10 11; do
  variant="$BUILD_DIR/test/sim_build/EVAL-026-physical/v${opt}h"
  python3 -B -m models.physical.run_full_core_probe --opt "$opt" --host-reg \
    --pdk "$pdk_dir" --def "$tiles" --work "$variant" --out "$variant"
  python3 -B -m models.physical.run_full_core_cts --top full_core_host \
    --pdk "$pdk_dir" --def "$tiles" --work "$variant" --out "$variant"
done
```
