"""Checks for the wait-timeout study (EVAL-017)."""

import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, skipUnless

from . import g4_timeout as t
from .i2c_fixture import I2CCase

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 20_000


class TimeoutTests(TestCase):
    def test_timed_wait_keeps_regression_and_isolates_a_stuck_bus(self):
        self.assertTrue(t.regression_case(I2CCase("combined", True, 600), "C", LIMIT)["pass"])
        row = t.stuck_case(True, "C", None, (9,), LIMIT)
        self.assertTrue(row["pass"], row["errors"])
        self.assertEqual(row["other_context"], "complete")

    def test_watchdog_and_host_stop_detect_but_stop_the_other_context(self):
        for option in ("A", "D"):
            with self.subTest(option=option):
                row = t.stuck_case(True, option, None, (9,), LIMIT)
                self.assertTrue(row["pass"], row["errors"])
                self.assertTrue(row["other_context"].startswith("stopped"))

    def test_polling_stretches_the_next_clock_period(self):
        row = t.regression_case(I2CCase("combined", True, 600), "B", LIMIT, 32)
        self.assertFalse(row["pass"])
        self.assertIn("SCL bit period", row["errors"][0])

    def test_poll_budget_is_limited_by_a_16_bit_counter(self):
        with self.assertRaisesRegex(ValueError, "16-bit"):
            t.i2c_program(True, "combined", "B", interval=16, limit=1_500_000)

    @skipUnless(shutil.which("iverilog") and shutil.which("vvp"), "needs Icarus Verilog")
    def test_wait_slot_probe_modes(self):
        with tempfile.TemporaryDirectory() as scratch:
            for mode in (1, 2):
                vvp = Path(scratch) / f"w{mode}.vvp"
                subprocess.run(["iverilog", "-g2005", "-s", "wait_timeout_probe_tb", "-P",
                                f"wait_timeout_probe_tb.TIMEOUT={mode}", "-o", str(vvp),
                                "models/physical/wait_timeout_probe.v", "models/physical/wait_timeout_probe_tb.v"],
                               cwd=ROOT, check=True, capture_output=True)
                out = subprocess.run(["vvp", str(vvp)], cwd=ROOT, check=True, capture_output=True, text=True).stdout
                self.assertIn(f"TIMEOUT={mode}: 0 errors", out)
