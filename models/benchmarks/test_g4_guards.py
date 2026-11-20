"""Directed boundary checks for the 24-bit guard rules in EVAL-011."""

from unittest import TestCase

from .cycle import Level, ModelError, Pins
from .encoded import Image, Issue
from .g4_edges import FORMATS, EdgeProbe
from .g4_guards import guard_class
from .g4_isa import HALF, MASK, SaveLevel, assemble
from .g4_payload import prepare
from .g4_timing import TimingProbe

ARM = 1  # The fetch issues on cycle 0, so the guard is first evaluated on cycle 1.


def fence_program(at):
    yield Issue("fetch")
    yield Issue("fence", at)
    yield Issue("fetch")
    yield Issue("execute")  # halt


def probe(policy, programs, *, epoch=0, events=()):
    bus = Pins({"input": 1})
    for t, value in events:
        bus.external(t, {"input": value})
    cls = guard_class(TimingProbe, policy)
    return cls(programs, bus, [()] * len(programs), epoch=epoch)


def fence_retire(policy, delta, epoch=0):
    """Return the cycle the fence retires when its target is ``delta`` after the arm cycle."""
    machine = probe(policy, [fence_program((ARM + delta) & MASK)], epoch=epoch)
    machine.run(2 * HALF, skip_idle=True)
    (t, _, _), = [entry for entry in machine.issue_log if entry[2] == "fence"]
    return t, machine


class FenceBoundaryTests(TestCase):
    def test_sticky_boundaries(self):
        cases = {0: ARM, 1: ARM + 1, HALF - 1: ARM + HALF - 1,
                 HALF: ARM, HALF + 1: ARM, MASK: ARM}
        for epoch in (0, MASK - 2):
            for delta, expected in cases.items():
                with self.subTest(epoch=epoch, delta=delta):
                    t, machine = fence_retire("sticky", delta, epoch)
                    self.assertEqual(t, expected)
                    self.assertEqual(machine.guard_log[0][3], delta)

    def test_future_fence_retires_on_target_across_wrap(self):
        t, machine = fence_retire("sticky", 10, epoch=MASK - 2)
        self.assertEqual(machine.timer(t), (MASK - 2 + ARM + 10) & MASK)
        self.assertLess(machine.timer(t), machine.timer(ARM))

    def test_compare_waits_on_half_boundary(self):
        self.assertEqual(fence_retire("compare", HALF)[0], ARM + HALF)
        self.assertEqual(fence_retire("compare", HALF + 1)[0], ARM)

    def test_strict_faults_unless_target_is_future(self):
        self.assertEqual(fence_retire("strict", 1)[0], ARM + 1)
        for delta in (0, HALF, MASK):
            with self.subTest(delta=delta), self.assertRaisesRegex(ModelError, "future half"):
                fence_retire("strict", delta)

    def test_contexts_classify_independently(self):
        machine = probe("sticky", [fence_program(ARM + 50), fence_program(0)])
        machine.run(200, skip_idle=True)
        fences = {owner: t for t, owner, kind in machine.issue_log if kind == "fence"}
        arms = {owner: (t, wait) for t, owner, _, _, wait in machine.guard_log}
        self.assertEqual(fences[0], ARM + 50)
        self.assertEqual(arms[1][1], 0)  # Target 0 has passed when context 1 arms.
        self.assertEqual(fences[1], arms[1][0])


def wait_program(op):
    yield Issue("fetch")
    yield op
    yield Issue("fetch")


def first_capture(policy, op, events, *, epoch=0, limit=4 * HALF):
    machine = probe(policy, [wait_program(op)], epoch=epoch, events=events)
    machine.run(limit, skip_idle=True)
    (t, _, _, _, stamp), = machine.capture_log
    return t, stamp, machine


class WaitGuardTests(TestCase):
    def test_observation_on_target_cycle_counts(self):
        t, stamp, machine = first_capture("sticky", Level(ARM + 5, "input", 1), [], epoch=MASK - 2)
        self.assertEqual(t, ARM + 5)
        self.assertEqual(stamp, machine.timer(ARM + 5))

    def test_reached_guard_matches_after_arm_edge(self):
        for delta in (0, HALF, MASK):
            with self.subTest(delta=delta):
                t, _, _ = first_capture("sticky", Level((ARM + delta) & MASK, "input", 1), [])
                self.assertEqual(t, ARM + 1)

    def test_open_guard_stays_open_for_late_level(self):
        # Level arrives 2^23 + 1000 cycles after the target, then passes the synchronizer.
        arrival = ARM + 100 + HALF + 1000
        op = Level(ARM + 100, "input", 0)
        t, _, _ = first_capture("sticky", op, [(arrival, 0)])
        self.assertEqual(t, arrival + 2)
        t, _, _ = first_capture("compare", op, [(arrival, 0)])
        self.assertEqual(t, ARM + 100 + MASK + 1)  # Closed until the counter returns to the target.

    def test_unguarded_wait_ignores_epoch(self):
        # Spend 1.5 half ranges in fences, then wait with no saved time.
        def program():
            yield Issue("fetch")
            yield Issue("fence", HALF - 1)
            yield Issue("fetch")
            yield Issue("fence", HALF - 1 + HALF // 2)
            yield Issue("fetch")
            yield SaveLevel(0, "input", 1, guarded=False)
            yield Issue("fetch")

        machine = probe("sticky", [program()])
        machine.run(4 * HALF, skip_idle=True)
        arm = max(t for t, _, kind in machine.issue_log if kind == "arm")
        (t, *_), = machine.capture_log
        self.assertEqual(t, arm + 1)
        self.assertEqual(machine.guard_log[-1][3], None)

    def test_strict_rejects_reached_wait(self):
        with self.assertRaisesRegex(ModelError, "future half"):
            first_capture("strict", Level(0, "input", 1), [])


class EncodedGuardTests(TestCase):
    def run_lines(self, lines, *, epoch=0):
        code, _ = assemble(lines, formats=FORMATS)
        image = Image((code,), (0,), (b"",))
        endpoint, _ = prepare(image, ((),), enabled=1, owner1=0)
        cls = guard_class(EdgeProbe, "sticky")
        machine = cls.from_image("B", image, Pins({"input": 1}), epoch=epoch, endpoint=endpoint)
        machine.run(4 * HALF)
        return machine

    def test_fence_on_saved_time_is_already_reached(self):
        machine = self.run_lines([("save_now",), ("fence", 0), ("halt",)], epoch=MASK - 1)
        (_, _, _, delta, wait), = machine.guard_log
        self.assertEqual((delta, wait), (MASK - 1, 0))

    def test_split_offset_fence_waits_for_target(self):
        machine = self.run_lines([("save_now",), ("set", 6, 0x7F), ("set", 0, 0xFFF0),
                                  ("fence", 0), ("halt",)], epoch=MASK - 1)
        save = next(t for t, _, kind in machine.issue_log if kind == "read_timer")
        fence = next(t for t, _, kind in machine.issue_log if kind == "fence")
        self.assertEqual(fence - save, 0x7FFFF0)
        self.assertEqual(machine.guard_log[0][4], fence - machine.guard_log[0][0])

    def test_wait_save_without_saved_time_is_unguarded(self):
        machine = self.run_lines([("wait_save", 0, 1, 0), ("halt",)])
        self.assertEqual(machine.guard_log[0][2:], ("wait", None, 0))
