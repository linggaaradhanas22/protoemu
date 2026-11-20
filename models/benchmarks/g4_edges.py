"""Replay the RC5 fixture with encoded, protocol-neutral edge instructions."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from .cycle import Pins, clock_json
from .encoded import Image
from .flex import rc5_check, rc5_stimulus
from .g4_isa import MASK, assemble
from .g4_payload import FORMATS as PAYLOAD_FORMATS
from .g4_payload import PayloadProbe, drain, prepare
from .run_compare import measure

FORMATS = dict(PAYLOAD_FORMATS, edge_save=(25, (3, 2)), edge_delta=(26, (3, 2, 3)),
               shr=(27, (3, 4)), addoff_r=(28, (3,)), xor=(29, (3, 3)),
               ult=(30, (3, 16)), mov=(31, (3, 3)))
DECODE = {code: (op, widths) for op, (code, widths) in FORMATS.items()}
PIN = 6
HALF_PERIODS = (50_673, 53_340, 56_007)


class EdgeProbe(PayloadProbe):
    decode_table = DECODE

    def run(self, limit, *, skip_idle=True):
        return super().run(limit, skip_idle=skip_idle)


def build():
    # R1 and R2 take the elapsed interval. R3/R4 collect the two symbol halves.
    code, _ = assemble([
        ("set", 5, 2), "frame",
        ("edge_save", PIN, 0), ("edge_delta", PIN, 1, 1),
        ("jnz", 2, "bad"),
        ("mov", 2, 1), ("ult", 2, 48_000), ("jnz", 2, "bad"),
        ("mov", 2, 1), ("ult", 2, 59_001), ("jnz", 2, "init"), ("jump", "bad"),
        "init", ("mov", 0, 1), ("shr", 0, 1),
        ("set", 3, 1), ("set", 4, 0), ("set", 7, 13),
        "bit", ("cap", PIN, 3, 1, 0), ("addoff_r", 1),
        ("cap", PIN, 4, 1, 0), ("addoff_r", 1), ("loop", 7, "bit"),
        ("xor", 4, 3), ("set", 2, 0x3FFF), ("xor", 4, 2), ("jnz", 4, "bad"),
        ("mov", 2, 3), ("ult", 2, 0x3000), ("jnz", 2, "bad"),
        ("host_put", 3), ("fence", 0), ("loop", 5, "frame"),
        # Keep observing through the final 100-half-bit idle interval.
        ("set", 7, 100), "tail", ("addoff_r", 1), ("loop", 7, "tail"),
        ("fence", 0), ("halt",),
        "bad", ("set", 3, 0xFFFF), ("host_put", 3), ("halt",),
    ], formats=FORMATS)
    return Image((code,), (0,), (b"",))


def fields(word):
    return [(word >> 6) & 31, word & 63, (word >> 11) & 1]


def run_case(half, wrap, *, probe_cls=EdgeProbe):
    image = build()
    endpoint, link = prepare(image, ((),), enabled=1, owner1=0)
    code = b"".join(endpoint.fetch(pc) for pc in range(endpoint.cfg.count))
    pins = {"rc5" if i == PIN else f"unused{i}": int(i == PIN) for i in range(8)}
    bus = Pins(pins)
    starts = rc5_stimulus(bus, half)
    # In the wrap run the first falling edge is observed five cycles before wrap.
    epoch = (-(starts[0] + half + 2 + 5) & MASK) if wrap else 0
    probe = probe_cls.from_image("B", Image((code,), image.entries, image.lanes), bus,
                                 epoch=epoch, endpoint=endpoint)
    results = []
    observation_end = starts[-1] + 128 * half

    def calibration(machine):
        sample_times = {sample[0] for sample in machine.samples}
        return [entry for entry in machine.capture_log if entry[0] not in sample_times]

    def verify(machine, end):
        results.extend(drain(endpoint, link, 0))
        valid = [word for word in results if 0x3000 <= word < 0x4000]
        times = [t for t, _, op, _ in machine.transfers if op == "host_put"]
        frames = [fields(word) for word in valid]
        view = SimpleNamespace(samples=machine.samples, report={"rc5_frame": frames,
                                                                  "rc5_error": len(results) != len(valid)},
                               emits=[(t, "rc5_frame", frame) for t, frame in zip(times, frames)])
        errors, margin = rc5_check(view, starts, half)
        expected_edges = [start + n * half + 2 for start in starts for n in (1, 2)]
        observed_edges = [entry[0] for entry in calibration(machine)]
        if observed_edges != expected_edges:
            errors.append("unexpected calibration edges")
        if end < observation_end:
            errors.append("final idle interval was not observed")
        return errors, margin

    row, _ = measure(f"rc5-{half}", "B", probe, observation_end + half, verify)
    return dict(row, epoch=epoch, wrap=wrap, words=len(code) // 3, host_output=results,
                sample_slack=probe.min_sample_slack, transfers=probe.transfers,
                calibration=calibration(probe), observation_end=observation_end)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = [run_case(half, wrap) for half in HALF_PERIODS for wrap in (False, True)]
    for row in rows:
        print(row["case"], "wrap" if row["wrap"] else "initial zero",
              "PASS" if row["pass"] else "; ".join(row["errors"]))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, default=clock_json, indent=2) + "\n", encoding="utf-8")
    return int(not all(row["pass"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
