"""EVAL-015: area of multi-word host FIFO access against single-word FIFOs."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from .ihp_map import CORE_UM2, liberty, map_area

HERE = Path(__file__).resolve().parent
DEPTHS = (4, 8, 16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = []
    for depth in DEPTHS:
        single = map_area(args.pdk, HERE / "fifo_probe.v", "fifo_probe", {"DEPTH": depth, "BYPASS": 0})
        multi = map_area(args.pdk, HERE / "fifo_multi_probe.v", "fifo_multi_probe", {"DEPTH": depth})
        rows.append({"depth": depth, "single": single, "multi": multi,
                     "multi_extra_um2": round(multi["area_um2"] - single["area_um2"], 1)})
        print(f"depth {depth:2d}: single {single['area_um2']:9.1f} um2, multi {multi['area_um2']:9.1f} um2"
              f" ({rows[-1]['multi_extra_um2']:+.1f})")
    sources = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
               for name in ("fifo_probe.v", "fifo_multi_probe.v")}
    summary = {"queues": 4, "rows": rows, "core_um2": round(CORE_UM2, 1), "corner": "typ_1p20V_25C",
               "liberty_sha256": hashlib.sha256(liberty(args.pdk).read_bytes()).hexdigest(),
               "source_sha256": sources, "yosys": subprocess.check_output(["yosys", "-V"], text=True).strip()}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
