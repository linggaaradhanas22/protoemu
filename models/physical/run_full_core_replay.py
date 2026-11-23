"""Run the draft programs on the probe RTL with the independent Python pin fixtures."""

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from ..benchmarks.cycle import ModelError, Pins, clock_json
from ..benchmarks.g4_isa import assemble
from ..benchmarks.g4_pad_encoding import PIN_ORDERS
from ..benchmarks.g4_payload import SPI_WORD, build
from ..benchmarks.g4_suite import WRAP, pins_for
from ..benchmarks.g4_timeout import Both, FORMATS, REGRESSION, i2c_program, prefixed, spi_loop_program
from ..benchmarks.i2c_fixture import I2CPeer, i2c_check
from ..benchmarks.run_encoded import spi_bench, words_to_bytes
from ..benchmarks.spi_uart import SPIPeer, spi_check
from .run_full_core_probe import SOURCES
from .run_probes import HERE


def rtl(exe, code, entries, ingress, bus, owners, epoch, limit):
    names = tuple(bus.idle)
    assert len(names) == 8 and len(code) % 3 == 0 and len(code) // 3 <= 128

    def mask(names_on):
        names_on = set(names_on)
        return sum(1 << n for n, name in enumerate(names) if name in names_on)

    def pins():
        return mask(name for name in names if bus.level[name])

    words = [int.from_bytes(code[i:i+3], 'little') for i in range(0, len(code), 3)]
    queues = [deque(q) for q in (*ingress, ())[:2]]
    result = [[], []]
    samples = []
    error = None
    trace = hashlib.sha256()
    args = [len(words), *(*entries, 0)[:2], (1 << len(entries)) - 1,
            *(*map(mask, owners), 0)[:2], mask(bus.open_drain), pins(), epoch]
    with subprocess.Popen(['vvp', str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          text=True, bufsize=1) as proc:
        def send(values):
            proc.stdin.write(' '.join(f'{x:x}' for x in values) + '\n')

        try:
            proc.stdin.write(' '.join(f'{x:x}' for x in args) + '\n' +
                             '\n'.join(f'{w:x}' for w in words) + '\n')
            proc.stdin.flush()
            ready = proc.stdout.readline().strip()
            if ready != 'READY':
                raise RuntimeError(f'probe startup failed: {ready}')
            oe_prev = val_prev = 0
            for t in range(limit + 1):
                bus.advance(t)
                send((pins(), sum(bool(q) << i for i, q in enumerate(queues)),
                      sum((len(q) < 8) << i for i, q in enumerate(result)),
                      (queues[0][0] if queues[0] else 0) | ((queues[1][0] if queues[1] else 0) << 16)))
                reply = proc.stdout.readline().split()
                if len(reply) != 13:
                    raise RuntimeError(f'bad probe tick at {t}: {reply}')
                fields = [int(s, 16) for s in reply]
                trace.update(' '.join(reply).encode('ascii') + b'\n')
                val, oe, pop, push, word, done, faulted, ctx, pc, cause, sample, pin, bit = fields
                if sample:
                    samples.append((t, names[pin], bit))
                for i in range(2):
                    if pop & (1 << i):
                        queues[i].popleft()
                    if push & (1 << i):
                        result[i].append(word)
                changed = (oe ^ oe_prev) | ((val ^ val_prev) & oe)
                if changed:
                    bus.apply(t, 'dut', {name: ((val >> i) & 1) if oe & (1 << i) else None
                                         for i, name in enumerate(names) if changed & (1 << i)})
                oe_prev, val_prev = oe, val
                if faulted:
                    error = f'core fault ctx={ctx} pc={pc} cause={cause} at {t}'
                    break
                if done and not bus.events:
                    if any(queues):
                        error = 'unused host payload'
                    break
            else:
                error = f'not done by cycle {limit}'
        except ModelError as exc:
            error = str(exc)
        finally:
            proc.stdin.close()
            proc.wait(timeout=5)
    return result, samples, t, error, trace.hexdigest()


def i2c_case(exe, epoch, case, concurrent):
    names = {6: 'scl', 7: 'sda', 0: 'cs', 1: 'mosi', 2: 'miso', 3: 'sclk'}
    peer = I2CPeer(case)
    if concurrent:
        peer = Both(peer, SPIPeer(0, 30))
    bus = Pins(pins_for(names, {'scl': 1, 'sda': 1, 'cs': 1}), open_drain=('scl', 'sda'), peer=peer)
    body = i2c_program(True, case.variant, 'C')
    if concurrent:
        code, labels = assemble(['entry0', *prefixed(body, 'i2c'), 'entry1',
                                 *prefixed(spi_loop_program(6, 400), 'spi')], formats=FORMATS)
        entries, ingress, owners = (0, labels['entry1']), ([0x964B], [SPI_WORD]*6), ({'scl', 'sda'}, {'cs', 'mosi', 'sclk'})
    else:
        code, _ = assemble(body, formats=FORMATS)
        entries, ingress, owners = (0,), ([0x964B],), ({'scl', 'sda'},)
    got, _, end, error, trace = rtl(exe, code, entries, ingress, bus, owners, epoch, 50_000)
    ok = got[0][-1:] == [0]
    errors, margin = i2c_check(bus, {'i2c_ok': [ok] if got[0] else [],
                                    'i2c_rx': words_to_bytes(got[0][:-1]) if ok else []}, case)
    if concurrent:
        starts = [t for t, name, v in bus.edges if name == 'cs' and v == 0]
        spi_errors, _, _ = spi_check(bus, words_to_bytes(got[1]), 0, 30, starts)
        if len(starts) != 6:
            spi_errors.append(f'{len(starts)} of 6 SPI transactions started')
        errors += spi_errors
    return dict(case=case.name, concurrent=concurrent, epoch=epoch, end_cycle=end, margin=margin, trace_sha256=trace,
                errors=([error] if error else []) + errors)


def overlap_case(exe, epoch, offset, phase):
    image = build(offset)
    case, bus, limit, monitor = spi_bench('B', image, 0, True, machine_factory=lambda _, __, bus: bus,
                                         uart_phase=phase, spi_offset=offset, pin_order=PIN_ORDERS['overlap'])
    got, samples, end, error, trace = rtl(exe, image.programs[0], image.entries, ((), (SPI_WORD, SPI_WORD)),
                                         bus, (set(), {'cs', 'mosi', 'sclk'}), epoch, limit)
    decoded = dict(uart_rx=[w for w in got[0] if w < 256], uart_error=[w for w in got[0] if w >= 256],
                   spi_rx_word=got[1])
    errors, margin = monitor(SimpleNamespace(bus=bus, samples=samples, report=decoded), end)
    return dict(case=case, offset=offset, phase=phase, epoch=epoch, end_cycle=end, margin=margin, trace_sha256=trace,
                errors=([error] if error else []) + errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opt', type=int, choices=range(2, 12), required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    exe = Path(f'test/sim_build/EVAL-020/replay-{args.opt}.vvp')
    exe.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['iverilog', '-g2005', '-s', 'full_core_replay_tb', f'-Pfull_core_replay_tb.OPT={args.opt}',
                    '-o', str(exe), *(str(HERE / f) for f in (*SOURCES, 'full_core_replay_tb.v'))], check=True)
    cases = [(i2c_case, epoch, case, concurrent) for epoch in (0, WRAP) for case in REGRESSION if case.fast
             for concurrent in (False, True)]
    cases += [(overlap_case, epoch, offset, Fraction(phase, 16)) for epoch in (0, (1 << 24) - 500)
              for offset in (-4, 0, 4) for phase in range(16)]
    if args.quick:
        cases = [cases[0], cases[1], cases[-1]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda case: case[0](exe, *case[1:]), cases))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2, default=clock_json) + '\n', encoding='utf-8')
    passed = sum(not row['errors'] for row in rows)
    print(f'OPT={args.opt}: {passed}/{len(rows)} protocol cases passed')
    for row in [r for r in rows if r['errors']][:4]:
        print(row['case'], row['errors'][:3])
    return int(passed != len(rows))


if __name__ == '__main__':
    raise SystemExit(main())
