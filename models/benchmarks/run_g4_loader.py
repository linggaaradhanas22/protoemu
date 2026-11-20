"""Compare sampled G4 loader timings against a common frame format."""

import argparse
import json
from pathlib import Path

from .encoded_programs import build
from .g4_loader import OK, PHASES, START, US, Endpoint, Transport, load, packet, transact


def shapes():
    for profile, args, config in (
        ("spi", ("spi", 0), (1, 0, 0, 0b1011, 0, 0)),
        ("i2c", ("i2c",), (1, 0, 0, 0xC0, 0, 0xC0)),
        ("overlap", ("overlap",), (3, 0, 0, 0, 0b1011, 0)),
    ):
        image = build("B", *args)
        if profile == "overlap":
            config = (3, *image.entries, *config[3:])
        yield profile, image.programs[0], config
    yield "max-image", bytes(x % 256 for x in range(384)), (1, 0, 0, 0, 0, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = []
    for kind, slip in (("nibble", 0), ("nibble", 25), ("serial", 0)):
        for name, image, config in shapes():
            for phase in range(PHASES):
                link, dut = Transport(kind, phase, slip * US), Endpoint()
                ms = load(link, dut, image, config)
                assert dut.fetch(0) is None and ms < 1000
                answer, _ = transact(link, dut, packet(START))
                assert answer == (OK, b"") and dut.fetch(0) == image[:3]
                rows.append(dict(transport=kind, poll_slip_us=slip, image=name, words=len(image) // 3,
                                 phase=phase, load_ms=ms))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        lines = ",\n".join("  " + json.dumps(row) for row in rows)
        args.out.write_text(f"[\n{lines}\n]", encoding="utf-8")
    print(f"{len(rows)} loads passed; maximum times (ms):")
    for kind, slip in (("nibble", 0), ("nibble", 25), ("serial", 0)):
        selected = [r for r in rows if (r["transport"], r["poll_slip_us"]) == (kind, slip)]
        print(kind, slip, {name: max(r["load_ms"] for r in selected if r["image"] == name)
                           for name, *_ in shapes()})


if __name__ == "__main__":
    main()
