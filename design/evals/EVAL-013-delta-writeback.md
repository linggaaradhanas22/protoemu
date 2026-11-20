# EVAL-013 — Register writes for the two-word `edge_delta` result
- Status: done
- Traces to: BLK-CORE, SPEC-PROG-003
- Compares: held word, narrow second port, full second port
- Model: `models/physical/regfile_probe.v`, `models/benchmarks/g4_writeback.py`

## Question

`edge_delta` returns the low 16 bits of an interval in `Rd` and the zero-extended high bits in `Rd+1` (`Rd` is R1–R4). On the same retirement it clears the offset pair R0/R6. The model writes all of this on one edge, but the hardware schedule was left open. Which register-file write structure should BLK-CORE use?

## Options

Every option keeps write port A (any register, 16 bits), the dedicated offset-pair path (R0 ← bits 15:0, R6 ← bits 22:16) and the clear on `START`/flush. The low word always uses port A.

| Option | High word | Extra state |
|---|---|---|
| Held word | Held in a register, then written through port A in a later issue slot | 11 flops plus an address/data mux on port A |
| **Narrow port** | Written on the same edge to `Rd+1` (R2–R5 only) as `{9'b0, bits 22:16}` | None |
| Full second port | Written on the same edge by a general 16-bit port to any register | None |

`Rd+1` can never be R0 or R6, and `Rd` is never R0, R6 or `Rd+1`. So the three writes on one edge always hit different registers.

## Method

- **Function:** an Icarus testbench drives 4,000 random instructions (1,248 `edge_delta`) into all three variants and a reference model. It compares all 16 registers after each instruction. A deliberately wrong `Rd+1` address must be detected.
- **Area:** map each variant to IHP `sg13cmos5l` cells at `typ_1p20V_25C` with Yosys, using the same `dont_use` list and steps as EVAL-002 and EVAL-008. Two contexts × eight 16-bit registers, two read ports and the offset output are included.
- **Issue cost:** replay the six RC5 cases with the held word taking one more issue slot. Also run a busy two-context case: context 0 runs `edge_delta` on an input edge every 30, 40 or 60 cycles (200 edges); context 1 schedules a pad toggle every 16 cycles.

## Results

**Function:** all three variants matched the reference with 0 errors. The mutation produced 7,931 errors.

| Option | Cells | Flops | Area (µm²) | Share of 8×4 tile | Compared with held word |
|---|---:|---:|---:|---:|---:|
| Held word | 1,526 | 267 | 25,098.7 | 2.08 % | – |
| **Narrow port** | 1,497 | 256 | **24,437.4** | **2.02 %** | **−661.3** |
| Full second port | 1,876 | 256 | 27,647.2 | 2.29 % | +2,548.5 |

The narrow port is the smallest. This reverses the generic Yosys cell count (1,445 / 1,682 / 1,712), so the mapped result is the one to use. The held word adds 11 flops and a mux on the shared port A address and data. The narrow port adds write gating to only 4 × 16 bits per context. Mapping did not show which cells account for the 661 µm² difference. The held word would also need a scheduler micro-op, which is not included in its area.

| Issue cost of the held word | Result |
|---|---|
| RC5, six cases | All pass with the same output words. 948 instead of 946 issues. Minimum sample slack 1 cycle lower (25,307 instead of 25,308 at the fastest rate). |
| Two contexts, edge every 30 / 40 / 60 cycles | All pass. +199 issues in context 0 (one per `edge_delta`). Context 1's minimum drive slack is unchanged at 14 cycles. The longest runnable wait rises by at most 1 cycle. |

The register file is about 24,400 µm², roughly 16 % of BLK-CORE's 0.150 mm² planning allowance.

## Conclusion

Use the narrow port. It is the smallest option, needs no extra issue slot, and matches the behavior the model and CHG-006 already describe: both words are written on the retirement edge. [CHG-009](../changes/CHG-009-delta-writeback.md) records it as a small BLK-CORE change.

Trade-off: the port only reaches R2–R5. If a later change lets `Rd` be any register, or moves the offset pair, the narrow port must be widened. The full second port would add about 3,200 µm² compared with the narrow one.

## Limits

- Typical-corner area after synthesis only; no placement, routing or timing. The extra port adds a 2:1 mux in front of 128 flops; its effect on setup timing is not measured.
- The probe is not the production register file. The decode, read-port count and offset-path width may change in RTL.
- Issue cost is measured on RC5 and one synthetic two-context case. No baseline protocol uses `edge_delta`.

## Reproduce

```bash
source scripts/env.sh
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-013/regfile.json
python3 -B -m models.physical.run_regfile_probe \
  --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
  --out design/evals/EVAL-013/regfile.json
iverilog -g2005 -s regfile_probe_tb -o test/sim_build/EVAL-013/regfile.vvp \
  models/physical/regfile_probe.v models/physical/regfile_probe_tb.v
vvp test/sim_build/EVAL-013/regfile.vvp
python3 -B -m models.benchmarks.g4_writeback --out design/evals/EVAL-013/issue.json
python3 -B -m unittest models.benchmarks.test_g4_writeback
```

[`regfile.json`](EVAL-013/regfile.json) records the areas, Yosys version and Liberty hash. [`issue.json`](EVAL-013/issue.json) holds the replay results.
