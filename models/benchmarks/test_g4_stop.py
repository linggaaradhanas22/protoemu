"""Directed checks for global fault, host stop and halt ordering (EVAL-012)."""

from unittest import TestCase

from .cycle import Level, ModelError, Out, Pins
from .encoded import Issue
from .g4_stop import StopRule, check, stop_class, sweep
from .g4_timing import TimingProbe


def queue_then_fault(fault_at, drives):
    yield Issue("fetch")
    for at, values in drives:
        yield Out(at, values)
    yield Issue("fence", fault_at)
    raise ModelError("deliberate fault")


def queue_then_halt(drives):
    yield Issue("fetch")
    for at, values in drives:
        yield Out(at, values)
    yield Issue("fetch")
    yield Issue("execute")  # halt


def machine(programs, owners, cls=None, events=()):
    bus = Pins({"a": 0, "b": 0, "c": 0, "input": 1})
    for t, value in events:
        bus.external(t, {"input": value})
    return (cls or stop_class(TimingProbe))(programs, bus, owners, epoch=(1 << 24) - 5)


class StopOrderTests(TestCase):
    def test_fault_keeps_work_due_on_fault_edge_and_flushes_the_next(self):
        run = machine([queue_then_fault(10, [(10, {"a": 1}), (11, {"b": 1})])], [{"a", "b"}])
        self.assertEqual(run.run(100), 11)
        self.assertEqual(run.fault[0], 10)
        self.assertEqual([(t, e.values) for t, e in run.retired], [(10, {"a": 1})])
        self.assertEqual([e.values for e in run.flushed], [{"b": 1}])
        self.assertEqual(run.bus.raw, [(10, "dut", "a", 1), (11, "dut", "a", None)])
        self.assertNotIn("fence", [kind for _, _, kind in run.issue_log])

    def test_host_stop_suppresses_updates_and_captures_on_its_edge(self):
        def capture():
            yield Issue("fetch")
            yield Level(0, "input", 0)
            yield Issue("fetch")

        run = machine([queue_then_halt([(10, {"a": 1})]), capture()], [{"a"}, set()],
                      events=[(8, 0)])  # Synchronized low is first observed on edge 10.
        run.safe_at = 10
        run.run(100)
        self.assertEqual((run.retired, run.capture_log), ([], []))
        self.assertEqual(len(run.flushed), 1)

    def test_halted_context_updates_retire_until_the_other_faults(self):
        halted = queue_then_halt([(50, {"a": 1}), (100, {"c": 1})])
        faulting = queue_then_fault(60, [])
        run = machine([halted, faulting], [{"a", "c"}, set()])
        self.assertEqual(run.run(200), 61)
        self.assertEqual([t for t, _ in run.retired], [50])
        self.assertEqual([e.values for e in run.flushed], [{"c": 1}])

    def test_checker_detects_an_update_retired_on_the_safe_edge(self):
        class Leaky(StopRule, TimingProbe):
            def _safe_stop(self, t, due):
                self.retired.extend((t, event) for event in due)
                return super()._safe_stop(t, [])

        make = lambda cls=None: machine([queue_then_halt([(10, {"a": 1}), (20, {"b": 1})])],
                                        [{"a", "b"}], cls)
        base = make()
        base.run(100)
        good, bad = make(), make(Leaky)
        good.safe_at = bad.safe_at = 10
        good.run(100)
        bad.run(100)
        self.assertEqual(check(base, good, 10, 10), [])
        self.assertTrue(any("expected flushed" in error for error in check(base, bad, 10, 10)))

    def test_benchmark_sweeps_hold_the_invariants(self):
        for name in ("overlap", "i2c", "rc5"):
            with self.subTest(name=name):
                _, rows = sweep(name, issue_step=61, stop_points=range(1, 9000, 1013))
                self.assertTrue(rows)
                self.assertEqual([row for row in rows if not row["pass"]], [])
