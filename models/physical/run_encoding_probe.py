"""Check the draft instruction and host encodings against their decoders."""

import argparse
from collections import Counter
import json
from pathlib import Path

from ..benchmarks.g4_host_rate import READN, WRITEN, MultiEndpoint
from ..benchmarks.g4_isa import assemble
from ..benchmarks.g4_loader import (BEGIN, COMMIT, DATA, READ, START, STATE, STOP, WRITE, Endpoint,
                                    Transport, packet)
from ..benchmarks.g4_suite import DECODE, FORMATS

CORPUS = [
    ("pad", 0, 0, 0, 0), ("pad", 7, 1, 1, 511),
    ("pad2", 0, 0, 1, 1, 1, 0, 511),
    ("shift_pin", 0, 0, 0, 0), ("shift_pin", 7, 7, 511, 1),
    ("shift_pair", 0, 0, 1, 1, 0),
    ("drivev", 0, 255, 255), ("drivev", 7, 0, 0),
]


def instruction_rows():
    image, _ = assemble(CORPUS, formats=FORMATS)
    rows = []
    for pc, line in enumerate(CORPUS):
        word = int.from_bytes(image[pc * 3:pc * 3 + 3], "little")
        op, widths = DECODE[word & 31]
        args = []
        field = word >> 5
        for width in widths:
            args.append(field & ((1 << width) - 1))
            field >>= width
        rows.append({"word": f"{word:06x}", "op": op, "args": args, "encodes": list(line[1:])})
    return rows


def host_rows():
    endpoint, transport = MultiEndpoint(), Transport("serial", 0)
    endpoint.depth = 8
    rows = []
    sequence = (("BEGIN", BEGIN, bytes((1, 1, 0, 0, 0, 0, 0))), ("DATA", DATA, b"\x00\x00\x00"),
                ("COMMIT", COMMIT, b""), ("START", START, b""), ("WRITE", WRITE, b"\x00\x00\x00"),
                ("READ", READ, b"\x00"), ("WRITEN", WRITEN, b"\x00\x01\x00"),
                ("READN", READN, b"\x00\x01"), ("STOP", STOP, b""))
    bad = [("unknown-0", 0, b""), ("unknown-255", 255, b""), ("STATE", STATE, b"")]
    for name, op, body in sequence + tuple(bad):
        frame = packet(op, body)
        try:
            request, validate = transport.frame(frame)
            reply = endpoint.command(request, validate)
            answer, _ = transport.frame(reply, reply=True)
            rows.append({"command": name, "opcode": op, "request_bytes": len(frame), "status": answer[0],
                         "reply_bytes": len(answer)})
        except (ValueError, AssertionError, TypeError) as exc:
            rows.append({"command": name, "opcode": op, "request_bytes": len(frame), "exception": str(exc)})
    endpoint, transport = MultiEndpoint(), Transport("serial", 0)
    endpoint.egress[0].extend((0x1234, 0x5678))
    request, validate = transport.frame(packet(READN, bytes((0, 2))))
    reply = endpoint.command(request, validate)
    first, _ = transport.frame(reply[:6], reply=True)
    second, _ = transport.frame(reply, reply=True)
    third, _ = transport.frame(reply, reply=True)
    rows.append({"command": "READN interrupted reply", "first_bytes": len(first), "restart_bytes": len(second),
                 "same_reply": second == third, "fifo_after": len(endpoint.egress[0])})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=Path("design/evals/EVAL-024/encoding.json"), type=Path)
    args = parser.parse_args()
    codes = Counter(code for code, _ in FORMATS.values())
    summary = {
        "isa": {
            "opcodes_defined": len(codes),
            "duplicate_opcodes": sorted(code for code, count in codes.items() if count > 1),
            "corpus": instruction_rows(),
        },
        "host": host_rows(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"ISA: {len(codes)} opcodes, duplicates {summary['isa']['duplicate_opcodes']}, "
          f"{len(summary['isa']['corpus'])} round-tripped words")
    for row in summary["host"]:
        print(row)


if __name__ == "__main__":
    main()
