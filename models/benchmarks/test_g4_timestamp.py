"""Directed checks of the timestamp exploration, not RTL tests."""

from unittest import TestCase

from .g4_timestamp import CAPTURE_AT, OPTIONS, evaluate


class TimestampTests(TestCase):
    def test_low_word_carry_and_full_wrap(self):
        for option in OPTIONS:
            for stamp, expected in ((0x00FFFC, 0x010034), (0xFFFFFC, 0x34)):
                with self.subTest(option=option, stamp=stamp):
                    row = evaluate(option, stamp, 56)
                    self.assertIsNone(row["rejection"])
                    self.assertEqual(row["deadline"], expected)
                    self.assertEqual(row["instruction_words"], 4 if option == "pair-split" else 2)

    def test_competing_context_still_allows_uart_like_sample(self):
        for option in OPTIONS:
            row = evaluate(option, 0xFFFFFC, 781, competitor=2, operation="sample")
            self.assertIsNone(row["rejection"])
            self.assertEqual(row["deadline"], 777)
            self.assertGreater(row["slack"], 0)

    def test_one_clock_slack_and_expiry_do_not_move_deadline(self):
        for option in OPTIONS:
            row = evaluate(option, 0xFFFFFC, 56, queue_until=CAPTURE_AT + 55)
            self.assertEqual(row["slack"], 1)
            self.assertGreater(row["blocked_cycles"], 0)
            late = evaluate(option, 0xFFFFFC, 56, queue_until=CAPTURE_AT + 56)
            self.assertIsNone(late["capture_to_admit"])
            self.assertIn("invalid at cycle 78", late["rejection"])

    def test_short_deadline_discriminates_split_and_fused(self):
        self.assertIsNotNone(evaluate("pair-split", 0x123456, 4)["rejection"])
        self.assertEqual(evaluate("dedicated", 0x123456, 4)["slack"], 1)
        self.assertEqual(evaluate("pair-fused", 0x123456, 4)["slack"], 1)
