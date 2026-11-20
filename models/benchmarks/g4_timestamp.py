"""Compare native 24-bit capture operands without changing the G3 encoding."""

import argparse
import json
from itertools import product
from pathlib import Path

from .cycle import ModelError, Out, Pins, Sample
from .encoded import Issue
from .g4_timing import Edge, TimingProbe

MASK = (1 << 24) - 1
EDGE_AT = 20
CAPTURE_AT = EDGE_AT + 2
OPTIONS = ("pair-split", "pair-fused", "dedicated")


class TimestampProbe(TimingProbe):
    def _observe(self, t, sampled, previous):
        super()._observe(t, sampled, previous)
        for capture in self.captures:
            if capture is not None and isinstance(capture.op, Edge) and capture.ready_at == t + 1:
                capture.value = capture.stamp


def from_capture(option, epoch, delay, operation):
    yield Issue("fetch")
    stamp = yield Edge("input", 1)
    if option.startswith("pair-"):
        low, high = stamp & 0xFFFF, stamp >> 16
    if option == "pair-split":
        yield Issue("fetch")
        yield Issue("add-low")
        total = low + delay
        low, carry = total & 0xFFFF, total >> 16
        yield Issue("fetch")
        yield Issue("adc-high")
        high = (high + carry) & 0xFF
    yield Issue("fetch")
    if option == "pair-split":
        deadline = (high << 16) | low
    elif option == "pair-fused":
        deadline = (((high << 16) | low) + delay) & MASK
    else:
        deadline = (stamp + delay) & MASK
    # Out/Sample's interface is elapsed program cycles. The probe converts back
    # to the native timestamp at admission; it does not recompute from 'now'.
    elapsed = (deadline - epoch) & MASK
    if operation == "sample":
        yield Sample(elapsed, "input")
    else:
        yield Out(elapsed, {"output": 1})


def competing_context(start):
    yield Issue("fence", start)
    for _ in range(24):
        yield Issue("fetch")
        yield Issue("execute")
        yield Issue("branch_bubble")


def full_queue(retire_at):
    for pin in range(4):
        yield Out(retire_at, {f"peer{pin}": 1})


def evaluate(option, stamp, delay, *, competitor=None, queue_until=None, operation="drive"):
    if option not in OPTIONS or not 1 <= delay <= 0x7FFF:
        raise ValueError("unsupported timestamp sequence")
    if competitor is not None and queue_until is not None:
        raise ValueError("choose one kind of contention")
    epoch = (stamp - CAPTURE_AT) & MASK
    idle = {"input": 0, "output": 0}
    programs = [from_capture(option, epoch, delay, operation)]
    owners = [{"output"}]
    if competitor is not None:
        programs.append(competing_context(competitor))
        owners.append(set())
    if queue_until is not None:
        idle.update({f"peer{i}": 0 for i in range(4)})
        programs.append(full_queue(queue_until))
        owners.append(set(idle) - {"input", "output"})
    bus = Pins(idle)
    bus.external(EDGE_AT, {"input": 1})
    probe = TimestampProbe(programs, bus, owners, epoch=epoch)
    expected_edge = CAPTURE_AT + delay
    rejection = None
    try:
        probe.run(max(expected_edge + 8, 128))
    except ModelError as exc:
        rejection = str(exc)
        if "deadline" not in rejection or "invalid" not in rejection:
            raise
    captured = probe.capture_log[0]
    assert captured == (CAPTURE_AT, 0, "input", 1, stamp)
    timed_kind = "arm" if operation == "sample" else "drive"
    accepted_at = next((t for t, owner, kind in probe.issue_log
                        if owner == 0 and kind == timed_kind and t > CAPTURE_AT), None)
    observed = (probe.samples if operation == "sample" else
                [edge for edge in bus.edges if edge[1] == "output"])
    expected = [(expected_edge, "input" if operation == "sample" else "output", 1)]
    assert observed == (expected if rejection is None else [])
    if operation == "drive" and rejection is None:
        event = next(event for _, event in probe.admitted if event.owner == 0)
        assert event.deadline == (stamp + delay) & MASK
    assert (accepted_at is None) == (rejection is not None)
    return dict(option=option, stamp=stamp, delay=delay, competitor=competitor,
                queue_until=queue_until, operation=operation, deadline=(stamp + delay) & MASK,
                instruction_words=sum(owner == 0 and kind == "fetch" for _, owner, kind in probe.issue_log),
                capture_to_admit=None if accepted_at is None else accepted_at - CAPTURE_AT,
                slack=None if accepted_at is None else expected_edge - accepted_at,
                blocked_cycles=probe.full_cycles, rejection=rejection)


def sweep():
    for option, stamp, delay, competitor in product(
        OPTIONS, (0x123456, 0x00FFFC, 0xFFFFFC), (4, 8, 12, 16, 56, 781), (None, 0, 1, 2)
    ):
        yield evaluate(option, stamp, delay, competitor=competitor,
                       operation="sample" if delay == 781 else "drive")
    for option in OPTIONS:
        yield evaluate(option, 0xFFFFFC, 56, queue_until=CAPTURE_AT + 54)
        yield evaluate(option, 0xFFFFFC, 56, queue_until=CAPTURE_AT + 58)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = list(sweep())
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        lines = ",\n".join("  " + json.dumps(row) for row in rows)
        args.out.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
    print(f"{len(rows)} timestamp cases")
    for option in OPTIONS:
        for delay in (4, 8, 12, 16, 56, 781):
            chosen = [r for r in rows if r["option"] == option and r["delay"] == delay
                      and r["queue_until"] is None]
            accepted = [r for r in chosen if r["rejection"] is None]
            print(option, delay, f"{len(accepted)}/{len(chosen)} admitted",
                  "capture-to-admit range:",
                  (min(r["capture_to_admit"] for r in accepted),
                   max(r["capture_to_admit"] for r in accepted)) if accepted else None)
    return int(any(r["rejection"] for r in rows if r["delay"] >= 56
                   and r["queue_until"] != CAPTURE_AT + 58))


if __name__ == "__main__":
    raise SystemExit(main())
