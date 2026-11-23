# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from random import Random

import cocotb
from cocotb.triggers import Timer

from test_blocks import tick


MODULUS = 1 << 24
HALF = MODULUS // 2


@dataclass(frozen=True)
class Update:
    deadline: int
    mask: int
    value: int = 0xFF
    oe: int = 0xFF
    ctx: int = 0


class DriveQueue:
    def __init__(self, dut):
        self.dut = dut

    def get(self, name):
        return int(getattr(self.dut, name).value)

    async def reset(self, epoch=0, owners=(0x0F, 0xF0)):
        self.now = epoch
        self.owners = owners
        self.pending = []
        self.fault_pending = False
        self.dut.clk.value = 0
        self.dut.owner0.value, self.dut.owner1.value = owners
        self.dut.detect_fault.value = 0
        self.dut.flush.value = 0
        self.dut.rst_n.value = 0
        self.dut.drive_valid.value = 0
        await Timer(1, unit='ns')
        await tick(self.dut.clk)
        assert self.get('drive_empty') == 1

    async def step(self, request=None, *, flush=False, reset=False, fault=False):
        dut = self.dut
        dut.cycle.value = self.now
        dut.rst_n.value = not reset
        dut.flush.value = flush
        dut.detect_fault.value = fault
        dut.drive_valid.value = request is not None
        if request is not None:
            dut.drive_ctx.value = request.ctx
            dut.drive_deadline.value = request.deadline
            dut.drive_mask.value = request.mask
            dut.drive_value.value = request.value
            dut.drive_oe.value = request.oe

        disabled = flush or reset or self.fault_pending
        due = [e for e in self.pending if e.deadline == self.now and not disabled]
        credit = not disabled and len(self.pending) - len(due) < 4
        mask, value, oe = 0, 0, 0
        for e in due:
            assert not mask & e.mask
            mask |= e.mask
            value |= e.value & e.mask
            oe |= e.oe & e.mask

        reject = False
        if request is not None and not disabled:
            owned = request.mask & self.owners[request.ctx]
            distance = (request.deadline - self.now) % MODULUS
            overlap = any(e.deadline == request.deadline and e.mask & request.mask for e in self.pending)
            reject = not (0 < distance < HALF and request.mask and owned == request.mask and not overlap)
        ready = request is not None and credit and not reject
        await Timer(1, unit='ns')
        actual = tuple(self.get(k) for k in ('drive_credit', 'drive_ready', 'drive_reject', 'drive_empty',
                                             'update_mask', 'update_value', 'update_oe'))
        expected = (credit, ready, reject, not self.pending, mask, value, oe)
        assert actual == expected, f'cycle {self.now:#08x}, request {request}: {actual} != {expected}'
        if disabled:
            self.pending.clear()
        else:
            self.pending = [e for e in self.pending if e not in due]
            if ready:
                self.pending.append(request)
        await tick(dut.clk)
        assert self.get('drive_empty') == (not self.pending)
        self.now = (self.now + 1) % MODULUS
        self.fault_pending = fault and not reset
        return actual

    async def drain(self, cycles):
        for _ in range(cycles):
            await self.step()
        assert not self.pending and self.get('drive_empty')


async def full_and_merge(q):
    await q.reset()
    assert (await q.step(Update(12, 0x01)))[1]
    assert (await q.step(Update(8, 0x02, 0x02, 0xFF)))[1]
    assert (await q.step(Update(8, 0x80, 0x7F, 0x7F, ctx=1)))[1]
    assert (await q.step(Update(10, 0x04)))[1]
    waiting = Update(17, 0x08)
    assert (await q.step(waiting))[:3] == (0, 0, 0)
    assert (await q.step(Update(12, 0x03)))[:3] == (0, 0, 1)
    assert (await q.step(Update(14, 0x11)))[:3] == (0, 0, 1)
    assert (await q.step(waiting))[:3] == (0, 0, 0)
    assert (await q.step(waiting)) == (1, 1, 0, 0, 0x82, 0x02, 0x02)
    await q.drain(12)

    await q.reset()
    for target in (20, 21, 22, 23):
        assert (await q.step(Update(target, 1)))[1]
    retry = Update(5, 2)
    assert (await q.step(retry))[:3] == (0, 0, 0)
    assert (await q.step(retry))[:3] == (0, 0, 1)
    assert (await q.step(retry))[:3] == (0, 0, 1)
    while q.now < 20:
        await q.step()
    assert (await q.step(Update(24, 2))) == (1, 1, 0, 0, 1, 1, 1)
    assert len(q.pending) == 4
    await q.drain(4)


async def wide_and_wrap(q):
    for owner in (0xFF, 0xFE):
        await q.reset(owners=(owner, 0))
        for target in (20, 21, 22):
            assert (await q.step(Update(target, 0x80)))[1]
        wide = await q.step(Update(12, 0xFF, 0xA5, 0x5A))
        assert wide[1:3] == (owner == 0xFF, owner != 0xFF)
        assert (await q.step())[0] == (owner != 0xFF)
        while q.now < 12:
            await q.step()
        output = await q.step()
        assert output[-3:] == ((0xFF, 0xA5, 0x5A) if owner == 0xFF else (0, 0, 0))
        await q.drain(12)

    await q.reset(epoch=MODULUS - 4)
    assert (await q.step(Update(0, 0x01)))[1]
    assert (await q.step(Update(MODULUS - 1, 0x80, ctx=1)))[1]
    assert (await q.step(Update(q.now, 0x02)))[2]
    assert (await q.step(Update(2, 0x08)))[-3:] == (0x80, 0x80, 0x80)
    assert (await q.step(Update(1, 0x04), flush=True)) == (0, 0, 0, 0, 0, 0, 0)
    await q.drain(5)

    await q.reset()
    assert (await q.step(Update(10, 0)))[2]
    assert (await q.step(Update(q.now + HALF, 1)))[2]
    assert (await q.step(Update(q.now + HALF + 1, 1)))[2]
    target = q.now + HALF - 1
    assert (await q.step(Update(target, 1)))[1]
    q.now = target
    assert (await q.step())[-3:] == (1, 1, 1)
    await q.drain(1)


async def flush_and_fault(q):
    for reset in (False, True):
        await q.reset()
        assert (await q.step(Update(2, 3)))[1]
        assert (await q.step(Update(3, 4)))[1]
        assert (await q.step(Update(4, 8), flush=not reset, reset=reset)) == (0, 0, 0, 0, 0, 0, 0)
        await q.drain(5)

    await q.reset()
    assert (await q.step(Update(4, 0x03, 0x02, 0x01)))[1]
    assert (await q.step(Update(5, 0x30, ctx=1)))[1]
    assert (await q.step(Update(7, 0x0C)))[1]
    await q.step()
    assert (await q.step(fault=True))[-3:] == (3, 2, 1)
    assert (await q.step()) == (0, 0, 0, 0, 0, 0, 0)
    await q.drain(5)


async def randomized(q):
    await q.reset(epoch=MODULUS - 120)
    rng = Random(0xD21E)
    n_accept = n_reject = n_stall = 0
    for _ in range(600):
        if rng.randrange(5) == 0:
            await q.step()
            continue
        ctx = rng.randrange(2)
        mask = rng.randrange(256) if rng.randrange(6) == 0 else rng.randrange(1, 16) << (ctx * 4)
        delta = rng.randint(-2, 24)
        e = Update((q.now + delta) % MODULUS, mask, rng.randrange(256), rng.randrange(256), ctx)
        _, accepted, rejected, *_ = await q.step(e, flush=rng.randrange(43) == 0)
        n_accept += accepted
        n_reject += rejected
        n_stall += not (accepted or rejected)
    await q.drain(25)
    assert all(n > 20 for n in (n_accept, n_reject, n_stall))


@cocotb.test()
async def test_timed_drive_queue(dut):
    """TEST-UNIT-003: admission, exact retirement, wrap, merge and cancellation."""
    q = DriveQueue(dut.drive_tb)
    for scenario in (full_and_merge, wide_and_wrap, flush_and_fault, randomized):
        dut._log.info(scenario.__name__)
        await scenario(q)
