"""Map architecture probes with the same rules and run pre-route timing checks."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
IMAGE = "ghcr.io/librelane/librelane:3.1.0.dev4"
CORNERS = ("typ_1p20V_25C", "slow_1p08V_125C", "fast_1p32V_m40C")


def geometry(path):
    text = path.read_text()
    units = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", text)[1])
    die = tuple(int(x) / units for x in re.search(r"DIEAREA \( (\d+) (\d+) \) \( (\d+) (\d+) \)", text).groups())
    rows = [tuple(map(int, m)) for m in re.findall(r"^ROW \S+ CoreSite (\d+) (\d+) \S+ DO (\d+) BY 1 STEP (\d+) 0", text, re.M)]
    ys = sorted({y for _, y, _, _ in rows})
    if len(rows) != len(ys) or len(ys) < 2 or len(set(ys[i + 1] - y for i, y in enumerate(ys[:-1]))) != 1:
        raise ValueError("expected full-width regularly spaced Tiny Tapeout rows")
    if len({(x, length, step) for x, _, length, step in rows}) != 1:
        raise ValueError("Tiny Tapeout rows have different widths")
    x, _, length, step = rows[0]
    core = (x / units, ys[0] / units, (x + length * step) / units, (ys[-1] + ys[1] - ys[0]) / units)
    return die, core


def run_log(cmd, path):
    completed = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    path.write_text("\n".join(line.rstrip() for line in completed.stdout.splitlines()).rstrip() + "\n",
                    encoding="utf-8")
    if completed.returncode:
        raise RuntimeError(f"command exited {completed.returncode}: {path}")
    return completed.stdout


def timing_summary(text):
    slack = dict(re.findall(r"^worst slack (max|min)\s+(-?[\d.]+)\s*$", text, re.M))
    if slack.keys() != {"max", "min"}:
        raise RuntimeError("expected two worst slack results")
    reg = text.split("REGISTER SETUP", 1)[1]
    path = re.search(r"^Startpoint: ([^\n]+).*?^Endpoint: ([^\n]+).*?^[ \t]+(-?[\d.]+)\s+slack \((?:MET|VIOLATED)\)",
                     reg, re.S | re.M)
    if path is None:
        raise RuntimeError("register path missing")
    start, end, reg_slack = path.groups()
    area = re.search(r"Design area ([0-9.]+) um\^2", text)
    return {"setup_ns": float(slack["max"]), "hold_ns": float(slack["min"]), "reg_setup_ns": float(reg_slack),
            "reg_start": start, "reg_end": end,
            "placed_area_um2": float(area[1]) if area else None}


def one(args, arch, die, core):
    scratch = args.work / arch
    scratch.mkdir(parents=True, exist_ok=True)
    lib = args.pdk / "libs.ref/sg13cmos5l_stdcell/lib"
    typical = lib / f"sg13cmos5l_stdcell_{CORNERS[0]}.lib"
    excluded = (args.pdk / "libs.tech/librelane/sg13cmos5l_stdcell/synth_exclude.cells").read_text().split()
    dont = " ".join(f"-dont_use {cell}" for cell in excluded)
    source = " ".join(str(path.relative_to(ROOT)) for path in sorted(HERE.glob("probe_*.v")))
    yosys = (f"read_verilog {source}; chparam -set ARCH {ord(arch) - ord('A')} probe_top; "
             "synth -top probe_top -flatten -noabc; "
             f'dfflibmap -liberty "{typical}" {dont}; abc -liberty "{typical}" {dont}; '
             f'clean; autoname; tee -o "{scratch / "stat.json"}" stat -json -liberty "{typical}"; '
             f'write_verilog -noattr -noexpr "{scratch / "mapped.v"}"')
    run_log(["yosys", "-p", yosys], scratch / "map.log")
    raw = json.loads((scratch / "stat.json").read_text())
    stats = raw["modules"]["\\probe_top"]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{arch}-cells.json").write_text(json.dumps(stats, indent=2) + "\n")
    rows = {}
    for corner in CORNERS:
        for placed in (False, True) if args.place and corner == CORNERS[1] else (False,):
            label = corner + ("-placed" if placed else "")
            flags = {"PROBE_PDK": "/pdk", "PROBE_CORNER": corner, "PROBE_ARCH": arch,
                     "PROBE_PLACE": int(placed), "PROBE_DIE": " ".join(map(str, die)),
                     "PROBE_CORE": " ".join(map(str, core))}
            env_flags = [item for k, v in flags.items() for item in ("-e", f"{k}={v}")]
            command = ["docker", "run", "--rm", "--pull", "never", "--network", "none", "--entrypoint", "openroad",
                       "-v", f"{args.pdk}:/pdk:ro", "-v", f"{args.work}:/work:ro",
                       "-v", f"{HERE / 'probe_sta.tcl'}:/probe.tcl:ro", *env_flags,
                       args.image, "-no_init", "-exit", "/probe.tcl"]
            path = args.out / f"{arch}-{label}.txt"
            rows[label] = timing_summary(run_log(command, path))
    area = stats["area"]
    core_area = (core[2] - core[0]) * (core[3] - core[1])
    return {"cells": stats["num_cells"], "area_um2": area, "core_fraction": area / core_area, "sta": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdk", required=True, type=Path)
    parser.add_argument("--def", dest="tile_def", required=True, type=Path)
    parser.add_argument("--arch", choices="ABC", action="append")
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--work", default="test/sim_build/EVAL-002", type=Path)
    parser.add_argument("--out", default="design/evals/EVAL-002", type=Path)
    parser.add_argument("--place", action="store_true", help="also estimate slow-corner timing after placement and repair")
    args = parser.parse_args()
    args.work, args.out, args.pdk = (getattr(args, key).resolve() for key in ("work", "out", "pdk"))
    die, core = geometry(args.tile_def)
    arches = args.arch or "ABC"
    with ThreadPoolExecutor(max_workers=len(arches)) as pool:
        jobs = {arch: pool.submit(one, args, arch, die, core) for arch in arches}
        measurements = {arch: job.result() for arch, job in jobs.items()}
    lib_dir = args.pdk / "libs.ref/sg13cmos5l_stdcell/lib"
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (lib_dir / f"sg13cmos5l_stdcell_{corner}.lib" for corner in CORNERS)}
    summary = {"die_um": die, "row_core_um": core, "clock_period_ns": 50 / 3,
               "def_sha256": hashlib.sha256(args.tile_def.read_bytes()).hexdigest(),
               "liberty_sha256": hashes, "yosys": subprocess.check_output(["yosys", "-V"], text=True).strip(),
               "openroad_image": args.image, "architectures": measurements}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for arch, row in measurements.items():
        sta = row["sta"][CORNERS[1]]
        print(f"{arch}: {row['cells']} cells, {row['area_um2']:.1f} um², slow register setup {sta['reg_setup_ns']:+.3f} ns")


if __name__ == "__main__":
    main()
