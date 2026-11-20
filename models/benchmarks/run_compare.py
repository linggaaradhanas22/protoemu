"""Run the G3 comparison cases and save reproducible pin-level evidence."""

import argparse
import gzip
import json
from fractions import Fraction
from pathlib import Path

from .cycle import Machine, ModelError, Pins, clock_json
from .flex import (
    OneWirePeer, onewire_check, onewire_program, rc5_check, rc5_program, rc5_stimulus,
    ws_check, ws_program,
)
from .i2c_fixture import I2CCase, I2CPeer, i2c_check, i2c_program
from .spi_uart import (
    OVERLAP_RX, UART_RATES, UART_RX, SPIPeer, spi_check, spi_program,
    uart_receive, uart_rx_check, uart_stimulus, uart_transmit, uart_tx_check,
)


def measure(name, arch, machine, limit, verify):
    try:
        end = machine.run(limit)
    except ModelError as exc:
        end = None
        errors, margin = [str(exc)], None
    else:
        errors, margin = verify(machine, end)
    return {
        "case": name, "arch": arch, "pass": not errors, "errors": errors,
        "min_margin": margin, "end_cycle": end, "pins": list(machine.bus.idle),
        "payload": machine.report, "issued_ops": machine.issue,
        "resources_peak": machine.hi,
    }, {"idle": machine.bus.idle, "resolved_edges": machine.bus.edges, "drive_edges": machine.bus.raw,
        "samples": machine.samples, "emits": machine.emits}


def spi_case(arch, mode, half, concurrent=False):
    pins = {"cs": 1, "sclk": mode // 2, "mosi": 0, "miso": 0}
    if concurrent:
        pins["uart_rx"] = 1
    bus = Pins(pins, peer=SPIPeer(mode, half))
    programs = []
    starts = [32]
    if concurrent:
        starts = [360, 5550]
        uart_end, uart_edges = uart_stimulus(bus, 0, Fraction(3125, 6), OVERLAP_RX)
        programs.append(uart_receive(arch, len(OVERLAP_RX), 521))
    programs.append(spi_program(arch, starts, mode, half))

    def verify(machine, end):
        errors, margin, spans = spi_check(machine.bus, machine.report.get("spi_rx"), mode, half, starts)
        if concurrent:
            rx_errors, rx_margin = uart_rx_check(machine, OVERLAP_RX, 0, Fraction(3125, 6))
            errors.extend(rx_errors)
            margin = min(filter(None, (margin, rx_margin)), default=None)
            for start, end in spans:
                if not (0 <= start < end <= uart_end
                        and any(start < edge < end for edge in uart_edges)):
                    errors.append(f"SPI span {start}..{end} does not overlap an RX transition")
        return errors, margin

    name = "uart-spi-overlap" if concurrent else f"spi-{60_000_000 // (2 * half)}-mode{mode}"
    return measure(name, arch, Machine(arch, programs, bus), 20_000, verify)


def i2c_case(arch, case):
    bus = Pins({"scl": 1, "sda": 1}, open_drain=("scl", "sda"), peer=I2CPeer(case))
    return measure(case.name, arch, Machine(arch, [i2c_program(case)], bus), 50_000,
                   lambda m, _: i2c_check(m.bus, m.report, case))


def uart_cases(arch):
    for baud in UART_RATES:
        nominal = Fraction(60_000_000, baud)
        bus = Pins({"uart_tx": 1})
        yield measure(f"uart-tx-{baud}", arch, Machine(arch, [uart_transmit(arch, baud, 16)], bus),
                      16 + 51 * round(nominal), lambda m, end: uart_tx_check(m.bus, end, baud, 16))
        for error in range(-4, 5):
            peer_period = nominal / (1 + Fraction(error, 200))
            for phase in range(16):
                start = 16 + Fraction(phase, 16)
                bus = Pins({"uart_rx": 1})
                end, _ = uart_stimulus(bus, start, peer_period, UART_RX)
                machine = Machine(arch, [uart_receive(arch, len(UART_RX), round(nominal))], bus)
                yield measure(f"uart-rx-{baud}-e{error:+d}-p{phase:02d}", arch, machine,
                              round(end + nominal), lambda m, _: uart_rx_check(m, UART_RX, start, peer_period))


def run_all(arches, *, first_only=False):
    for arch in arches:
        for half in (30, 300):
            for mode in range(4):
                yield spi_case(arch, mode, half)
        for fast in (True, False):
            for stretch in (60, 300, 600):
                yield i2c_case(arch, I2CCase("combined", fast, stretch))
            for variant in ("combined", "separate", "nack-address", "nack-data"):
                yield i2c_case(arch, I2CCase(variant, fast))
        yield spi_case(arch, 0, 30, concurrent=True)
        if not first_only:
            yield from uart_cases(arch)
            yield from flex_cases(arch)


def flex_cases(arch):
    bus = Pins({"ws": 0})
    yield measure("ws2812", arch, Machine(arch, [ws_program(arch)], bus), 25_000,
                  lambda m, end: ws_check(m.bus, end))
    for delayed in (False, True):
        bus = Pins({"wire": 1}, open_drain=("wire",), peer=OneWirePeer(delayed))
        name = "1-wire-delayed" if delayed else "1-wire-nominal"
        yield measure(name, arch, Machine(arch, [onewire_program()], bus), 400_000,
                      lambda m, _: onewire_check(m, delayed))
    for half in (50_673, 53_340, 56_007):
        bus = Pins({"rc5": 1})
        starts = rc5_stimulus(bus, half)
        yield measure(f"rc5-{half}", arch, Machine(arch, [rc5_program(arch)], bus), 16_000_000,
                      lambda m, _: rc5_check(m, starts, half))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices="ABC", action="append")
    parser.add_argument("--first-only", action="store_true", help="SPI, I2C, and overlap only")
    parser.add_argument("--out", type=Path, help="write compressed JSONL results and pin traces")
    args = parser.parse_args()
    rows, traces = [], []
    for row, trace in run_all(args.arch or "ABC", first_only=args.first_only):
        rows.append(row)
        traces.append({"arch": row["arch"], "case": row["case"], **trace})
        if not row["pass"]:
            print(row["arch"], row["case"], "; ".join(row["errors"][:5]))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for name, data in (("results", rows), ("traces", traces)):
            text = "\n".join(json.dumps(line, default=clock_json, separators=(",", ":")) for line in data) + "\n"
            (args.out / f"{name}.jsonl.gz").write_bytes(gzip.compress(text.encode(), mtime=0))
    passed = sum(row["pass"] for row in rows)
    print(f"EVAL-001 exploratory comparison: {passed}/{len(rows)} cases passed")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
