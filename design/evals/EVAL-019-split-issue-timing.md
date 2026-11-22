# EVAL-019 — Compare same-cycle issue paths
- Status: done
- Traces to: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, SPEC-PHY-001
- Compares: ARCH-B
- Model: `models/physical/full_core_probe.v`, `models/physical/run_full_core_probe.py`

## Method

Compare three elaborations of the [EVAL-018](EVAL-018-full-core-timing.md) probe. None adds an issue cycle or changes the programmer-visible contract.

- `OPT=0`: rerun the shared validator as a control. Synthesis can name and order logic differently in the parameterized source, so compare the variants within this run; keep EVAL-018 as historical context.
- `OPT=1`: compute the fresh request and its timing from the registered fetch context. Validate each saved drive request in parallel with context selection. Select the verdict and data for the chosen route. Compute the modular future-half predicate with equality and a low-bit comparison rather than a full subtract on the selection path.
- `OPT=2`: also use carry-save three-operand sums for the absolute deadline and timeout calculation. This tests arithmetic depth separately from the validator split.

Use the same IHP libraries, 8×4 row geometry, 60 MHz period and 0.25 ns uncertainty as EVAL-018. The host is still stubbed. This is placement with estimated parasitics, not CTS, hold repair, routing or full-chip sign-off.

## Functional checks

All three elaborations passed the Icarus probe test. The 228 recorded edge samples per elaboration matched byte for byte. They cover retry across wrap, a deadline reached while the queue is still full, progress in the other context, guarded match and expiry, and fault-edge output followed by safe on F+1. The 89 existing Python benchmark checks also passed. These checks are not an exhaustive equivalence proof, a protocol replay on this probe or registered project verification.

## Results

| Variant | Slow setup, overall | Slow setup, internal | Saved request to drive queue, slow setup | Fast hold, overall | Fast hold, internal | Slow placed cell area |
|---|---:|---:|---:|---:|---:|---:|
| `OPT=0` Shared validator | −9.209 ns | −7.445 ns | −4.203 ns | −0.204 ns | −0.047 ns | 379,863 µm² |
| `OPT=1` Split validation | −7.173 ns | −5.402 ns | −3.397 ns | −0.199 ns | −0.053 ns | 382,786 µm² |
| `OPT=2` Split + carry-save sums | −5.996 ns | −5.265 ns | −2.938 ns | −0.204 ns | −0.054 ns | 385,232 µm² |

The best variant improves worst internal setup by 2.180 ns against the control and adds 5,369 µm² (1.4%). It still misses 60 MHz. Across all three variants, the worst internal slow setup path starts at the cycle counter and ends at register-file writeback. The worst internal fast hold path is between the two pin synchronizer stages. In `OPT=2`, fresh fetch-to-drive and fetch-to-capture paths also miss setup by 0.983 ns and 1.165 ns, respectively. The changes help the worst path but do not improve every path group. These are structural STA paths, not a finding that every path is sensitizable.

## Recommendation

Do not freeze or adopt any of the three probes. Next, test a registered select/commit boundary. Check whether that boundary can use an existing issue slot; if it changes issue latency, replay the Fast-mode I2C and concurrent UART/SPI workloads with the exact new schedule. Check that saved deadlines are not recomputed, expiration still faults without a late drive, and the safe edge remains F+1. Recheck hold after CTS and hold repair. G4 approval and the agreed block contracts are unchanged.

## Reproduce

From the repo root in WSL, with the EVAL-018 tools and LibreLane image available:

```bash
source scripts/env.sh
for v in 0 1 2; do
  work="test/sim_build/EVAL-019/v$v"
  python3 -B -m models.physical.run_full_core_probe --opt "$v" \
    --work "$work" --out "design/evals/EVAL-019/v$v" \
    --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
    --def "$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def" || exit 1
  iverilog -g2005 -s full_core_probe_tb -Pfull_core_probe_tb.OPT="$v" -o "$work/probe.vvp" \
    models/physical/full_core_probe_tb.v models/physical/full_core_probe.v \
    models/physical/full_core_drive.v models/physical/full_core_capture.v \
    models/physical/probe_store.v models/physical/regfile_probe.v || exit 1
  vvp "$work/probe.vvp" +trace > "$work/smoke.txt" || exit 1
done
cmp test/sim_build/EVAL-019/v0/smoke.txt test/sim_build/EVAL-019/v1/smoke.txt
cmp test/sim_build/EVAL-019/v0/smoke.txt test/sim_build/EVAL-019/v2/smoke.txt
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-019/v0/summary.json
```

Each variant directory holds its summary and both corner reports. The Git command identifies the source revision that produced the archive.
