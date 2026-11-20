"""Checks for image bounds, decoding, and execution from packed bytes."""

from dataclasses import replace
from unittest import TestCase

from .cycle import ModelError
from .encoded import STORES, assemble, decode
from .encoded_programs import build
from .i2c_fixture import I2CCase
from .run_compare import measure
from .run_encoded import i2c_bench, spi_bench


def result(arch, scenario):
    name, machine, limit, verify = scenario
    row, _ = measure(name, arch, machine, limit, verify)
    return row, machine.slot_counts


class EncodingTests(TestCase):
    def test_word_layout_and_reserved_bits(self):
        code, labels = assemble(["start", ("set", 7, 0xFFFF), ("jump", "start")], 3, 64)
        self.assertEqual(labels, {"start": 0})
        self.assertEqual(decode(code, 0, 3), ("set", [7, 0xFFFF]))
        self.assertEqual(decode(code, 1, 3), ("jump", [0]))
        with self.assertRaises(ModelError):
            decode(b"\xe0\x00\x00", 0, 3)
        with self.assertRaises(ValueError):
            assemble([("out", 1, 1, 512)], 3, 64)

    def test_memory_limits(self):
        for arch, (width, depth) in STORES.items():
            with self.subTest(arch=arch):
                image = build(arch, "spi")
                with self.assertRaises(ValueError):
                    replace(image, programs=(bytes(width * (depth + 1)),)).validate(arch)
        image = build("C", "spi")
        with self.assertRaises(ValueError):
            replace(image, lanes=(image.lanes[0] * 5,)).validate("C")

    def test_spi_transmits_the_encoded_data_not_fixture_data(self):
        for arch, (width, _) in STORES.items():
            with self.subTest(arch=arch):
                image = build(arch, "spi")
                good, slots = result(arch, spi_bench(arch, image, 0, False))
                self.assertTrue(good["pass"], good)
                self.assertGreater(slots["fetch"], 0)
                self.assertGreater(slots["branch_bubble"], 0)
                source = image.programs[0]
                pc = next(pc for pc in range(len(source) // width) if decode(source, pc, width) == ("set", [1, 0x964B]))
                bad_word, _ = assemble([("set", 1, 0x964A)], width, 1)
                bad = source[:pc * width] + bad_word + source[(pc + 1) * width:]
                bad_image = replace(image, programs=(bad,))
                row, _ = result(arch, spi_bench(arch, bad_image, 0, False))
                self.assertFalse(row["pass"])
                self.assertTrue(any("pin data mismatch" in error for error in row["errors"]))

    def test_one_i2c_image_handles_peers_with_different_responses(self):
        for arch in STORES:
            image = build(arch, "i2c")
            for variant, stretch, nack in (("combined", 600, 0), ("nack-address", 0, 1), ("nack-data", 0, 1)):
                with self.subTest(arch=arch, variant=variant):
                    row, _ = result(arch, i2c_bench(arch, image, I2CCase(variant, True, stretch)))
                    self.assertTrue(row["pass"], row)
                    self.assertEqual(row["payload"]["i2c_nack"], [nack])
