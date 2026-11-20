"""Map and place the G4 pad-path probe at 60 MHz. No CTS or routing."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess

from .run_probes import CORNERS, HERE, IMAGE, geometry, run_log

VARIANTS = ("compact", "vector", "hybrid")
QUEUE = r"(?:deadline|mask|value|oe)_bank\[\d+\]|live"
GROUPS = {
    "decode_to_queue": (r"insn|ctx", QUEUE),
    "vector_read_to_queue": (r"gpr\[\d+\]", QUEUE),
    "deadline_to_admission": (r"stamp|offset|timer", QUEUE + r"|accepted|rejected|blocked"),
    "queue_to_pads": (QUEUE + r"|timer|open_drain", r"pad_value|pad_oe"),
}


def endpoint_script(module, variant):
    netnames = module["netnames"]
    drivers = {cell["connections"]["Q"][0]: name for name, cell in module["cells"].items()
               if cell["type"].startswith("sg13cmos5l_df") and "Q" in cell["connections"]}

    def registers(pattern, pin):
        names = {drivers[bit] for net, spec in netnames.items() if re.fullmatch(pattern, net)
                 for bit in spec["bits"] if bit in drivers}
        if not names:
            raise ValueError(f"no mapped register found for {pattern}")
        return " ".join(f"{name}/{pin}" for name in sorted(names))

    script = []
    for name, (source, target) in GROUPS.items():
        if variant == "compact" and name == "vector_read_to_queue":
            continue
        launch = registers(source, "Q")
        capture = registers(target, "D")
        script.extend((f'puts "GROUP {name}"', f"report_checks -from [get_pins {{{launch}}}] "
                       f"-to [get_pins {{{capture}}}] -path_delay max -format full_clock_expanded -digits 3"))
    return "\n".join(script) + "\n"


def paths(text, variant):
    sections = re.split(r"^GROUP (\S+)\s*$", text, flags=re.M)
    records = {}
    for group, report in zip(sections[1::2], sections[2::2]):
        match = re.search(r"^Startpoint: ([^\n]+).*?^Endpoint: ([^\n]+).*?"
                          r"^\s*(-?[\d.]+)\s+slack \((?:MET|VIOLATED)\)", report, re.M | re.S)
        if not match:
            raise ValueError(f"{variant}: no STA path for {group}")
        start, end, slack = match.groups()
        records[group] = {"slack_ns": float(slack), "start": start, "end": end}
    expected = {"all_setup", "all_hold", "reg_setup", "reg_hold", *GROUPS}
    if variant == "compact":
        expected.remove("vector_read_to_queue")
    if records.keys() != expected:
        raise ValueError(f"{variant}: missing path groups: {expected - records.keys()}")
    return records


def measure(args, variant, die, core):
    work = args.work / variant
    work.mkdir(parents=True, exist_ok=True)
    lib = args.pdk / "libs.ref/sg13cmos5l_stdcell/lib/sg13cmos5l_stdcell_typ_1p20V_25C.lib"
    cells = (args.pdk / "libs.tech/librelane/sg13cmos5l_stdcell/synth_exclude.cells").read_text().split()
    dont = " ".join(f"-dont_use {cell}" for cell in cells)
    top = "pad_path_probe"
    yosys = (f"read_verilog models/physical/{top}.v; chparam -set FORMAT {VARIANTS.index(variant)} {top}; "
             f"synth -top {top} -flatten -noabc; dfflibmap -liberty \"{lib}\" {dont}; "
             f"abc -liberty \"{lib}\" {dont}; clean; autoname; "
             f'tee -o "{work / "stat.json"}" stat -json -liberty "{lib}"; '
             f'write_json "{work / "mapped.json"}"; write_verilog -noattr -noexpr "{work / "mapped.v"}"')
    run_log(["yosys", "-p", yosys], work / "map.log")
    module = json.loads((work / "mapped.json").read_text())["modules"][top]
    (work / "endpoints.tcl").write_text(endpoint_script(module, variant))
    stats = json.loads((work / "stat.json").read_text())["modules"][f"\\{top}"]
    sta = {}
    for corner in CORNERS[1:]:
        env = dict(PROBE_PDK="/pdk", PROBE_CORNER=corner, PROBE_DIE=" ".join(map(str, die)),
                   PROBE_CORE=" ".join(map(str, core)))
        cmd = ["docker", "run", "--rm", "--pull", "never", "--network", "none", "--entrypoint", "openroad",
               "-v", f"{args.pdk}:/pdk:ro", "-v", f"{work}:/work:ro",
               "-v", f"{HERE / 'pad_path_sta.tcl'}:/probe.tcl:ro"]
        for key, value in env.items():
            cmd.extend(("-e", f"{key}={value}"))
        cmd.extend((args.image, "-no_init", "-exit", "/probe.tcl"))
        text = run_log(cmd, args.out / f"{variant}-{corner}.txt")
        area = re.search(r"Design area ([0-9.]+) um\^2", text)
        sta[corner] = {"placed_area_um2": float(area[1]), "paths": paths(text, variant)}
    return {"cells": stats["num_cells"], "mapped_area_um2": stats["area"], "sta": sta}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--def", dest="tile_def", required=True, type=Path)
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--work", default="test/sim_build/EVAL-008", type=Path)
    parser.add_argument("--out", default="design/evals/EVAL-008", type=Path)
    parser.add_argument("--variant", choices=VARIANTS, action="append")
    args = parser.parse_args()
    args.work, args.out, args.pdk = (getattr(args, key).resolve() for key in ("work", "out", "pdk"))
    die, core = geometry(args.tile_def)
    args.out.mkdir(parents=True, exist_ok=True)
    variants = args.variant or VARIANTS
    with ThreadPoolExecutor(max_workers=len(variants)) as pool:
        pending = {v: pool.submit(measure, args, v, die, core) for v in variants}
        results = {v: request.result() for v, request in pending.items()}
    lib_dir = args.pdk / "libs.ref/sg13cmos5l_stdcell/lib"
    tools = {"yosys": subprocess.check_output(["yosys", "-V"], text=True).strip(), "image": args.image,
             "image_id": subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}",
                                                   args.image], text=True).strip()}
    summary = dict(die_um=die, row_core_um=core, period_ns=50 / 3, tools=tools,
                   def_sha256=hashlib.sha256(args.tile_def.read_bytes()).hexdigest(),
                   liberty_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                   (lib_dir / f"sg13cmos5l_stdcell_{c}.lib" for c in CORNERS)}, variants=results)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for v, data in results.items():
        slacks = {k: p["slack_ns"] for k, p in data["sta"][CORNERS[1]]["paths"].items()}
        print(f"{v}: {data['mapped_area_um2']:.1f} um², slow placed slack (ns): {slacks}")


if __name__ == "__main__":
    main()
