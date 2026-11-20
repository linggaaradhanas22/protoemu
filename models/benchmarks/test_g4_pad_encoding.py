"""Directed eight-pad encoding and drive/release checks (Python only)."""

from unittest import TestCase

from .cycle import ModelError, Pins
from .encoded import Image
from .g4_isa import PAD_DECODE, PAD_FORMATS, assemble, decode
from .g4_pad_encoding import OPTIONS, PadProbe


class PadEncodingTests(TestCase):
    def run_program(self, lines, bus):
        code, _ = assemble(lines, formats=PAD_FORMATS)
        model = PadProbe.from_image("B", Image((code,), (0,), (b"",)), bus,
                                    epoch=(1 << 24) - 32)
        model.run(90)
        return model

    def test_pad_opcodes_fit_and_keep_pad_seven(self):
        self.assertEqual(len(PAD_FORMATS), len(PAD_DECODE))
        for op in ("pad", "pad2", "shift_pin", "shift_pair", "drivev"):
            _, fields = PAD_FORMATS[op]
            values = [(1 << width) - 1 for width in fields]
            word, _ = assemble([(op, *values)], formats=PAD_FORMATS)
            self.assertEqual(len(word), 3)
            self.assertEqual(decode(word, 0, table=PAD_DECODE), (op, values))

    def test_all_eight_pads_change_together_with_independent_enables(self):
        names = tuple(f"p{i}" for i in range(8))
        for option in OPTIONS:
            with self.subTest(option=option):
                bus = Pins(dict.fromkeys(names, 1))
                lines = [("save_now",)]
                # First drive all low. Then drive odd pads high and release even pads.
                for delay, values, enables in ((32, 0, 0xFF), (64, 0xAA, 0xAA)):
                    if option == "vector":
                        lines += [("set", 7, (values << 8) | 0xFF), ("drivev", 7, enables, delay)]
                    else:
                        for i in range(0, 8, 2):
                            pair = tuple(arg for bit in (i, i + 1)
                                         for arg in (bit, (values >> bit) & 1, (enables >> bit) & 1))
                            lines.append(("pad2", *pair, delay))
                model = self.run_program(lines + [("halt",)], bus)
                self.assertEqual([sum(t == tick for t, _ in model.retired) for tick in (33, 65)],
                                 [4, 4] if option == "compact" else [1, 1])
                self.assertEqual(model.hi["output_queue"], 4 if option == "compact" else 2)
                self.assertEqual(model.admission_slack, 24 if option == "compact" else 28)
                self.assertEqual(bus.raw, [(33, "dut", pin, 0) for pin in names] +
                                 [(65, "dut", pin, 1 if i % 2 else None) for i, pin in enumerate(names)])

    def test_open_drain_overrides_enabled_high(self):
        for commands in (
            [("pad", 7, 0, 1, 10), ("pad", 7, 1, 1, 20)],
            [("set", 7, 0x0080), ("drivev", 7, 0x80, 10),
             ("set", 7, 0x8080), ("drivev", 7, 0x80, 20)],
        ):
            bus = Pins({f"p{i}": 1 for i in range(8)}, open_drain=("p7",))
            self.run_program([("save_now",), *commands, ("halt",)], bus)
            self.assertEqual(bus.raw, [(11, "dut", "p7", 0), (21, "dut", "p7", None)])

    def test_shift_extra_pad_is_not_a_sentinel(self):
        bus = Pins({f"p{i}": 0 for i in range(8)})
        self.run_program([("save_now",), ("set", 1, 0x8000), ("shift_pair", 1, 6, 7, 1, 10),
                          ("shift_pin", 1, 7, 20), ("halt",)], bus)
        self.assertEqual(bus.edges, [(11, "p6", 1), (11, "p7", 1), (21, "p7", 0)])

    def test_duplicate_empty_and_unowned_masks_fault(self):
        for commands, error in (
            ([("pad2", 0, 0, 1, 0, 1, 1, 10)], "duplicate pad"),
            ([("drivev", 7, 0xFF, 10)], "invalid or colliding output mask"),
            ([("pad", 7, 1, 1, 10)], "invalid or colliding output mask"),
        ):
            bus = Pins({**{f"p{i}": 0 for i in range(7)}, "unused7": 0})
            with self.assertRaisesRegex(ModelError, error):
                self.run_program([("save_now",), *commands, ("halt",)], bus)
            self.assertFalse(bus.raw)
