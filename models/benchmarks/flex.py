"""Non-target protocol programs and their independent trace checks."""

from itertools import groupby

from .cycle import Emit, Level, Out, Peer, Sample, Shift, as_bits, as_bytes, window


PIXELS = (0xA5, 0x12, 0x3C, 0x40, 0xE7, 0x81)
ROM = (0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xE9)
RC5_EXPECTED = [[0x05, 0x35, 0], [0x1A, 0x0C, 1]]
RC5_BITS = ("11000101110101", "11111010001100")


def ws_program(arch, start=16):
    at = start
    for bit, run in groupby(as_bits(PIXELS)):
        n = len(list(run))
        high = 51 if bit else 18
        if arch == "C":
            yield Shift(at, n, 75, ((0, {"ws": 1}), (high, {"ws": 0})))
        else:
            for i in range(n):
                tick = at + i * 75
                yield Out(tick, {"ws": 1})
                yield Out(tick + high, {"ws": 0})
        at += 75 * n
    yield Out(at - 75 + high + 18_000, {"ws": 0})


def ws_check(bus, end):
    edges = [(t, v) for t, pin, v in bus.edges if pin == "ws"]
    if len(edges) != 96 or [v for _, v in edges] != [1, 0] * 48:
        return ["expected exactly 48 high pulses from idle low"], None
    decoded, margins, errors = [], [], []
    for i in range(48):
        rise, fall = edges[2 * i][0], edges[2 * i + 1][0]
        width = fall - rise
        if 14 <= width <= 22:
            bit, high, low = 0, (14, 22), (35, 60)
        elif 35 <= width <= 60:
            bit, high, low = 1, (35, 60), (14, 25)
        else:
            return [f"pulse {i}: invalid high width {width}"], None
        decoded.append(bit)
        margins.append((window(width, *high), fall, "WS2812 high"))
        if i < 47:
            next_edge = edges[2 * i + 2][0]
            margins.append((window(next_edge - fall, *low), next_edge, "WS2812 low"))
        else:
            margins.append((window(end - fall, 16_801), end, "WS2812 latch"))
    if as_bytes(decoded) != list(PIXELS):
        errors.append(f"wrong GRB data: {as_bytes(decoded)}")
    if min(margins)[0] < 0:
        errors.append(f"timing violation {min(margins)}")
    return errors, min(margins)


def wire_bits(data):
    return tuple((byte >> i) & 1 for byte in data for i in range(8))


class OneWirePeer(Peer):
    def __init__(self, delayed):
        self.presence = (3600, 3600) if delayed else (1800, 7200)
        self.low = None
        self.state = "reset"
        self.bits = []
        self.reply = iter(wire_bits(ROM))

    def before_dut(self, bus, at, updates):
        if "wire" not in updates:
            return {}
        value = updates["wire"]
        if value == 0 and bus.drive["dut"].get("wire") is None:
            self.low = at
            if self.state == "command":
                bus.external(at + 1800, self.command_bit)
            elif self.state == "read" and next(self.reply, 1) == 0:
                bus.external(at + 60, {"wire": 0})
                bus.external(at + 1800, {"wire": None})
        elif value is None and self.state == "reset" and self.low is not None:
            if 28_800 <= at - self.low <= 57_600:
                delay, duration = self.presence
                bus.external(at + delay, {"wire": 0})
                bus.external(at + delay + duration, {"wire": None})
                self.state = "command"
        return {}

    def command_bit(self, bus, at):
        self.bits.append(bus.level["wire"])
        if len(self.bits) == 8:
            self.state = "read" if sum(bit << i for i, bit in enumerate(self.bits)) == 0x33 else "off"


def onewire_program():
    start = 16
    release = start + 30_000
    yield Out(start, {"wire": 0})
    yield Out(release, {"wire": None})
    presence = yield Level(release + 8, "wire", 0, release + 5000)
    if presence is None:
        yield Emit("wire_error", "no presence")
        return
    yield Emit("wire_presence", presence)
    start = release + 30_000
    for bit in wire_bits((0x33,)):
        yield Out(start, {"wire": 0})
        yield Out(start + (360 if bit else 3600), {"wire": None})
        start += 4200
    words = []
    for _ in range(8):
        value = 0
        for i in range(8):
            yield Out(start, {"wire": 0})
            yield Out(start + 360, {"wire": None})
            value |= (yield Sample(start + 840, "wire")) << i
            start += 4200
        words.append(value)
    yield Emit("wire_rom", words)


def onewire_check(machine, delayed):
    bus = machine.bus
    raw = [(at, v) for at, side, pin, v in bus.raw if side == "dut" and pin == "wire"]
    if len(raw) != 146 or [v for _, v in raw] != [0, None] * 73:
        return ["expected one reset and 72 open-drain data slots"], None
    if any(v not in (0, None) for _, _, _, v in bus.raw):
        return ["active high drive on open-drain bus"], None
    errors, margins = [], []
    starts, releases = [at for at, _ in raw[::2]], [at for at, _ in raw[1::2]]
    at = releases[0]
    margins.append((window(at - starts[0], 28_800, 57_600), at, "1-Wire reset low"))
    margins.append((window(starts[1] - at, 28_800), starts[1], "1-Wire reset recovery"))
    d, w = (3600, 3600) if delayed else (1800, 7200)
    presence = [(t, v) for t, _, v in bus.edges if at < t < starts[1]]
    if presence != [(at + d, 0), (at + d + w, 1)]:
        errors.append(f"unexpected resolved presence pulse {presence}")
    seen = machine.report.get("wire_presence", [])
    if len(seen) != 1 or not at + d <= seen[0] - 2 < at + d + w:
        errors.append(f"presence not detected during pulse: {seen}")
    samples = [t for t, pin, _ in machine.samples if pin == "wire"]
    if len(samples) != 64 or machine.report.get("wire_rom") != [list(ROM)]:
        errors.append(f"expected all ROM bytes: {machine.report!r}")
    highs = [t for t, _, level in bus.edges if level]
    for i, (start, release) in enumerate(zip(starts[1:], releases[1:])):
        cmd = i < 8
        want = (0x33 >> i) & 1 if cmd else 1
        bounds = (60, 900) if want else (3600, 7200)
        margins.append((window(release - start, *bounds), release, "1-Wire low pulse"))
        if i + 2 < len(starts):
            next_start = starts[i + 2]
            last_high = max((t for t in highs if start < t < next_start), default=next_start)
            margins.append((window(next_start - start, 3900, 7200), next_start, "1-Wire slot"))
            margins.append((window(next_start - last_high, 60), next_start, "1-Wire recovery high"))
        if not cmd and i - 8 < len(samples):
            t = samples[i - 8] - 2
            margins.append((window(t - start, release - start + 1, 900), t, "1-Wire sample window"))
    if min(margins)[0] < 0:
        errors.append(f"timing violation {min(margins)}")
    return errors, min(margins)


def rc5_stimulus(bus, half):
    first = 160_000
    starts = [first, first + 128 * half]
    for at, frame in zip(starts, RC5_BITS):
        for bit in frame:
            lead = int(bit)
            bus.external(at, {"rc5": lead})
            bus.external(at + half, {"rc5": 1 - lead})
            at += 2 * half
        bus.external(at, {"rc5": 1})
    return starts


def rc5_program(arch):
    earliest = 0
    while True:
        fall = yield Level(earliest, "rc5", 0, earliest + 6_400_000)
        if fall is None:
            return
        rise = yield Level(fall + 1, "rc5", 1, fall + 65_000)
        if rise is None or not 48_000 <= rise - fall <= 59_000:
            yield Emit("rc5_error", "invalid first half-bit")
            return
        half = rise - fall
        if arch == "C":
            rest = yield Shift(rise + 8, 26, half, sample=(half // 2 - 8, "rc5"))
        else:
            rest = []
            for i in range(26):
                rest.append((yield Sample(rise + i * half + half // 2, "rc5")))
        halves = (1, 0, *rest)
        pairs = list(zip(halves[::2], halves[1::2]))
        if any(x == y for x, y in pairs) or [x for x, _ in pairs[:2]] != [1, 1]:
            yield Emit("rc5_error", "invalid bi-phase symbols")
            return
        bits = [x for x, _ in pairs]
        address = sum(bit << (4 - i) for i, bit in enumerate(bits[3:8]))
        command = sum(bit << (5 - i) for i, bit in enumerate(bits[8:]))
        yield Emit("rc5_frame", [address, command, bits[2]])
        earliest = rise + 26 * half + 8


def rc5_check(machine, starts, half):
    errors = []
    events = [(t, payload) for t, channel, payload in machine.emits if channel == "rc5_frame"]
    if [payload for _, payload in events] != RC5_EXPECTED or machine.report.get("rc5_error"):
        errors.append(f"wrong RC5 frames: {machine.report!r}")
    margins = []
    for (at, _), start in zip(events, starts):
        margin = window(at, start + 27 * half, start + 128 * half - 1)
        margins.append((margin, at, "RC5 report window"))
        if margin < 0:
            errors.append(f"RC5 frame emitted outside its window at {at}")
    samples = [t for t, pin, _ in machine.samples if pin == "rc5"]
    if len(samples) != 52:
        errors.append(f"expected 52 RC5 samples, got {len(samples)}")
    for i, t in enumerate(samples[:52]):
        start = starts[i // 26] + (i % 26 + 2) * half
        margin = window(t - 2, start, start + half - 1)
        margins.append((margin, t, "RC5 sample window"))
        if margin < 0:
            errors.append(f"RC5 sample outside its half-bit at {t}")
    return errors, min(margins, default=None)
