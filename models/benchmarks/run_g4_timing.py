"""Replay G3 fixtures with G4 timed I/O, scheduler and alternate queue sizes."""

import argparse
import json
from fractions import Fraction
from functools import partial
from pathlib import Path

from .cycle import clock_json
from .encoded_programs import build
from .g4_timing import TimingProbe
from .i2c_fixture import I2CCase
from .run_compare import measure
from .run_encoded import i2c_bench, spi_bench


def jobs(make, build_image=build, *, pin_orders=None):
    orders = pin_orders or {}
    for mode in range(4):
        yield spi_bench("B", build_image("B", "spi", mode), mode, False, machine_factory=make,
                        pin_order=orders.get("spi")), {}
    image = build_image("B", "i2c")
    cases = [I2CCase("combined", True, stretch) for stretch in (0, 60, 300, 600)]
    cases += [I2CCase(variant, True) for variant in ("nack-address", "nack-data")]
    for case in cases:
        yield i2c_bench("B", image, case, machine_factory=make, pin_order=orders.get("i2c")), {}
    for offset in (-4, 0, 4):
        image = build_image("B", "overlap", spi_offset=offset)
        for step in range(16):
            phase = Fraction(step, 16)
            yield spi_bench("B", image, 0, True, machine_factory=make, uart_phase=phase,
                            spi_offset=offset, pin_order=orders.get("overlap")), {
                                "uart_phase": phase, "spi_offset": offset}


def replay(slots, epoch):
    make = partial(TimingProbe.from_image, slots=slots, epoch=epoch)
    for (case, machine, limit, verify), params in jobs(make):
        row, _ = measure(case, "B", machine, limit, verify)
        row.update(params, slots=slots, epoch=epoch, runnable_wait=machine.max_issue_wait,
                   blocked_cycles=machine.full_cycles, admission_slack=machine.admission_slack,
                   admitted=len(machine.admitted), retired=len(machine.retired),
                   captures=len(machine.capture_log))
        yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    results = []
    for slots, epoch in ((4, 0), (4, (1 << 24) - 500), (3, 0)):
        rows = list(replay(slots, epoch))
        results.extend(rows)
        misses = [(r["case"], r["errors"]) for r in rows if not r["pass"]]
        print(f"slots={slots}, epoch={epoch}: {len(rows) - len(misses)}/{len(rows)} passed")
        for case, errors in dict((case, tuple(errors)) for case, errors in misses).items():
            print(f"  {case}: {'; '.join(errors[:3])}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        rows = ",\n".join("  " + json.dumps(row, default=clock_json) for row in results)
        args.out.write_text(f"[\n{rows}\n]\n", encoding="utf-8")
    return int(any(not row["pass"] for row in results if row["slots"] == 4))


if __name__ == "__main__":
    raise SystemExit(main())
