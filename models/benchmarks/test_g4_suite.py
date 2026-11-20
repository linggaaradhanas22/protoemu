"""Checks for the draft-ISA program suite (EVAL-016)."""

from fractions import Fraction
from unittest import TestCase

from . import g4_suite as suite
from .cycle import Pins
from .i2c_fixture import I2CCase
from .spi_uart import UART_TX, uart_tx_check


def ops(lines):
    return {line[0] for line in lines if not isinstance(line, str)}


class SuiteTests(TestCase):
    def test_one_case_per_protocol_passes_across_wrap(self):
        rows = [suite.uart_rx_case(115200, Fraction(-2), 5, suite.WRAP), suite.uart_rx_case(9600, Fraction(2), 11, 0),
                suite.uart_tx_case(57600, "host-reversed", suite.WRAP), suite.spi_case(1, 100, suite.WRAP),
                suite.i2c_case(I2CCase("combined", True, 300), suite.WRAP), suite.i2c_case(I2CCase("separate", False), 0),
                suite.ws_case(suite.WRAP), suite.onewire_case(True, suite.WRAP),
                suite.onewire_case(False, 0, device=False)]
        self.assertEqual([(r["case"], r["errors"]) for r in rows if not r["pass"]], [])

    def test_programs_use_only_draft_isa_operations(self):
        programs = [suite.uart_rx_program(Fraction(520)), suite.uart_tx_program(Fraction(520), "host-reversed"),
                    *(suite.spi_program(mode, 30) for mode in range(4)),
                    *(suite.i2c_program(fast, v) for fast in (False, True) for v in ("separate", "combined")),
                    suite.ws_program(), suite.onewire_program()]
        used = set().union(*map(ops, programs))
        self.assertLessEqual(used, set(suite.FORMATS))
        self.assertIn(("shift_pin", 1, 5, 0, 1), suite.uart_tx_program(Fraction(520), "lsb"))

    def test_monitors_reject_broken_programs(self):
        bus = Pins(suite.pins_for({5: "uart_tx"}, {"uart_tx": 1}))
        probe, *_ = suite.execute(suite.uart_tx_program(Fraction(60_000_000, 115200), "host-reversed"),
                                  [5, *[b << 8 for b in UART_TX]], bus, 0, formats=suite.FORMATS)
        end = probe.run(100_000)
        first = next(t for t, name, _ in bus.edges if name == "uart_tx")
        self.assertTrue(uart_tx_check(bus, end, 115200, first)[0])  # Bytes not reversed.

        original = suite.i2c_program
        try:
            suite.i2c_program = lambda fast, variant: [
                ("set", 5, 0xA200) if line == ("set", 5, 0xA000) else line for line in original(fast, variant)]
            self.assertFalse(suite.i2c_case(I2CCase("combined", True), 0)["pass"])
        finally:
            suite.i2c_program = original

        original = suite.ws_program
        try:
            suite.ws_program = lambda: [("shift_pin", 1, suite.WS, 12, 0) if line == ("shift_pin", 1, suite.WS, 18, 0)
                                        else line for line in original()]
            self.assertFalse(suite.ws_case(0)["pass"])
        finally:
            suite.ws_program = original

    def test_shift_order_bit_encoding(self):
        """CHG-012: order 0 is bit-identical to the old shift_pin; order 1 sets bit 20 only."""
        from .g4_isa import PAD_FORMATS, assemble
        old, _ = assemble([("shift_pin", 3, 5, 200)], formats=PAD_FORMATS)
        msb, _ = assemble([("shift_pin", 3, 5, 200, 0)], formats=suite.FORMATS)
        lsb, _ = assemble([("shift_pin", 3, 5, 200, 1)], formats=suite.FORMATS)
        self.assertEqual(old, msb)
        self.assertEqual(int.from_bytes(lsb, "little") ^ int.from_bytes(msb, "little"), 1 << 20)
