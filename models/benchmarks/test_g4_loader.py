"""Directed G4 probe checks; not the registered cocotb tests."""

from unittest import TestCase

from .g4_loader import (BAD, BEGIN, COMMIT, DATA, EMPTY, FULL, OK, PHASES, READ,
                        START, STATE, STOP, US, WRITE, Endpoint, Transport, load, packet,
                        sample, transact)

SINGLE = (1, 0, 0, 0b1011, 0, 0)
OVERLAP = (3, 0, 1, 0, 0b1011, 0)


class LoaderTests(TestCase):
    def check_command(self, link, dut, op, status, body=b""):
        answer, edge = transact(link, dut, packet(op, body))
        self.assertEqual(answer, (status, b""))
        return edge

    def test_load_maximum_over_all_phases(self):
        image = bytes(x % 256 for x in range(384))
        for kind in ("nibble", "serial"):
            for phase in range(PHASES):
                with self.subTest(kind=kind, phase=phase):
                    link, dut = Transport(kind, phase, 25 * US), Endpoint()
                    self.assertLess(load(link, dut, image, SINGLE), 1000)
                    self.assertIsNone(dut.fetch(0))
                    self.check_command(link, dut, START, OK)
                    self.assertEqual(b"".join(dut.fetch(i) for i in range(128)), image)
                    self.assertIsNone(dut.fetch(128))

    def test_incomplete_corrupt_and_overlong_images_never_start(self):
        good = packet(DATA, b"xyz")
        corrupt = good[:-1] + bytes((good[-1] ^ 1,))
        for bad in (packet(DATA, b"xy"), packet(DATA, b"wxyz"), good[:-1], corrupt):
            dut, link = Endpoint(), Transport("serial", 3)
            self.check_command(link, dut, BEGIN, OK, bytes((1, *SINGLE)))
            self.check_command(link, dut, COMMIT, BAD)
            self.check_command(link, dut, BEGIN, OK, bytes((1, *SINGLE)))
            self.assertEqual(transact(link, dut, bad)[0], (BAD, b""))
            self.check_command(link, dut, START, STATE)
            self.assertIsNone(dut.fetch(0))

    def test_writes_rejected_while_running_and_short_reload_hides_old_words(self):
        dut, link = Endpoint(), Transport("serial", 9)
        load(link, dut, b"oldold", SINGLE)
        self.check_command(link, dut, START, OK)
        for op in (BEGIN, DATA, COMMIT):
            self.check_command(link, dut, op, STATE)
        self.assertEqual(dut.fetch(1), b"old")
        self.check_command(link, dut, STOP, OK)
        self.check_command(link, dut, START, STATE)
        load(link, dut, b"new", SINGLE)
        self.check_command(link, dut, START, OK)
        self.assertEqual(dut.fetch(0), b"new")
        self.assertIsNone(dut.fetch(1))

    def test_invalid_entry_ownership_and_pad_modes(self):
        dut, link = Endpoint(), Transport("nibble", 1)
        for body in ((2, 3, 0, 2, 0, 0, 0), (2, 3, 0, 1, 1, 1, 0), (2, 1, 0, 0, 1, 0, 2)):
            self.check_command(link, dut, BEGIN, BAD, bytes(body))
            self.check_command(link, dut, START, STATE)

    def test_separate_context_payload_buffers_without_host_service(self):
        dut, link = Endpoint(), Transport("serial", 15)
        load(link, dut, b"abcdef", OVERLAP)
        for i in range(dut.depth):
            self.check_command(link, dut, WRITE, OK, bytes((1, i, 0)))
        self.check_command(link, dut, WRITE, FULL, b"\x01\xaa\x00")
        self.check_command(link, dut, START, OK)
        for ctx, words in enumerate(((0x55, 0xAA, 0x80), (0x964B, 0x1234))):
            for word in words:
                self.assertTrue(dut.report(ctx, word))
        self.assertEqual(list(dut.ingress[1]), list(range(dut.depth)))
        for ctx, words in enumerate(((0x55, 0xAA, 0x80), (0x964B, 0x1234))):
            for word in words:
                self.assertEqual(transact(link, dut, packet(READ, bytes((ctx,))))[0],
                                 (OK, word.to_bytes(2, "little")))
            self.check_command(link, dut, READ, EMPTY, bytes((ctx,)))
        for word in range(dut.depth):
            self.assertTrue(dut.report(0, word))
        self.assertFalse(dut.report(0, 0xFFFF))
        self.assertTrue(dut.report(1, 0xFFFF))

    def test_safe_edge_wins_over_due_output(self):
        for mode in ("STOP", "deselect", "reset"):
            with self.subTest(mode=mode):
                dut, link = Endpoint(), Transport("serial", 7)
                load(link, dut, b"old", SINGLE)
                self.check_command(link, dut, START, OK)
                tick = link.t
                if mode == "STOP":
                    frame, close = link.frame(packet(STOP))
                    safe = close + PHASES
                elif mode == "deselect":
                    safe = sample(tick)
                else:
                    safe = sample(tick) - 2 * PHASES
                dut.due = [(safe - PHASES, 1), (safe, 2), (safe + PHASES, 3)]
                if mode == "STOP":
                    self.assertEqual(dut.command(frame, close), packet(OK))
                else:
                    getattr(dut, mode)(tick)
                self.assertEqual(dut.safe_at, safe)
                self.assertEqual(dut.last_emitted, [(safe - PHASES, 1)])
                self.assertFalse(dut.due)
                self.assertIsNone(dut.fetch(0))
                self.check_command(link, dut, START, STATE)
                load(link, dut, b"new", SINGLE)
                self.check_command(link, dut, START, OK)
                self.assertEqual(dut.fetch(0), b"new")
