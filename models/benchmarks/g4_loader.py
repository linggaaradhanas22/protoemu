"""G4 loader probe: sampled host transfers and an abstract load/run endpoint."""

from binascii import crc_hqx
from collections import deque
from dataclasses import dataclass

PHASES = 16
MHZ = 60
US = MHZ * PHASES
OK, COMPLETE, BAD, STATE, FULL, EMPTY = range(6)
BEGIN, DATA, COMMIT, START, STOP, WRITE, READ = range(1, 8)


def sample(tick):
    """First ASIC decision edge that sees a pin through two flop stages."""
    return ((tick + PHASES - 1) // PHASES + 2) * PHASES


def packet(op, body=b""):
    header_body = bytes((op,)) + len(body).to_bytes(2, "little") + body
    return header_body + crc_hqx(header_body, 0xFFFF).to_bytes(2, "little")


def decode(frame):
    if len(frame) < 5 or len(frame) != int.from_bytes(frame[1:3], "little") + 5:
        raise ValueError("length")
    if crc_hqx(frame[:-2], 0xFFFF) != int.from_bytes(frame[-2:], "little"):
        raise ValueError("CRC")
    return frame[0], frame[3:-2]


class Transport:
    def __init__(self, kind, phase, poll_slip=0):
        self.kind = kind
        self.t = phase
        self.poll_slip = poll_slip

    def frame(self, data, *, reply=False):
        opened = sample(self.t)
        self.t += 2 * US
        received = bytearray()
        for byte in data:
            if self.kind == "serial":
                rx = 0
                for shift in range(7, -1, -1):
                    launch = self.t
                    rising = launch + 2 * US
                    next_launch = rising + 2 * US
                    if reply:
                        # TX bit is registered after synchronized falling SCK.
                        assert sample(launch) + PHASES < rising
                    else:
                        assert sample(launch) < sample(rising) < sample(next_launch)
                    assert opened < sample(rising)
                    rx = (rx << 1) | ((byte >> shift) & 1)
                    self.t = next_launch
            elif self.kind == "nibble":
                rx = 0
                for shift in (4, 0):
                    setup = self.t
                    req = setup + US
                    accept = sample(req) + PHASES
                    assert opened < accept and sample(setup) < accept
                    # The host polls the ACK toggle, then waits before reading
                    # the registered reply nibble and changing its own pins.
                    ack_seen = req + ((accept - req + 5 * US - 1) // (5 * US)) * 5 * US
                    ack_seen += self.poll_slip
                    self.t = ack_seen + US
                    assert accept < self.t
                    rx = (rx << 4) | ((byte >> shift) & 15)
            else:
                raise ValueError(self.kind)
            received.append(rx)
        closed = sample(self.t + 2 * US)
        # Inter-frame budget covers response register/READY and host dispatch.
        self.t += 24 * US
        assert self.t > closed
        return bytes(received), closed


@dataclass(frozen=True)
class Config:
    count: int
    enabled: int
    pc0: int
    pc1: int
    owner0: int
    owner1: int
    open_drain: int

    def valid(self):
        pcs = (self.pc0, self.pc1)
        masks = (self.owner0, self.owner1)
        return (1 <= self.count <= 128 and 1 <= self.enabled <= 3
                and not self.owner0 & self.owner1
                and not self.open_drain & ~(self.owner0 | self.owner1)
                and all(pc < self.count if self.enabled & (1 << i) else pc == masks[i] == 0
                        for i, pc in enumerate(pcs)))


class Endpoint:
    depth = 8

    def __init__(self):
        self.store = bytearray(384)
        self.clear()
        self.last_emitted = []

    def clear(self):
        self.valid = self.running = self.written = False
        self.cfg = None
        self.due = []
        self.safe_at = None
        self.ingress = [deque(), deque()]
        self.egress = [deque(), deque()]

    def stop_at(self, edge):
        self.last_emitted = [(t, value) for t, value in sorted(self.due) if t < edge]
        self.clear()
        self.safe_at = edge

    def deselect(self, tick):
        self.stop_at(sample(tick))

    def reset(self, tick):
        self.stop_at(((tick + PHASES - 1) // PHASES) * PHASES)

    def fetch(self, pc):
        if not self.running or not 0 <= pc < self.cfg.count:
            return None
        return bytes(self.store[pc * 3:pc * 3 + 3])

    def report(self, ctx, word):
        if not self.running or not self.cfg.enabled & (1 << ctx):
            return False
        fifo = self.egress[ctx]
        if len(fifo) == self.depth:
            return False
        fifo.append(word)
        return True

    def command(self, frame, edge):
        try:
            op, data = decode(frame)
        except ValueError:
            if not self.running:
                self.clear()
            return packet(BAD)
        if op in (BEGIN, DATA, COMMIT) and self.running:
            return packet(STATE)
        if op == BEGIN:
            self.clear()
            if len(data) != 7 or not (cfg := Config(*data)).valid():
                return packet(BAD)
            self.cfg = cfg
        elif op == DATA:
            if not self.cfg or self.written or self.valid or len(data) != self.cfg.count * 3:
                self.clear()
                return packet(BAD)
            self.store[:len(data)] = data
            self.written = True
        elif op == COMMIT:
            if data or not self.written or self.valid:
                self.clear()
                return packet(BAD)
            self.valid = True
            return packet(COMPLETE)
        elif op == START and not data:
            if not self.valid or self.running:
                return packet(STATE)
            self.running = True
        elif op == STOP and not data:
            self.stop_at(edge + PHASES)
        elif op in (WRITE, READ) and len(data) == (3 if op == WRITE else 1):
            ctx = data[0]
            if not self.valid or ctx not in (0, 1) or not self.cfg.enabled & (1 << ctx):
                return packet(STATE)
            if op == WRITE:
                fifo = self.ingress[ctx]
                if len(fifo) == self.depth:
                    return packet(FULL)
                fifo.append(int.from_bytes(data[1:], "little"))
            else:
                fifo = self.egress[ctx]
                if not fifo:
                    return packet(EMPTY)
                return packet(OK, fifo.popleft().to_bytes(2, "little"))
        else:
            return packet(BAD)
        return packet(OK)


def transact(link, endpoint, request):
    received, edge = link.frame(request)
    reply = endpoint.command(received, edge)
    received, _ = link.frame(reply, reply=True)
    return decode(received), edge


def load(link, endpoint, image, config):
    count = len(image) // 3
    start = link.t
    for op, body, status in ((BEGIN, bytes((count, *config)), OK),
                             (DATA, image, OK), (COMMIT, b"", COMPLETE)):
        answer, _ = transact(link, endpoint, packet(op, body))
        assert answer == (status, b"")
    return (link.t - start) / (1000 * US)
