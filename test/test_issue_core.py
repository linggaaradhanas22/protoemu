# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import cocotb
from cocotb.triggers import Timer

from test_blocks import tick


MASK = (1 << 24) - 1
HALF = 1 << 23
HALT, SAVE_NOW = 0, 15


def encode(op, *fields):
    word, shift = op, 5
    for value, width in fields:
        word |= (value & ((1 << width) - 1)) << shift
        shift += width
    return word


def set_reg(reg, value):
    return encode(1, (reg, 3), (value, 16))


def get(reg):
    return encode(23, (reg, 3))


def put(reg):
    return encode(24, (reg, 3))


def pad(pin, delay):
    return encode(18, (pin, 3), (1, 1), (1, 1), (delay, 9))


def shift_pin(reg, pin, delay, lsb):
    return encode(20, (reg, 3), (pin, 3), (delay, 9), (lsb, 1))


def edge_delta(pin, polarity, rd):
    return encode(26, (pin, 3), (polarity, 2), (rd, 3))


PORTS = (
    'running done faulted fault_safe fault_ctx fault_pc fault_cause fetch_req_valid fetch_pc '
    'drive_valid drive_ctx drive_deadline drive_mask drive_value drive_oe '
    'capture_arm capture_consume capture_ctx capture_pin capture_mode capture_polarity '
    'capture_level capture_guarded capture_target capture_timeout ingress_pop egress_push egress_word'
).split()


class Core:
    def __init__(self, dut):
        self.dut = dut

    def read(self, name):
        return int(getattr(self.dut, name).value)

    def reg(self, ctx, reg):
        return int(self.dut.u.regs[8 * ctx + reg].value)

    def stamp(self, ctx):
        return int(self.dut.u.saved_stamp[ctx].value)

    async def start(self, words, other=(), epoch=0, first=0):
        self.words = dict(enumerate(words, first))
        self.words.update(enumerate(other, 64))
        self.edges = []
        self.cycle = epoch
        self.reply = (0, 0, 0)
        self.dut.clk.value = 0
        await self.step(rst_n=0, start=0, flush=0, enable_ctx=3 if other else 1,
                        entry0=first, entry1=64, drive_credit=1, drive_ready=1,
                        drive_reject=0, drive_empty=1, capture_ready=0, capture_bit=0,
                        capture_arm_reject=0, capture_expired=0, capture_stamp=0,
                        ingress_ready=0, ingress_words=0, egress_ready=3, sample=False)
        await self.step(rst_n=1, start=1)

    async def step(self, sample=True, **inputs):
        if 'start' not in inputs:
            inputs['start'] = 0
        for name, value in inputs.items():
            getattr(self.dut, name).value = value
        self.dut.cycle.value = self.cycle
        for name, value in zip(('fetch_rsp_valid', 'fetch_rsp_fault', 'fetch_instruction'), self.reply):
            getattr(self.dut, name).value = value
        await Timer(1, unit='ns')
        if sample:
            edge = SimpleNamespace(cycle=self.cycle, **{x: self.read(x) for x in PORTS})
            self.edges.append(edge)
            pc = edge.fetch_pc
            self.reply = (int(edge.fetch_req_valid), int(bool(edge.fetch_req_valid) and pc not in self.words),
                          self.words.get(pc, 0))
        else:
            edge = None
        await tick(self.dut.clk)
        self.cycle = (self.cycle + 1) & MASK
        return edge

    async def until(self, name, limit=48):
        for _ in range(limit):
            edge = await self.step()
            if getattr(edge, name):
                return edge
        raise AssertionError(f'No {name} after {limit} edges')

    def fetches(self):
        return [(e.cycle, e.fetch_pc) for e in self.edges if e.fetch_req_valid]

    async def fault(self, pc, cause, ctx=0):
        edge = await self.until('fault_safe')
        assert not edge.faulted and (edge.fault_pc, edge.fault_cause, edge.fault_ctx) == (pc, cause, ctx)
        assert not any((edge.fetch_req_valid, edge.drive_valid, edge.capture_arm,
                        edge.capture_consume, edge.ingress_pop, edge.egress_push))
        assert self.read('faulted') == 1 and self.read('fault_safe') == 0
        held = await self.step(start=1)
        assert held.faulted and not held.running and not held.done
        await self.step(flush=1)
        assert self.read('faulted') == 0


async def scheduler_and_payload(c):
    jump = encode(11, (3, 7))
    await c.start([set_reg(1, 0x1111), jump, 12, HALT], [set_reg(1, 0x2222), put(1), HALT])
    await c.step(drive_empty=0)
    pushed = await c.until('egress_push')
    assert (pushed.egress_push, pushed.egress_word) == (2, 0x2222)
    for _ in range(8):
        assert not (await c.step()).done
    assert [pc for _, pc in c.fetches()] == [0, 64, 1, 65, 3, 66]
    first = c.fetches()[0][0]
    assert [t - first for t, _ in c.fetches()] == [0, 2, 4, 7, 9, 11]
    assert (c.reg(0, 1), c.reg(1, 1)) == (0x1111, 0x2222)
    assert (await c.step(drive_empty=1)).done

    await c.start([set_reg(1, 0x1234), get(1), put(1), HALT], [set_reg(1, 0xBEEF), put(1), HALT])
    await c.step(egress_ready=2)
    pushed = await c.until('egress_push')
    assert pushed.egress_push == 2
    assert c.reg(0, 1) == 0x1234
    assert (await c.step()).fetch_pc == 66
    assert not (await c.step(ingress_words=0xCAFE)).ingress_pop
    accepted = await c.step(ingress_ready=1)
    assert accepted.ingress_pop == 1 and not accepted.fetch_req_valid
    assert c.reg(0, 1) == 0xCAFE
    await c.step(ingress_ready=0)
    await c.step()
    assert not (await c.step()).egress_push
    accepted = await c.step(egress_ready=3)
    assert (accepted.egress_push, accepted.egress_word, accepted.fetch_req_valid) == (1, 0xCAFE, 0)
    await c.until('done')
    assert [e.ingress_pop for e in c.edges if e.ingress_pop] == [1]
    assert [e.egress_push for e in c.edges if e.egress_push] == [2, 1]
    assert [pc for _, pc in c.fetches()].count(1) == 1
    assert [pc for _, pc in c.fetches()].count(2) == 1


async def arithmetic_and_stack(c):
    await c.start([
        encode(7, (5, 7)), put(1), HALT, 12, 12,
        set_reg(1, 0xFFFE), encode(2, (1, 3), (-3, 15)), encode(27, (1, 3), (8, 4)),
        encode(7, (14, 7)), encode(9, (2, 3), (9, 7)), encode(10, (2, 3), (4, 7)), 8,
        12, 12, set_reg(2, 2), encode(29, (1, 3), (2, 3)), encode(31, (3, 3), (1, 3)),
        encode(30, (3, 3), (0x0100, 16)), 8,
    ])
    pushed = await c.until('egress_push')
    assert (pushed.egress_push, pushed.egress_word) == (1, 0x00FD)
    await c.until('done')
    assert (c.reg(0, 2), c.reg(0, 3)) == (0, 1)
    assert [pc for _, pc in c.fetches()] == [0, 5, 6, 7, 8, 14, 15, 16, 17, 18, 9, 9, 10, 11, 1, 2]

    await c.start([SAVE_NOW, set_reg(0, 0xFFF0), encode(16, (20, 15)), set_reg(1, 5),
                   encode(28, (1, 3)), pad(1, 0x30), HALT], epoch=MASK - 16)
    drive = await c.until('drive_valid')
    assert (c.reg(0, 6), c.reg(0, 0)) == (1, 9)
    assert drive.drive_deadline == (c.stamp(0) + 0x10039) & MASK
    await c.until('done')


async def drive_requests(c):
    pad2 = encode(19, (7, 3), (1, 1), (0, 1), (2, 3), (0, 1), (1, 1), (45, 9))
    pair = encode(21, (1, 3), (7, 3), (3, 3), (1, 1), (46, 9))
    vector = encode(22, (2, 3), (0x81, 8), (47, 8))
    await c.start([SAVE_NOW, set_reg(1, 0x8001), set_reg(2, 0xA587), pad(7, 44), pad2,
                   pair, vector, HALT])
    await c.until('done')
    stamp = c.stamp(0)
    assert [(e.drive_deadline - stamp, e.drive_mask, e.drive_value, e.drive_oe)
            for e in c.edges if e.drive_valid] == [
                (44, 0x80, 0x80, 0x80), (45, 0x84, 0x80, 0x04),
                (46, 0x88, 0x88, 0x88), (47, 0x87, 0xA5, 0x81)]
    assert c.reg(0, 1) == 2

    for order, value, expected in [(0, 0x8002, 4), (1, 0x4001, 0x2000)]:
        for admit in (True, False):
            instruction = shift_pin(1, 7, 60, order)
            await c.start([SAVE_NOW, set_reg(1, value), instruction, put(1), HALT],
                          [get(2), put(2), HALT], epoch=MASK - 14)
            await c.step(drive_credit=0, drive_ready=0)
            request = await c.until('drive_valid')
            assert (request.drive_ctx, request.drive_mask, request.drive_value, request.drive_oe) == (0, 128, 128, 128)
            assert request.drive_deadline == (c.stamp(0) + 60) & MASK
            assert c.reg(0, 1) == value
            sent = await c.step(ingress_ready=2, ingress_words=0xACDC0000)
            assert sent.ingress_pop == 2 and not sent.drive_valid
            assert (await c.until('egress_push')).egress_word == 0xACDC
            c.cycle = (request.drive_deadline - 1) & MASK
            retry = await c.step(drive_credit=1, drive_ready=int(admit), drive_reject=int(not admit))
            assert (retry.drive_deadline, retry.drive_mask, retry.drive_value, retry.drive_oe) == (
                request.drive_deadline, request.drive_mask, request.drive_value, request.drive_oe)
            assert retry.drive_valid and not retry.fetch_req_valid
            assert [pc for _, pc in c.fetches()].count(2) == 1
            if admit:
                assert c.reg(0, 1) == expected
                assert (await c.until('egress_push')).egress_word == expected
            else:
                assert c.reg(0, 1) == value
                await c.fault(2, 5)

    await c.start([SAVE_NOW, pad(0, 30), HALT], [get(1), put(1), HALT])
    await c.step(drive_credit=0, drive_ready=0)
    timed = await c.until('drive_valid')
    c.cycle = timed.drive_deadline
    competing = await c.step(ingress_ready=2, ingress_words=0xACDC0000)
    assert competing.ingress_pop == 2 and not competing.fault_safe
    fault_edge = await c.step(ingress_ready=0)
    assert not any((fault_edge.fault_safe, fault_edge.faulted, fault_edge.fetch_req_valid,
                    fault_edge.drive_valid, fault_edge.ingress_pop, fault_edge.egress_push))
    assert c.read('fault_safe') == 1 and c.read('faulted') == 0 and c.reg(1, 1) == 0xACDC
    await c.fault(1, 5)


async def capture_and_intervals(c):
    edge_save = encode(25, (3, 3), (2, 2))
    cap = encode(5, (7, 3), (2, 3), (2, 2), (30, 9))
    wait_save = encode(17, (4, 3), (1, 1), (0, 9))
    await c.start([edge_save, cap, HALT], [wait_save, HALT])
    arm0 = await c.until('capture_arm')
    arm1 = await c.until('capture_arm')
    assert (arm0.capture_ctx, arm0.capture_mode, arm0.capture_pin, arm0.capture_polarity) == (0, 2, 3, 2)
    assert (arm1.capture_ctx, arm1.capture_mode, arm1.capture_guarded, arm1.capture_level) == (1, 1, 0, 1)
    for _ in range(3):
        idle = await c.step()
        assert not (idle.fetch_req_valid or idle.capture_arm or idle.capture_consume)
    assert (await c.step(capture_ready=2, capture_stamp=arm1.cycle + 1)).capture_ctx == 1
    assert c.stamp(1) == arm1.cycle + 1
    assert c.stamp(0) == 0
    used = await c.step(capture_ready=1, capture_stamp=arm0.cycle + 1)
    assert used.capture_consume and used.capture_ctx == 0
    await c.step(capture_ready=0)
    sample = await c.until('capture_arm')
    assert (sample.capture_mode, sample.capture_target, sample.capture_pin) == (0, arm0.cycle + 31, 7)
    assert (await c.step(capture_ready=1, capture_stamp=sample.capture_target, capture_bit=1)).capture_consume
    assert c.reg(0, 2) == 128 and c.stamp(0) == arm0.cycle + 1

    for rd in range(1, 5):
        await c.start([edge_save, set_reg(0, 0x5100), set_reg(6, 3), set_reg(7, 0xBEEF),
                       edge_delta(5, 1, rd), HALT])
        await c.until('capture_arm')
        await c.step(capture_ready=1, capture_stamp=MASK - 0x10)
        await c.step(capture_ready=0)
        arm = await c.until('capture_arm')
        assert (arm.capture_pin, arm.capture_polarity) == (5, 1)
        before = [c.reg(0, i) for i in range(8)]
        result = await c.step(capture_ready=1, capture_stamp=0x23456)
        assert result.capture_consume
        before[0] = before[6] = 0
        before[rd], before[rd + 1] = 0x3467, 2
        assert [c.reg(0, i) for i in range(8)] == before and c.stamp(0) == 0x23456

    for interval in (0, HALF):
        await c.start([edge_save, set_reg(1, 0x101), set_reg(2, 0x202), edge_delta(3, 0, 1), HALT])
        await c.until('capture_arm')
        await c.step(capture_ready=1, capture_stamp=9)
        await c.step(capture_ready=0)
        await c.until('capture_arm')
        attempted = await c.step(capture_ready=1, capture_stamp=9 + interval)
        assert not attempted.capture_consume and c.stamp(0) == 9
        assert c.reg(0, 1) == 0x101 and c.reg(0, 2) == 0x202
        await c.fault(3, 4)


async def fences_and_timed_wait(c):
    fence = encode(14, (0, 9))
    for epoch in (0, MASK - 7):
        for delta in (0, 1, HALF - 1, HALF, MASK):
            await c.start([SAVE_NOW, fence, HALT], epoch=epoch)
            await c.until('fetch_req_valid')
            await c.step()
            stamp = c.stamp(0)
            await c.until('fetch_req_valid')
            c.cycle = (stamp - delta) & MASK
            await c.step()
            if 0 < delta < HALF:
                if delta > 1:
                    c.cycle = (stamp - 1) & MASK
                    assert not (await c.step()).fetch_req_valid
                assert not (await c.step()).fetch_req_valid  # Guard retires this edge, no fetch.
            assert (await c.step()).fetch_req_valid
            await c.until('done')

    await c.start([SAVE_NOW, encode(14, (40, 9)), HALT],
                  [SAVE_NOW, encode(14, (44, 9)), HALT])
    for _ in range(4):
        await c.until('fetch_req_valid')
    await c.step()
    for ctx, delay, pc in [(0, 40, 2), (1, 44, 66)]:
        c.cycle = c.stamp(ctx) + delay - 1
        assert not (await c.step()).fetch_req_valid
        assert not (await c.step()).fetch_req_valid
        fetched = await c.step()
        assert fetched.fetch_req_valid and fetched.fetch_pc == pc
        await c.step()
    await c.until('done')

    await c.start([SAVE_NOW, encode(14, (20, 9)), put(2), HALT], [get(1), HALT])
    await c.until('fetch_req_valid')
    await c.step()
    target = c.stamp(0) + 20
    for _ in range(6):
        await c.step()
    c.cycle = target - 2
    assert (await c.step(ingress_ready=2)).ingress_pop == 2
    assert (await c.step()).fetch_pc == 65
    assert not (await c.step()).fetch_req_valid
    # The target has passed while the other context occupied the execute slot.
    c.cycle = (target + HALF) & MASK
    assert not (await c.step()).fetch_req_valid
    next_fetch = await c.step()
    assert next_fetch.fetch_req_valid and next_fetch.fetch_pc == 2
    await c.until('done')

    timed_wait = encode(6, (2, 3), (1, 1), (5, 9), (3, 3))
    for expired, rt in [(True, 2), (False, 2), (False, 0)]:
        await c.start([SAVE_NOW, set_reg(3, rt), set_reg(0, 9), timed_wait, HALT],
                      [get(4), put(4), HALT])
        arm = await c.until('capture_arm')
        old_stamp = c.stamp(0)
        assert (arm.capture_mode, arm.capture_target, arm.capture_timeout, arm.capture_guarded) == (
            1, old_stamp + 14, rt, 1)
        assert (await c.step(ingress_ready=2, ingress_words=0xABCD0000)).ingress_pop == 2
        assert (await c.until('egress_push')).egress_word == 0xABCD
        captured = await c.step(capture_ready=1, capture_expired=int(expired), capture_stamp=arm.capture_target + 2)
        assert captured.capture_consume and captured.capture_ctx == 0
        assert (c.reg(0, 3), c.reg(0, 0), c.stamp(0)) == (
            (0, 9, old_stamp) if expired else (rt, 0, arm.capture_target + 2))

    await c.start([SAVE_NOW, set_reg(3, 0xFFFF), timed_wait, HALT])
    for _ in range(3):
        await c.until('fetch_req_valid')
    c.cycle = (c.stamp(0) + HALF) & MASK
    assert not (await c.step()).capture_arm
    await c.fault(2, 4)


async def invalid_and_flush(c):
    bad_cases = [([12], 0, 2), ([get(1) | (1 << 23)], 0, 2), ([8], 0, 3),
                 ([7], 0, 3), ([edge_delta(0, 1, 1)], 0, 4), ([edge_delta(0, 1, 6)], 0, 2),
                 ([pad(0, 40)], 0, 4),
                 ([encode(16, (-1, 15))], 0, 4),
                 ([SAVE_NOW, set_reg(0, 0xffff), set_reg(6, 127), pad(1, 1)], 3, 4),
                 ([SAVE_NOW, encode(22, (1, 3), (1, 8), (48, 8))], 1, 5),
                 ([SAVE_NOW, encode(19, (1, 3), (1, 1), (1, 1), (1, 3), (0, 1), (1, 1), (30, 9))], 1, 2)]
    for words, pc, cause in bad_cases:
        await c.start(words)
        await c.fault(pc, cause)
        assert not any(e.capture_arm or e.drive_valid or e.ingress_pop or e.egress_push for e in c.edges)

    await c.start([set_reg(1, 1)], first=127)
    await c.fault(128, 1)
    assert [pc for _, pc in c.fetches()] == [127]
    await c.start([encode(11, (5, 7)), HALT])
    await c.fault(5, 1)

    await c.start([encode(25, (7, 3), (0, 2)), HALT])
    await c.step(capture_arm_reject=1)
    assert (await c.step()).capture_arm
    await c.fault(0, 6)

    await c.start([SAVE_NOW, get(1), HALT])
    await c.until('fetch_req_valid')
    await c.until('fetch_req_valid')
    await c.step()
    assert c.read('running') == 1
    stopped = await c.step(flush=1, ingress_ready=1)
    assert not stopped.ingress_pop
    assert c.read('running') == 0 and c.stamp(0) == 0
    c.words = {0: pad(0, 50), 1: HALT}
    await c.step(flush=0, start=1)
    await c.fault(0, 4)


@cocotb.test()
async def test_issue_context_isolation(dut):
    """TEST-UNIT-001: decode, scheduling, same-edge retry, and fault ordering."""
    c = Core(dut.core_tb)
    for check in (scheduler_and_payload, arithmetic_and_stack, drive_requests,
                  capture_and_intervals, fences_and_timed_wait, invalid_and_flush):
        dut._log.info(check.__name__)
        await check(c)
