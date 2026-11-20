"""Replay the 24-bit ARCH-B ISA prototype against the independent G3 monitors."""

import argparse
import json
from pathlib import Path

from .cycle import clock_json
from .g4_isa import ISAProbe, build
from .run_compare import measure
from .run_g4_timing import jobs


def replay(epoch):
    def make_image(arch, profile, mode=0, *, spi_offset=0):
        return build(profile, mode, spi_offset=spi_offset)

    def make_machine(arch, image, bus):
        machine = ISAProbe.from_image(arch, image, bus, epoch=epoch)
        machine.image_words = len(image.programs[0]) // 3
        return machine

    for (case, machine, limit, verify), params in jobs(make_machine, make_image):
        row, _ = measure(case, "B", machine, limit, verify)
        yield dict(row, **params, epoch=epoch, words=machine.image_words,
                   drive_slack=machine.admission_slack, sample_slack=machine.min_sample_slack,
                   blocked_cycles=machine.full_cycles, runnable_wait=machine.max_issue_wait)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    opts = parser.parse_args()
    rows = []
    for epoch in (0, (1 << 24) - 500):
        cases = list(replay(epoch))
        rows.extend(cases)
        print(f"epoch={epoch}: {sum(row['pass'] for row in cases)}/{len(cases)} passed")
        for group in ("spi-", "i2c-", "uart-"):
            passed = [row for row in cases if row["case"].startswith(group) and row["pass"]]
            if passed:
                print(group, "words", sorted({row["words"] for row in passed}),
                      "min drive/sample slack", min(row["drive_slack"] for row in passed),
                      min(row["sample_slack"] for row in passed))
        for case, errors in sorted({(row["case"], tuple(row["errors"])) for row in cases if not row["pass"]}):
            print(case, "; ".join(errors[:3]))
    if opts.out:
        opts.out.parent.mkdir(parents=True, exist_ok=True)
        lines = ",\n".join("  " + json.dumps(row, default=clock_json) for row in rows)
        opts.out.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
    return int(not all(row["pass"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
