"""Build and run the encoded G3 cases; optionally archive images and traces."""

import argparse
import gzip
import json
from fractions import Fraction
from pathlib import Path

from .cycle import Pins, clock_json
from .encoded import STORES, EncodedMachine
from .encoded_programs import build
from .i2c_fixture import I2CCase, I2CPeer, i2c_check
from .run_compare import measure
from .spi_uart import OVERLAP_RX, SPIPeer, spi_check, uart_rx_check, uart_stimulus


def words_to_bytes(values):
    return [[word >> 8, word & 255] for word in values]


def spi_bench(arch, image, mode, concurrent, *, machine_factory=EncodedMachine,
              uart_phase=0, spi_offset=0, pin_order=None):
    pins = {"cs": 1, "sclk": mode // 2, "mosi": 0, "miso": 0}
    if concurrent:
        pins["uart_rx"] = 1
    if pin_order is not None:
        pins = {pin: pins.get(pin, 0) for pin in pin_order}
    bus = Pins(pins, peer=SPIPeer(mode, 30))
    starts = [32]
    if concurrent:
        starts = [360 + spi_offset, 5550 + spi_offset]
        period = Fraction(3125, 6)
        uart_end, uart_edges = uart_stimulus(bus, uart_phase, period, OVERLAP_RX)

    def verify(machine, _):
        rx = words_to_bytes(machine.report.get("spi_rx_word", []))
        errors, margin, spans = spi_check(machine.bus, rx, mode, 30, starts)
        if concurrent:
            rx_errors, rx_margin = uart_rx_check(machine, OVERLAP_RX, uart_phase, period)
            errors.extend(rx_errors)
            margin = min(filter(None, (margin, rx_margin)), default=None)
            for start, end in spans:
                if not (0 <= start < end <= uart_end and any(start < t < end for t in uart_edges)):
                    errors.append(f"SPI span {start}..{end} does not cross a UART transition")
        return errors, margin

    name = "uart-spi-overlap" if concurrent else f"spi-1mhz-mode{mode}"
    return name, machine_factory(arch, image, bus), 20_000, verify


def i2c_bench(arch, image, case, *, machine_factory=EncodedMachine, pin_order=None):
    pins = {"scl": 1, "sda": 1}
    if pin_order is not None:
        pins = {pin: pins.get(pin, 0) for pin in pin_order}
    bus = Pins(pins, open_drain=("scl", "sda"), peer=I2CPeer(case))

    def verify(machine, _):
        report = machine.report
        unpacked = {"i2c_ok": [not value for value in report.get("i2c_nack", [])],
                    "i2c_rx": words_to_bytes(report.get("i2c_rx_word", []))}
        return i2c_check(machine.bus, unpacked, case)

    return case.name, machine_factory(arch, image, bus), 15_000, verify


def run_arch(arch, save=None):
    jobs = []
    for mode in range(4):
        image_id = f"spi-mode{mode}"
        image = build(arch, "spi", mode)
        jobs.append((image_id, image, spi_bench(arch, image, mode, False)))
    image = build(arch, "overlap")
    jobs.append(("overlap", image, spi_bench(arch, image, 0, True)))
    image = build(arch, "i2c")
    cases = [I2CCase("combined", True, stretch) for stretch in (0, 60, 300, 600)]
    cases.extend(I2CCase(variant, True) for variant in ("nack-address", "nack-data"))
    jobs.extend(("i2c", image, i2c_bench(arch, image, case)) for case in cases)
    for image_id, image, (name, machine, limit, verify) in jobs:
        row, trace = measure(name, arch, machine, limit, verify)
        width, depth = STORES[arch]
        row.update(image=image_id, program_words=[len(bank) // width for bank in image.programs],
                   program_limit_words=depth, program_bytes=sum(map(len, image.programs)),
                   lane_words=[len(bank) // 3 for bank in image.lanes],
                   descriptor_bytes=sum(map(len, image.lanes)), entries=image.entries,
                   slot_counts=machine.slot_counts)
        if save:
            for kind, banks in (("code", image.programs), ("lane", image.lanes)):
                for i, binary in enumerate(banks):
                    if binary:
                        (save / f"{arch}-{image_id}-{kind}{i}.hex").write_text(binary.hex() + "\n", encoding="ascii")
        yield row, {"arch": arch, "case": name, **trace}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices="ABC", action="append")
    parser.add_argument("--out", type=Path)
    flags = parser.parse_args()
    binaries = flags.out / "images" if flags.out else None
    if binaries:
        binaries.mkdir(parents=True, exist_ok=True)
    results, traces = [], []
    for arch in flags.arch or "ABC":
        for row, trace in run_arch(arch, binaries):
            results.append(row)
            traces.append(trace)
            if not row["pass"]:
                print(arch, row["case"], "; ".join(row["errors"][:4]))
    if flags.out:
        (flags.out / "results.json").write_text(json.dumps(results, indent=2, default=clock_json) + "\n", encoding="utf-8")
        lines = "\n".join(json.dumps(row, default=clock_json, separators=(",", ":")) for row in traces) + "\n"
        (flags.out / "traces.jsonl.gz").write_bytes(gzip.compress(lines.encode(), mtime=0))
    passed = sum(row["pass"] for row in results)
    print(f"EVAL-001 encoded comparison: {passed}/{len(results)} cases passed")
    return int(passed != len(results))


if __name__ == "__main__":
    raise SystemExit(main())
