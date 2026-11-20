"""Explore global fault, host stop and halt ordering on the draft ISA (EVAL-012).

A fault is detected when the issue path tries to execute an operation (edge F).
Two latencies are compared:

* ``next`` - register the fault. Everything else due on F happens normally.
  The safe edge is F + 1: flush queued and due updates, clear capture slots,
  release every owned pad and stop issue.
* ``same`` - the safe edge is F itself, so updates and captures due on F are
  also suppressed. This needs a combinational path from decode to the pads.

A host ``STOP`` has a safe edge S. Nothing issues, captures or retires on S.
Each stopped run is compared with the same run without a stop.
"""

import argparse
import json
from fractions import Fraction
from pathlib import Path

from .cycle import ModelError, Pins, clock_json
from .encoded import Image
from .flex import rc5_stimulus
from .g4_edges import EdgeProbe
from .g4_edges import build as rc5_build
from .g4_isa import MASK, ISAProbe
from .g4_isa import build as isa_build
from .g4_pad_encoding import PIN_ORDERS
from .g4_payload import SPI_WORD, PayloadProbe, prepare
from .g4_payload import build as overlap_build
from .i2c_fixture import I2CCase
from .run_encoded import i2c_bench, spi_bench

WRAP_EPOCH = (1 << 24) - 500


class StopRule:
    """Mixin: turn a model fault into a global stop instead of an exception."""

    inject_issue = None  # Fault the issue attempt made after this many issues.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fault = None
        self.flushed = []
        self.stopped_at = None

    def _runnable(self, owner, t):
        return self.fault is None and super()._runnable(owner, t)

    def _issue(self, owner, t):
        if self.fault is not None:
            return False
        if self.inject_issue is not None and sum(self.issue) == self.inject_issue:
            return self._fault(owner, t, "injected fault")
        try:
            return super()._issue(owner, t)
        except ModelError as exc:
            return self._fault(owner, t, str(exc))

    def _fault(self, owner, t, cause):
        # The faulting operation does not retire. The safe edge is the next one.
        self.fault = (t, owner, cause)
        self.continuation = None
        self.safe_at = t + 1
        return False


def stop_class(base):
    return type(f"Stop{base.__name__}", (StopRule, base), {})


def overlap(offset=0, phase=Fraction(0), epoch=WRAP_EPOCH):
    """UART RX + SPI with host payload: guards, captures, drives, host_get/put."""
    image = overlap_build(offset)
    endpoint, _ = prepare(image, ((), (SPI_WORD, SPI_WORD)))
    cls = stop_class(PayloadProbe)

    def make(arch, original, bus):
        code = b"".join(endpoint.fetch(pc) for pc in range(endpoint.cfg.count))
        return cls.from_image(arch, Image((code,), original.entries, original.lanes), bus,
                              epoch=epoch, endpoint=endpoint)

    _, machine, limit, _ = spi_bench("B", image, 0, True, machine_factory=make, uart_phase=phase,
                                     spi_offset=offset, pin_order=PIN_ORDERS["overlap"])
    return machine, limit


def i2c(stretch=60, epoch=WRAP_EPOCH):
    """Open-drain I2C with clock stretching: wait guards and released pads."""
    cls = stop_class(ISAProbe)
    make = lambda arch, image, bus: cls.from_image(arch, image, bus, epoch=epoch)
    _, machine, limit, _ = i2c_bench("B", isa_build("i2c"), I2CCase("combined", True, stretch),
                                     machine_factory=make)
    return machine, limit


def rc5(half=53_340):
    """RC5 receive: edge_save/edge_delta, long fences and host_put, across wrap."""
    image = rc5_build()
    endpoint, _ = prepare(image, ((),), enabled=1, owner1=0)
    code = b"".join(endpoint.fetch(pc) for pc in range(endpoint.cfg.count))
    bus = Pins({"rc5" if i == 6 else f"unused{i}": int(i == 6) for i in range(8)})
    starts = rc5_stimulus(bus, half)
    epoch = -(starts[0] + half + 2 + 5) & MASK
    machine = stop_class(EdgeProbe).from_image("B", Image((code,), image.entries, image.lanes), bus,
                                               epoch=epoch, endpoint=endpoint)
    return machine, starts[-1] + 129 * half


SCENARIOS = {"overlap": overlap, "i2c": i2c, "rc5": rc5}


def due_edge(machine, t0, event):
    return t0 + machine._delta(event.deadline, t0)


def dut_writes(machine):
    return [entry for entry in machine.bus.raw if entry[1] == "dut"]


def check(base, run, cut, safe):
    """Compare a stopped run with the unstopped one. Return a list of violations."""
    errors = []
    before = lambda entries, edge: [entry for entry in entries if entry[0] < edge]
    if run.stopped_at != safe:
        errors.append(f"safe edge {run.stopped_at}, expected {safe}")
    if run.issue_log != before(base.issue_log, cut):
        errors.append("issue trace differs before the stop")
    if run.admitted != before(base.admitted, cut):
        errors.append("admitted updates differ")
    if run.retired != before(base.retired, safe):
        errors.append("retired updates differ before the safe edge")
    if run.capture_log != before(base.capture_log, safe) or run.samples != before(base.samples, safe):
        errors.append("captures differ before the safe edge")
    if getattr(run, "transfers", []) != before(getattr(base, "transfers", []), cut):
        errors.append("payload transfers differ")
    retired = [event.seq for _, event in run.retired]
    flushed = {event.seq for event in run.flushed}
    if len(retired) != len(set(retired)):
        errors.append("an update retired twice")
    for t0, event in run.admitted:
        due = due_edge(run, t0, event)
        expected = "retired" if due < safe else "flushed"
        actual = ("retired" if event.seq in retired else "") + ("flushed" if event.seq in flushed else "")
        if actual != expected:
            errors.append(f"update {event.seq} due {due}: {actual or 'lost'}, expected {expected}")
    writes = dut_writes(run)
    if before(writes, safe) != before(dut_writes(base), safe):
        errors.append("pad writes differ before the safe edge")
    late = [entry for entry in writes if entry[0] > safe or (entry[0] == safe and entry[3] is not None)]
    if late:
        errors.append(f"pad written after or on the safe edge: {late[:2]}")
    if any(run.bus.drive["dut"].get(pin) is not None for pin in set().union(*run.owners)):
        errors.append("owned pad still driven after the safe edge")
    return errors


def stats(base, run, safe):
    lead = [due_edge(run, t0, e) - safe for t0, e in run.admitted if e in run.flushed]
    writes = dut_writes(run)
    released = [entry for entry in writes if entry[0] == safe]
    # Shortest time a pad held its last programmed value before the safe edge released it.
    held = []
    for _, _, pin, _ in released:
        previous = [entry[0] for entry in writes if entry[2] == pin and entry[0] < safe]
        if previous:
            held.append(safe - previous[-1])
    return {"flushed": len(run.flushed), "max_flushed_lead": max(lead, default=None),
            "released": len(released), "min_held": min(held, default=None),
            "retired_edge_before_safe": sum(t == safe - 1 for t, _ in run.retired)}


def sweep(name, *, issue_step=1, stop_points=None):
    """Inject a fault at each issue attempt and a host stop at selected edges."""
    base, limit = SCENARIOS[name]()
    end = base.run(limit)
    issues = sum(base.issue)
    rows = []

    def record(kind, point, run, cut, safe, error=None):
        errors = [error] if error else check(base, run, cut, safe)
        row = {"scenario": name, "kind": kind, "point": point, "safe_edge": safe,
               "pass": not errors, "errors": errors, **stats(base, run, safe)}
        if kind.startswith("fault") and cut is not None:
            # Work the base run did on the fault edge: kept by "next", suppressed by "same".
            row["base_work_on_fault_edge"] = (sum(t == cut for t, _ in base.retired)
                                              + sum(entry[0] == cut for entry in base.capture_log))
        rows.append(row)

    for k in range(0, issues, issue_step):
        run, _ = SCENARIOS[name]()
        run.inject_issue = k
        try:
            run.run(limit)
        except ModelError as exc:
            record("fault-next", k, run, None, None, str(exc))
            continue
        fault_edge = run.fault[0]
        record("fault-next", k, run, fault_edge, fault_edge + 1)
        same, _ = SCENARIOS[name]()
        same.safe_at = fault_edge
        same.run(limit)
        record("fault-same", k, same, fault_edge, fault_edge)
    if stop_points is None:
        marks = {t for t, *_ in base.issue_log} | {t for t, _ in base.retired}
        marks |= {entry[0] for entry in base.capture_log}
        stride = max(997, end // 2000)
        stop_points = sorted({m + d for m in marks for d in (0, 1)} | set(range(1, end, stride)))
    for s in stop_points:
        if not 0 < s <= end:
            continue
        run, _ = SCENARIOS[name]()
        run.safe_at = s
        run.run(limit)
        record("stop", s, run, s, s)
    summary = {"scenario": name, "end_cycle": end, "issues": issues, "admitted": len(base.admitted),
               "captures": len(base.capture_log), "transfers": len(getattr(base, "transfers", []))}
    return summary, rows


def aggregate(rows):
    """Summarize one scenario and stop kind."""
    leads = [row["max_flushed_lead"] for row in rows if row["max_flushed_lead"] is not None]
    held = [row["min_held"] for row in rows if row["min_held"] is not None]
    work = [row.get("base_work_on_fault_edge", 0) for row in rows]
    return {"runs": len(rows), "passed": sum(row["pass"] for row in rows),
            "max_flushed": max((row["flushed"] for row in rows), default=0),
            "max_flushed_lead": max(leads, default=None), "min_held": min(held, default=None),
            "runs_with_work_on_fault_edge": sum(n > 0 for n in work),
            "failures": [row for row in rows if not row["pass"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    results = []
    for name in SCENARIOS:
        summary, rows = sweep(name)
        print(summary)
        for kind in ("fault-next", "fault-same", "stop"):
            agg = aggregate([row for row in rows if row["kind"] == kind])
            summary[kind] = agg
            print(f"  {kind:10s} {agg['passed']}/{agg['runs']} pass; max flushed {agg['max_flushed']},"
                  f" max lead {agg['max_flushed_lead']}, min held {agg['min_held']},"
                  f" fault-edge work in {agg['runs_with_work_on_fault_edge']} runs")
            for row in agg["failures"][:5]:
                print("     ", row["point"], row["errors"][:2])
        results.append(summary)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, default=clock_json, indent=1) + "\n", encoding="utf-8")
    return int(not all(summary[kind]["passed"] == summary[kind]["runs"]
                       for summary in results for kind in ("fault-next", "fault-same", "stop")))


if __name__ == "__main__":
    raise SystemExit(main())
