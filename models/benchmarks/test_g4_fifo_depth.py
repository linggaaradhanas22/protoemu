"""Checks for the payload FIFO study (EVAL-014)."""

import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, skipUnless

from .g4_fifo_depth import DEMAND, host_timing, max_burst

ROOT = Path(__file__).resolve().parents[2]


class FifoDepthTests(TestCase):
    def test_host_transaction_timing(self):
        timing = host_timing()
        self.assertEqual(timing["read"]["period_us"], 468)
        self.assertEqual(timing["read_empty"]["period_us"], 404)
        self.assertAlmostEqual(timing["read"]["pop_us"], 196, places=1)  # Includes the synchronizer.

    def test_burst_limits_at_115200_baud(self):
        timing = host_timing()
        self.assertEqual(max_burst(115200, 1, 4, timing), 5)
        self.assertEqual(max_burst(115200, 1, 8, timing), 10)
        self.assertIsNone(max_burst(19200, 1, 2, timing))  # The host keeps up.

    def test_depth_eight_holds_every_unpacked_demand_except_one_wire(self):
        over = [row["test"] for row in DEMAND if row["unpacked"] > 8]
        self.assertEqual(over, ["TEST-SYS-013 1-Wire"])

    @skipUnless(shutil.which("iverilog") and shutil.which("vvp"), "needs Icarus Verilog")
    def test_fifo_rules_match_reference(self):
        with tempfile.TemporaryDirectory() as scratch:
            for bypass in (0, 1):
                vvp = Path(scratch) / f"fifo{bypass}.vvp"
                subprocess.run(["iverilog", "-g2005", "-s", "fifo_probe_tb", "-P", f"fifo_probe_tb.BYPASS={bypass}",
                                "-o", str(vvp), "models/physical/fifo_probe.v", "models/physical/fifo_probe_tb.v"],
                               cwd=ROOT, check=True, capture_output=True)
                out = subprocess.run(["vvp", str(vvp)], cwd=ROOT, check=True, capture_output=True, text=True).stdout
                self.assertIn(f"DEPTH=8 BYPASS={bypass}", out)
                self.assertIn(" 0 errors", out)
