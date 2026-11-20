"""Open-drain I2C controller stimulus, reactive target, and trace checks."""

from dataclasses import dataclass
from itertools import groupby

from .cycle import Emit, Level, Out, Peer, Sample, as_bits, as_bytes, window


WRITE = (0x96, 0x4B)
READ = (0x3A, 0xD2)
ADDRESS = 0x50


@dataclass(frozen=True)
class I2CCase:
    variant: str
    fast: bool
    stretch: int = 0

    @property
    def name(self):
        rate = "400k" if self.fast else "100k"
        return f"i2c-{rate}-{self.variant}" + (f"-{self.stretch}clk" if self.stretch else "")


class I2CPeer(Peer):
    def __init__(self, case):
        self.case = case
        self.mode = "off"
        self.segment = 0
        self.nedges = 0
        self.i = self.word = self.byte_index = 0
        self.ack = False
        self.response = tuple(as_bits((b,)) for b in READ)

    def before_dut(self, bus, at, updates):
        if (self.case.stretch and self.segment == 1 and self.nedges in (9, 17)
                and bus.drive["dut"].get("scl") == 0 and "scl" in updates and updates["scl"] is None):
            bus.external(at + self.case.stretch, {"scl": None})
            return {"scl": 0}
        return {}

    def observe(self, bus, at, changes):
        if "sda" in changes and bus.level["scl"] == 1 and "scl" not in changes:
            if changes["sda"] == 0:
                self.segment += 1
                self.mode = "address"
                self.nedges = self.i = self.word = self.byte_index = 0
                self.ack = False
            else:
                self.mode = "off"
            return
        if changes.get("scl") == 1:
            self.nedges += 1
            if self.mode in ("address", "write"):
                if self.i < 8:
                    self.word = (self.word << 1) | bus.level["sda"]
                    self.i += 1
                    if self.i == 8:
                        if self.mode == "address":
                            self.ack = self.word >> 1 == ADDRESS and self.case.variant != "nack-address"
                        else:
                            self.ack = not (self.case.variant == "nack-data" and self.byte_index == 0)
                else:
                    if not self.ack:
                        self.mode = "off"
                    elif self.mode == "address":
                        self.mode = "read" if self.word & 1 else "write"
                    else:
                        self.byte_index += 1
                    self.i = self.word = 0
            elif self.mode == "read":
                if self.i < 8:
                    self.i += 1
                else:
                    self.byte_index += 1
                    self.i = 0
                    if bus.level["sda"] or self.byte_index == len(self.response):
                        self.mode = "off"
        elif changes.get("scl") == 0:
            low = ((self.mode in ("address", "write") and self.i == 8 and self.ack)
                   or (self.mode == "read" and self.i < 8 and not self.response[self.byte_index][self.i]))
            bus.external(at + 1, {"sda": 0 if low else None})


def i2c_program(case):
    low_period, high_period = (94, 56) if case.fast else (310, 300)
    start_hold, bus_free, setup = (48, 90, 8) if case.fast else (255, 300, 20)

    def start(at):
        yield Out(at, {"sda": 0})
        fall = at + start_hold
        yield Out(fall, {"scl": 0})
        return fall

    def rise(fall, bit):
        yield Out(fall + setup, {"sda": None if bit else 0})
        release = fall + low_period
        yield Out(release, {"scl": None})
        return (yield Level(release, "scl", 1))

    def wire_bit(fall, bit):
        seen = yield from rise(fall, bit)
        got = yield Sample(seen + 4, "sda")
        next_fall = seen + high_period
        yield Out(next_fall, {"scl": 0})
        return next_fall, got

    def write(fall, byte):
        for bit in as_bits((byte,)):
            fall, _ = yield from wire_bit(fall, bit)
        return (yield from wire_bit(fall, 1))  # release SDA for ACK

    def stop(fall):
        seen = yield from rise(fall, 0)
        at = seen + start_hold
        yield Out(at, {"sda": None})
        return at

    fall = yield from start(16)
    for value in (ADDRESS << 1, *WRITE):
        fall, nack = yield from write(fall, value)
        if nack:
            yield from stop(fall)
            yield Emit("i2c_ok", False)
            return
    if case.variant == "separate":
        end = yield from stop(fall)
        fall = yield from start(end + bus_free)
    else:
        seen = yield from rise(fall, 1)
        fall = yield from start(seen + (48 if case.fast else 300))
    fall, nack = yield from write(fall, (ADDRESS << 1) | 1)
    if nack:
        yield from stop(fall)
        yield Emit("i2c_ok", False)
        return
    result = []
    for index in range(2):
        bits = []
        for _ in range(8):
            fall, got = yield from wire_bit(fall, 1)
            bits.append(got)
        result.extend(as_bytes(bits))
        fall, _ = yield from wire_bit(fall, int(index == 1))
    yield from stop(fall)
    yield Emit("i2c_rx", result)
    yield Emit("i2c_ok", True)


def i2c_check(bus, report, case):
    if case.variant == "nack-address":
        expected = [[(0xA0, 1)]]
    elif case.variant == "nack-data":
        expected = [[(0xA0, 0), (0x96, 1)]]
    else:
        expected = [[(0xA0, 0), (0x96, 0), (0x4B, 0)], [(0xA1, 0), (0x3A, 0), (0xD2, 1)]]
    ok = not case.variant.startswith("nack")
    events_wanted = ["START", "STOP"]
    if ok:
        events_wanted = ["START", "STOP", "START", "STOP"] if case.variant == "separate" else ["START", "RESTART", "STOP"]
    fast = case.fast
    bit_min, bit_max = (150, 157) if fast else (600, 631)
    low_min, high_min = (78, 36) if fast else (282, 240)
    setup_min = 6 if fast else 15
    restart_min = 36 if fast else 282
    errors, margins, segments, delimiters = [], [], [], []
    pin = bus.idle.copy()
    active = False
    last_fall = last_rise = last_start = last_stop = pending = None
    last_data = 0
    words = []
    stretch_holds = []
    hold = None
    for at, side, name, value in bus.raw:
        if side == "dut" and name in ("scl", "sda") and value not in (0, None):
            errors.append(f"at {at}: DUT actively drove {name} high")
        if side == "peer" and name == "scl":
            if value == 0:
                hold = at
            elif value is None and hold is not None:
                stretch_holds.append((hold, at))
                hold = None

    def check(label, at, actual, lower, upper=None):
        margin = window(actual, lower, upper)
        margins.append((margin, at, label))
        if margin < 0:
            errors.append(f"at {at}: {label} of {actual} clocks violates {lower}..{upper}")

    for at, group in groupby(bus.edges, key=lambda edge: edge[0]):
        changes = {name: value for _, name, value in group}
        pin.update(changes)
        if "sda" in changes:
            last_data = at
        if "sda" in changes and "scl" in changes:
            errors.append(f"at {at}: SDA and SCL changed together")
        if "sda" in changes and pin["scl"] == 1 and "scl" not in changes:
            kind = ("RESTART" if active else "START") if pin["sda"] == 0 else "STOP"
            delimiters.append(kind)
            if active:
                segments.append(words)
                if pending is None:
                    errors.append(f"at {at}: missing SCL rise before {kind}")
                else:
                    check(f"{kind} setup", at, at - pending[0], restart_min if kind == "RESTART" else high_min)
                    if last_fall is not None:
                        check(f"SCL low before {kind}", pending[0], pending[0] - last_fall, low_min)
            if kind == "START" and last_stop is not None:
                check("bus free", at, at - last_stop, low_min)
            active = kind != "STOP"
            if active:
                last_start = at
            else:
                last_stop = at
            words, pending, last_fall, last_rise = [], None, None, None
            continue
        if not active or "scl" not in changes:
            continue
        if pin["scl"] == 1:
            pending = (at, pin["sda"], last_data)
        elif pending is None:
            check("START hold", at, at - last_start, high_min)
            last_fall = at
        else:
            rise, bit, data_at = pending
            stretched = any(last_fall <= hold_start < release == rise for hold_start, release in stretch_holds)
            check("SCL low", rise, rise - last_fall, low_min)
            check("SCL high", at, at - rise, high_min)
            check("SDA setup", rise, rise - data_at, setup_min)
            if last_rise is not None and not stretched:
                check("SCL bit period", rise, rise - last_rise, bit_min, bit_max)
            words.append((bit, stretched))
            last_fall, last_rise, pending = at, rise, None

    if active or delimiters != events_wanted:
        errors.append(f"unexpected START/STOP sequence: {delimiters}")
    if len(segments) != len(expected):
        errors.append(f"expected {len(expected)} segments, got {len(segments)}")
    got_stretches = []
    for index, (bits, wanted) in enumerate(zip(segments, expected)):
        got_stretches.extend((index, i) for i, (_, stretched) in enumerate(bits) if stretched)
        if len(bits) != len(wanted) * 9:
            errors.append(f"segment {index}: expected {len(wanted) * 9} clocks, got {len(bits)}")
            continue
        raw = [bit for bit, _ in bits]
        got = [(as_bytes(raw[j:j + 8])[0], raw[j + 8]) for j in range(0, len(raw), 9)]
        if got != wanted:
            errors.append(f"segment {index}: byte/ACK mismatch {got!r}")
    releases = [at for at, side, name, value in bus.raw if side == "dut" and name == "scl" and value is None]
    if (got_stretches != ([(0, 9), (0, 17)] if case.stretch else [])
            or any(release - start != case.stretch or start not in releases for start, release in stretch_holds)):
        errors.append(f"unexpected stretch positions or durations: {got_stretches}, {stretch_holds}")
    if report.get("i2c_ok") != [ok] or report.get("i2c_rx", []) != ([list(READ)] if ok else []):
        errors.append(f"I2C result mismatch: {report!r}")
    return errors, min(margins, default=None)
