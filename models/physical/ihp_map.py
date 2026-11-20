"""Map a Verilog probe to IHP sg13cmos5l cells with Yosys and return its area."""

import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CORE_UM2 = (1721.28 - 2.88) * (706.86 - 3.78)  # 8x4 tile row area, EVAL-002 summary
CORNER = "typ_1p20V_25C"


def liberty(pdk):
    return pdk / f"libs.ref/sg13cmos5l_stdcell/lib/sg13cmos5l_stdcell_{CORNER}.lib"


def map_area(pdk, source, top, params):
    lib = liberty(pdk)
    excluded = (pdk / "libs.tech/librelane/sg13cmos5l_stdcell/synth_exclude.cells").read_text().split()
    dont = " ".join(f"-dont_use {cell}" for cell in excluded)
    chparam = "".join(f"chparam -set {key} {value} {top}; " for key, value in params.items())
    with tempfile.TemporaryDirectory() as scratch:
        stat = Path(scratch) / "stat.json"
        script = (f"read_verilog {Path(source).resolve().relative_to(ROOT)}; {chparam}"
                  f"synth -top {top} -flatten -noabc; "
                  f'dfflibmap -liberty "{lib}" {dont}; abc -liberty "{lib}" {dont}; clean; '
                  f'tee -q -o "{stat}" stat -json -liberty "{lib}"')
        subprocess.run(["yosys", "-q", "-p", script], cwd=ROOT, check=True)
        module = json.loads(stat.read_text())["modules"][f"\\{top}"]
    flops = sum(n for cell, n in module["num_cells_by_type"].items() if "df" in cell.lower())
    return {"cells": module["num_cells"], "flops": flops, "area_um2": round(module["area"], 1),
            "core_fraction": round(module["area"] / CORE_UM2, 5)}
