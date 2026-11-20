"""Directed edge, interval, and idle-skip checks for EVAL-010."""

from unittest import TestCase

from .cycle import ModelError, Pins
from .encoded import Image
from .g4_edges import DECODE, FORMATS, EdgeProbe, run_case
from .g4_isa import HALF, MASK, assemble, decode
from .g4_payload import drain, prepare


def make_probe(lines, events, *, epoch=0):
    code, _ = assemble(lines, formats=FORMATS)
    image = Image((code,), (0,), (b"",))
    endpoint, link = prepare(image, ((),), enabled=1, owner1=0)
    bus = Pins({"input": 1})
    for t, value in events:
        bus.external(t, {"input": value})
    probe = EdgeProbe.from_image("B", image, bus, epoch=epoch, endpoint=endpoint)
    return probe, endpoint, link


class EdgeTests(TestCase):
    def test_idle_skip_matches_dense_across_wrap(self):
        lines = [("edge_save", 0, 0), ("edge_delta", 0, 2, 1), ("host_put", 1),
                 ("host_put", 2), ("cap", 0, 3, 0, 30), ("fence", 40), ("halt",)]
        traces = []
        for skip in (False, True):
            probe, endpoint, link = make_probe(lines, [(10, 0), (24, 1)], epoch=MASK - 14)
            end = probe.run(100, skip_idle=skip)
            self.assertEqual(drain(endpoint, link, 0), [14, 0])
            self.assertGreater(probe.capture_log[0][-1], probe.capture_log[1][-1])
            traces.append((end, probe.issue_log, probe.capture_log, probe.samples, probe.transfers))
        self.assertEqual(*traces)

    def test_long_interval_uses_both_words(self):
        lines = [("edge_save", 0, 0), ("edge_delta", 0, 1, 3),
                 ("host_put", 3), ("host_put", 4), ("halt",)]
        probe, endpoint, link = make_probe(lines, [(10, 0), (65_549, 1)])
        probe.run(65_600)
        self.assertEqual(drain(endpoint, link, 0), [3, 1])

    def test_reject_half_range_and_invalid_encodings(self):
        probe, _, _ = make_probe([("edge_save", 0, 0), ("edge_delta", 0, 1, 1)],
                                 [(10, 0), (10 + HALF, 1)])
        with self.assertRaisesRegex(ModelError, "interval outside"):
            probe.run(HALF + 40)
        for lines, error in [([("edge_delta", 0, 1, 1)], "needs saved time"),
                             ([("edge_save", 0, 3)], "invalid edge polarity"),
                             ([("save_now",), ("edge_delta", 0, 1, 5)], "register pair")]:
            probe, _, _ = make_probe(lines, [])
            with self.assertRaisesRegex(ModelError, error):
                probe.run(40)
        with self.assertRaisesRegex(ModelError, "reserved"):
            decode(bytes((25, 0, 128)), 0, table=DECODE)

    def test_rc5_reports_expected_words_across_wrap(self):
        row = run_case(53_340, True)
        self.assertTrue(row["pass"], row["errors"])
        self.assertEqual(row["host_output"], [0x3175, 0x3E8C])
        self.assertGreater(row["calibration"][0][-1], row["calibration"][1][-1])
