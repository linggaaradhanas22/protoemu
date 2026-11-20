"""Host payload rate: loader SCK, frame overhead and multi-word transfers (EVAL-015).

Builds on the EVAL-004 SPI transport. Two provisional commands are added:

* ``READN ctx, n``: reply with up to ``n`` egress words. The words stay in the
  FIFO while the reply is sent and are removed when the reply frame closes, so
  an interrupted reply can restart from bit zero without losing data.
* ``WRITEN ctx, words``: accept as many leading words as fit when the request
  frame is validated. The reply carries the accepted count.

``n = 1`` uses the existing single-word ``READ``/``WRITE``.
"""

import argparse
import json
from pathlib import Path

from .g4_loader import (EMPTY, FULL, OK, PHASES, READ, START, STATE, US, WRITE, Endpoint, Transport,
                        decode, load, packet)

READN, WRITEN = 8, 9  # Provisional opcodes for this study only.
SCK_MHZ = (0.25, 0.5, 1, 2, 4, 8)
OVERHEADS = {
    # EVAL-004 assumption: 2 us lead guard; 2 us lag guard within a 24 us tail budget.
    "eval004": {"lead": 2 * US, "lag": 2 * US, "tail": 24 * US},
    # Guess for tight RP2350 firmware: 1 us guards and 4 us dispatch. Not measured.
    "tight": {"lead": US, "lag": US, "tail": 5 * US},
}
WORDS = (1, 4, 8)
DEPTHS = (4, 8, 16)
BAUDS = (38400, 57600, 115200)
LONG = 2000  # Bytes per simulated stream; no failure within this counts as sustained.


class MultiEndpoint(Endpoint):
    def __init__(self):
        super().__init__()
        self.pending_pop = None

    def command(self, frame, edge):
        self.pending_pop = None
        try:
            op, data = decode(frame)
        except ValueError:
            return super().command(frame, edge)
        if op not in (READN, WRITEN):
            return super().command(frame, edge)
        if not data or not self.valid or data[0] not in (0, 1) or not self.cfg.enabled & (1 << data[0]):
            return packet(STATE)
        ctx = data[0]
        if op == READN and len(data) == 2:
            fifo = self.egress[ctx]
            k = min(data[1], len(fifo))
            if not k:
                return packet(EMPTY)
            self.pending_pop = (ctx, k)
            return packet(OK, b"".join(word.to_bytes(2, "little") for word in list(fifo)[:k]))
        if op == WRITEN and len(data) % 2 == 1:
            words = [int.from_bytes(data[i:i + 2], "little") for i in range(1, len(data), 2)]
            fifo = self.ingress[ctx]
            k = min(len(words), self.depth - len(fifo))
            fifo.extend(words[:k])
            return packet(OK if k == len(words) else FULL, bytes((k,)))
        return packet(STATE)

    def reply_done(self):
        if self.pending_pop:
            ctx, k = self.pending_pop
            for _ in range(k):
                self.egress[ctx].popleft()
            self.pending_pop = None


def link(sck_mhz, overhead, phase=0):
    half = round(US / (2 * sck_mhz))
    return Transport("serial", phase, half=half, **OVERHEADS[overhead])


def started(sck_mhz, overhead, depth=8, phase=0):
    endpoint, transport = MultiEndpoint(), link(sck_mhz, overhead, phase)
    endpoint.depth = depth
    load(transport, endpoint, b"\x00\x00\x00", (1, 0, 0, 0, 0, 0))
    run(transport, endpoint, packet(START))
    return endpoint, transport


def run(transport, endpoint, request):
    """One request and reply. Return status, body and times relative to the start (ticks)."""
    start = transport.t
    received, validate = transport.frame(request)
    reply = endpoint.command(received, validate)
    answer, closed = transport.frame(reply, reply=True)
    endpoint.reply_done()
    status, body = decode(answer)
    return status, body, validate - start, closed - start, transport.t - start


def feasible(sck_mhz, overhead):
    """Check the transport's synchronizer assertions at every host phase."""
    try:
        for phase in range(PHASES):
            endpoint, transport = started(sck_mhz, overhead, phase=phase)
            endpoint.egress[0].extend(range(8))
            run(transport, endpoint, packet(READN, bytes((0, 8))))
            run(transport, endpoint, packet(WRITEN, bytes((0,)) + bytes(16)))
    except AssertionError:
        return False
    return True


def timing(sck_mhz, overhead, n):
    """Per-transaction times in us, by number of words moved (0..n)."""
    endpoint, transport = started(sck_mhz, overhead, depth=16)
    rx, tx = {}, {}
    for k in range(n + 1):
        endpoint.egress[0].clear()
        endpoint.egress[0].extend(range(k))
        request = packet(READ, b"\x00") if n == 1 else packet(READN, bytes((0, n)))
        status, body, validate, closed, period = run(transport, endpoint, request)
        assert len(body) == 2 * k and status == (OK if k else EMPTY)
        # Single-word READ pops on validation; READN frees words when its reply closes.
        rx[k] = {"free_us": (validate if n == 1 else closed) / US, "check_us": validate / US, "period_us": period / US}
    for k in range(1, n + 1):
        endpoint.ingress[0].clear()
        request = (packet(WRITE, bytes((0, 0, 0))) if n == 1
                   else packet(WRITEN, bytes((0,)) + bytes(2 * k)))
        status, _, validate, _, period = run(transport, endpoint, request)
        assert status == OK
        tx[k] = {"push_us": validate / US, "period_us": period / US}
    return rx, tx


def rx_burst(baud, depth, n, rx):
    """Longest back-to-back UART receive burst (one byte per word) without a full egress."""
    frame = 10e6 / baud
    pushes = [(j + 1) * frame for j in range(LONG)]
    t, count, reserved, i, releases = 0.0, 0, 0, 0, []
    while i < len(pushes):
        check = t + rx[0]["check_us"]
        while i < len(pushes) and pushes[i] < check:
            for release in sorted(releases):
                if release[0] <= pushes[i]:
                    count -= release[1]
                    reserved -= release[1]
                    releases.remove(release)
            if count == depth:
                return i
            count += 1
            i += 1
        k = min(n, count - reserved)
        if k:
            reserved += k
            if n == 1:
                count -= k
                reserved -= k
            else:
                releases.append((t + rx[k]["free_us"], k))
        t += rx[k]["period_us"]
    return None


def tx_burst(baud, depth, n, tx):
    """Longest back-to-back UART transmit burst from a preloaded ingress FIFO."""
    frame = 10e6 / baud
    needs = [j * frame for j in range(LONG)]
    count, sent, popped, t = min(depth, LONG), min(depth, LONG), 0, 0.0
    while popped < LONG:
        k = min(n, LONG - sent)
        push = t + tx[max(k, 1)]["push_us"]
        while popped < LONG and needs[popped] <= push:
            if count == 0:
                return popped
            count -= 1
            popped += 1
        if k:
            accepted = min(k, depth - count)
            count += accepted
            sent += accepted
        t += tx[max(k, 1)]["period_us"]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows, ok = [], {}
    for overhead in OVERHEADS:
        for sck in SCK_MHZ:
            ok[(sck, overhead)] = feasible(sck, overhead)
            for n in WORDS:
                rx, tx = timing(sck, overhead, n)
                for depth in DEPTHS:
                    for baud in BAUDS:
                        rows.append({"overhead": overhead, "sck_mhz": sck, "words": n, "depth": depth,
                                     "baud": baud, "feasible": ok[(sck, overhead)],
                                     "rx_us_per_word": rx[n]["period_us"] / n, "tx_us_per_word": tx[n]["period_us"] / n,
                                     "rx_burst": rx_burst(baud, depth, n, rx), "tx_burst": tx_burst(baud, depth, n, tx)})
    for overhead in OVERHEADS:
        print(f"\n{overhead}: depth 8, max burst bytes RX/TX ('-' = sustained over {LONG})")
        print("SCK MHz  words  us/word(rx)  " + "  ".join(f"{b:>13d}" for b in BAUDS))
        for row in rows:
            if row["overhead"] == overhead and row["depth"] == 8 and row["baud"] == BAUDS[0]:
                cells = []
                for baud in BAUDS:
                    r = next(x for x in rows if x["overhead"] == overhead and x["depth"] == 8
                             and x["sck_mhz"] == row["sck_mhz"] and x["words"] == row["words"] and x["baud"] == baud)
                    cells.append(f"{r['rx_burst'] or '-':>6}/{r['tx_burst'] or '-':<6}")
                flag = "" if row["feasible"] else "  (fails synchronizer check)"
                print(f"{row['sck_mhz']:7}  {row['words']:5d}  {row['rx_us_per_word']:11.1f}  " + "  ".join(cells) + flag)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        feas = [{"overhead": o, "sck_mhz": s, "feasible": v} for (s, o), v in ok.items()]
        args.out.write_text(json.dumps({"overheads_us": {k: {x: v / US for x, v in o.items()} for k, o in OVERHEADS.items()},
                                        "long_stream_bytes": LONG, "feasible": feas, "rows": rows}, indent=1) + "\n",
                            encoding="utf-8")


if __name__ == "__main__":
    main()
