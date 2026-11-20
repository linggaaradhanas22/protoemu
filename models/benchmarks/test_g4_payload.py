"""Directed checks for the exploratory host payload operations."""

from fractions import Fraction
from unittest import TestCase

from .cycle import ModelError, Pins
from .encoded import Image
from .g4_isa import assemble, decode
from .g4_loader import OK, READ, WRITE, packet
from .g4_payload import DECODE, FORMATS, PayloadProbe, drain, prepare, run_case


class PayloadTests(TestCase):
    def test_encode_and_reject_old_report_opcode(self):
        for op in ("host_get", "host_put"):
            code, _ = assemble([(op, 7)], formats=FORMATS)
            self.assertEqual(len(code), 3)
            self.assertEqual(decode(code, 0, table=DECODE), (op, [7]))
        with self.assertRaisesRegex(ModelError, "invalid ARCH-B"):
            decode(bytes((12, 0, 0)), 0, table=DECODE)
        with self.assertRaisesRegex(ModelError, "reserved"):
            decode(bytes((23, 1, 0)), 0, table=DECODE)

    def test_empty_ingress_and_full_egress_retry_once(self):
        # Each context runs the same three words with independent registers and FIFOs.
        code, _ = assemble([("host_get", 1), ("host_put", 1), ("halt",)], formats=FORMATS)
        image = Image((code,), (0, 0), (b"", b""))
        endpoint, link = prepare(image, ((), (0xBEEF,)), depth=1)
        self.assertTrue(endpoint.report(0, 0xCAFE))
        bus = Pins({"p0": 0})
        probe = PayloadProbe.from_image("B", image, bus, endpoint=endpoint)
        seen = []

        def write_word(_, t):
            seen.append(endpoint.command(packet(WRITE, b"\x00\x34\x12"), t))

        def read_word(_, t):
            seen.append(endpoint.command(packet(READ, b"\x00"), t))

        # Deliver completed host commands at the start of the selected model cycles.
        bus.external(10, write_word)
        bus.external(20, read_word)
        probe.run(40)
        self.assertEqual(seen, [packet(OK), packet(OK, b"\xfe\xca")])
        self.assertEqual([(owner, op, value) for _, owner, op, value in probe.transfers],
                         [(1, "host_get", 0xBEEF), (1, "host_put", 0xBEEF),
                          (0, "host_get", 0x1234), (0, "host_put", 0x1234)])
        self.assertLess(probe.transfers[1][0], 10)
        self.assertEqual(probe.transfers[2][0], 10)
        self.assertEqual(probe.transfers[3][0], 20)
        self.assertEqual(sum(owner == 0 and kind == "fetch" for _, owner, kind in probe.issue_log), 3)
        self.assertFalse(any(endpoint.ingress))
        self.assertEqual(drain(endpoint, link, 0), [0x1234])
        self.assertEqual(drain(endpoint, link, 1), [0xBEEF])

    def test_overlap_spi_pins_follow_the_preloaded_word(self):
        row = run_case(0, 0, Fraction(0), tx=0xBEEF)
        self.assertFalse(row["pass"])
        self.assertTrue(any("SPI pin data mismatch" in error for error in row["errors"]))
        self.assertEqual([word for _, _, kind, word in row["transfers"] if kind == "host_get"],
                         [0xBEEF, 0xBEEF])
