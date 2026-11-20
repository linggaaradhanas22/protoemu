"""Explore generic host payload instructions on the G4 cycle scheduler."""

import argparse
import json
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from .cycle import ModelError, clock_json
from .encoded import Image
from .encoded_programs import TX
from .g4_isa import PAD_FORMATS, assemble, source
from .g4_loader import EMPTY, OK, READ, START, WRITE, Endpoint, Transport, load, packet, transact
from .g4_pad_encoding import PIN_ORDERS, PadProbe, translate
from .run_compare import measure
from .run_encoded import spi_bench
from .spi_uart import TX as PEER_TX

FORMATS = {op: fmt for op, fmt in PAD_FORMATS.items() if op != "report"}
FORMATS.update(host_get=(23, (3,)), host_put=(24, (3,)))
DECODE = {code: (op, bits) for op, (code, bits) in FORMATS.items()}
SPI_WORD = int.from_bytes(bytes(PEER_TX), "big")


class PayloadProbe(PadProbe):
    decode_table = DECODE

    def __init__(self, *args, endpoint, **kwargs):
        super().__init__(*args, **kwargs)
        self.endpoint = endpoint
        self.transfers = []

    def _instruction_ready(self, owner, op, t):
        if op.kind == "host_get":
            return bool(self.endpoint.ingress[owner])
        if op.kind == "host_put":
            return len(self.endpoint.egress[owner]) < self.endpoint.depth
        return super()._instruction_ready(owner, op, t)

    def _issue_result(self, owner, op, t):
        if op.kind == "host_get":
            word = self.endpoint.ingress[owner].popleft()
        elif op.kind == "host_put":
            word = op.word
            if not self.endpoint.report(owner, word):
                raise ModelError("payload write not accepted by the loader endpoint")
        else:
            return super()._issue_result(owner, op, t)
        self.transfers.append((t, owner, op.kind, word))
        return word


def build(offset):
    lines, entries = source("overlap", spi_offset=offset)
    pins = (0, 3, 1, 2, 6)
    rewritten = []
    replaced_tx = 0
    for line in translate(lines, pins, "compact"):
        if line == ("set", TX, SPI_WORD):
            rewritten.append(("host_get", TX))
            replaced_tx += 1
        elif not isinstance(line, str) and line[0] == "report":
            _, channel, reg = line
            if channel == 2:
                # This program uses bit 8 to distinguish a bad stop bit from a byte.
                rewritten.append(("set", reg, 0x100))
            elif channel not in (0, 1):
                raise ValueError("unexpected report in the overlap fixture")
            rewritten.append(("host_put", reg))
        else:
            rewritten.append(line)
    if replaced_tx != 1:
        raise ValueError("expected one SPI transmit load inside the shared subroutine")
    code, labels = assemble(rewritten, formats=FORMATS)
    return Image((code,), tuple(labels[name] for name in entries), (b"", b""))


def prepare(image, words, *, depth=8, enabled=3, owner0=0, owner1=0x0B):
    endpoint, link = Endpoint(), Transport("serial", 0)
    endpoint.depth = depth
    pcs = (*image.entries, 0)[:2]
    load(link, endpoint, image.programs[0], (enabled, *pcs, owner0, owner1, 0))
    for owner, values in enumerate(words):
        for word in values:
            assert command(endpoint, link, WRITE, bytes((owner,)) + word.to_bytes(2, "little")) == (OK, b"")
    assert command(endpoint, link, START) == (OK, b"")
    return endpoint, link


def command(endpoint, link, op, body=b""):
    return transact(link, endpoint, packet(op, body))[0]


def drain(endpoint, link, owner):
    words = []
    for _ in range(endpoint.depth + 1):
        status, body = command(endpoint, link, READ, bytes((owner,)))
        if (status, body) == (EMPTY, b""):
            return words
        if status != OK or len(body) != 2:
            raise ValueError("unexpected response to payload read")
        words.append(int.from_bytes(body, "little"))
    raise ValueError("egress did not drain")


def run_case(epoch, offset, phase, tx=SPI_WORD):
    image = build(offset)
    endpoint, link = prepare(image, ((), (tx, tx)))

    def make_machine(arch, original, bus):
        # Read back the committed words from the loader model's fetch endpoint.
        code = b"".join(endpoint.fetch(pc) for pc in range(endpoint.cfg.count))
        return PayloadProbe.from_image(arch, Image((code,), original.entries, original.lanes), bus,
                                       epoch=epoch, endpoint=endpoint)

    case, machine, limit, monitor = spi_bench("B", image, 0, True, machine_factory=make_machine,
                                             uart_phase=phase, spi_offset=offset,
                                             pin_order=PIN_ORDERS["overlap"])
    host_output = []

    def verify(probe, end):
        uart, spi = (drain(endpoint, link, owner) for owner in (0, 1))
        host_output.extend((uart, spi))
        decoded = {"uart_rx": [word for word in uart if word < 256],
                   "uart_error": [word for word in uart if word >= 256], "spi_rx_word": spi}
        view = SimpleNamespace(bus=probe.bus, samples=probe.samples, report=decoded)
        errors, margin = monitor(view, end)
        reads = [word for _, owner, kind, word in probe.transfers if owner == 1 and kind == "host_get"]
        if reads != [tx, tx] or any(endpoint.ingress):
            errors.append("host transmit words did not retire exactly once")
        return errors, margin

    row, _ = measure(case, "B", machine, limit, verify)
    return dict(row, epoch=epoch, phase=phase, spi_offset=offset, words=len(image.programs[0]) // 3,
                drive_slack=machine.admission_slack, sample_slack=machine.min_sample_slack,
                host_output=host_output, transfers=machine.transfers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    opts = parser.parse_args()
    rows = []
    for epoch in (0, (1 << 24) - 500):
        cases = [run_case(epoch, offset, Fraction(phase, 16))
                 for offset in (-4, 0, 4) for phase in range(16)]
        rows.extend(cases)
        print(f"epoch={epoch}: {sum(row['pass'] for row in cases)}/{len(cases)} passed")
        for error in sorted({e for row in cases for e in row["errors"]}):
            print(error)
    if opts.out:
        opts.out.parent.mkdir(parents=True, exist_ok=True)
        lines = ",\n".join("  " + json.dumps(row, default=clock_json) for row in rows)
        opts.out.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
    return int(not all(row["pass"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
