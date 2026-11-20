"""SPI peer and pin monitor, plus UART stimuli for the overlap run."""

from bisect import bisect_right
from fractions import Fraction

from .cycle import Emit, Level, Out, Peer, Sample, Shift, as_bits, as_bytes, window


TX = (0x96, 0x4B)
RX = (0x3A, 0xD2)
OVERLAP_RX = (0x55, 0x55, 0xA3)
UART_TX = (0x55, 0x55, 0x55, 0x80, 0x01)
UART_RX = (0x00, 0xFF, 0x55, 0xAA, 0x80, 0x01)
UART_RATES = (9600, 19200, 38400, 57600, 115200)


class SPIPeer(Peer):
    def __init__(self, mode, half):
        self.idle, self.late = divmod(mode, 2)
        self.lag = Fraction(half, 4)
        self.reply = as_bits(RX)
        self.sampled = 0

    def observe(self, bus, at, changes):
        if changes.get("cs") == 0:
            self.sampled = 0
            if not self.late:
                bus.external(at, {"miso": self.reply[0]})
        if "sclk" in changes and bus.level["cs"] == 0:
            leading = changes["sclk"] != self.idle
            if leading != self.late:
                self.sampled += 1
            elif self.sampled < len(self.reply):
                bus.external(at + self.lag, {"miso": self.reply[self.sampled]})


def spi_program(arch, starts, mode, half):
    idle, late = divmod(mode, 2)
    tx = as_bits(TX)
    for start in starts:
        base = start + 4 + late * half
        yield Out(start, {"cs": 0})
        samples = []
        if arch == "C":
            phases = ((0, {"sclk": 1 - idle if late else idle}),
                      (half, {"sclk": idle if late else 1 - idle}))
            samples = yield Shift(base, len(tx), 2 * half, phases,
                                  (0, "mosi", tx), (half + 2, "miso"))
        else:
            for i, bit in enumerate(tx):
                phase = base + i * 2 * half
                yield Out(phase, {"sclk": 1 - idle if late else idle, "mosi": bit})
                yield Out(phase + half, {"sclk": idle if late else 1 - idle})
                samples.append((yield Sample(phase + half + 2, "miso")))
        end = base + 2 * half * len(tx)
        if not late:
            yield Out(end, {"sclk": idle})
        yield Out(end + 4, {"cs": 1})
        yield Emit("spi_rx", as_bytes(samples))


def spi_check(bus, received, mode, half, starts):
    idle, late = divmod(mode, 2)
    pin = bus.idle.copy()
    transactions = []
    outside_clock_edges = []
    start = None
    for at, name, value in bus.edges:
        pin[name] = value
        if name == "cs" and value == 0:
            start, clock, data, returned, sampled_ticks = at, [], [], [], []
            if pin["sclk"] != idle:
                return ["SCLK not idle at CS assertion"], None, []
        if name == "sclk":
            if start is None:
                outside_clock_edges.append(at)
                continue
            clock.append((at, value))
            if (value != idle) != late:
                data.append(pin["mosi"])
                returned.append(pin["miso"])
                sampled_ticks.append(at)
        if name == "cs" and value == 1 and start is not None:
            transactions.append((start, at, clock, data, returned, sampled_ticks, pin["sclk"]))
            start = None

    errors = []
    if outside_clock_edges:
        errors.append(f"extra SCLK activity outside CS at {outside_clock_edges}")
    if start is not None or [row[0] for row in transactions] != list(starts):
        errors.append("unexpected CS assertion/deassertion times")
    if received != [list(RX) for _ in starts]:
        errors.append(f"SPI RX mismatch: {received!r}")
    margins = []
    for first, last, clock, data, returned, sample_ticks, final_clk in transactions:
        if len(clock) != 32 or len(sample_ticks) != 16 or final_clk != idle:
            errors.append(f"at {first}: expect 32 SCLK edges, 16 samples and return to idle")
        if tuple(data) != as_bits(TX) or tuple(returned) != as_bits(RX):
            errors.append(f"at {first}: SPI pin data mismatch")
        if clock and (clock[0][0] <= first or clock[-1][0] >= last):
            errors.append(f"at {first}: CS does not enclose SCLK")
        if sample_ticks:
            drive_ticks = {at for at, level in clock if (level != idle) == late}
            if any(name == "mosi" and first <= at <= last and at not in drive_ticks
                   and (late or at >= sample_ticks[0]) for at, name, _ in bus.edges):
                errors.append(f"at {first}: MOSI changed on the wrong clock phase")
        for (t0, _), (t1, _) in zip(clock, clock[1:]):
            margin = window(t1 - t0, half - 1, half + 1)
            margins.append((margin, t1, "SPI half-period"))
            if margin < 0:
                errors.append(f"at {t1}: SPI half-period is {t1 - t0} clocks")
    return errors, min(margins, default=None), [(row[0], row[1]) for row in transactions]


def uart_stimulus(bus, start, bit_period, payload):
    level = 1
    changes = []
    for byte in payload:
        for bit in (0, *((byte >> i) & 1 for i in range(8)), 1):
            if bit != level:
                bus.external(start, {"uart_rx": bit})
                changes.append(start)
                level = bit
            start += bit_period
    return start, changes


def uart_receive(arch, count, period, earliest=0):
    for _ in range(count):
        seen = yield Level(earliest, "uart_rx", 0)
        if arch == "C":
            samples = yield Shift(seen + period, 9, period, sample=(period // 2, "uart_rx"))
        else:
            samples = []
            for i in range(1, 10):
                samples.append((yield Sample(seen + i * period + period // 2, "uart_rx")))
        if samples[-1] != 1:
            yield Emit("uart_error", "bad stop bit")
        yield Emit("uart_rx", sum(bit << i for i, bit in enumerate(samples[:-1])))
        earliest = seen + 9 * period + period // 2


def uart_transmit(arch, baud, start):
    period = round(Fraction(60_000_000, baud))
    bits = tuple(bit for byte in UART_TX for bit in (0, *((byte >> i) & 1 for i in range(8)), 1))
    if arch == "C":
        yield Shift(start, len(bits), period, serial=(0, "uart_tx", bits))
    else:
        for i, bit in enumerate(bits):
            yield Out(start + i * period, {"uart_tx": bit})
    yield Out(start + len(bits) * period, {"uart_tx": 1})


def uart_tx_check(bus, end, baud, first):
    nominal = Fraction(60_000_000, baud)
    lo, hi = nominal * Fraction(99, 100), nominal * Fraction(101, 100)
    edges = [(t, v) for t, name, v in bus.edges if name == "uart_tx"]
    times = [t for t, _ in edges]
    errors, margins, decoded = [], [], []
    if not edges or edges[0] != (first, 0) or bus.level["uart_tx"] != 1:
        return ["UART TX first start or final idle missing"], None
    # The three alternating bytes give one real edge per bit, including their boundaries.
    if len(edges) < 31:
        return ["missing alternating TX edges"], None
    for t0, t1 in zip(times[:30], times[1:31]):
        margins.append((window(t1 - t0, lo, hi), t1, "UART TX bit interval"))

    start_index = 0
    for frame in range(len(UART_TX)):
        at, v = edges[start_index]
        if v:
            errors.append(f"frame {frame} does not begin low")
        bits = [edges[bisect_right(times, at + (i + Fraction(1, 2)) * nominal) - 1][1] for i in range(10)]
        if bits[0] != 0 or bits[9] != 1:
            errors.append(f"frame {frame}: bad start/stop bits")
        decoded.append(sum(bit << i for i, bit in enumerate(bits[1:9])))
        stop_center = at + Fraction(19, 2) * nominal
        start_index = bisect_right(times, stop_center)
        if frame < len(UART_TX) - 1:
            if start_index == len(edges):
                errors.append("missing UART TX frames")
                break
            next_at = edges[start_index][0]
            margins.append((window(next_at - at, 10 * lo, 10 * hi), next_at, "UART TX frame period"))
        else:
            margins.append((window(end - at, 10 * lo), end, "UART TX final stop duration"))
            if start_index != len(edges):
                errors.append("extra edge after final stop bit")
    if decoded != list(UART_TX):
        errors.append(f"UART TX decoded {decoded}")
    if margins and min(margins)[0] < 0:
        errors.append(f"UART TX minimum margin {min(margins)}")
    return errors, min(margins, default=None)


def uart_rx_check(machine, want, start, period):
    errors = []
    if machine.report.get("uart_rx") != list(want) or machine.report.get("uart_error"):
        errors.append(f"UART receive mismatch: {machine.report!r}")
    samples = [t for t, pin, _ in machine.samples if pin == "uart_rx"]
    if len(samples) != len(want) * 9:
        return errors + [f"unexpected RX sample count: {len(samples)}"], None
    margins = []
    for i, t in enumerate(samples):
        frame, bit = divmod(i, 9)
        left = start + (frame * 10 + bit + 1) * period
        # At edge t a core consumes the input latched into the synchronizer at t-2.
        margin = window(t - 2, left, left + period)
        if not left <= t - 2 < left + period:
            errors.append(f"RX sample at {t} outside frame {frame} bit {bit + 1}")
        margins.append((margin, t, "UART RX input aperture"))
    return errors, min(margins, default=None)
