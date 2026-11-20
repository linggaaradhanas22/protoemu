"""Payload FIFO demand and streaming limits for the SPI loader host (EVAL-014).

Timing comes from the EVAL-004 serial transport model: 250 kHz SCK, 2 us guards
and a 24 us inter-frame budget. A host READ pops one word on the edge that
validates its request frame; the reply follows in the next frame.
"""

import argparse
import json
from pathlib import Path

from .g4_loader import EMPTY, OK, READ, START, US, WRITE, Endpoint, Transport, load, packet, transact

UART_RATES = (9600, 19200, 38400, 57600, 115200)
DEPTHS = (2, 4, 6, 8, 16)
UNBOUNDED = 2000  # A burst this long without a stall counts as "host keeps up".

# Words a context must hold without host service during one specified test.
# ``unpacked``: one byte (or one result) per word; ``packed``: two bytes per word.
# Source: the TEST text in design/06_verif_plan.md and the EVAL-009/010 replays.
DEMAND = [
    {"test": "TEST-SYS-005 UART RX", "direction": "egress", "unpacked": 6, "packed": 3,
     "note": "six back-to-back frames at up to 115200 baud"},
    {"test": "TEST-SYS-006 SPI", "direction": "ingress", "unpacked": 2, "packed": 1, "note": "two bytes per CS"},
    {"test": "TEST-SYS-006 SPI", "direction": "egress", "unpacked": 2, "packed": 1, "note": "two bytes per CS"},
    {"test": "EVAL-009 overlap, UART context", "direction": "egress", "unpacked": 3, "packed": 2,
     "note": "measured: three bytes, one per word"},
    {"test": "EVAL-009 overlap, SPI context", "direction": "ingress", "unpacked": 4, "packed": 2,
     "note": "measured: two 16-bit words"},
    {"test": "EVAL-009 overlap, SPI context", "direction": "egress", "unpacked": 4, "packed": 2,
     "note": "measured: two 16-bit words"},
    {"test": "TEST-SYS-013 WS2812", "direction": "ingress", "unpacked": 6, "packed": 3,
     "note": "two RGB values, if the host supplies them"},
    {"test": "TEST-SYS-013 1-Wire", "direction": "egress", "unpacked": 9, "packed": 5,
     "note": "presence + 64-bit ROM; slow enough for the host to drain during the read"},
    {"test": "TEST-SYS-013 RC5", "direction": "egress", "unpacked": 2, "packed": 2,
     "note": "measured: two 14-bit frames"},
]


def host_timing():
    """Measure a READ that returns a word, an EMPTY READ, and a WRITE, in microseconds."""
    endpoint, link = Endpoint(), Transport("serial", 0)
    load(link, endpoint, b"\x00\x00\x00", (1, 0, 0, 0, 0, 0))
    assert transact(link, endpoint, packet(START))[0] == (OK, b"")
    endpoint.egress[0].append(0x1234)
    rows = {}
    for name, request in (("read", packet(READ, b"\x00")), ("read_empty", packet(READ, b"\x00")),
                          ("write", packet(WRITE, b"\x00\x34\x12"))):
        start = link.t
        (status, _), edge = transact(link, endpoint, request)
        rows[name] = {"status": status, "period_us": (link.t - start) / US, "pop_us": (edge - start) / US}
    assert rows["read"]["status"] == OK and rows["read_empty"]["status"] == EMPTY
    return rows


def max_burst(rate, per_word, depth, timing):
    """Longest burst of back-to-back 8N1 bytes that never finds the egress FIFO full.

    The host polls READ continuously from the first byte. A context packs
    ``per_word`` bytes into each word and pushes it when the last byte ends.
    """
    frame_us = 10e6 / rate
    hit, miss = timing["read"], timing["read_empty"]
    for n in range(1, UNBOUNDED + 1):
        pushes = [((k + 1) * per_word) * frame_us for k in range(-(-n // per_word))]
        t, count, i = 0.0, 0, 0
        ok = True
        while i < len(pushes) or count:
            pop_at = t + hit["pop_us"]
            # Words pushed before this pop edge are visible to it.
            while i < len(pushes) and pushes[i] < pop_at:
                if count == depth:
                    ok = False
                    break
                count += 1
                i += 1
            if not ok:
                break
            if count:
                count -= 1
                t += hit["period_us"]
            else:
                t += miss["period_us"]
        if not ok:
            return n - 1
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    timing = host_timing()
    for name, row in timing.items():
        print(f"{name:10s} period {row['period_us']:.1f} us, FIFO access {row['pop_us']:.1f} us after start")
    demand = DEMAND
    for row in demand:
        print(f"{row['test']:32s} {row['direction']:7s} {row['unpacked']} words unpacked, {row['packed']} packed")
    bursts = []
    for per_word in (1, 2):
        for rate in UART_RATES:
            row = {"rate": rate, "bytes_per_word": per_word,
                   "max_burst_bytes": {depth: max_burst(rate, per_word, depth, timing) for depth in DEPTHS}}
            bursts.append(row)
            print(per_word, rate, row["max_burst_bytes"])
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"host_timing": timing, "demand": demand, "uart_bursts": bursts,
                                        "unbounded_limit": UNBOUNDED}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
