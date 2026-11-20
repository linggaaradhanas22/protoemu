"""Compare 24-bit rules for fence and wait_save time guards (EVAL-011).

Earlier probes check a guard as ``elapsed >= target``. That needs an unbounded
counter. Hardware only has the 24-bit ``cycle``. This module models four rules:

* ``elapsed`` - the earlier model baseline (not implementable with 24 bits).
* ``sticky``  - classify ``delta = (target - cycle) mod 2^24`` once, at arm.
  ``1 <= delta < 2^23`` waits until ``cycle == target``; zero or the past half
  opens the guard now. The guard then stays open until the operation retires.
* ``compare`` - no arm state: open while ``(cycle - target) mod 2^24 < 2^23``.
* ``strict``  - as ``sticky``, but fault if the target is not in the future
  half at arm (the drive admission rule).
"""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from .cycle import Level, ModelError, clock_json
from .g4_edges import HALF_PERIODS, EdgeProbe
from .g4_edges import run_case as rc5_case
from .g4_isa import HALF, ISAProbe, build
from .run_compare import measure
from .run_g4_timing import jobs

POLICIES = ("elapsed", "sticky", "compare", "strict")
EPOCHS = (0, (1 << 24) - 500)


class ModularGuards:
    """Mixin for TimingProbe subclasses. Set ``guard_policy`` on the class."""

    guard_policy = "sticky"
    instances = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.armed = [None] * len(self.tasks)
        self.compare_targets = {}
        # (arm cycle, owner, "fence"/"wait", delta at arm or None, wait cycles)
        self.guard_log = []
        if self.instances is not None:
            self.instances.append(self)

    def _classify(self, owner, kind, target, t):
        """Return the linear cycle at which the guard opens."""
        delta = (target - self.timer(t)) & self.mask
        future = 0 < delta < HALF
        if self.guard_policy == "strict" and not future:
            raise ModelError(f"context {owner}: {kind} target not in the future half at arm")
        if self.guard_policy == "compare":
            future = 0 < delta <= HALF
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
                self.guard_log.append((t, owner, "wait", delta, delta if 0 < delta <= HALF else 0))
                task.op = replace(op, earliest=t)
                self.compare_targets[id(task.op)] = target
            else:
                task.op = replace(op, earliest=self._classify(owner, "wait", self.timer(op.earliest), t))
        return super()._issue(owner, t)

    def _open(self, op, t):
        target = self.compare_targets.get(id(op))
        return target is None or ((self.timer(t) - target) & self.mask) < HALF

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
            change = (self.mask + 1 - elapsed) if elapsed >= HALF else (HALF - elapsed)
            nxt = min(nxt, max(t + 1, t + change))
        return nxt


def guard_class(base, policy):
    return type(f"{policy.title()}{base.__name__}", (ModularGuards, base),
                {"guard_policy": policy, "instances": []})


def digest(machine):
    """Hash the cycle-level traces so policies can be compared with the baseline."""
    trace = (machine.issue_log, [(t, e.seq, e.deadline) for t, e in machine.retired],
             machine.capture_log, machine.samples, getattr(machine, "transfers", []))
    return hashlib.sha256(repr(trace).encode()).hexdigest()[:16]


def summarize(machine):
    log = getattr(machine, "guard_log", [])
    guarded = [entry for entry in log if entry[3] is not None]
    waits = [entry[4] for entry in guarded if entry[4]]
    return {"guards": len(log), "unguarded": len(log) - len(guarded),
            "reached_at_arm": sum(not entry[4] for entry in guarded),
            "future_at_arm": len(waits), "max_future_delta": max(waits, default=None),
            "trace": digest(machine)}


def replay(policy):
    for epoch in EPOCHS:
        cls = guard_class(ISAProbe, policy)

        def make_machine(arch, image, bus, cls=cls, epoch=epoch):
            return cls.from_image(arch, image, bus, epoch=epoch)

        def make_image(arch, profile, mode=0, *, spi_offset=0):
            return build(profile, mode, spi_offset=spi_offset)

        for (case, machine, limit, verify), params in jobs(make_machine, make_image):
            row, _ = measure(case, "B", machine, limit, verify)
            yield {"suite": "isa", "case": case, "params": params, "epoch": epoch, "policy": policy,
                   "pass": row["pass"], "errors": row["errors"], **summarize(machine)}
    cls = guard_class(EdgeProbe, policy)
    for half in HALF_PERIODS:
        for wrap in (False, True):
            cls.instances.clear()
            row = rc5_case(half, wrap, probe_cls=cls)
            machine, = cls.instances
            yield {"suite": "rc5", "case": row["case"], "params": {}, "epoch": row["epoch"],
                   "policy": policy, "pass": row["pass"], "errors": row["errors"], **summarize(machine)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = [row for policy in POLICIES for row in replay(policy)]
    key = lambda row: (row["suite"], row["case"], json.dumps(row["params"], default=clock_json), row["epoch"])
    baseline = {key(row): row["trace"] for row in rows if row["policy"] == "elapsed"}
    for row in rows:
        row["same_trace_as_elapsed"] = row["pass"] and baseline[key(row)] == row["trace"]
    for policy in POLICIES:
        mine = [row for row in rows if row["policy"] == policy]
        armed = [row for row in mine if row["pass"]]
        print(f"{policy:8s} pass {sum(r['pass'] for r in mine)}/{len(mine)}"
              f"  same trace {sum(r['same_trace_as_elapsed'] for r in mine)}"
              f"  guards {sum(r['guards'] for r in armed)}"
              f"  reached-at-arm {sum(r['reached_at_arm'] for r in armed)}"
              f"  future {sum(r['future_at_arm'] for r in armed)}"
              f"  unguarded {sum(r['unguarded'] for r in armed)}")
        for error in sorted({e for row in mine for e in row["errors"]}):
            print("   ", error)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        lines = ",\n".join("  " + json.dumps(row, default=clock_json) for row in rows)
        args.out.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
    return int(not all(row["pass"] for row in rows if row["policy"] in ("elapsed", "sticky")))


if __name__ == "__main__":
    raise SystemExit(main())
