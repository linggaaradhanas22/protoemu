"""Checks for the host payload rate study (EVAL-015)."""

import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, skipUnless

from .g4_host_rate import READN, WRITEN, feasible, run, rx_burst, started, timing, tx_burst
from .g4_loader import EMPTY, FULL, OK, packet

ROOT = Path(__file__).resolve().parents[2]


class HostRateTests(TestCase):
    def test_single_word_at_250_khz_matches_eval_014(self):
        rx, tx = timing(0.25, "eval004", 1)
        self.assertEqual(rx[1]["period_us"], 468)
        self.assertEqual(rx_burst(115200, 8, 1, rx), 10)
        self.assertEqual(tx_burst(115200, 8, 1, tx), 10)

    def test_readn_keeps_words_until_the_reply_closes(self):
        endpoint, transport = started(1, "eval004")
        endpoint.egress[0].extend([1, 2, 3])
        reply = endpoint.command(transport.frame(packet(READN, bytes((0, 4))))[0], 0)
        self.assertEqual(len(endpoint.egress[0]), 3)  # Still held while the reply is sent.
        endpoint.reply_done()
        self.assertEqual(len(endpoint.egress[0]), 0)
        self.assertEqual(reply, packet(OK, bytes((1, 0, 2, 0, 3, 0))))
        self.assertEqual(run(transport, endpoint, packet(READN, bytes((0, 4))))[0], EMPTY)

    def test_writen_accepts_only_what_fits(self):
        endpoint, transport = started(1, "eval004", depth=4)
        endpoint.ingress[0].extend([9, 9, 9])
        status, body, *_ = run(transport, endpoint, packet(WRITEN, bytes((0, 1, 0, 2, 0))))
        self.assertEqual((status, body), (FULL, bytes((1,))))
        self.assertEqual(list(endpoint.ingress[0]), [9, 9, 9, 1])

    def test_synchronizer_limit_lies_between_4_and_8_mhz(self):
        self.assertTrue(feasible(4, "eval004"))
        self.assertFalse(feasible(8, "eval004"))

    def test_1_mhz_four_words_sustains_115200_at_depth_4(self):
        rx, tx = timing(1, "eval004", 4)
        self.assertIsNone(rx_burst(115200, 4, 4, rx))
        self.assertIsNone(tx_burst(115200, 4, 4, tx))

    @skipUnless(shutil.which("iverilog") and shutil.which("vvp"), "needs Icarus Verilog")
    def test_multi_word_fifos_match_reference(self):
        with tempfile.TemporaryDirectory() as scratch:
            vvp = Path(scratch) / "multi.vvp"
            subprocess.run(["iverilog", "-g2005", "-s", "fifo_multi_probe_tb", "-o", str(vvp),
                            "models/physical/fifo_multi_probe.v", "models/physical/fifo_multi_probe_tb.v"],
                           cwd=ROOT, check=True, capture_output=True)
            out = subprocess.run(["vvp", str(vvp)], cwd=ROOT, check=True, capture_output=True, text=True).stdout
        self.assertIn("DEPTH=8", out)
        self.assertIn(" 0 errors", out)
