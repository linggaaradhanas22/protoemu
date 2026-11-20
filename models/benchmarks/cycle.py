"""Exploratory G3 pin simulation. Time is in 60 MHz clocks (Fractions off-edge)."""

from dataclasses import dataclass
from fractions import Fraction
from heapq import heappop, heappush
from itertools import count
from math import ceil


class ModelError(Exception):
    pass


class Pins:
    def __init__(self, idle, open_drain=(), peer=None):
        self.idle = dict(idle)
        self.level = dict(idle)
        self.open_drain = set(open_drain)
        self.peer = peer
        self.drive = {"dut": {}, "peer": {}}
        self.raw = []
        self.edges = []
        self.events = []
        self.serial = count()

    def external(self, at, updates):
        heappush(self.events, (at, next(self.serial), updates))

    def _write(self, at, side, updates):
        for pin, value in updates.items():
            if pin not in self.level:
                raise ModelError(f"unknown pin {pin}")
            if self.drive[side].get(pin) != value:
                self.drive[side][pin] = value
                self.raw.append((at, side, pin, value))

    def apply(self, at, side, updates):
        extra = {}
        if side == "dut" and self.peer:
            extra = self.peer.before_dut(self, at, updates)
            self._write(at, "peer", extra)
        self._write(at, side, updates)
        changes = {}
        for pin in sorted(updates.keys() | extra.keys()):
            dut = self.drive["dut"].get(pin)
            ext = self.drive["peer"].get(pin)
            if pin in self.open_drain:
                value = 0 if dut == 0 or ext == 0 else 1
            elif dut is not None and ext is not None:
                raise ModelError(f"push-pull contention on {pin}")
            else:
                value = dut if dut is not None else ext if ext is not None else self.idle[pin]
            if value != self.level[pin]:
                self.level[pin] = changes[pin] = value
                self.edges.append((at, pin, value))
        if changes and self.peer:
            self.peer.observe(self, at, changes)

    def advance(self, clock):
        while self.events and self.events[0][0] <= clock:
            at, _, updates = heappop(self.events)
            if callable(updates):
                updates(self, at)
            else:
                self.apply(at, "peer", updates)


class Peer:
    def before_dut(self, bus, at, updates):
        return {}

    def observe(self, bus, at, changes):
        pass


@dataclass(frozen=True)
class Out:
    at: int
    values: dict


@dataclass(frozen=True)
class Sample:
    at: int
    pin: str


@dataclass(frozen=True)
class Level:
    earliest: int
    pin: str
    value: int
    deadline: int | None = None


@dataclass(frozen=True)
class Emit:
    channel: str
    value: object


@dataclass(frozen=True)
class Shift:
    """One lane operation: repeat two pin phases, optionally shift and sample."""

    start: int
    count: int
    period: int
    phases: tuple = ()  # (cycle offset, static outputs)
    serial: tuple | None = None  # (cycle offset, output pin, shift bits)
    sample: tuple | None = None  # (cycle offset, input pin)
    trigger: tuple | None = None  # (pin, level), qualified by start

    @property
    def offsets(self):
        offsets = [offset for offset, _ in self.phases]
        if self.serial:
            offsets.append(self.serial[0])
        if self.sample:
            offsets.append(self.sample[0])
        return offsets

    def __post_init__(self):
        offsets = self.offsets
        if (not 0 < self.count <= 64 or not 0 < self.period <= 65535
                or len(self.phases) > 2 or any(not 0 <= i < self.period for i in offsets)
                or not offsets or (self.serial and len(self.serial[2]) != self.count)):
            raise ModelError("lane descriptor does not fit")


class Task:
    def __init__(self, program):
        self.program = program
        self.op = None
        self.finished = False
        self.wait = None
        self.consume()

    def consume(self, value=None):
        try:
            self.op = self.program.send(value)
        except StopIteration:
            self.finished = True
            self.op = None


class Machine:
    """One issue slot per PIO engine, single queued core, or sequencer + lanes."""

    queue_limit = 4

    def __init__(self, arch, programs, bus):
        if arch not in ("A", "B", "C") or not 1 <= len(programs) <= 2:
            raise ValueError("unsupported model configuration")
        self.arch = arch
        self.tasks = [Task(p) for p in programs]
        self.bus = bus
        self.report = {}
        self.issue = [0] * len(programs)
        self.hi = {"output_queue": 0, "capture_slots": 0, "lanes": 0}
        self.outputs = []
        self.samples = []
        self.emits = []
        self.cursor = 0

    def _put(self, updates, values):
        if updates.keys() & values.keys():
            raise ModelError("overlapping pin updates on the same clock")
        updates.update(values)

    def _hardware(self, t, sampled, updates):
        keep = []
        for at, values in self.outputs:
            if at == t:
                self._put(updates, values)
            else:
                keep.append((at, values))
        self.outputs = keep
        for task in self.tasks:
            if task.wait is None:
                continue
            op, origin, bits = task.wait
            if isinstance(op, Sample) and t == op.at:
                self.samples.append((t, op.pin, sampled[op.pin]))
                task.wait = None
                task.consume(sampled[op.pin])
            elif isinstance(op, Level) and (self._level_match(op, t, sampled) or self._expired(op, t)):
                task.wait = None
                task.consume(t if self._level_match(op, t, sampled) else None)
            elif isinstance(op, Shift):
                if origin is None:
                    if t < op.start or (op.trigger and sampled[op.trigger[0]] != op.trigger[1]):
                        continue
                    origin = t
                    task.wait = (op, origin, bits)
                i, phase = divmod(t - origin, op.period)
                if (i >= op.count or (i == op.count - 1 and phase > max(op.offsets))):
                    task.wait = None
                    task.consume(tuple(bits))
                    continue
                values = {}
                for offset, phase_values in op.phases:
                    if phase == offset:
                        values.update(phase_values)
                if op.serial and phase == op.serial[0]:
                    values[op.serial[1]] = op.serial[2][i]
                self._put(updates, values)
                if op.sample and phase == op.sample[0]:
                    bits.append(sampled[op.sample[1]])
                    self.samples.append((t, op.sample[1], bits[-1]))

    def _execute(self, i, t, sampled, updates):
        task = self.tasks[i]
        if task.finished or task.wait is not None:
            return False
        op = task.op
        result = None
        if isinstance(op, Out):
            if self.arch == "B":
                if op.at <= t:
                    raise ModelError(f"output deadline {op.at} missed at {t}")
                if len(self.outputs) == self.queue_limit:
                    return False
                self.outputs.append((op.at, op.values))
                self.hi["output_queue"] = max(self.hi["output_queue"], len(self.outputs))
            else:
                if t < op.at:
                    return False
                if t != op.at:
                    raise ModelError(f"output deadline {op.at} missed at {t}")
                self._put(updates, op.values)
        elif isinstance(op, Sample):
            if self.arch == "B":
                if op.at <= t:
                    raise ModelError(f"capture deadline {op.at} missed at {t}")
                task.wait = (op, None, None)
            else:
                if t < op.at:
                    return False
                if t != op.at:
                    raise ModelError(f"capture deadline {op.at} missed at {t}")
                result = sampled[op.pin]
                self.samples.append((t, op.pin, result))
        elif isinstance(op, Level):
            if self.arch == "B":
                task.wait = (op, None, None)
            elif self._level_match(op, t, sampled):
                result = t
            elif not self._expired(op, t):
                return False
        elif isinstance(op, Shift) and self.arch == "C":
            if op.start <= t:
                raise ModelError(f"lane start {op.start} missed at {t}")
            task.wait = (op, None, [])
        elif isinstance(op, Emit):
            self.report.setdefault(op.channel, []).append(op.value)
            self.emits.append((t, op.channel, op.value))
        else:
            raise ModelError(f"unsupported operation {op!r}")
        self.issue[i] += 1
        if task.wait is None:
            task.consume(result)
        pending = [task.wait[0] for task in self.tasks if task.wait is not None]
        self.hi["lanes"] = max(self.hi["lanes"], sum(isinstance(p, Shift) for p in pending))
        self.hi["capture_slots"] = max(self.hi["capture_slots"], sum(isinstance(p, (Sample, Level)) for p in pending))
        return True

    @staticmethod
    def _level_match(op, t, sampled):
        return t >= op.earliest and sampled[op.pin] == op.value

    @staticmethod
    def _expired(op, t):
        return op.deadline is not None and t >= op.deadline

    def _next_idle_event(self, t, limit):
        future = [limit + 1, *(at for at, _ in self.outputs)]
        if self.bus.events:
            future.append(ceil(self.bus.events[0][0]))
        for task in self.tasks:
            if task.finished:
                continue
            if task.wait is None:
                op = task.op
                if self.arch != "B" and isinstance(op, (Out, Sample)):
                    future.append(op.at)
                elif isinstance(op, Level):
                    future.extend(x for x in (op.earliest, op.deadline) if x is not None and x > t)
                continue
            op, origin, _ = task.wait
            if isinstance(op, Sample):
                future.append(op.at)
            elif isinstance(op, Level):
                future.extend(x for x in (op.earliest, op.deadline) if x is not None and x > t)
            elif isinstance(op, Shift):
                if origin is None:
                    if op.start > t:
                        future.append(op.start)
                else:
                    i, phase = divmod(t - origin, op.period)
                    later = [off - phase for off in op.offsets if off > phase]
                    if later:
                        future.append(t + min(later))
                    elif i == op.count - 1:
                        future.append(t + 1)
                    else:
                        future.append(t + op.period - phase + min(op.offsets))
        return max(t + 1, min(future))

    def run(self, limit, *, skip_idle=True):
        ff1 = ff2 = self.bus.idle.copy()
        t = 0
        while t <= limit:
            self.bus.advance(t)
            incoming = self.bus.level.copy()
            stable = incoming == ff1 == ff2
            updates = {}
            before = sum(self.issue)
            self._hardware(t, ff2, updates)
            if self.arch == "A":
                for i in range(len(self.tasks)):
                    self._execute(i, t, ff2, updates)
            else:
                for offset in range(len(self.tasks)):
                    i = (self.cursor + offset) % len(self.tasks)
                    if self._execute(i, t, ff2, updates):
                        self.cursor = (i + 1) % len(self.tasks)
                        break
            if updates:
                self.bus.apply(t, "dut", updates)
            ff1, ff2 = incoming, ff1
            if not self.outputs and all(task.finished for task in self.tasks) and not self.bus.events:
                return t
            if skip_idle and stable and not updates and before == sum(self.issue):
                t = self._next_idle_event(t, limit)
            else:
                t += 1
        raise ModelError(f"benchmark timed out after {limit} clocks")


def window(actual, minimum, maximum=None):
    return min(actual - minimum, maximum - actual) if maximum is not None else actual - minimum


def as_bits(values):
    return tuple((byte >> i) & 1 for byte in values for i in range(7, -1, -1))


def as_bytes(bits):
    if len(bits) % 8:
        raise ValueError("incomplete byte")
    return [sum(bit << (7 - i) for i, bit in enumerate(bits[j:j + 8])) for j in range(0, len(bits), 8)]


def clock_json(value):
    if isinstance(value, Fraction):
        return int(value) if value.denominator == 1 else str(value)
    raise TypeError(f"not a clock value: {value!r}")
