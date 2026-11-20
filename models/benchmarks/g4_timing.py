"""Cycle-level exploration of ARCH-B's G4 issue and timed-I/O contracts."""

from dataclasses import dataclass, replace
from math import ceil

from .cycle import Emit, Level, Machine, ModelError, Out, Sample
from .encoded import Issue, execute


@dataclass(frozen=True)
class Drive:
    seq: int
    owner: int
    deadline: int
    values: dict


@dataclass(frozen=True)
class Edge:
    pin: str
    level: int | None


@dataclass
class Capture:
    op: Sample | Level | Edge
    ready_at: int | None = None
    value: int | None = None
    stamp: int | None = None


class TimingProbe(Machine):
    def __init__(self, programs, bus, owners, *, epoch=0, width=24, slots=4):
        super().__init__("B", programs, bus)
        self.owners = tuple(map(frozenset, owners))
        if len(self.owners) != len(self.tasks) or sum(map(len, self.owners)) != len(set().union(*self.owners)):
            raise ValueError("each context needs a disjoint set of writable pins")
        self.queue_limit = slots
        self.epoch = epoch
        self.modulus = 1 << width
        self.mask = self.modulus - 1
        self.captures = [None] * len(self.tasks)
        self.continuation = None
        self.ready_since = [None] * len(self.tasks)
        self.max_issue_wait = [0] * len(self.tasks)
        self.full_cycles = 0
        self.admission_slack = None
        self.admitted = []
        self.retired = []
        self.capture_log = []
        self.issue_log = []

    @classmethod
    def from_image(cls, arch, image, bus, *, epoch=0, slots=4):
        if arch != "B":
            raise ValueError("the G4 probe only models ARCH-B")
        image.validate(arch)
        pins = tuple(bus.idle)
        programs = [execute(image.programs[0], pc, 3, image.lanes[i], pins, bus.open_drain)
                    for i, pc in enumerate(image.entries)]
        writable = set(pins) - {"uart_rx", "miso"}
        owners = ((), writable) if len(programs) == 2 else (writable,)
        return cls(programs, bus, owners, epoch=epoch, slots=slots)

    def timer(self, elapsed):
        return (self.epoch + elapsed) & self.mask

    def _delta(self, deadline, t):
        return (deadline - self.timer(t)) & self.mask

    def _valid_delta(self, delta):
        return 0 < delta < self.modulus // 2

    def _observe(self, t, sampled, previous):
        for owner, capture in enumerate(self.captures):
            if capture is None or capture.ready_at is not None:
                continue
            op = capture.op
            value = sampled[op.pin]
            if isinstance(op, Sample):
                if self.timer(t) != self.timer(op.at):
                    continue
                result = value
                self.samples.append((t, op.pin, value))
            elif isinstance(op, Edge):
                if (op.level is not None and value != op.level) or previous[op.pin] == value:
                    continue
                result = t
            else:
                if not self._level_match(op, t, sampled):
                    continue
                result = t
            capture.value = result
            capture.stamp = self.timer(t)
            capture.ready_at = t + 1
            self.capture_log.append((t, owner, op.pin, value, capture.stamp))

    def _runnable(self, owner, t):
        task = self.tasks[owner]
        capture = self.captures[owner]
        if capture is not None:
            return capture.ready_at is not None and capture.ready_at <= t
        op = task.op
        if isinstance(op, Out) and len(self.outputs) >= self.queue_limit:
            delta = self._delta(self.timer(op.at), t)
            return not self._valid_delta(delta) or self._bad_mask(owner, op)
        if isinstance(op, Issue):
            return self._instruction_ready(owner, op, t)
        return not task.finished

    def _bad_mask(self, owner, op):
        return not op.values or bool(op.values.keys() - self.owners[owner]) or any(
            item.deadline == self.timer(op.at) and item.values.keys() & op.values.keys()
            for item in self.outputs)

    def _capture_result(self, capture):
        return capture.value

    def _instruction_ready(self, owner, op, t):
        return t >= op.at

    def _issue_result(self, owner, op, t):
        return None

    def _issue(self, owner, t):
        task = self.tasks[owner]
        op = task.op
        capture = self.captures[owner]
        self.continuation = None
        if capture is not None:
            self.captures[owner] = None
            task.consume(self._capture_result(capture))
            kind = "consume"
        elif isinstance(op, Issue):
            if not self._instruction_ready(owner, op, t):
                return False
            task.consume(self._issue_result(owner, op, t))
            if op.kind == "fetch":
                self.continuation = owner
            kind = op.kind
        elif isinstance(op, Out):
            deadline = self.timer(op.at)
            delta = self._delta(deadline, t)
            if not self._valid_delta(delta):
                raise ModelError(f"context {owner}: output deadline {op.at} invalid at cycle {t}")
            if self._bad_mask(owner, op):
                raise ModelError(f"context {owner}: invalid or colliding output mask at cycle {t}")
            if len(self.outputs) >= self.queue_limit:
                return False
            event = Drive(len(self.admitted), owner, deadline, op.values.copy())
            self.outputs.append(event)
            self.admitted.append((t, event))
            self.admission_slack = delta if self.admission_slack is None else min(self.admission_slack, delta)
            task.consume()
            kind = "drive"
        elif isinstance(op, (Sample, Level, Edge)):
            if isinstance(op, Sample) and not self._valid_delta(self._delta(self.timer(op.at), t)):
                raise ModelError(f"context {owner}: capture deadline {op.at} invalid at cycle {t}")
            self.captures[owner] = Capture(op)
            kind = "arm"
        elif isinstance(op, Emit):
            self.report.setdefault(op.channel, []).append(op.value)
            self.emits.append((t, op.channel, op.value))
            task.consume()
            kind = "report"
        else:
            raise ModelError(f"unexpected G4 operation: {op!r}")
        if isinstance(task.op, Issue) and task.op.kind == "branch_bubble":
            self.continuation = owner
        self.issue[owner] += 1
        self.issue_log.append((t, owner, kind))
        return True

    def _next_quiet_cycle(self, t, limit):
        candidates = [limit + 1]
        if self.bus.events:
            candidates.append(ceil(self.bus.events[0][0]))
        for task, capture in zip(self.tasks, self.captures):
            if task.finished:
                continue
            if capture is None:
                if not isinstance(task.op, Issue) or task.op.kind != "fence":
                    return t + 1
                candidates.append(task.op.at)
            elif capture.ready_at is not None:
                candidates.append(capture.ready_at)
            elif isinstance(capture.op, Sample):
                candidates.append(t + self._delta(self.timer(capture.op.at), t))
            elif isinstance(capture.op, Level) and capture.op.earliest > t:
                candidates.append(capture.op.earliest)
        return max(t + 1, min(candidates))

    def run(self, limit, *, skip_idle=False):
        ff1 = ff2 = previous = self.bus.idle.copy()
        t = 0
        while t <= limit:
            self.bus.advance(t)
            incoming = self.bus.level.copy()
            due = [event for event in self.outputs if event.deadline == self.timer(t)]
            self.outputs = [event for event in self.outputs if event.deadline != self.timer(t)]
            self._observe(t, ff2, previous)
            runnable = [self._runnable(i, t) for i in range(len(self.tasks))]
            if any(isinstance(self.tasks[i].op, Out) and not ready for i, ready in enumerate(runnable)):
                self.full_cycles += 1
            for i, ready in enumerate(runnable):
                self.ready_since[i] = (t if self.ready_since[i] is None else self.ready_since[i]) if ready else None
            if self.continuation is not None:
                choice = self.continuation
            else:
                order = ((self.cursor + i) % len(self.tasks) for i in range(len(self.tasks)))
                choice = next((i for i in order if runnable[i]), None)
            if choice is not None and self._issue(choice, t):
                if self.ready_since[choice] is not None:
                    self.max_issue_wait[choice] = max(self.max_issue_wait[choice], t - self.ready_since[choice])
                self.ready_since[choice] = None
                self.cursor = (choice + 1) % len(self.tasks)
            updates = {}
            for event in due:
                self._put(updates, event.values)
                self.retired.append((t, event))
            if updates:
                self.bus.apply(t, "dut", updates)
            self.hi["output_queue"] = max(self.hi["output_queue"], len(self.outputs))
            self.hi["capture_slots"] = max(self.hi["capture_slots"], sum(c is not None for c in self.captures))
            quiet = skip_idle and not any(runnable) and choice is None and not due and not self.outputs
            next_cycle = (self._next_quiet_cycle(t, limit)
                          if quiet and incoming == ff1 == ff2 == previous else t + 1)
            previous, ff2, ff1 = ff2, ff1, incoming
            if not self.outputs and all(task.finished for task in self.tasks) and not self.bus.events:
                expected = sorted((t0 + self._delta(e.deadline, t0), e.seq) for t0, e in self.admitted)
                if sorted((t1, e.seq) for t1, e in self.retired) != expected:
                    raise ModelError("accepted output did not retire exactly once at its deadline")
                return t
            t = next_cycle
        raise ModelError(f"G4 probe timed out after {limit} clocks")


class ModularGuards:
    """24-bit fence and wait_save guards (CHG-007). Set ``guard_policy`` on the class.

    ``sticky`` is the approved rule; the others exist only for EVAL-011.
    """

    guard_policy = "sticky"
    instances = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.half = self.modulus // 2
        self.armed = [None] * len(self.tasks)
        self.compare_targets = {}
        # (arm cycle, owner, "fence"/"wait", delta at arm or None, wait cycles)
        self.guard_log = []
        if self.instances is not None:
            self.instances.append(self)

    def _classify(self, owner, kind, target, t):
        """Return the linear cycle at which the guard opens."""
        delta = (target - self.timer(t)) & self.mask
        future = 0 < delta < self.half
        if self.guard_policy == "strict" and not future:
            raise ModelError(f"context {owner}: {kind} target not in the future half at arm")
        if self.guard_policy == "compare":
            future = 0 < delta <= self.half
        release = t + delta if future else t
        self.guard_log.append((t, owner, kind, delta, release - t))
        return release

    def _instruction_ready(self, owner, op, t):
        task = self.tasks[owner]
        if (self.guard_policy != "elapsed" and op.kind == "fence"
                and task.op is op and self.armed[owner] is not op):
            # First evaluation is the execute slot: classify the target once.
            op = replace(op, at=self._classify(owner, "fence", self.timer(op.at), t))
            task.op = self.armed[owner] = op
        return super()._instruction_ready(owner, op, t)

    def _issue(self, owner, t):
        task = self.tasks[owner]
        op = task.op
        if self.guard_policy != "elapsed" and self.captures[owner] is None and isinstance(op, Level):
            if not getattr(op, "guarded", True):
                self.guard_log.append((t, owner, "wait", None, 0))
                task.op = replace(op, earliest=t)
            elif self.guard_policy == "compare":
                target = self.timer(op.earliest)
                delta = (target - self.timer(t)) & self.mask
                wait = delta if 0 < delta <= self.half else 0
                self.guard_log.append((t, owner, "wait", delta, wait))
                task.op = replace(op, earliest=t)
                self.compare_targets[id(task.op)] = target
            else:
                task.op = replace(op, earliest=self._classify(owner, "wait", self.timer(op.earliest), t))
        return super()._issue(owner, t)

    def _open(self, op, t):
        target = self.compare_targets.get(id(op))
        return target is None or ((self.timer(t) - target) & self.mask) < self.half

    def _level_match(self, op, t, sampled):
        return super()._level_match(op, t, sampled) and self._open(op, t)

    def _next_quiet_cycle(self, t, limit):
        nxt = super()._next_quiet_cycle(t, limit)
        for capture in self.captures:
            if capture is None or capture.ready_at is not None or id(capture.op) not in self.compare_targets:
                continue
            target = self.compare_targets[id(capture.op)]
            elapsed = (self.timer(t) - target) & self.mask
            # Next change of the compare result: open at target, close at target + 2^23.
            change = (self.mask + 1 - elapsed) if elapsed >= self.half else (self.half - elapsed)
            nxt = min(nxt, max(t + 1, t + change))
        return nxt
