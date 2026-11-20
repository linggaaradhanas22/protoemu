"""EVAL-013: map the register-file write variants to IHP cells and report area."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from .ihp_map import CORE_UM2, liberty, map_area

SOURCE = Path(__file__).resolve().parent / "regfile_probe.v"
VARIANTS = {0: "held-word", 1: "narrow-port", 2: "second-port"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = {name: map_area(args.pdk, SOURCE, "regfile_probe", {"VARIANT": v}) for v, name in VARIANTS.items()}
    base = rows["held-word"]["area_um2"]
    for name, row in rows.items():
        row["delta_vs_held_um2"] = round(row["area_um2"] - base, 1)
        print(f"{name:12s} {row['cells']:5d} cells {row['flops']:4d} flops {row['area_um2']:9.1f} um2"
              f" ({100 * row['core_fraction']:.2f} % of tile) {row['delta_vs_held_um2']:+.1f}")
    lib = liberty(args.pdk)
    summary = {"variants": rows, "core_um2": round(CORE_UM2, 1), "corner": "typ_1p20V_25C",
               "liberty_sha256": hashlib.sha256(lib.read_bytes()).hexdigest(),
               "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               "yosys": subprocess.check_output(["yosys", "-V"], text=True).strip()}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
