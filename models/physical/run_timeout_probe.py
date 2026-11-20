"""EVAL-017: IHP area of the timed-wait slot extension and the per-context watchdog."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from .ihp_map import CORE_UM2, liberty, map_area

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = {
        "wait_slots": map_area(args.pdk, HERE / "wait_timeout_probe.v", "wait_timeout_probe", {"TIMEOUT": 0}),
        "wait_slots_timeout": map_area(args.pdk, HERE / "wait_timeout_probe.v", "wait_timeout_probe", {"TIMEOUT": 1}),
        "wait_slots_unguarded_timeout": map_area(args.pdk, HERE / "wait_timeout_probe.v", "wait_timeout_probe",
                                                 {"TIMEOUT": 2}),
        "watchdog": map_area(args.pdk, HERE / "watchdog_probe.v", "watchdog_probe", {}),
    }
    base = rows["wait_slots"]["area_um2"]
    rows["timeout_extra_um2"] = round(rows["wait_slots_timeout"]["area_um2"] - base, 1)
    rows["unguarded_timeout_extra_um2"] = round(rows["wait_slots_unguarded_timeout"]["area_um2"] - base, 1)
    for name, row in rows.items():
        print(name, row)
    sources = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
               for name in ("wait_timeout_probe.v", "watchdog_probe.v")}
    summary = {"rows": rows, "core_um2": round(CORE_UM2, 1), "corner": "typ_1p20V_25C",
               "liberty_sha256": hashlib.sha256(liberty(args.pdk).read_bytes()).hexdigest(),
               "source_sha256": sources, "yosys": subprocess.check_output(["yosys", "-V"], text=True).strip()}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
