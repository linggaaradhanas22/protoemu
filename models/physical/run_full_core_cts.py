"""Check CTS and setup/hold repair on an already mapped exploratory core."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from .run_probes import HERE, IMAGE, geometry, run_log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdk', type=Path, required=True)
    parser.add_argument('--def', dest='tile_def', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--image', default=IMAGE)
    parser.add_argument('--top', default='full_core_probe',
                        help='mapped top module, full_core_host for the registered-host wrapper')
    parser.add_argument('--from-log', action='store_true', help='summarize a completed cts.txt without rerunning OpenROAD')
    args = parser.parse_args()
    die, core = geometry(args.tile_def)
    script = HERE / 'full_core_cts.tcl'
    work = args.work.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    env = {'PROBE_PDK': '/pdk', 'PROBE_DIE': ' '.join(map(str, die)),
           'PROBE_CORE': ' '.join(map(str, core)), 'PROBE_TOP': args.top}
    cmd = ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none', '--entrypoint', 'openroad',
           '-v', f'{args.pdk.resolve()}:/pdk:ro', '-v', f'{work}:/work:ro', '-v', f'{script}:/probe.tcl:ro']
    for key, value in env.items():
        cmd.extend(('-e', f'{key}={value}'))
    cmd.extend((args.image, '-no_init', '-exit', '/probe.tcl'))
    report = args.out / 'cts.txt'
    if args.from_log:
        log = report.read_text(encoding='utf-8')
        report.write_text('\n'.join(line.rstrip() for line in log.splitlines()).rstrip() + '\n', encoding='utf-8')
    else:
        log = run_log(cmd, report)
    phases = re.split(r'^PHASE (\w+)\s*$', log, flags=re.M)
    results = {}
    for name, body in zip(phases[1::2], phases[2::2]):
        groups = re.split(r'^GROUP (\w+)\s*$', body, flags=re.M)
        area = re.search(r'Design area ([\d.]+) um\^2', body)
        slacks = {}
        for group, data in zip(groups[1::2], groups[2::2]):
            end = re.search(r'^\s*(-?[\d.]+)\s+slack \((?:MET|VIOLATED)\)', data, flags=re.M)
            if not end:
                raise ValueError(f'{name}: no slack for {group}')
            slacks[group] = float(end[1])
        if not area or slacks.keys() != {'all_setup', 'reg_setup', 'all_hold', 'reg_hold'}:
            raise ValueError(f'incomplete timing reports for {name}')
        results[name] = {'area_um2': float(area[1]), **slacks}
        print(name, results[name])
    if results.keys() != {'placed', 'cts', 'repaired'}:
        raise ValueError(f'incomplete CTS run: {list(results)}')
    summary = {'mapped_sha256': hashlib.sha256((work / 'mapped.v').read_bytes()).hexdigest(),
               'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(), 'image': args.image,
               'phases': results}
    (args.out / 'cts.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
