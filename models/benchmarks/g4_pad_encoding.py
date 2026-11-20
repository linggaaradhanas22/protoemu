"""Compare compact and vector drive formats with the approved eight-pad map."""

import argparse
import json
from pathlib import Path

from .cycle import clock_json
from .encoded import NO_PIN, Image
from .g4_isa import PAD_DECODE, PAD_FORMATS, ISAProbe, assemble, source
from .run_compare import measure
from .run_g4_timing import jobs

OPTIONS = ("compact", "vector")
SPI_PINS = ("cs", "mosi", "miso", "sclk", "unused4", "unused5", "unused6", "unused7")
PIN_ORDERS = {
    "spi": SPI_PINS,
    "overlap": SPI_PINS[:6] + ("uart_rx", "unused7"),
    "i2c": tuple(f"unused{i}" for i in range(6)) + ("scl", "sda"),
}
VECTOR_SCRATCH = 7


class PadProbe(ISAProbe):
    decode_table = PAD_DECODE


def translate(lines, pins, option):
    for line in lines:
        if isinstance(line, str):
            yield line
            continue
        op, *args = line
        if op == "out":
            mask, values, delay = args
            updates = [(pin, (values >> i) & 1, 1) for i, pin in enumerate(pins) if mask & (1 << i)]
            if not updates:
                raise ValueError("empty pad mask")
            if option == "compact":
                for start in range(0, len(updates), 2):
                    pair = updates[start:start + 2]
                    yield "pad" if len(pair) == 1 else "pad2", *(x for p in pair for x in p), delay
            else:
                select = sum(1 << pin for pin, _, _ in updates)
                bits = sum(bit << pin for pin, bit, _ in updates)
                yield "set", VECTOR_SCRATCH, select | (bits << 8)
                yield "drivev", VECTOR_SCRATCH, select, delay
        elif op == "shift_out":
            reg, index, extra, level, delay = args
            if extra == NO_PIN:
                yield "shift_pin", reg, pins[index], delay
            else:
                yield "shift_pair", reg, pins[index], pins[extra], level, delay
        elif op in ("cap", "wait_save"):
            yield op, pins[args[0]], *args[1:]
        else:
            yield line


def build(profile, mode=0, *, spi_offset=0, option):
    if option not in OPTIONS:
        raise ValueError(f"unknown pad encoding: {option}")
    names = {"spi": ("cs", "sclk", "mosi", "miso"),
             "overlap": ("cs", "sclk", "mosi", "miso", "uart_rx"),
             "i2c": ("scl", "sda")}[profile]
    pins = tuple(PIN_ORDERS[profile].index(name) for name in names)
    lines, entries = source(profile, mode, spi_offset=spi_offset)
    code, labels = assemble(translate(lines, pins, option), formats=PAD_FORMATS)
    return Image((code,), tuple(labels[name] for name in entries), (b"",) * len(entries))


def replay(option, epoch):
    def make_image(arch, profile, mode=0, *, spi_offset=0):
        return build(profile, mode, spi_offset=spi_offset, option=option)

    def make_machine(arch, image, bus):
        machine = PadProbe.from_image(arch, image, bus, epoch=epoch)
        machine.image_words = len(image.programs[0]) // 3
        return machine

    for (case, machine, limit, verify), params in jobs(make_machine, make_image, pin_orders=PIN_ORDERS):
        row, _ = measure(case, "B", machine, limit, verify)
        yield dict(row, **params, option=option, epoch=epoch, words=machine.image_words,
                   executed_words=sum(kind == "fetch" for _, _, kind in machine.issue_log),
                   drive_slack=machine.admission_slack, sample_slack=machine.min_sample_slack,
                   blocked_cycles=machine.full_cycles)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    opts = parser.parse_args()
    rows = []
    for option in OPTIONS:
        for epoch in (0, (1 << 24) - 500):
            cases = list(replay(option, epoch))
            rows.extend(cases)
            print(f"{option}, epoch={epoch}: {sum(row['pass'] for row in cases)}/{len(cases)} passed")
            for group in ("spi-", "i2c-", "uart-"):
                subset = [row for row in cases if row["case"].startswith(group) and row["pass"]]
                if subset:
                    print(group, "words", sorted({r["words"] for r in subset}), "max executed",
                          max(r["executed_words"] for r in subset), "min drive/sample slack",
                          min(r["drive_slack"] for r in subset), min(r["sample_slack"] for r in subset))
            for case, errors in sorted({(row["case"], tuple(row["errors"])) for row in cases if not row["pass"]}):
                print(case, "; ".join(errors[:3]))
    if opts.out:
        opts.out.parent.mkdir(parents=True, exist_ok=True)
        lines = ",\n".join("  " + json.dumps(row, default=clock_json) for row in rows)
        opts.out.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
    return int(not all(row["pass"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
