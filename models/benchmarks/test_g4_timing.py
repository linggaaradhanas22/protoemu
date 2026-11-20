"""Directed checks on the G4 exploration model, not RTL tests."""

from unittest import TestCase

from .cycle import Emit, ModelError, Out, Pins, Sample
from .encoded import Issue
from .g4_timing import Edge, TimingProbe


class TimingTests(TestCase):
    def test_same_edge_retirement_and_slot_reuse_at_wrap(self):
        def first():
            yield Out(4, {"a": 1})
            yield Out(5, {"a": 0})

        def second():
            yield Out(4, {"b": 1})

        bus = Pins({"a": 0, "b": 0})
        probe = TimingProbe([first(), second()], bus, [{"a"}, {"b"}], slots=2, epoch=12, width=4)
        probe.run(5)
        self.assertEqual([(t, e.deadline) for t, e in probe.admitted], [(0, 0), (1, 0), (4, 1)])
        self.assertEqual(bus.edges, [(4, "a", 1), (4, "b", 1), (5, "a", 0)])
        self.assertGreater(probe.full_cycles, 0)

    def test_overcommit_faults_without_late_drive_or_blocking_other_context(self):
        def first():
            yield Out(6, {"a": 1})
            yield Issue("fetch")
            yield Out(5, {"a": 0})

        def second():
            yield Issue("fence", 3)
            yield Emit("progress", 1)

        bus = Pins({"a": 0})
        probe = TimingProbe([first(), second()], bus, [{"a"}, set()], slots=1)
        with self.assertRaisesRegex(ModelError, "deadline 5 invalid at cycle 5"):
            probe.run(10)
        self.assertEqual(probe.emits, [(4, "progress", 1)])
        self.assertGreater(probe.full_cycles, 0)
        self.assertEqual(len(probe.admitted), 1)
        self.assertEqual(bus.raw, [])

    def test_reject_precedes_full(self):
        def program():
            yield Out(4, {"a": 1})
            yield Out(4, {"a": 0})

        probe = TimingProbe([program()], Pins({"a": 0}), [{"a"}], slots=1)
        with self.assertRaisesRegex(ModelError, "colliding output mask at cycle 1"):
            probe.run(5)

    def test_two_observations_and_distinct_consume_slots(self):
        def program(pin):
            sample = yield Sample(4, pin)
            yield Emit(pin, sample)

        bus = Pins({"a": 0, "b": 1})
        bus.external(2, {"a": 1, "b": 0})
        probe = TimingProbe([program("a"), program("b")], bus, [set(), set()], epoch=12, width=4)
        probe.run(9)
        self.assertEqual(probe.capture_log, [(4, 0, "a", 1, 0), (4, 1, "b", 0, 0)])
        self.assertEqual([(t, i) for t, i, op in probe.issue_log if op == "consume"], [(5, 0), (6, 1)])
        self.assertEqual(probe.report, {"a": [1], "b": [0]})

    def test_edge_arm_excludes_a_transition_on_the_arm_edge(self):
        def program():
            yield Issue("fence", 2)
            yield Edge("a", 1)

        bus = Pins({"a": 0})
        bus.external(1, {"a": 1})
        bus.external(2, {"a": 0})
        bus.external(3, {"a": 1})
        probe = TimingProbe([program()], bus, [set()])
        probe.run(8)
        self.assertEqual(probe.capture_log, [(5, 0, "a", 1, 5)])

    def test_accept_only_future_half_range(self):
        for delta in (0, 1, 7, 8, 15):
            with self.subTest(delta=delta):
                probe = TimingProbe([iter_program(delta)], Pins({"a": 0}), [{"a"}], width=4)
                if delta in (1, 7):
                    self.assertEqual(probe.run(8), delta)
                else:
                    with self.assertRaisesRegex(ModelError, "invalid at cycle 0"):
                        probe.run(8)

    def test_fence_releases_issue_path_but_does_not_retire_early(self):
        def first():
            yield Issue("fetch")
            yield Issue("fence", 5)
            yield Emit("after_fence", 1)

        def second():
            yield Emit("other_context", 1)

        probe = TimingProbe([first(), second()], Pins({"a": 0}), [set(), set()])
        probe.run(8)
        self.assertEqual(probe.emits, [(2, "other_context", 1), (6, "after_fence", 1)])


def iter_program(deadline):
    yield Out(deadline, {"a": 1})
