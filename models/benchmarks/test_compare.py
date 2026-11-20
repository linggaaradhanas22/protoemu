"""Sanity checks for EVAL-001, separate from the RTL verification plan."""

from fractions import Fraction
from unittest import TestCase

from .cycle import Machine, Pins
from .flex import OneWirePeer, onewire_check, onewire_program, rc5_check, rc5_program, rc5_stimulus, ws_check, ws_program
from .i2c_fixture import I2CCase, I2CPeer, i2c_check, i2c_program
from .spi_uart import (
    UART_RX, SPIPeer, spi_check, spi_program, uart_receive, uart_rx_check, uart_stimulus, uart_transmit, uart_tx_check,
)


def stretched_i2c(arch, skip=True):
    case = I2CCase("combined", True, 600)
    bus = Pins({"scl": 1, "sda": 1}, ("scl", "sda"), I2CPeer(case))
    model = Machine(arch, [i2c_program(case)], bus)
    end = model.run(15_000, skip_idle=skip)
    return model, end, case


class MonitorTests(TestCase):
    def test_spi_detects_shifted_clock_edge(self):
        bus = Pins({"cs": 1, "sclk": 0, "mosi": 0, "miso": 0}, peer=SPIPeer(0, 30))
        model = Machine("A", [spi_program("A", [32], 0, 30)], bus)
        model.run(1200)
        got = model.report["spi_rx"]
        self.assertFalse(spi_check(bus, got, 0, 30, [32])[0])
        index = next(i for i, (_, pin, _) in enumerate(bus.edges) if pin == "sclk")
        t, pin, value = bus.edges[index]
        bus.edges[index] = (t + 3, pin, value)
        self.assertTrue(any("half-period" in error for error in spi_check(bus, got, 0, 30, [32])[0]))

    def test_i2c_detects_illegal_high_drive(self):
        model, _, case = stretched_i2c("B")
        self.assertFalse(i2c_check(model.bus, model.report, case)[0])
        model.bus.raw.append((1000, "dut", "scl", 1))
        self.assertTrue(any("actively drove" in error for error in i2c_check(model.bus, model.report, case)[0]))

    def test_idle_skip_matches_dense_clock_model(self):
        for arch in "ABC":
            with self.subTest(arch=arch):
                sparse, end, _ = stretched_i2c(arch)
                dense, dense_end, _ = stretched_i2c(arch, skip=False)
                self.assertEqual((sparse.bus.raw, sparse.bus.edges, sparse.samples, sparse.emits, end),
                                 (dense.bus.raw, dense.bus.edges, dense.samples, dense.emits, dense_end))

    def test_uart_tx_detects_short_bit(self):
        bus = Pins({"uart_tx": 1})
        model = Machine("A", [uart_transmit("A", 115200, 16)], bus)
        end = model.run(27_000)
        self.assertFalse(uart_tx_check(bus, end, 115200, 16)[0])
        t, pin, value = bus.edges[1]
        bus.edges[1] = (t - 8, pin, value)
        self.assertTrue(uart_tx_check(bus, end, 115200, 16)[0])

    def test_uart_rx_detects_sample_outside_bit(self):
        period, start = Fraction(3125, 6), Fraction(257, 16)
        bus = Pins({"uart_rx": 1})
        uart_stimulus(bus, start, period, UART_RX)
        model = Machine("B", [uart_receive("B", len(UART_RX), 521)], bus)
        model.run(32_000)
        self.assertFalse(uart_rx_check(model, UART_RX, start, period)[0])
        t, pin, value = model.samples[0]
        model.samples[0] = (t - 300, pin, value)
        self.assertTrue(uart_rx_check(model, UART_RX, start, period)[0])

    def test_ws2812_detects_truncated_latch(self):
        bus = Pins({"ws": 0})
        model = Machine("C", [ws_program("C")], bus)
        end = model.run(25_000)
        self.assertFalse(ws_check(bus, end)[0])
        self.assertTrue(ws_check(bus, end - 2000)[0])

    def test_onewire_detects_late_sample(self):
        bus = Pins({"wire": 1}, ("wire",), OneWirePeer(True))
        model = Machine("A", [onewire_program()], bus)
        model.run(400_000)
        self.assertFalse(onewire_check(model, True)[0])
        t, pin, value = model.samples[-1]
        model.samples[-1] = (t + 100, pin, value)
        self.assertTrue(onewire_check(model, True)[0])

    def test_rc5_detects_early_report(self):
        half = 53_340
        bus = Pins({"rc5": 1})
        starts = rc5_stimulus(bus, half)
        model = Machine("C", [rc5_program("C")], bus)
        model.run(16_000_000)
        self.assertFalse(rc5_check(model, starts, half)[0])
        _, channel, payload = model.emits[0]
        model.emits[0] = (starts[0] - 1, channel, payload)
        self.assertTrue(rc5_check(model, starts, half)[0])
