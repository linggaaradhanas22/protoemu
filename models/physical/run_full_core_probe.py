"""Map and place the exploratory core with the EVAL-008 timing assumptions."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess

from .run_probes import CORNERS, HERE, IMAGE, geometry, run_log


SOURCES = (
    "full_core_probe.v", "full_core_drive.v", "full_core_capture.v", "probe_store.v", "regfile_probe.v",
)
GROUPS = {
    "pc_to_fetch": (r"pc\[\d+\]", r"insn"),
    "fetch_to_register": (r"insn", r"rf\.regs\[\d+\]"),
    "fetch_to_queue": (r"insn", r"drive\.due_at\[\d+\]"),
    "fetch_to_capture": (r"insn", r"capture\.slot\[\d+\]\.deadline"),
    "register_to_capture": (r"rf\.regs\[\d+\]", r"capture\.slot\[\d+\]\.deadline"),
    "pending_to_queue": (r"wait_(?:at|kind|mask|word)\[\d+\]", r"drive\.due_at\[\d+\]"),
    "capture_to_register": (r"capture\.seen\[\d+\]", r"rf\.regs\[\d+\]"),
    "queue_to_pads": (r"drive\.(?:due_at|slot_value|slot_oe)\[\d+\]", r"pad_(?:value|oe)"),
    "fault_to_pads": (r"fault_pending", r"pad_(?:value|oe)"),
}


def endpoints(module):
    drivers = {cell["connections"]["Q"][0]: name for name, cell in module["cells"].items()
               if cell["type"].startswith("sg13cmos5l_df") and "Q" in cell["connections"]}

    def pins(pattern, pin):
        names = {drivers[bit] for name, spec in module["netnames"].items()
                 if re.fullmatch(pattern, name[4:] if name.startswith("dut.") else name)
                 for bit in spec["bits"] if bit in drivers}
        if not names:
            raise ValueError(f"no register for {pattern}")
        return " ".join(f"{name}/{pin}" for name in sorted(names))

    return "\n".join(
        f'puts "GROUP {group}"\nreport_checks -from [get_pins {{{pins(src, "Q")}}}] '
        f'-to [get_pins {{{pins(dst, "D")}}}] -path_delay max -format full_clock_expanded -digits 3'
        for group, (src, dst) in GROUPS.items()
    ) + "\n"


def report(text):
    parts = re.split(r"^GROUP (\S+)\s*$", text, flags=re.M)
    paths = {}
    for group, data in zip(parts[1::2], parts[2::2]):
        path = re.search(r"^Startpoint: ([^\n]+).*?^Endpoint: ([^\n]+).*?"
                         r"^\s*(-?[\d.]+)\s+slack \((?:MET|VIOLATED)\)", data, re.M | re.S)
        if not path:
            raise ValueError(f"no STA path for {group}")
        start, end, slack = path.groups()
        paths[group] = {"slack_ns": float(slack), "start": start, "end": end}
    if paths.keys() != {"all_setup", "all_hold", "reg_setup", "reg_hold", *GROUPS}:
        raise ValueError(f"incomplete path report: {list(paths)}")
    area = re.search(r"Design area ([0-9.]+) um\^2", text)
    return {"placed_area_um2": float(area[1]), "paths": paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--def", dest="tile_def", required=True, type=Path)
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--opt", type=int, choices=range(11), default=0)
    parser.add_argument("--host-reg", action="store_true",
                        help="map the registered-host wrapper as top instead of the bare core")
    parser.add_argument("--work", default=Path("test/sim_build/EVAL-018"), type=Path)
    parser.add_argument("--out", default=Path("design/evals/EVAL-018"), type=Path)
    args = parser.parse_args()
    args.pdk, args.work, args.out = (path.resolve() for path in (args.pdk, args.work, args.out))
    args.work.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    die, core = geometry(args.tile_def)
    top = "full_core_host" if args.host_reg else "full_core_probe"
    lib_dir = args.pdk / "libs.ref/sg13cmos5l_stdcell/lib"
    libs = {c: lib_dir / f"sg13cmos5l_stdcell_{c}.lib" for c in CORNERS}
    lib = libs[CORNERS[0]]
    excluded = (args.pdk / "libs.tech/librelane/sg13cmos5l_stdcell/synth_exclude.cells").read_text().split()
    dont = " ".join(f"-dont_use {c}" for c in excluded)
    sources = " ".join(f"models/physical/{f}" for f in (*SOURCES, "full_core_host.v"))
    opt = f"chparam -set OPT {args.opt} {top}; " if args.opt else ""
    rename = f"rename -top {top}; " if args.opt else ""
    run_log(["yosys", "-p", f"read_verilog {sources}; {opt}synth -top {top} -flatten -noabc; "
             f'{rename}dfflibmap -liberty "{lib}" {dont}; abc -liberty "{lib}" {dont}; clean; autoname; '
             f'tee -o "{args.work}/stat.json" stat -json -liberty "{lib}"; '
             f'write_json "{args.work}/mapped.json"; write_verilog -noattr -noexpr "{args.work}/mapped.v"'],
            args.work / "map.log")
    module = json.loads((args.work / "mapped.json").read_text())["modules"][top]
    (args.work / "endpoints.tcl").write_text(endpoints(module))
    stats = json.loads((args.work / "stat.json").read_text())["modules"][f"\\{top}"]

    def place(corner):
        env = {"PROBE_PDK": "/pdk", "PROBE_CORNER": corner, "PROBE_DIE": " ".join(map(str, die)),
               "PROBE_CORE": " ".join(map(str, core)), "PROBE_TOP": top}
        cmd = ["docker", "run", "--rm", "--pull", "never", "--network", "none", "--entrypoint", "openroad",
               "-v", f"{args.pdk}:/pdk:ro", "-v", f"{args.work}:/work:ro",
               "-v", f"{HERE / 'full_core_sta.tcl'}:/probe.tcl:ro"]
        for key, value in env.items():
            cmd.extend(("-e", f"{key}={value}"))
        cmd.extend((args.image, "-no_init", "-exit", "/probe.tcl"))
        return report(run_log(cmd, args.out / f"{corner}.txt"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        sta = dict(zip(CORNERS[1:], pool.map(place, CORNERS[1:])))
    tools = {"yosys": subprocess.check_output(["yosys", "-V"], text=True).strip(), "image": args.image,
             "image_id": subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}",
                                                  args.image], text=True).strip()}
    hashes = {f: hashlib.sha256((HERE / f).read_bytes()).hexdigest()
              for f in (*SOURCES, "full_core_host.v", "full_core_sta.tcl", "run_full_core_probe.py")}
    summary = {"opt": args.opt, "host_reg": args.host_reg, "top": top,
               "period_ns": 50 / 3, "die_um": die, "row_core_um": core, "tools": tools,
               "source_sha256": hashes, "def_sha256": hashlib.sha256(args.tile_def.read_bytes()).hexdigest(),
               "liberty_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in libs.values()},
               "cells": stats["num_cells"], "mapped_area_um2": stats["area"], "sta": sta}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for corner, data in sta.items():
        slacks = {name: path["slack_ns"] for name, path in data["paths"].items()}
        print(f"{corner}: {data['placed_area_um2']:.0f} um²; {slacks}")


if __name__ == "__main__":
    main()
