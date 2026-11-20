"""EVAL-014: map four payload FIFOs (2 contexts x in/out) to IHP cells by depth."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from .ihp_map import CORE_UM2, liberty, map_area

SOURCE = Path(__file__).resolve().parent / "fifo_probe.v"
DEPTHS = (2, 4, 6, 8, 16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = []
    for bypass in (0, 1):
        for depth in DEPTHS:
            row = {"depth": depth, "bypass": bypass,
                   **map_area(args.pdk, SOURCE, "fifo_probe", {"DEPTH": depth, "BYPASS": bypass})}
            rows.append(row)
            print(f"depth {depth:2d} bypass {bypass}: {row['cells']:5d} cells {row['flops']:4d} flops"
                  f" {row['area_um2']:9.1f} um2 ({100 * row['core_fraction']:.2f} % of tile)")
    summary = {"queues": 4, "word_bits": 16, "rows": rows, "core_um2": round(CORE_UM2, 1),
               "corner": "typ_1p20V_25C",
               "liberty_sha256": hashlib.sha256(liberty(args.pdk).read_bytes()).hexdigest(),
               "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               "yosys": subprocess.check_output(["yosys", "-V"], text=True).strip()}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
