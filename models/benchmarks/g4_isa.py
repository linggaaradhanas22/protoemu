"""Exploratory ARCH-B encoding with native capture-derived deadlines."""

from dataclasses import dataclass

from .cycle import Emit, Level, ModelError, Out, Sample
from .encoded import FORMATS as LEGACY_FORMATS
from .encoded import NO_PIN, REPORTS, Image, Issue, pack, unpack
from .encoded_programs import T, i2c_code, spi_code, uart_code
from .g4_timing import Edge, TimingProbe

MASK = (1 << 24) - 1
HALF = 1 << 23
OFFSET_HI = 6
FORMATS = {op: (code, widths) for code, (op, widths) in enumerate(LEGACY_FORMATS.items())
           if op not in ("wait", "lane")}
FORMATS.update(save_now=(15, ()), addoff=(16, (15,)), wait_save=(17, (3, 1, 9)))
DECODE = {code: (op, widths) for op, (code, widths) in FORMATS.items()}
PAD_FORMATS = dict(FORMATS, pad=(18, (3, 1, 1, 9)), pad2=(19, (3, 1, 1, 3, 1, 1, 9)),
                   shift_pin=(20, (3, 3, 9)), shift_pair=(21, (3, 3, 3, 1, 9)),
                   drivev=(22, (3, 8, 8)))
PAD_DECODE = {code: (op, widths) for op, (code, widths) in PAD_FORMATS.items()}


@dataclass(frozen=True)
class SaveLevel(Level):
    """Return the stored observation timestamp at consume, not elapsed time.

    ``guarded`` is false when ``wait_save`` runs without a saved time: there is
    no earliest-observation target, not a target at the model epoch.
    """

    guarded: bool = True


class SaveEdge(Edge):
    """Return the native timestamp from the context capture slot."""


@dataclass(frozen=True)
class PayloadWrite(Issue):
    word: int = 0


def assemble(lines, *, formats=FORMATS):
    labels, words = {}, []
    for line in lines:
        if isinstance(line, str):
            if line in labels:
                raise ValueError(f"duplicate label {line}")
            labels[line] = len(words)
        else:
            words.append(line)
    if not 1 <= len(words) <= 128:
        raise ValueError("ISA probe program must fit in 1–128 words")
    image = bytearray()
    for op, *operands in words:
        opcode, widths = formats[op]
        args = [labels[arg] if isinstance(arg, str) else arg for arg in operands]
        image.extend((opcode | (pack(args, widths) << 5)).to_bytes(3, "little"))
    return bytes(image), labels


def decode(image, pc, *, table=DECODE):
    start = pc * 3
    if not 0 <= start <= len(image) - 3:
        raise ModelError(f"program counter outside loaded image: {pc}")
    word = int.from_bytes(image[start:start + 3], "little")
    try:
        op, widths = table[word & 31]
    except KeyError as exc:
        raise ModelError("invalid ARCH-B probe opcode") from exc
    return op, unpack(word >> 5, widths)


def execute(code, pc, pins, open_drain, epoch, *, table=DECODE):
    regs = [0] * 8
    stack = []
    stamp = None

    def offset():
        return (regs[OFFSET_HI] << 16) | regs[T]

    def at(immediate):
        if stamp is None:
            raise ModelError("timestamp used before save")
        relative = offset() + immediate
        if not 0 <= relative < HALF:
            raise ModelError("timestamp offset outside the half range")
        deadline = (stamp + relative) & MASK
        return (deadline - epoch) & MASK

    def pin(index):
        if index >= len(pins):
            raise ModelError("pin index outside image mapping")
        return pins[index]

    def pad(index, value, enable=1):
        name = pin(index)
        return {name: None if not enable or (value and name in open_drain) else value}

    while True:
        yield Issue("fetch")
        op, args = decode(code, pc, table=table)
        pc += 1
        if op == "halt":
            yield Issue("execute")
            return
        if op == "save_now":
            stamp = yield Issue("read_timer")
            regs[T] = regs[OFFSET_HI] = 0
        elif op == "wait_save":
            index, value, delay = args
            if stamp is None and (offset() or delay):
                raise ModelError("timestamp used before save")
            stamp = yield (SaveLevel(at(delay), pin(index), value) if stamp is not None
                           else SaveLevel(0, pin(index), value, guarded=False))
            regs[T] = regs[OFFSET_HI] = 0
        elif op in ("edge_save", "edge_delta"):
            index, polarity = args[:2]
            if polarity == 3:
                raise ModelError("invalid edge polarity")
            if op == "edge_delta" and (stamp is None or args[2] not in (1, 2, 3, 4)):
                raise ModelError("edge_delta needs saved time and a non-offset register pair")
            observed = yield SaveEdge(pin(index), None if polarity == 2 else polarity)
            if op == "edge_delta":
                elapsed = (observed - stamp) & MASK
                if not 0 < elapsed < HALF:
                    raise ModelError("edge interval outside the future half range")
                dest = args[2]
                regs[dest], regs[dest + 1] = elapsed & 0xFFFF, elapsed >> 16
            stamp = observed
            regs[T] = regs[OFFSET_HI] = 0
        elif op in ("addoff", "addoff_r"):
            change, = args
            if op == "addoff_r":
                change = regs[change]
            else:
                change -= (1 << 15) if change & (1 << 14) else 0
            updated = offset() + change
            if not 0 <= updated < HALF:
                raise ModelError("timestamp offset outside the half range")
            yield Issue("execute")
            regs[T], regs[OFFSET_HI] = updated & 0xFFFF, updated >> 16
        elif op in ("set", "add"):
            reg, value = args
            yield Issue("execute")
            if op == "add":
                value += regs[reg] - ((1 << 15) if value & (1 << 14) else 0)
            regs[reg] = value & 0xFFFF
        elif op in ("shr", "xor", "ult", "mov"):
            dest, arg = args
            yield Issue("execute")
            if op == "shr":
                regs[dest] >>= arg
            elif op == "xor":
                regs[dest] ^= regs[arg]
            elif op == "ult":
                regs[dest] = int(regs[dest] < arg)
            else:
                regs[dest] = regs[arg]
        elif op == "out":
            mask, values, delay = args
            changes = {}
            for index in range(5):
                if mask & (1 << index):
                    changes.update(pad(index, (values >> index) & 1))
            yield Out(at(delay), changes)
        elif op == "shift_out":
            reg, serial, extra, level, delay = args
            changes = pad(serial, regs[reg] >> 15)
            if extra != NO_PIN:
                changes.update(pad(extra, level))
            yield Out(at(delay), changes)
            regs[reg] = (regs[reg] << 1) & 0xFFFF
        elif op in ("pad", "pad2"):
            changes = pad(*args[:3])
            if op == "pad2":
                if args[0] == args[3]:
                    raise ModelError("duplicate pad in pair")
                changes.update(pad(*args[3:6]))
            yield Out(at(args[-1]), changes)
        elif op in ("shift_pin", "shift_pair"):
            reg, index = args[:2]
            changes = pad(index, regs[reg] >> 15)
            if op == "shift_pair":
                extra, value = args[2:4]
                if index == extra:
                    raise ModelError("duplicate pad in shift pair")
                changes.update(pad(extra, value))
            yield Out(at(args[-1]), changes)
            regs[reg] = (regs[reg] << 1) & 0xFFFF
        elif op == "drivev":
            reg, oe, delay = args
            mask, values = regs[reg] & 0xFF, regs[reg] >> 8
            changes = {name: bit for i in range(8) if mask & (1 << i)
                       for name, bit in pad(i, (values >> i) & 1, (oe >> i) & 1).items()}
            yield Out(at(delay), changes)
        elif op == "cap":
            index, reg, mode, delay = args
            if mode > 2:
                raise ModelError("invalid sample mode")
            bit = yield Sample(at(delay), pin(index))
            if mode == 1:
                bit |= (regs[reg] << 1) & 0xFFFF
            elif mode == 2:
                bit = (bit << 7) | (regs[reg] >> 1)
            regs[reg] = bit
        elif op in ("call", "ret", "loop", "jnz", "jump"):
            yield Issue("execute")
            destination = args[-1] if args else None
            if op == "call":
                if len(stack) == 2:
                    raise ModelError("return stack overflow")
                stack.append(pc)
            elif op == "ret":
                if not stack:
                    raise ModelError("return stack underflow")
                destination = stack.pop()
            elif op in ("loop", "jnz"):
                reg = args[0]
                if op == "loop":
                    regs[reg] = (regs[reg] - 1) & 0xFFFF
                if not regs[reg]:
                    continue
            pc = destination
            yield Issue("branch_bubble")
        elif op == "report":
            channel, reg = args
            if channel >= len(REPORTS):
                raise ModelError("invalid report channel")
            yield Emit(REPORTS[channel], regs[reg])
        elif op == "host_get":
            (dest,) = args
            regs[dest] = yield Issue("host_get")
        elif op == "host_put":
            (source_reg,) = args
            yield PayloadWrite("host_put", word=regs[source_reg])
        elif op == "fence":
            yield Issue("fence", at(args[0]))


class ISAProbe(TimingProbe):
    decode_table = DECODE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_sample_slack = None

    @classmethod
    def from_image(cls, arch, image, bus, *, epoch=0, slots=4, **kwargs):
        if arch != "B":
            raise ValueError("the ISA probe only models ARCH-B")
        image.validate(arch)
        code, = image.programs
        programs = [execute(code, pc, tuple(bus.idle), bus.open_drain, epoch, table=cls.decode_table)
                    for pc in image.entries]
        writable = {name for name in bus.idle if name not in {"uart_rx", "miso"} and not name.startswith("unused")}
        owners = ((), writable) if len(programs) == 2 else (writable,)
        return cls(programs, bus, owners, epoch=epoch, slots=slots, **kwargs)

    def _capture_result(self, capture):
        return capture.stamp if isinstance(capture.op, (SaveLevel, SaveEdge)) else capture.value

    def _issue_result(self, owner, op, t):
        return self.timer(t) if op.kind == "read_timer" else None

    def _issue(self, owner, t):
        op = self.tasks[owner].op
        arming = self.captures[owner] is None and isinstance(op, Sample)
        issued = super()._issue(owner, t)
        if arming and issued:
            slack = self._delta(self.timer(op.at), t)
            self.min_sample_slack = slack if self.min_sample_slack is None else min(slack, self.min_sample_slack)
        return issued


def native(lines):
    for line in lines:
        if isinstance(line, str):
            yield line
        elif line[0] == "wait":
            yield "wait_save", *line[1:]
        elif line[:2] == ("add", T):
            yield "addoff", line[2]
        else:
            yield line


def source(profile, mode=0, *, spi_offset=0):
    if profile == "i2c":
        lines, _ = i2c_code()
        lines[1:2] = [("save_now",), ("set", T, 15)]
        entries = ("i2c",)
    else:
        overlap = profile == "overlap"
        if profile not in ("overlap", "spi"):
            raise ValueError(f"unknown ISA probe profile: {profile}")
        # The fixture launches both contexts on elapsed cycle zero. SPI reads
        # the clock at execute cycle 1 alone, or cycle 3 after UART's first arm.
        starts = (357 + spi_offset, 5547 + spi_offset) if overlap else (31,)
        lines, _ = spi_code("B", mode, starts)
        lines.insert(1, ("save_now",))
        entries = ("spi",)
        if overlap:
            uart, _ = uart_code("B")
            lines = uart + lines
            entries = ("uart", "spi")
    return native(lines), entries


def build(profile, mode=0, *, spi_offset=0):
    lines, entries = source(profile, mode, spi_offset=spi_offset)
    code, labels = assemble(lines)
    return Image((code,), tuple(labels[name] for name in entries), (b"",) * len(entries))
