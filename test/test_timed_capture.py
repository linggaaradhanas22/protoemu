# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass

import cocotb
from cocotb.triggers import Timer

from test_blocks import tick


MASK = (1 << 24) - 1
HALF = 1 << 23
SAMPLE, LEVEL, EDGE = 0, 1, 2


@dataclass(frozen=True)
class Arm:
    mode: int
    pin: int = 7
    polarity: int = 0
    level: int = 1
    guarded: bool = False
    target: int = 0
    timeout: int = 0


@dataclass(frozen=True)
class Status:
    ready: int
    bit: int
    expired: int
    stamp: int
    reject: int

    @property
    def result(self):
        return self.bit, self.expired, self.stamp


class Capture:
    def __init__(self, dut):
        self.dut = dut

    def status(self):
        return Status(*(int(getattr(self.dut, name).value) for name in (
            'capture_ready', 'capture_bit', 'capture_expired', 'capture_stamp', 'capture_arm_reject')))

    async def reset(self, epoch=0, pins=0):
        self.dut.clk.value = 0
        self.now = (epoch - 1) & MASK
        await self.step(pins=pins, reset=True)

    async def step(self, *, ctx=0, pins=None, arm=None, consume=False, reset=False,
                   flush=False, fault=False):
        dut = self.dut
        dut.cycle.value = self.now
        dut.rst_n.value = not reset
        dut.flush.value = flush
        dut.detect_fault.value = fault
        if pins is not None:
            dut.pin_sample.value = pins
        dut.capture_ctx.value = ctx
        dut.capture_arm.value = arm is not None
        dut.capture_consume.value = consume
        fields = arm or Arm(SAMPLE)
        for name, value in vars(fields).items():
            getattr(dut, f'capture_{name}').value = value
        await Timer(1, unit='ns')
        before = None if reset else self.status()
        await tick(dut.clk)
        self.now = (self.now + 1) & MASK
        return before, self.status()

    async def arm(self, arm, *, reject=False, **kwargs):
        before, after = await self.step(arm=arm, **kwargs)
        assert before.reject == reject
        return after


async def ownership_and_edges(c):
    await c.reset(epoch=MASK - 4)
    assert (await c.arm(Arm(EDGE, polarity=1), pins=0x80)).ready == 0
    assert (await c.arm(Arm(EDGE, pin=2, polarity=2), ctx=1)).ready == 0
    before, after = await c.step(pins=0)
    assert before.ready == after.ready == 0  # Falling is not a rising-edge match.
    busy = await c.arm(Arm(LEVEL), reject=True)
    assert busy.ready == 0
    stamp = c.now
    before, after = await c.step(pins=0x84, consume=True)
    assert before.ready == 0 and before.result == (0, 0, 0)
    assert after.ready == 3 and after.result == (1, 0, stamp)
    for pins in (0, 0xFF, 0, 0):
        before, after = await c.step(pins=pins, ctx=1)
        assert before.ready == after.ready == 3 and after.result == (1, 0, stamp)
    assert c.now < stamp  # Both results are still readable after wrap.
    held = await c.arm(Arm(LEVEL), ctx=1, reject=True)
    assert held.ready == 3 and held.result == (1, 0, stamp)
    before, after = await c.step(ctx=1, consume=True)
    assert before.result == (1, 0, stamp)
    assert after.ready == 1 and after.result == (0, 0, 0)
    before, after = await c.step(consume=True)
    assert before.result == (1, 0, stamp) and after.ready == 0

    await c.arm(Arm(EDGE, polarity=0), pins=0x80)
    await c.step(pins=0x80)
    stamp = c.now
    before, after = await c.step(pins=0)
    assert not before.ready and after.ready == 1 and after.result == (0, 0, stamp)
    await c.step(consume=True)
    await c.arm(Arm(EDGE, polarity=2), pins=0x80)
    stamp = c.now
    _, after = await c.step(pins=0)
    assert after.ready == 1 and after.result == (0, 0, stamp)


async def timed_samples(c):
    await c.reset(epoch=MASK - 6)
    for distance in (0, HALF, MASK):
        assert not (await c.arm(Arm(SAMPLE, target=(c.now + distance) & MASK), reject=True)).ready
    assert not (await c.arm(Arm(EDGE, polarity=3), reject=True)).ready
    assert not (await c.arm(Arm(3), reject=True)).ready
    target = 2
    assert not (await c.arm(Arm(SAMPLE, pin=1, target=target))).ready
    for pins in (0xFF, 0, 0xFF):
        _, after = await c.step(pins=pins)
        assert not after.ready
    assert c.now == target
    before, after = await c.step(pins=0x02)
    assert not before.ready and after.ready == 1 and after.result == (1, 0, target)
    before, after = await c.step(ctx=1, consume=True, pins=0)
    assert before.ready == after.ready == 1 and after.result == (0, 0, 0)
    before, after = await c.step(consume=True)
    assert before.result == (1, 0, target) and not after.ready


async def guarded_levels(c):
    for distance in (0, 1, HALF - 1, HALF, MASK):
        for epoch in (10, MASK):
            await c.reset(epoch=epoch, pins=0x80)
            target = (epoch + distance) & MASK
            assert not (await c.arm(Arm(LEVEL, guarded=True, target=target))).ready
            expected = target if 0 < distance < HALF else c.now
            if distance == HALF - 1:
                _, after = await c.step()
                assert not after.ready
                c.now = (target - 1) & MASK
                _, after = await c.step()
                assert not after.ready
            before, after = await c.step()
            assert not before.ready and after.ready == 1 and after.result == (1, 0, expected)

    await c.reset()
    assert not (await c.arm(Arm(LEVEL, target=HALF - 1, timeout=1), pins=0x80)).ready
    stamp = c.now
    _, after = await c.step()
    assert after.ready == 1 and after.result == (1, 0, stamp)

    await c.reset(epoch=100)
    await c.arm(Arm(LEVEL, guarded=True, target=102))
    await c.step()
    _, after = await c.step()
    assert not after.ready
    # Advance the external timer while keeping the pin at the nonmatching level.
    c.now = 102 + HALF + 1
    stamp = c.now
    before, after = await c.step(pins=0x80)
    assert not before.ready and after.ready == 1 and after.result == (1, 0, stamp)


async def timed_waits(c):
    for epoch, offset, scenario in ((0, 3, 'early'), (0, 3, 'expiry'), (0, 3, 'tie'),
                                    (20, -5, 'expiry'), (20, -5, 'first'), (MASK - 6, 3, 'expiry'),
                                    (0, 3, 'disabled')):
        await c.reset(epoch=epoch)
        target = (epoch + offset) & MASK
        timeout = 0 if scenario == 'disabled' else 1
        expiry = (target + 64) & MASK
        await c.arm(Arm(LEVEL, pin=0, guarded=True, target=target, timeout=timeout))
        if offset > 0:
            for _ in range(offset - 1):
                _, after = await c.step()
                assert not after.ready
            assert c.now == target
            _, after = await c.step()
            assert not after.ready
        match = scenario != 'expiry'
        if scenario not in ('early', 'first'):
            c.now = (expiry - 1) & MASK
            _, after = await c.step()
            assert not after.ready
        stamp = c.now
        before, after = await c.step(pins=int(match and scenario != 'disabled'))
        assert not before.ready
        if scenario == 'disabled':
            assert not after.ready
            stamp = c.now
            _, after = await c.step(pins=1)
        assert after.ready == 1 and after.result == (int(match), int(not match), stamp)
        _, after = await c.step(pins=0 if match else 1)
        assert after.result == (int(match), int(not match), stamp)


async def flush_and_fault(c):
    for reset in (False, True):
        await c.reset()
        await c.arm(Arm(SAMPLE, target=2))
        await c.arm(Arm(SAMPLE, target=3), ctx=1)
        before, after = await c.step(pins=0x80, fault=True)
        assert not before.ready and after.ready == 1 and after.result == (1, 0, 2)
        _, after = await c.step(reset=reset, flush=not reset, pins=0x80)
        assert after.ready == 0 and after.result == (0, 0, 0)

    await c.reset()
    await c.arm(Arm(LEVEL), pins=0x80)
    await c.arm(Arm(SAMPLE, target=3), ctx=1)
    before, after = await c.step(fault=True)
    assert before.ready == after.ready == 1
    before, after = await c.step(ctx=1, pins=0x80)
    assert before.ready == 1 and before.result == (0, 0, 0)
    assert not after.ready
    target = c.now + 2
    await c.arm(Arm(LEVEL, guarded=True, target=target), ctx=1)
    _, after = await c.step(ctx=1)
    assert not after.ready
    _, after = await c.step(ctx=1)
    assert after.ready == 2 and after.result == (1, 0, target)


@cocotb.test()
async def test_capture_slot_ownership(dut):
    """TEST-UNIT-004: isolated captures, modular guards, timeouts and flush priority."""
    c = Capture(dut.capture_tb)
    for scenario in (ownership_and_edges, timed_samples, guarded_levels, timed_waits, flush_and_fault):
        dut._log.info(scenario.__name__)
        await scenario(c)
