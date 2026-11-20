"""Timeout options for input waits, applied to I2C clock stretching (EVAL-017).

Options:
* ``A`` host stop: the wait has no limit; the host sends STOP after its own timeout.
* ``B`` software polling with today's ISA: sample SCL every ``interval`` cycles.
* ``C`` timed wait ``wait_to`` (CHG-013): guarded like wait_save, expiring R7 x 64
  cycles after the guard target.
* ``C2`` rejected variant: unguarded ``wait_tou`` with a fence to the release first.
* ``D`` per-context watchdog: fault the chip if the I2C context issues nothing for too long.

Status words from the I2C program: 0 = OK, 1 = NACK, 2 = SCL timeout.
"""

import argparse
import json
from fractions import Fraction
from pathlib import Path

from .cycle import Peer, Pins, clock_json
from .encoded import Image
from .g4_host_rate import run as host_run
from .g4_host_rate import started as host_started
from .g4_isa import TimedLevel, assemble
from .g4_isa import execute as isa_execute
from .g4_loader import PHASES, STOP, US, packet
from .g4_payload import drain, prepare
from .g4_stop import StopRule
from .g4_suite import FORMATS as SUITE_FORMATS
from .g4_suite import SuiteProbe, advance, pins_for
from .i2c_fixture import I2CCase, I2CPeer, i2c_check
from .run_encoded import words_to_bytes
from .spi_uart import SPIPeer, spi_check

FORMATS = dict(SUITE_FORMATS, wait_to=(6, (3, 1, 9, 3)),  # CHG-013, provisional opcode 6.
               wait_tou=(12, (3, 1, 9, 3)))  # Rejected unguarded variant, EVAL-017 only.
DECODE = {code: (op, widths) for op, (code, widths) in FORMATS.items()}
SCL, SDA = 6, 7
CS, MOSI, MISO, SCLK = 0, 1, 2, 3
OK, NACK, TIMEOUT = 0, 1, 2
UNIT = 64  # wait_to timeout unit in cycles


class TimeoutProbe(StopRule, SuiteProbe):
    decode_table = DECODE
    watchdog = {}  # owner -> limit in cycles (option D)
    host_stop = None  # (peer, host timeout, stop delay) for option A

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expire = [None] * len(self.tasks)
        self.last_issue = [0] * len(self.tasks)

    def _runnable(self, owner, t):
        if self.host_stop and self.safe_at is None:
            peer, timeout, delay = self.host_stop
            # The host stops the chip only if the I2C result has not arrived by its timeout.
            if peer.stuck_at is not None and not self.tasks[0].finished and t >= peer.stuck_at + timeout:
                self.safe_at = t + delay
        limit = self.watchdog.get(owner)
        if (limit and self.fault is None and not self.tasks[owner].finished
                and t - self.last_issue[owner] >= limit):
            self._fault(owner, t, "watchdog")
            return False
        return super()._runnable(owner, t)

    def _issue(self, owner, t):
        op = self.tasks[owner].op
        arming = self.captures[owner] is None and isinstance(op, TimedLevel) and self.fault is None
        if arming and op.timeout:
            # CHG-013: classify the expiry once at arm, like a timed sample; it must be in the future half.
            delta = (self.timer(op.earliest) + op.timeout - self.timer(t)) & self.mask
            if not 0 < delta < self.half:
                return self._fault(owner, t, "wait_to expiry not in the future half")
        issued = super()._issue(owner, t)
        if issued:
            self.last_issue[owner] = t
            if arming and op.timeout:
                self.expire[owner] = t + delta
        if self.captures[owner] is None:
            self.expire[owner] = None
        return issued

    def _observe(self, t, sampled, previous):
        super()._observe(t, sampled, previous)
        for owner, capture in enumerate(self.captures):
            if (capture is not None and capture.ready_at is None and self.expire[owner] is not None
                    and t >= self.expire[owner]):
                capture.ready_at, capture.value, capture.stamp = t + 1, None, None
                self.capture_log.append((t, owner, capture.op.pin, None, None))

    def _next_quiet_cycle(self, t, limit):
        nxt = super()._next_quiet_cycle(t, limit)
        candidates = [e for e in self.expire if e is not None and e > t]
        candidates += [self.last_issue[o] + lim for o, lim in self.watchdog.items()
                       if not self.tasks[o].finished and self.last_issue[o] + lim > t]
        if self.host_stop and self.host_stop[0].stuck_at is not None:
            candidates += [self.host_stop[0].stuck_at + self.host_stop[1]]
        candidates = [c for c in candidates if c > t]
        return min([nxt, *candidates])


class StuckPeer(I2CPeer):
    """Holds SCL low when it is released after ``at_rises`` completed clocks, for ``hold`` cycles or forever."""

    def __init__(self, case, hold, at_rises):
        super().__init__(case)
        self.hold, self.at_rises, self.stuck_at = hold, at_rises, None

    def before_dut(self, bus, at, updates):
        if (self.stuck_at is None and self.segment == 1 and self.nedges in self.at_rises
                and bus.drive["dut"].get("scl") == 0 and "scl" in updates and updates["scl"] is None):
            self.stuck_at = at
            if self.hold is not None:
                bus.external(at + self.hold, {"scl": None})
            return {"scl": 0}
        return super().before_dut(bus, at, updates)


class Both(Peer):
    def __init__(self, *peers):
        self.peers = peers

    def before_dut(self, bus, at, updates):
        extra = {}
        for peer in self.peers:
            extra.update(peer.before_dut(bus, at, updates))
        return extra

    def observe(self, bus, at, changes):
        for peer in self.peers:
            peer.observe(bus, at, changes)


def i2c_program(fast, variant, option, *, interval=32, limit=60_000, sample=28):
    """EVAL-016 I2C controller with the status in R5 and a timeout path for B and C."""
    low, high, hold, setup = (94, 56, 48, 20) if fast else (310, 300, 255, 20)
    restart_gap, bus_free = (48, 90) if fast else (300, 300)
    TX, RX, FLAG, N, STATUS, SCRATCH = 1, 2, 3, 4, 5, 7

    def put(pin, value, delay=0):
        return ("pad", pin, value, 1, delay)

    if option == "B":
        if limit // interval > 0xFFFF:
            raise ValueError("poll budget exceeds a 16-bit loop counter; needs a nested loop")
        # A released SCL reaches the second synchronizer stage 3 cycles later, as wait_save sees it.
        rise = ["rise", put(SCL, 1, low), *advance(low + 3), ("set", SCRATCH, limit // interval),
                "poll", ("cap", SCL, FLAG, 0, 0), ("jnz", FLAG, "risen"), *advance(interval),
                ("loop", SCRATCH, "poll"), ("jump", "timeout"), "risen", ("ret",)]
    elif option == "C":
        rise = ["rise", put(SCL, 1, low), ("set", SCRATCH, limit // UNIT), ("wait_to", SCL, 1, low, SCRATCH),
                ("jnz", SCRATCH, "risen"), ("jump", "timeout"), "risen", ("ret",)]
    elif option in ("C2", "C2-nofence"):
        # Unguarded: the program runs ahead of the pins, so the previous SCL fall may still be
        # queued and SCL still high. C2 fences to the release first; C2-nofence shows the failure.
        fence = [("fence", low)] if option == "C2" else []
        rise = ["rise", put(SCL, 1, low), ("set", SCRATCH, limit // UNIT), *fence,
                ("wait_tou", SCL, 1, low, SCRATCH), ("jnz", SCRATCH, "risen"), ("jump", "timeout"), "risen", ("ret",)]
    else:
        rise = ["rise", put(SCL, 1, low), ("wait_save", SCL, 1, low), ("ret",)]
    # 64-cycle lead: with another context issuing, 16 cycles is not enough to admit the first drive.
    lines = [("host_get", TX), ("save_now",), *advance(64), ("set", RX, 0),
             ("call", "start"), ("set", STATUS, 0xA000), ("call", "write_status"), ("jnz", FLAG, "nack"),
             ("call", "write"), ("jnz", FLAG, "nack"), ("call", "write"), ("jnz", FLAG, "nack")]
    if variant == "separate":
        lines += [("call", "stop"), *advance(hold + bus_free), ("call", "start")]
    else:
        lines += [put(SDA, 1, setup), ("call", "rise"), *advance(restart_gap), ("call", "start")]
    lines += [("set", STATUS, 0xA100), ("call", "write_status"), ("jnz", FLAG, "nack"),
              ("call", "read"), put(SDA, 0, setup), ("call", "rise"), ("call", "fall"),
              ("call", "read"), put(SDA, 1, setup), ("call", "rise"), ("call", "fall"),
              ("host_put", RX), ("set", STATUS, OK), ("jump", "finish"),
              "nack", ("set", STATUS, NACK),
              "finish", ("call", "stop"), ("host_put", STATUS), ("halt",),
              # Release both lines from a fresh timebase; a held SCL cannot see a STOP.
              "timeout", ("save_now",), ("pad2", SCL, 1, 1, SDA, 1, 1, 8), ("set", STATUS, TIMEOUT),
              ("host_put", STATUS), ("halt",),
              "start", put(SDA, 0), put(SCL, 0, hold), *advance(hold), ("ret",),
              "stop", put(SDA, 0, setup), ("call", "rise"), put(SDA, 1, hold), ("fence", hold + 1), ("ret",),
              *rise,
              "fall", put(SCL, 0, high), *advance(high), ("ret",),
              # write_status sends the address byte held in STATUS; write sends the next byte of TX.
              "write_status", ("set", N, 8), "wsbit", ("shift_pin", STATUS, SDA, setup, 0), ("call", "rise"),
              ("call", "fall"), ("loop", N, "wsbit"), ("jump", "ack"),
              "write", ("set", N, 8), "wbit", ("shift_pin", TX, SDA, setup, 0), ("call", "rise"), ("call", "fall"),
              ("loop", N, "wbit"),
              "ack", put(SDA, 1, setup), ("call", "rise"), ("cap", SDA, FLAG, 0, sample), ("call", "fall"), ("ret",),
              "read", ("set", N, 8), "rbit", put(SDA, 1, setup), ("call", "rise"), ("cap", SDA, RX, 1, sample),
              ("call", "fall"), ("loop", N, "rbit"), ("ret",)]
    return lines


def spi_loop_program(count, gap, mode=0, half=30):
    """Context 1: ``count`` SPI exchanges, ``gap`` cycles apart, one host word each way."""
    idle, late = divmod(mode, 2)
    phase0 = 1 - idle if late else idle
    lines = [("set", 5, count), ("save_now",), *advance(2000),
             "txn", ("host_get", 1), ("set", 2, 0), ("set", 4, 16), ("pad", CS, 0, 1, 16),
             *advance(16 + 16 + half * late),
             "bit", ("shift_pair", 1, MOSI, SCLK, phase0, 0), ("pad", SCLK, 1 - phase0, 1, half),
             ("cap", MISO, 2, 1, half + 3), *advance(2 * half), ("loop", 4, "bit")]
    if not late:
        lines.append(("pad", SCLK, idle, 1, 0))
    return lines + [("pad", CS, 1, 1, 8), ("fence", 9), ("host_put", 2), *advance(gap), ("loop", 5, "txn"), ("halt",)]


def prefixed(lines, tag):
    out = []
    for line in lines:
        if isinstance(line, str):
            out.append(f"{tag}.{line}")
        else:
            out.append(tuple(f"{tag}.{a}" if isinstance(a, str) and i else a for i, a in enumerate(line)))
    return out


def build(programs, ingress, bus, owners, *, epoch=0):
    """Assemble one image with an entry per program and start every context."""
    lines = [line for tag, body in programs for line in [f"{tag}.entry", *prefixed(body, tag)]]
    code, labels = assemble(lines, formats=FORMATS)
    entries = tuple(labels[f"{tag}.entry"] for tag, _ in programs)
    image = Image((code,), entries, (b"",) * len(entries))
    masks = [sum(1 << i for i, name in enumerate(bus.idle) if name in owner) for owner in owners]
    endpoint, link = prepare(image, tuple(map(tuple, ingress)), enabled=(1 << len(entries)) - 1,
                             owner0=masks[0], owner1=masks[1] if len(masks) > 1 else 0)
    fetched = b"".join(endpoint.fetch(pc) for pc in range(endpoint.cfg.count))
    pins = tuple(bus.idle)
    runs = [isa_execute(fetched, pc, pins, bus.open_drain, epoch, table=DECODE) for pc in entries]
    probe = TimeoutProbe(runs, bus, owners, epoch=epoch, endpoint=endpoint)
    return probe, endpoint, link, len(code) // 3


def stop_delay():
    """Cycles from the host deciding to stop until the safe edge, at 1 MHz SCK (DEC-005)."""
    endpoint, transport = host_started(1, "eval004")
    _, _, validate, _, _ = host_run(transport, endpoint, packet(STOP))
    return (validate + PHASES) // PHASES


def regression_case(case, option, limit, interval=32):
    """One EVAL-016 I2C case, single context, with a timeout option enabled."""
    bus = Pins(pins_for({SCL: "scl", SDA: "sda"}, {"scl": 1, "sda": 1}), open_drain=("scl", "sda"),
               peer=I2CPeer(case))
    program = i2c_program(case.fast, case.variant, option, interval=interval, limit=limit)
    probe, endpoint, link, words = build([("i2c", program)], [[0x964B]], bus, [{"scl", "sda"}])
    if option == "D":
        probe.watchdog = {0: limit}
    end = probe.run(200_000)
    got = drain(endpoint, link, 0)
    ok = bool(got) and got[-1] == OK
    errors = [f"fault {probe.fault}"] if probe.fault else []
    if not errors:
        errors, _ = i2c_check(bus, {"i2c_ok": [ok] if got else [], "i2c_rx": words_to_bytes(got[:-1]) if ok else []},
                              case)
    return {"kind": "regression", "case": case.name, "option": option, "interval": interval if option == "B" else None,
            "pass": not errors, "errors": errors[:2], "words": words, "end": end}


def stuck_case(fast, option, hold, at_rises, limit, interval=32, spi_count=6):
    """I2C in context 0 with a stuck SCL; SPI exchanges in context 1 over 1.5 x the limit."""
    case = I2CCase("combined", fast)
    i2c_peer = StuckPeer(case, hold, at_rises)
    spi_peer = SPIPeer(0, 30)
    names = {SCL: "scl", SDA: "sda", CS: "cs", MOSI: "mosi", MISO: "miso", SCLK: "sclk"}
    bus = Pins(pins_for(names, {"scl": 1, "sda": 1, "cs": 1}), open_drain=("scl", "sda"),
               peer=Both(i2c_peer, spi_peer))
    gap = (3 * limit) // (2 * spi_count)
    programs = [("i2c", i2c_program(fast, "combined", option, interval=interval, limit=limit)),
                ("spi", spi_loop_program(spi_count, gap))]
    probe, endpoint, link, words = build(programs, [[0x964B], [0x964B] * spi_count], bus,
                                         [{"scl", "sda"}, {"cs", "mosi", "sclk"}])
    if option == "D":
        probe.watchdog = {0: limit}
    if option == "A":
        probe.host_stop = (i2c_peer, limit, stop_delay())
    horizon = 4 * limit + (hold or 0) + 50_000
    error = None
    try:
        end = probe.run(horizon)
    except Exception as exc:  # A model timeout means the stall was never resolved.
        end, error = None, f"{type(exc).__name__}: {exc}"
    i2c_words, spi_words = drain(endpoint, link, 0), drain(endpoint, link, 1)
    status_at = next((t for t, owner, kind, word in probe.transfers if owner == 0 and kind == "host_put"
                      and word == TIMEOUT), None)
    detected = status_at if status_at is not None else (probe.fault[0] if probe.fault else None)
    if option == "A" and probe.stopped_at is not None:
        detected = probe.stopped_at
    stuck = i2c_peer.stuck_at
    latency = None if detected is None or stuck is None else detected - stuck
    released = all(probe.bus.drive["dut"].get(pin) is None for pin in ("scl", "sda"))
    starts = [t for t, name, v in bus.edges if name == "cs" and v == 0]
    spi_errors, _, _ = spi_check(bus, words_to_bytes(spi_words), 0, 30, starts)
    expect_timeout = hold is None or hold > limit
    errors = []
    if error:
        errors.append(error)
    if expect_timeout:
        if latency is None:
            errors.append("stuck SCL not detected")
        # B and C count in poll intervals or 64-cycle units and D from the last issue, so allow 2 %.
        elif not 0.98 * limit <= latency <= 1.02 * limit + (stop_delay() if option == "A" else 0):
            errors.append(f"detection latency {latency} outside the limit window")
        if option in ("B", "C") and i2c_words != [TIMEOUT]:
            errors.append(f"expected a timeout status, got {i2c_words}")
        if not released:
            errors.append("I2C lines still driven after the timeout")
    elif i2c_words[-1:] != [OK]:
        errors.append(f"legitimate stretch did not complete: {i2c_words}")
    return {"kind": "stuck", "case": f"{'400k' if fast else '100k'}-clock{at_rises[0] + 1}-"
                                     + ("forever" if hold is None else f"{hold}clk"),
            "option": option, "interval": interval if option == "B" else None, "limit": limit,
            "pass": not errors, "errors": errors[:3], "latency": latency,
            "other_context": "complete" if not spi_errors and len(starts) == spi_count
                             else f"stopped after {len(starts)} of {spi_count} exchanges",
            "words": words}


def contended_case(case, option, gap=400):
    """An EVAL-016 I2C case with full timing checks while context 1 runs SPI exchanges ``gap`` cycles apart."""
    names = {SCL: "scl", SDA: "sda", CS: "cs", MOSI: "mosi", MISO: "miso", SCLK: "sclk"}
    bus = Pins(pins_for(names, {"scl": 1, "sda": 1, "cs": 1}), open_drain=("scl", "sda"),
               peer=Both(I2CPeer(case), SPIPeer(0, 30)))
    programs = [("i2c", i2c_program(case.fast, case.variant, option)), ("spi", spi_loop_program(6, gap))]
    probe, endpoint, link, words = build(programs, [[0x964B], [0x964B] * 6], bus,
                                         [{"scl", "sda"}, {"cs", "mosi", "sclk"}])
    probe.run(400_000)
    got = drain(endpoint, link, 0)
    ok = bool(got) and got[-1] == OK
    errors, margin = i2c_check(bus, {"i2c_ok": [ok] if got else [], "i2c_rx": words_to_bytes(got[:-1]) if ok else []},
                               case)
    starts = [t for t, name, v in bus.edges if name == "cs" and v == 0]
    spi_errors, _, _ = spi_check(bus, words_to_bytes(drain(endpoint, link, 1)), 0, 30, starts)
    errors = ([f"fault {probe.fault}"] if probe.fault else []) + errors + spi_errors
    return {"kind": "contended", "case": case.name, "option": option, "interval": None, "gap": gap,
            "pass": not errors, "errors": errors[:2], "min_margin": margin[0] if margin else None, "words": words}


REGRESSION = [I2CCase(v, fast) for fast in (False, True) for v in ("separate", "combined", "nack-address", "nack-data")]
REGRESSION += [I2CCase("combined", fast, s) for fast in (False, True) for s in (60, 300, 600)]
LIMIT = 60_000  # 1 ms sweep limit; one run per option uses 25 ms (1.5 M cycles).
OPTIONS = [("A", None), ("B", 16), ("B", 32), ("B", 64), ("C", None), ("C2", None), ("D", None)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = []
    for option, interval in OPTIONS:
        if option != "A":  # A uses the unchanged program, already covered by EVAL-016.
            rows += [regression_case(case, option, LIMIT, interval or 32) for case in REGRESSION]
        for fast in (False, True):
            # Clock 10 is the first data bit; clock 28 sets up the repeated START.
            for hold, rises in ((None, (9,)), (None, (27,)), (2 * LIMIT, (9,)), (600, (27,))):
                rows.append(stuck_case(fast, option, hold, rises, LIMIT, interval or 32))
        try:
            rows.append(stuck_case(True, option, 1_800_000, (9,), 1_500_000, interval or 32))
        except ValueError as exc:
            rows.append({"kind": "stuck", "case": "400k-clock10-1800000clk", "option": option, "interval": interval,
                         "limit": 1_500_000, "pass": None, "errors": [str(exc)], "latency": None,
                         "other_context": None, "words": None})
    for option in ("A", "C", "C2"):
        rows += [contended_case(case, option) for case in REGRESSION]
        rows += [contended_case(case, option, gap) for case in REGRESSION if case.fast for gap in range(380, 440, 3)]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"stop_delay_cycles": stop_delay(), "rows": rows}, default=clock_json,
                                       indent=1) + "\n", encoding="utf-8")
    for option, interval in OPTIONS:
        mine = [r for r in rows if r["option"] == option and r["interval"] == interval]
        reg = [r for r in mine if r["kind"] == "regression"]
        cont = [r for r in mine if r["kind"] == "contended"]
        if cont:
            print(f"{option} with SPI busy: {sum(r['pass'] for r in cont)}/{len(cont)},"
                  f" min I2C margin {min((r['min_margin'] for r in cont if r['min_margin'] is not None), default=None)}")
        stuck = [r for r in mine if r["kind"] == "stuck"]
        lat = [r["latency"] - r["limit"] for r in stuck if r["latency"] is not None and r["pass"]
               and r["case"].endswith(("forever", "clk")) and not r["case"].endswith("600clk")]
        print(f"{option}{'' if interval is None else f' every {interval}'}: regression {sum(r['pass'] is True for r in reg)}"
              f"/{len(reg)}, stuck {sum(r['pass'] is True for r in stuck)}/{len(stuck)},"
              f" words {sorted({r['words'] for r in mine if r['words']})},"
              f" latency beyond limit {min(lat, default=None)}..{max(lat, default=None)},"
              f" other context {sorted({r['other_context'] for r in stuck} - {None})}")
        for r in mine:
            if r["pass"] is not True:
                print("   ", r["kind"], r["case"], r["pass"], r["errors"][:2])
    return int(not all(r["pass"] is not False for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
