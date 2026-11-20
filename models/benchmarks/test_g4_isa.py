"""Directed checks for the exploratory 24-bit binary encoding."""

from unittest import TestCase

from .cycle import ModelError, Out, Pins
from .encoded import Image, Issue
from .g4_isa import FORMATS, MASK, ISAProbe, assemble, decode, execute


class ISATests(TestCase):
    def test_encoding_bounds_and_reserved_bits(self):
        self.assertEqual(len({opcode for opcode, _ in FORMATS.values()}), len(FORMATS))
        for op, (opcode, widths) in FORMATS.items():
            self.assertLess(opcode, 32)
            self.assertLessEqual(sum(widths), 19)
            operands = [(1 << width) - 1 for width in widths]
            code, _ = assemble([(op, *operands)])
            self.assertEqual(len(code), 3)
            self.assertEqual(decode(code, 0), (op, operands))
        with self.assertRaisesRegex(ValueError, "does not fit"):
            assemble([("out", 1, 1, 512)])
        with self.assertRaisesRegex(ModelError, "reserved"):
            decode(b"\x0f\x00\x80", 0)
        with self.assertRaisesRegex(ValueError, "128 words"):
            assemble([("halt",)] * 129)

    def test_long_offset_carries_and_uses_24_bit_anchor(self):
        code, _ = assemble([("save_now",), ("set", 0, 65530),
                            ("addoff", 12), ("out", 1, 1, 2)])
        epoch = MASK - 7
        program = execute(code, 0, ("out",), (), epoch)
        self.assertEqual(next(program), Issue("fetch"))
        self.assertEqual(next(program), Issue("read_timer"))
        self.assertEqual(program.send(epoch + 1), Issue("fetch"))
        self.assertEqual(next(program), Issue("execute"))
        self.assertEqual(next(program), Issue("fetch"))
        self.assertEqual(next(program), Issue("execute"))
        self.assertEqual(next(program), Issue("fetch"))
        self.assertEqual(next(program), Out(65545, {"out": 1}))
        code, _ = assemble([("save_now",), ("set", 6, 128), ("out", 1, 1, 0)])
        with self.assertRaisesRegex(ModelError, "offset outside the half range"):
            ISAProbe.from_image("B", Image((code,), (0,), (b"",)), Pins({"out": 0})).run(10)

    def test_timed_drive_before_save_faults(self):
        code, _ = assemble([("out", 1, 1, 10)])
        bus = Pins({"pin": 0})
        probe = ISAProbe.from_image("B", Image((code,), (0,), (b"",)), bus)
        with self.assertRaisesRegex(ModelError, "before save"):
            probe.run(12)
        self.assertFalse(bus.edges)

    def test_sample_does_not_replace_saved_edge(self):
        code, _ = assemble([("wait_save", 0, 1, 0), ("cap", 0, 1, 0, 8),
                            ("out", 2, 2, 16), ("halt",)])
        bus = Pins({"input": 0, "output": 0})
        bus.external(10, {"input": 1})
        probe = ISAProbe.from_image("B", Image((code,), (0,), (b"",)), bus, epoch=MASK - 14)
        probe.run(30)
        self.assertEqual(probe.samples, [(20, "input", 1)])
        self.assertEqual(bus.edges, [(10, "input", 1), (28, "output", 1)])
