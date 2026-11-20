"""Replay the baseline and non-target programs on the draft ISA (TASK-043, EVAL-016).

Every program is written in draft-ISA operations only. Payload comes from the
host through ``host_get`` and results go back through ``host_put``. Independent
peers and monitors from the G3 fixtures check the pins. Guards follow CHG-007.

One exploration operation, ``shift_lsb`` (prototype opcode 6), is used only by
the ``lsb`` UART TX variant. It is not part of the draft ISA.
"""

import argparse
import json
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from .cycle import Pins, clock_json
from .encoded import Image
from .flex import PIXELS, OneWirePeer, onewire_check, ws_check
from .g4_edges import FORMATS as EDGE_FORMATS
from .g4_edges import HALF_PERIODS, EdgeProbe
from .g4_edges import run_case as rc5_case
from .g4_isa import MASK, assemble
from .g4_payload import drain, prepare
from .g4_payload import run_case as overlap_case
from .i2c_fixture import I2CCase, I2CPeer, i2c_check
from .run_encoded import words_to_bytes
from .spi_uart import (RX as SPI_RX, TX as SPI_TX, UART_RATES, UART_RX, UART_TX, SPIPeer, spi_check,
                       uart_rx_check, uart_stimulus, uart_tx_check)

FORMATS = {op: fmt for op, fmt in EDGE_FORMATS.items() if op not in ("out", "shift_out")}
PROTO_FORMATS = dict(FORMATS, shift_lsb=(6, (3, 3, 9)))
DECODE = {code: (op, widths) for op, (code, widths) in PROTO_FORMATS.items()}
WRAP = MASK - 2000  # Epoch that wraps the timer early in each run.
MAX_ADDOFF = (1 << 14) - 1


class SuiteProbe(EdgeProbe):
    decode_table = DECODE


def advance(cycles):
    """Split an offset step into addoff immediates (signed 15-bit)."""
    lines = []
    while cycles > MAX_ADDOFF:
        lines.append(("addoff", MAX_ADDOFF))
        cycles -= MAX_ADDOFF
    if cycles:
        lines.append(("addoff", cycles))
    return lines


def pins_for(names, idle):
    """Eight uio pads; ``names`` maps a pad index to a protocol pin."""
    return {names.get(i, f"unused{i}"): idle.get(names.get(i), 0) for i in range(8)}


def bit_reverse(byte):
    return int(f"{byte:08b}"[::-1], 2)


def execute(lines, ingress, bus, epoch, *, formats=FORMATS):
    code, _ = assemble(lines, formats=formats)
    image = Image((code,), (0,), (b"",))
    endpoint, link = prepare(image, (tuple(ingress),), enabled=1, owner1=0)
    fetched = b"".join(endpoint.fetch(pc) for pc in range(endpoint.cfg.count))
    probe = SuiteProbe.from_image("B", Image((fetched,), (0,), (b"",)), bus, epoch=epoch, endpoint=endpoint)
    return probe, endpoint, link, len(code) // 3


def outcome(name, params, probe, words, errors, margin):
    return {"case": name, **params, "pass": not errors, "errors": errors[:3], "words": words,
            "min_margin": margin, "drive_slack": probe.admission_slack, "sample_slack": probe.min_sample_slack,
            "end_cycle": getattr(probe, "end", None)}


def run(probe, limit):
    try:
        probe.end = probe.run(limit)
        return None
    except Exception as exc:  # ModelError or a timeout: report as a failed case.
        probe.end = None
        return f"{type(exc).__name__}: {exc}"


# UART receive: count from the host, one received byte per host_put.
def uart_rx_program(period):
    rx = 6
    first, step = round(Fraction(3, 2) * period), round(period)
    return [("host_get", 5), "next", ("wait_save", rx, 0, 0), ("set", 1, 0), *advance(first), ("set", 4, 8),
            "bit", ("cap", rx, 1, 2, 0), *advance(step), ("loop", 4, "bit"),
            ("cap", rx, 2, 0, 0), ("jnz", 2, "good"),
            ("set", 2, 0x100), ("host_put", 2), ("halt",),
            "good", ("host_put", 1), ("loop", 5, "next"), ("halt",)]


def uart_rx_case(baud, error_pct, phase, epoch):
    period = Fraction(60_000_000) / (baud * (1 + Fraction(error_pct) / 100))
    bus = Pins(pins_for({6: "uart_rx"}, {"uart_rx": 1}))
    start = 1000 + Fraction(phase, 16)
    uart_stimulus(bus, start, period, UART_RX)
    probe, endpoint, link, words = execute(uart_rx_program(Fraction(60_000_000, baud)), [len(UART_RX)], bus, epoch)
    failure = run(probe, int(start + 70 * period) + 10_000)
    got = drain(endpoint, link, 0)
    view = SimpleNamespace(report={"uart_rx": [w for w in got if w < 256], "uart_error": [w for w in got if w >= 256]},
                           samples=probe.samples)
    errors, margin = ([failure], None) if failure else uart_rx_check(view, UART_RX, start, period)
    return outcome(f"uart-rx-{baud}", {"error_pct": error_pct, "phase": phase, "epoch": epoch},
                   probe, words, errors, margin)


# UART transmit: count + bytes from the host; start, 8 data bits LSB first, stop.
def uart_tx_program(period, variant):
    tx, step = 5, round(period)
    shift = ("shift_lsb", 1, tx, 0) if variant == "lsb" else ("shift_pin", 1, tx, 0)
    return [("host_get", 5), ("save_now",), *advance(64), "frame", ("host_get", 1),
            ("pad", tx, 0, 1, 0), *advance(step), ("set", 4, 8),
            "bit", shift, *advance(step), ("loop", 4, "bit"),
            ("pad", tx, 1, 1, 0), *advance(step), ("loop", 5, "frame"), ("fence", 0), ("halt",)]


def uart_tx_case(baud, variant, epoch):
    period = Fraction(60_000_000, baud)
    bus = Pins(pins_for({5: "uart_tx"}, {"uart_tx": 1}))
    data = [b if variant == "lsb" else bit_reverse(b) << 8 for b in UART_TX]
    probe, *_, words = execute(uart_tx_program(period, variant), [len(data), *data], bus, epoch,
                               formats=PROTO_FORMATS)
    failure = run(probe, int(60 * period) + 10_000)
    edges = [t for t, name, _ in bus.edges if name == "uart_tx"]
    errors, margin = ([failure], None) if failure else uart_tx_check(bus, probe.end, baud, edges[0] if edges else None)
    return outcome(f"uart-tx-{baud}", {"variant": variant, "epoch": epoch}, probe, words, errors, margin)


# SPI controller: one 16-bit exchange per word from the host.
SPI_PADS = {0: "cs", 1: "mosi", 2: "miso", 3: "sclk"}
CS, MOSI, MISO, SCLK = 0, 1, 2, 3


def spi_program(mode, half):
    idle, late = divmod(mode, 2)
    phase0 = 1 - idle if late else idle
    lines = [("host_get", 1), ("save_now",), ("set", 2, 0), ("set", 4, 16), ("pad", CS, 0, 1, 16),
             *advance(16 + 16 + half * late),
             "bit", ("shift_pair", 1, MOSI, SCLK, phase0, 0), ("pad", SCLK, 1 - phase0, 1, half),
             ("cap", MISO, 2, 1, half + 3), *advance(2 * half), ("loop", 4, "bit")]
    if not late:
        lines.append(("pad", SCLK, idle, 1, 0))
    return lines + [("pad", CS, 1, 1, 8), ("fence", 9), ("host_put", 2), ("halt",)]


def spi_case(mode, khz, epoch):
    half = 30_000 // khz
    bus = Pins(pins_for(SPI_PADS, {"cs": 1, "sclk": mode // 2}), peer=SPIPeer(mode, half))
    tx_word = (SPI_TX[0] << 8) | SPI_TX[1]
    probe, endpoint, link, words = execute(spi_program(mode, half), [tx_word], bus, epoch)
    failure = run(probe, 20 * 2 * half + 5_000)
    starts = [t for t, name, v in bus.edges if name == "cs" and v == 0]
    if failure:
        errors, margin = [failure], None
    else:
        errors, margin, _ = spi_check(bus, words_to_bytes(drain(endpoint, link, 0)), mode, half, starts)
        if len(starts) != 1:
            errors.append("expected one CS assertion")
    return outcome(f"spi-{khz}k-mode{mode}", {"epoch": epoch}, probe, words, errors, margin)


# I2C controller: address in the image, write data from the host, read data and status back.
SCL, SDA = 6, 7


def i2c_program(fast, variant):
    low, high, hold, setup = (94, 56, 48, 20) if fast else (310, 300, 255, 20)
    restart_gap, bus_free = (48, 90) if fast else (300, 300)
    TX, RX, N, FLAG = 1, 2, 4, 3

    def put(pin, value, delay=0):
        return ("pad", pin, value, 1, delay)

    lines = [("host_get", TX), ("save_now",), *advance(16), ("set", RX, 0), ("set", FLAG, 0),
             ("call", "start"), ("set", 5, 0xA000), ("call", "write5"), ("jnz", FLAG, "finish"),
             ("call", "write"), ("jnz", FLAG, "finish"), ("call", "write"), ("jnz", FLAG, "finish")]
    if variant == "separate":
        # The STOP edge is `hold` after the observed SCL rise; count bus free from it.
        lines += [("call", "stop"), *advance(hold + bus_free), ("call", "start")]
    else:
        lines += [put(SDA, 1, setup), ("call", "rise"), *advance(restart_gap), ("call", "start")]
    lines += [("set", 5, 0xA100), ("call", "write5"), ("jnz", FLAG, "finish"),
              ("call", "read"), put(SDA, 0, setup), ("call", "rise"), ("call", "fall"),
              ("call", "read"), put(SDA, 1, setup), ("call", "rise"), ("call", "fall"),
              ("host_put", RX),
              "finish", ("call", "stop"), ("host_put", FLAG), ("halt",),
              "start", put(SDA, 0), put(SCL, 0, hold), *advance(hold), ("ret",),
              "stop", put(SDA, 0, setup), ("call", "rise"), put(SDA, 1, hold), ("fence", hold + 1), ("ret",),
              "rise", put(SCL, 1, low), ("wait_save", SCL, 1, low), ("ret",),
              "fall", put(SCL, 0, high), *advance(high), ("ret",),
              # write5 sends the address byte from R5; write sends the next byte of TX.
              "write5", ("set", N, 8), "w5bit", ("shift_pin", 5, SDA, setup), ("call", "rise"), ("call", "fall"),
              ("loop", N, "w5bit"), ("jump", "ack"),
              "write", ("set", N, 8), "wbit", ("shift_pin", TX, SDA, setup), ("call", "rise"), ("call", "fall"),
              ("loop", N, "wbit"),
              "ack", put(SDA, 1, setup), ("call", "rise"), ("cap", SDA, FLAG, 0, 14), ("call", "fall"), ("ret",),
              "read", ("set", N, 8), "rbit", put(SDA, 1, setup), ("call", "rise"), ("cap", SDA, RX, 1, 14),
              ("call", "fall"), ("loop", N, "rbit"), ("ret",)]
    return lines


def i2c_case(case, epoch):
    bus = Pins(pins_for({SCL: "scl", SDA: "sda"}, {"scl": 1, "sda": 1}), open_drain=("scl", "sda"),
               peer=I2CPeer(case))
    data = (0x96 << 8) | 0x4B
    probe, endpoint, link, words = execute(i2c_program(case.fast, case.variant), [data], bus, epoch)
    failure = run(probe, 80_000)
    if failure:
        errors, margin = [failure], None
    else:
        got = drain(endpoint, link, 0)
        ok = bool(got) and got[-1] == 0
        report = {"i2c_ok": [ok] if got else [], "i2c_rx": words_to_bytes(got[:-1]) if ok else []}
        errors, margin = i2c_check(bus, report, case)
    return outcome(case.name, {"epoch": epoch}, probe, words, errors, margin)


# WS2812: pixel words from the host, MSB first; data-dependent pulse width with shift_pin.
WS = 0


def ws_program():
    return [("host_get", 5), ("save_now",), *advance(16), "word", ("host_get", 1), ("set", 4, 16),
            "bit", ("pad", WS, 1, 1, 0), ("shift_pin", 1, WS, 18), ("pad", WS, 0, 1, 51), *advance(75),
            ("loop", 4, "bit"), ("loop", 5, "word"), *advance(18_000), ("fence", 0), ("halt",)]


def ws_case(epoch):
    bus = Pins(pins_for({WS: "ws"}, {}))
    pixel_words = [(PIXELS[i] << 8) | PIXELS[i + 1] for i in range(0, len(PIXELS), 2)]
    probe, *_, words = execute(ws_program(), [len(pixel_words), *pixel_words], bus, epoch)
    failure = run(probe, 40_000)
    errors, margin = ([failure], None) if failure else ws_check(bus, probe.end)
    return outcome("ws2812", {"epoch": epoch}, probe, words, errors, margin)


# 1-Wire: reset, presence, READ ROM (0x33, LSB first), then 64 bits back as 8 bytes.
# Presence is sampled 70 us after release, as 1-Wire masters do, so a missing
# device gives an error word instead of an endless wait.
WIRE = 0
NO_DEVICE = 0xFFFF


def onewire_program():
    lines = [("save_now",), *advance(16), ("pad", WIRE, 0, 1, 0), *advance(30_000), ("pad", WIRE, 1, 1, 0),
             *advance(4200 - 456), ("cap", WIRE, 3, 0, 456), ("jnz", 3, "absent"), *advance(30_000 - 4200 + 456),
             ("set", 1, bit_reverse(0x33) << 8), ("set", 4, 8),
             # A 0 bit holds the bus low for 65 us (minimum 60 us); a 1 bit releases it after 6 us.
             "cmd", ("pad", WIRE, 0, 1, 0), ("shift_pin", 1, WIRE, 360), *advance(3900), ("pad", WIRE, 1, 1, 0),
             *advance(300), ("loop", 4, "cmd"),
             ("set", 5, 8), "byte", ("set", 2, 0), ("set", 4, 8),
             # The cap immediate is 9 bits, so the read sample 840 cycles in is 384 + 456.
             "rbit", ("pad", WIRE, 0, 1, 0), ("pad", WIRE, 1, 1, 360), *advance(384), ("cap", WIRE, 2, 2, 456),
             *advance(4200 - 384), ("loop", 4, "rbit"), ("host_put", 2), ("loop", 5, "byte"), ("halt",),
             "absent", ("set", 2, NO_DEVICE), ("host_put", 2), ("halt",)]
    return lines


def onewire_case(delayed, epoch, *, device=True):
    peer = OneWirePeer(delayed) if device else None
    bus = Pins(pins_for({WIRE: "wire"}, {"wire": 1}), open_drain=("wire",), peer=peer)
    probe, endpoint, link, words = execute(onewire_program(), [], bus, epoch)
    failure = run(probe, 700_000)
    got = drain(endpoint, link, 0)
    name = "onewire" + ("-delayed" if delayed else "") + ("" if device else "-absent")
    if failure:
        errors, margin = [failure], None
    elif not device:
        errors, margin = ([] if got == [NO_DEVICE] else [f"expected the no-device word, got {got}"]), None
    else:
        # The first sample is the presence check; onewire_check counts only the 64 ROM samples.
        presence, *rom = probe.samples
        view = SimpleNamespace(bus=bus, samples=rom,
                               report={"wire_presence": [presence[0]] if presence[2] == 0 else [], "wire_rom": [got]})
        errors, margin = onewire_check(view, delayed)
    return outcome(name, {"epoch": epoch}, probe, words, errors, margin)


def suite():
    rows = []
    for epoch in (0, WRAP):
        for baud in UART_RATES:
            rows += [uart_tx_case(baud, variant, epoch) for variant in ("host-reversed", "lsb")]
        for mode in range(4):
            rows += [spi_case(mode, khz, epoch) for khz in (100, 1000)]
        for fast in (False, True):
            cases = [I2CCase(v, fast) for v in ("separate", "combined", "nack-address", "nack-data")]
            cases += [I2CCase("combined", fast, stretch) for stretch in (60, 300, 600)]
            rows += [i2c_case(case, epoch) for case in cases]
        rows.append(ws_case(epoch))
        rows += [onewire_case(delayed, epoch) for delayed in (False, True)]
        rows.append(onewire_case(False, epoch, device=False))
        rows += [uart_rx_case(baud, 0, phase, epoch) for baud in UART_RATES for phase in range(0, 16, 5)]
    # Full TEST-SYS-005 sweep at epoch 0: nine baud errors and sixteen start phases.
    for baud in UART_RATES:
        for error in (-2, -1.5, -1, -0.5, 0.5, 1, 1.5, 2):
            rows += [uart_rx_case(baud, Fraction(error).limit_denominator(4), phase, 0) for phase in range(16)]
        rows += [uart_rx_case(baud, 0, phase, 0) for phase in range(16) if phase % 5]
    for half in HALF_PERIODS:
        for wrap in (False, True):
            row = rc5_case(half, wrap)
            rows.append({"case": row["case"], "epoch": row["epoch"], "pass": row["pass"], "errors": row["errors"][:3],
                         "words": row["words"], "min_margin": row["min_margin"], "drive_slack": None,
                         "sample_slack": row["sample_slack"], "end_cycle": row["end_cycle"]})
    for epoch in (0, (1 << 24) - 500):
        for offset in (-4, 0, 4):
            for phase in range(16):
                row = overlap_case(epoch, offset, Fraction(phase, 16))
                rows.append({"case": "uart-spi-overlap", "epoch": epoch, "spi_offset": offset, "phase": phase,
                             "pass": row["pass"], "errors": row["errors"][:3], "words": row["words"],
                             "min_margin": row["min_margin"], "drive_slack": row["drive_slack"],
                             "sample_slack": row["sample_slack"], "end_cycle": row["end_cycle"]})
    return rows


def summarize(rows):
    groups = {}
    for row in rows:
        key = row["case"] + (f" ({row['variant']})" if "variant" in row else "")
        groups.setdefault(key, []).append(row)
    table = []
    for key, items in groups.items():
        margins = [r["min_margin"][0] for r in items if r["min_margin"]]
        slack = [r[k] for r in items for k in ("drive_slack", "sample_slack") if r.get(k) is not None]
        table.append({"group": key, "cases": len(items), "passed": sum(r["pass"] for r in items),
                      "words": sorted({r["words"] for r in items}),
                      "min_monitor_margin": min(margins, default=None), "min_issue_slack": min(slack, default=None),
                      "errors": sorted({e for r in items for e in r["errors"]})[:3]})
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = suite()
    table = summarize(rows)
    for row in table:
        print(f"{row['group']:34s} {row['passed']:4d}/{row['cases']:<4d} words {row['words']} "
              f"margin {row['min_monitor_margin']} slack {row['min_issue_slack']} {row['errors'][:1]}")
    print(f"total {sum(r['pass'] for r in rows)}/{len(rows)}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"summary": table, "rows": rows}, default=clock_json, indent=1) + "\n",
                            encoding="utf-8")
    return int(not all(row["pass"] for row in rows if row.get("variant") != "lsb"))


if __name__ == "__main__":
    raise SystemExit(main())
