"""EVAL-013: map the register-file write variants to IHP cells and report area."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent / "regfile_probe.v"
VARIANTS = {0: "held-word", 1: "narrow-port", 2: "second-port"}
CORE_UM2 = (1721.28 - 2.88) * (706.86 - 3.78)  # 8x4 tile row area, EVAL-002 summary


def map_variant(pdk, variant, scratch):
    lib = pdk / "libs.ref/sg13cmos5l_stdcell/lib/sg13cmos5l_stdcell_typ_1p20V_25C.lib"
    excluded = (pdk / "libs.tech/librelane/sg13cmos5l_stdcell/synth_exclude.cells").read_text().split()
    dont = " ".join(f"-dont_use {cell}" for cell in excluded)
    stat = scratch / f"stat{variant}.json"
    script = (f"read_verilog {SOURCE.relative_to(ROOT)}; chparam -set VARIANT {variant} regfile_probe; "
              "synth -top regfile_probe -flatten -noabc; "
              f'dfflibmap -liberty "{lib}" {dont}; abc -liberty "{lib}" {dont}; clean; '
              f'tee -q -o "{stat}" stat -json -liberty "{lib}"')
    subprocess.run(["yosys", "-q", "-p", script], cwd=ROOT, check=True)
    module = json.loads(stat.read_text())["modules"]["\\regfile_probe"]
    flops = sum(n for cell, n in module["num_cells_by_type"].items() if "df" in cell.lower())
    return {"cells": module["num_cells"], "flops": flops, "area_um2": round(module["area"], 1),
            "core_fraction": round(module["area"] / CORE_UM2, 5)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as scratch:
        rows = {name: map_variant(args.pdk, v, Path(scratch)) for v, name in VARIANTS.items()}
    base = rows["held-word"]["area_um2"]
    for name, row in rows.items():
        row["delta_vs_held_um2"] = round(row["area_um2"] - base, 1)
        print(f"{name:12s} {row['cells']:5d} cells {row['flops']:4d} flops {row['area_um2']:9.1f} um2"
              f" ({100 * row['core_fraction']:.2f} % of tile) {row['delta_vs_held_um2']:+.1f}")
    lib = args.pdk / "libs.ref/sg13cmos5l_stdcell/lib/sg13cmos5l_stdcell_typ_1p20V_25C.lib"
    summary = {"variants": rows, "core_um2": round(CORE_UM2, 1), "corner": "typ_1p20V_25C",
               "liberty_sha256": hashlib.sha256(lib.read_bytes()).hexdigest(),
               "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               "yosys": subprocess.check_output(["yosys", "-V"], text=True).strip()}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
