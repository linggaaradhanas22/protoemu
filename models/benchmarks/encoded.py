"""Bounded candidate instruction images and their cycle-level interpreter."""

from dataclasses import dataclass

from .cycle import Emit, Level, Machine, ModelError, Out, Sample, Shift


FORMATS = {
    "halt": (), "set": (3, 16), "add": (3, 15), "out": (5, 5, 9),
    "shift_out": (3, 3, 3, 1, 9), "cap": (3, 3, 2, 9), "wait": (3, 1, 9),
    "call": (7,), "ret": (), "loop": (3, 7), "jnz": (3, 7), "jump": (7,),
    "report": (3, 3), "lane": (2, 9), "fence": (9,),
}
OPCODES = tuple(FORMATS)
STORES = {"A": (4, 64), "B": (3, 128), "C": (3, 64)}
REPORTS = ("spi_rx_word", "uart_rx", "uart_error", "i2c_rx_word", "i2c_nack")
NO_PIN = 7


def pack(values, widths):
    if len(values) != len(widths):
        raise ValueError("wrong number of fields")
    word = offset = 0
    for value, width in zip(values, widths):
        if not 0 <= value < 1 << width:
            raise ValueError(f"field value {value} does not fit in {width} bits")
        word |= value << offset
        offset += width
    return word


def unpack(word, widths):
    result = []
    for width in widths:
        result.append(word & ((1 << width) - 1))
        word >>= width
    if word:
        raise ModelError("nonzero reserved bits")
    return result


def assemble(lines, word_bytes, depth):
    labels, insns = {}, []
    for line in lines:
        if isinstance(line, str):
            if line in labels:
                raise ValueError(f"duplicate label {line}")
            labels[line] = len(insns)
        else:
            insns.append(line)
    if len(insns) > depth:
        raise ValueError(f"program uses {len(insns)} words, store holds {depth}")
    image = bytearray()
    for op, *args in insns:
        args = [labels[arg] if isinstance(arg, str) else arg for arg in args]
        word = OPCODES.index(op) | (pack(args, FORMATS[op]) << 5)
        image.extend(word.to_bytes(word_bytes, "little"))
    return bytes(image), labels


def decode(image, pc, word_bytes):
    start = pc * word_bytes
    if not 0 <= start < len(image):
        raise ModelError(f"program counter outside loaded image: {pc}")
    word = int.from_bytes(image[start:start + word_bytes], "little")
    opcode = word & 31
    if opcode >= len(OPCODES):
        raise ModelError(f"unknown opcode {opcode}")
    op = OPCODES[opcode]
    return op, unpack(word >> 5, FORMATS[op])


def lane_words(*, period, count, clock=NO_PIN, polarity=0, clock_phase=0, serial=NO_PIN,
               tx=0, sample=NO_PIN, rx=0, sample_phase=0, lsb=False):
    words = (
        pack((period, count), (16, 7)),
        pack((clock_phase, sample_phase), (8, 16)),
        pack((clock, polarity, serial, tx, sample, rx, lsb), (3, 1, 3, 3, 3, 3, 1)),
        0,
    )
    return b"".join(word.to_bytes(3, "little") for word in words)


def descriptor(bank, index, start, registers, pins):
    raw = bank[index * 12:(index + 1) * 12]
    if len(raw) != 12:
        raise ModelError("lane descriptor outside loaded bank")
    words = [int.from_bytes(raw[i:i + 3], "little") for i in range(0, 12, 3)]
    period, count = unpack(words[0], (16, 7))
    clock_phase, sample_phase = unpack(words[1], (8, 16))
    clock, polarity, serial, tx, sample, rx, lsb = unpack(words[2], (3, 1, 3, 3, 3, 3, 1))
    if words[3] or count > 16:
        raise ModelError("descriptor exceeds lane register width or uses reserved bits")
    if any(pin != NO_PIN and pin >= len(pins) for pin in (clock, serial, sample)):
        raise ModelError("invalid pin in lane descriptor")
    phases = () if clock == NO_PIN else ((0, {pins[clock]: polarity}), (clock_phase, {pins[clock]: 1 - polarity}))
    bits = tuple((registers[tx] >> (i if lsb else count - i - 1)) & 1 for i in range(count))
    drive = None if serial == NO_PIN else (0, pins[serial], bits)
    capture = None if sample == NO_PIN else (sample_phase, pins[sample])
    return Shift(start, count, period, phases, drive, capture), rx, lsb


@dataclass(frozen=True)
class Issue:
    kind: str
    at: int = 0


@dataclass(frozen=True)
class Image:
    programs: tuple[bytes, ...]
    entries: tuple[int, ...]
    lanes: tuple[bytes, ...]

    def validate(self, arch):
        width, depth = STORES[arch]
        expect = len(self.entries) if arch == "A" else 1
        if not 1 <= len(self.entries) <= 2 or len(self.programs) != expect:
            raise ValueError("wrong number of program banks or contexts")
        if any(len(bank) % width or not 0 < len(bank) <= width * depth for bank in self.programs):
            raise ValueError("invalid program bank size")
        if len(self.lanes) != len(self.entries):
            raise ValueError("lane bank and context count differ")
        if any((bank and arch != "C") or len(bank) % 12 or len(bank) > 16 * 3 for bank in self.lanes):
            raise ValueError("invalid lane bank size")
        for i, pc in enumerate(self.entries):
            if not 0 <= pc < len(self.programs[i if arch == "A" else 0]) // width:
                raise ValueError("entry outside loaded image")


class EncodedMachine(Machine):
    def __init__(self, arch, image, bus):
        image.validate(arch)
        programs = [execute(image.programs[i if arch == "A" else 0], pc, STORES[arch][0],
                            image.lanes[i], tuple(bus.idle), bus.open_drain)
                    for i, pc in enumerate(image.entries)]
        super().__init__(arch, programs, bus)
        self.slot_counts = {"fetch": 0, "branch_bubble": 0, "execute": 0, "fence": 0, "descriptor_read": 0}

    def _execute(self, i, t, sampled, updates):
        task = self.tasks[i]
        if task.wait is None and isinstance(task.op, Issue):
            op = task.op
            if t < op.at:
                return False
            self.slot_counts[op.kind] += 1
            self.issue[i] += 1
            task.consume()
            return True
        return super()._execute(i, t, sampled, updates)

    def run(self, limit):
        return super().run(limit, skip_idle=False)


def execute(code, pc, width, bank, pins, open_drain):
    regs = [0] * 8
    stack = []

    def pad(pin, value):
        if pin >= len(pins):
            raise ModelError(f"invalid pin index {pin}")
        name = pins[pin]
        return {name: None if value and name in open_drain else value}

    while True:
        # A synchronous fetch occupies one issue slot. Each execution consumes another.
        yield Issue("fetch")
        op, a = decode(code, pc, width)
        pc += 1
        base = regs[0]
        if op == "halt":
            yield Issue("execute")
            return
        if op in ("set", "add"):
            reg, value = a
            yield Issue("execute")
            regs[reg] = (value if op == "set" else regs[reg] + (value if value < 16384 else value - 32768)) & 0xFFFF
        elif op == "out":
            mask, values, delay = a
            changes = {}
            for pin in range(5):
                if mask & (1 << pin):
                    changes.update(pad(pin, (values >> pin) & 1))
            yield Out(base + delay, changes)
        elif op == "shift_out":
            reg, serial, extra, level, delay = a
            changes = pad(serial, regs[reg] >> 15)
            if extra != NO_PIN:
                changes.update(pad(extra, level))
            yield Out(base + delay, changes)
            regs[reg] = (regs[reg] << 1) & 0xFFFF
        elif op == "cap":
            pin, reg, mode, delay = a
            if mode > 2 or pin >= len(pins):
                raise ModelError("invalid capture operand")
            value = yield Sample(base + delay, pins[pin])
            if mode == 1:
                value |= (regs[reg] << 1) & 0xFFFF
            elif mode == 2:
                value = (value << 7) | (regs[reg] >> 1)
            regs[reg] = value
        elif op == "wait":
            pin, level, delay = a
            if pin >= len(pins):
                raise ModelError("invalid wait pin")
            regs[0] = (yield Level(base + delay, pins[pin], level)) & 0xFFFF
        elif op in ("call", "ret", "loop", "jnz", "jump"):
            yield Issue("execute")
            dst = a[-1] if a else None
            if op == "call":
                if len(stack) == 2:
                    raise ModelError("return stack overflow")
                stack.append(pc)
            elif op == "ret":
                if not stack:
                    raise ModelError("return stack underflow")
                dst = stack.pop()
            elif op in ("loop", "jnz"):
                reg = a[0]
                if op == "loop":
                    regs[reg] = (regs[reg] - 1) & 0xFFFF
                if not regs[reg]:
                    continue
            pc = dst
            yield Issue("branch_bubble")
        elif op == "report":
            channel, reg = a
            if channel >= len(REPORTS):
                raise ModelError("invalid report channel")
            yield Emit(REPORTS[channel], regs[reg])
        elif op == "lane":
            index, delay = a
            for _ in range(4):
                yield Issue("descriptor_read")
            shift, reg, lsb = descriptor(bank, index, base + delay, regs, pins)
            values = yield shift
            if values:
                order = values if lsb else reversed(values)
                regs[reg] = sum(bit << i for i, bit in enumerate(order))
        elif op == "fence":
            yield Issue("fence", base + a[0])
