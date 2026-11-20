"""Issue cost of writing the edge_delta high word in a later slot (EVAL-013).

``narrow`` and ``second`` port options retire both words on one edge, as the
existing model does. ``held`` spends one more issue slot on the high word.
"""

import argparse
import json
from pathlib import Path

from .cycle import ModelError, Pins
from .encoded import Image
from .g4_edges import FORMATS, HALF_PERIODS, EdgeProbe
from .g4_edges import run_case as rc5_case
from .g4_isa import assemble
from .g4_payload import prepare

OPTIONS = {"one-edge": False, "held": True}


def probe_class(held):
    return type("HeldEdgeProbe" if held else "OneEdgeProbe", (EdgeProbe,), {"delta_writeback": held})


def rc5_rows():
    for name, held in OPTIONS.items():
        for half in HALF_PERIODS:
            for wrap in (False, True):
                row = rc5_case(half, wrap, probe_cls=probe_class(held))
                yield {"case": row["case"], "wrap": wrap, "option": name, "pass": row["pass"],
                       "errors": row["errors"], "min_margin": row["min_margin"],
                       "sample_slack": row["sample_slack"], "issued": row["issued_ops"],
                       "host_output": row["host_output"]}


def contention(held, gap, edges=200, half=16):
    """Context 0 measures every input edge; context 1 toggles a pad every ``half`` cycles."""
    code, labels = assemble([
        "meter", ("set", 5, edges - 1), ("edge_save", 0, 2),
        "m", ("edge_delta", 0, 2, 1), ("loop", 5, "m"), ("halt",),
        "drive", ("set", 7, edges * gap // (2 * half)), ("save_now",),
        "d", ("pad", 1, 1, 1, half), ("addoff", half), ("pad", 1, 0, 1, half), ("addoff", half),
        ("loop", 7, "d"), ("halt",),
    ], formats=FORMATS)
    image = Image((code,), (labels["meter"], labels["drive"]), (b"", b""))
    endpoint, _ = prepare(image, ((), ()))
    bus = Pins({"input": 0, "out": 0})
    for n in range(edges):
        bus.external(40 + n * gap, {"input": (n + 1) % 2})
    probe = probe_class(held).from_image("B", image, bus, endpoint=endpoint)
    try:
        end = probe.run(40 + edges * gap + 1000, skip_idle=False)
    except ModelError as exc:
        return {"gap": gap, "option": "held" if held else "one-edge", "pass": False, "error": str(exc)}
    deltas = sum(1 for entry in probe.capture_log if entry[1] == 0) - 1
    return {"gap": gap, "option": "held" if held else "one-edge", "pass": True, "end": end,
            "deltas": deltas, "issued": probe.issue, "max_issue_wait": probe.max_issue_wait,
            "drive_slack": probe.admission_slack}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rc5 = list(rc5_rows())
    for row in rc5:
        print(row["option"], row["case"], "wrap" if row["wrap"] else "zero", "PASS" if row["pass"] else row["errors"],
              "margin", row["min_margin"], "slack", row["sample_slack"], "issued", row["issued"])
    busy = [contention(held, gap) for gap in (30, 40, 60) for held in OPTIONS.values()]
    for row in busy:
        print(row)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"rc5": rc5, "contention": busy}, indent=1) + "\n", encoding="utf-8")
    return int(not all(row["pass"] for row in rc5 + busy))


if __name__ == "__main__":
    raise SystemExit(main())
