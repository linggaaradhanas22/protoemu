"""Checks for the edge_delta writeback study (EVAL-013)."""

import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, skipUnless

from .g4_edges import EdgeProbe
from .g4_writeback import contention, probe_class
from .g4_edges import run_case as rc5_case

ROOT = Path(__file__).resolve().parents[2]


class WritebackTests(TestCase):
    def test_default_probe_retires_both_words_on_one_edge(self):
        self.assertFalse(EdgeProbe.delta_writeback)

    def test_held_word_costs_one_issue_per_edge_delta(self):
        one, held = (rc5_case(53_340, True, probe_cls=probe_class(flag)) for flag in (False, True))
        self.assertTrue(one["pass"] and held["pass"])
        self.assertEqual(one["host_output"], held["host_output"])
        self.assertEqual(held["issued_ops"][0] - one["issued_ops"][0], 2)  # Two edge_delta per run.

    def test_contention_case_passes_with_both_options(self):
        rows = [contention(flag, 30) for flag in (False, True)]
        self.assertTrue(all(row["pass"] for row in rows), rows)
        self.assertEqual(rows[1]["issued"][0] - rows[0]["issued"][0], rows[0]["deltas"])
        self.assertEqual(rows[0]["drive_slack"], rows[1]["drive_slack"])

    @skipUnless(shutil.which("iverilog") and shutil.which("vvp"), "needs Icarus Verilog")
    def test_register_file_variants_match_reference(self):
        with tempfile.TemporaryDirectory() as scratch:
            vvp = Path(scratch) / "regfile.vvp"
            subprocess.run(["iverilog", "-g2005", "-s", "regfile_probe_tb", "-o", str(vvp),
                            "models/physical/regfile_probe.v", "models/physical/regfile_probe_tb.v"],
                           cwd=ROOT, check=True, capture_output=True)
            out = subprocess.run(["vvp", str(vvp)], cwd=ROOT, check=True, capture_output=True, text=True).stdout
        self.assertIn("1248 edge_delta, 0 errors", out)
