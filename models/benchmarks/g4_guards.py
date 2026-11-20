"""Compare 24-bit rules for fence and wait_save time guards (EVAL-011).

Earlier probes check a guard as ``elapsed >= target``. That needs an unbounded
counter. Hardware only has the 24-bit ``cycle``. This module models four rules:

* ``elapsed`` - the earlier model baseline (not implementable with 24 bits).
* ``sticky``  - approved in CHG-007; the ISAProbe default. Classify
  ``delta = (target - cycle) mod 2^24`` once, at arm.
  ``1 <= delta < 2^23`` waits until ``cycle == target``; zero or the past half
  opens the guard now. The guard then stays open until the operation retires.
* ``compare`` - no arm state: open while ``(cycle - target) mod 2^24 < 2^23``.
* ``strict``  - as ``sticky``, but fault if the target is not in the future
  half at arm (the drive admission rule).
"""

import argparse
import hashlib
import json
from pathlib import Path

from .cycle import clock_json
from .g4_edges import HALF_PERIODS, EdgeProbe
from .g4_edges import run_case as rc5_case
from .g4_timing import ModularGuards
from .g4_isa import ISAProbe, build
from .run_compare import measure
from .run_g4_timing import jobs

POLICIES = ("elapsed", "sticky", "compare", "strict")
EPOCHS = (0, (1 << 24) - 500)


def guard_class(base, policy):
    bases = (base,) if issubclass(base, ModularGuards) else (ModularGuards, base)
    return type(f"{policy.title()}{base.__name__}", bases, {"guard_policy": policy, "instances": []})


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
