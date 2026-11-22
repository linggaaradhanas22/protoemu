"""EVAL-023: compare retained timeout storage with a precomputed expiry."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from .ihp_map import CORE_UM2, liberty, map_area
from .run_probes import HERE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--out", default=Path("design/evals/EVAL-023/capture.json"), type=Path)
    args = parser.parse_args()
    rows = {
        "store_rt": map_area(args.pdk, HERE / "full_core_capture.v", "full_core_capture", {}),
        "precomputed_expiry": map_area(args.pdk, HERE / "capture_expiry_probe.v", "capture_expiry_probe", {}),
    }
    rows["precomputed_minus_store_um2"] = round(
        rows["precomputed_expiry"]["area_um2"] - rows["store_rt"]["area_um2"], 1)
    summary = {
        "rows": rows,
        "core_um2": round(CORE_UM2, 1),
        "corner": "typ_1p20V_25C",
        "liberty_sha256": hashlib.sha256(liberty(args.pdk).read_bytes()).hexdigest(),
        "source_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in (
            "full_core_capture.v", "capture_expiry_probe.v", "capture_expiry_probe_tb.v")},
        "yosys": subprocess.check_output(["yosys", "-V"], text=True).strip(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for name, row in rows.items():
        if isinstance(row, dict):
            print(f"{name}: {row['area_um2']} um², {row['flops']} flops")
    print(f"precomputed minus stored: {rows['precomputed_minus_store_um2']} um²")


if __name__ == "__main__":
    main()
