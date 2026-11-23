# SPDX-License-Identifier: Apache-2.0

from collections import deque
from random import Random

import cocotb
from cocotb.triggers import Timer

from test_blocks import tick


DEPTH = 8


class Payload:
    def __init__(self, dut):
        self.dut = dut

    def read(self, pins):
        return tuple(int(getattr(self.dut, pin).value) for pin in pins.split())

    def clear_model(self):
        self.ingress = [deque(), deque()]
        self.egress = [deque(), deque()]
        self.staging = [[], []]

    def check_committed(self):
        actual = self.read('ingress_ready egress_ready ingress_words')
        expected = (sum(bool(q) << i for i, q in enumerate(self.ingress)),
                    sum((len(q) < DEPTH) << i for i, q in enumerate(self.egress)),
                    sum((q[0] if q else 0) << (16 * i) for i, q in enumerate(self.ingress)))
        assert actual == expected, f'core view {actual} != {expected}'

    async def reset(self):
        self.dut.clk.value = 0
        self.clear_model()
        await self.step(reset=True)

    async def step(self, *, ctx=0, word=0, write=False, stage=False, index=0, commit=False,
                   abort=False, peek=0, release=0, pop=0, push=0, result=0, clear=False, reset=False):
        values = dict(rst_n=not reset, clear=clear, host_ctx=ctx, host_word=word,
                      host_write=write, host_stage=stage, host_stage_index=index, host_commit=commit,
                      host_abort=abort, host_peek=peek, host_release=release, ingress_pop=pop,
                      egress_push=push, egress_word=result)
        for name, value in values.items():
            getattr(self.dut, name).value = value
        await Timer(1, unit='ns')

        iq, eq, staged = self.ingress[ctx], self.egress[ctx], self.staging[ctx]
        can_host_write = not (reset or clear or abort or commit)
        wready = can_host_write and not staged and len(iq) < DEPTH
        tready = can_host_write and index == len(staged) and len(iq) + len(staged) < DEPTH
        expected = (wready, tready, len(staged), len(eq), eq[peek] if peek < len(eq) else 0)
        if not reset:
            self.check_committed()
            actual = self.read('host_write_ready host_stage_ready host_staged_count host_egress_count host_egress_word')
            assert actual == expected, f'host view {actual} != {expected}: {values}'

        if clear or reset:
            self.clear_model()
        else:
            pops = [bool(pop & (1 << i) and q) for i, q in enumerate(self.ingress)]
            pushes = [bool(push & (1 << i) and len(q) < DEPTH) for i, q in enumerate(self.egress)]
            if 0 < release <= min(4, len(eq)):
                for _ in range(release):
                    eq.popleft()
            for i in range(2):
                if pops[i]:
                    self.ingress[i].popleft()
                if pushes[i]:
                    self.egress[i].append(result)
            if abort:
                for pending in self.staging:
                    pending.clear()
            elif commit:
                iq.extend(staged)
                staged.clear()
            elif write and wready:
                iq.append(word)
            elif stage and tready:
                staged.append(word)
        await tick(self.dut.clk)
        self.check_committed()
        return expected


async def occupancy_matrix(p):
    for used in range(DEPTH + 1):
        for length in range(1, 5):
            await p.reset()
            ctx = (used + length) % 2
            core = 1 << ctx
            for i in range(used):
                await p.step(ctx=ctx, write=True, word=0x1000 + i, push=core, result=0x8000 + i)

            for i in range(length):
                _, staged, *_ = await p.step(ctx=ctx, stage=True, index=i, word=0x3000 + i)
                assert staged == (i < DEPTH - used)
            expected_count = min(length, DEPTH - used)
            before = await p.step(ctx=ctx, commit=True, pop=core)
            assert before[2] == expected_count
            expected = [0x1000 + i for i in range(used)][1:] + [0x3000 + i for i in range(expected_count)]
            for word in expected:
                assert p.read('ingress_words')[0] >> (16 * ctx) == word
                await p.step(pop=core)
            assert p.read('ingress_ready')[0] == 0

            returned = min(length, used)
            for _ in range(2):
                for i in range(length):
                    before = await p.step(ctx=ctx, peek=i)
                    assert before[3:] == (used, 0x8000 + i if i < returned else 0)
            await p.step(ctx=ctx, release=returned, push=core, result=0xFFFF)
            remaining = used - returned + int(used < DEPTH)
            before = await p.step(ctx=ctx)
            assert before[3] == remaining


async def abort_and_boundaries(p):
    await p.reset()
    for ctx in range(2):
        await p.step(ctx=ctx, stage=True, word=0x12 + ctx, pop=3)
        await p.step(ctx=ctx, stage=True, index=2, word=0x3456)
        assert p.read('host_staged_count')[0] == 1
    assert p.read('ingress_ready')[0] == 0
    await p.step(abort=True, commit=True, stage=True, pop=3)
    for ctx in range(2):
        assert (await p.step(ctx=ctx, commit=True))[2] == 0
    assert p.read('ingress_ready')[0] == 0

    await p.step(ctx=0, write=True, word=0x0011)
    await p.step(ctx=0, stage=True, word=0x1122)
    await p.step(ctx=0, abort=True)
    assert p.read('ingress_words')[0] == 0x0011
    await p.step(ctx=0, write=True, pop=1, word=0x2233)
    assert p.read('ingress_words')[0] == 0x2233
    for i in range(DEPTH - 1):
        await p.step(write=True, word=0x3000 + i, push=1, result=0x5000 + i)
    before = await p.step(write=True, word=0xFFFF, pop=1, push=1, result=0x6000)
    assert not before[0]  # The pop cannot make room for this edge's write.
    assert (await p.step(stage=True, word=0xAAAA))[1]
    assert not (await p.step(stage=True, index=1, word=0xAAAA, pop=1))[1]  # Tentative space is reserved.
    assert (await p.step(stage=True, index=1, word=0xBBBB))[1]
    await p.step(commit=True)
    for _ in range(6):
        await p.step(pop=1)
    assert p.read('ingress_words')[0] == 0xAAAA
    await p.step(pop=1)
    assert p.read('ingress_words')[0] == 0xBBBB

    before = await p.step(release=5, push=1, result=0xDEAD)
    assert before[3] == DEPTH
    before = await p.step()
    assert before[3:] == (DEPTH, 0x5000)
    await p.step(ctx=1, release=1, push=2, result=0xBEEF)
    assert (await p.step(ctx=1))[3:] == (1, 0xBEEF)
    await p.step(clear=True, commit=True, release=1, push=3, pop=3)
    assert p.read('ingress_ready egress_ready ingress_words') == (0, 3, 0)
    for ctx in range(2):
        assert (await p.step(ctx=ctx))[2:] == (0, 0, 0)


async def seeded_traffic(p):
    await p.reset()
    rng = Random(0xF1F0)
    for _ in range(512):
        ctx = rng.randrange(2)
        kind = rng.choice(('idle', 'write', 'stage', 'stage', 'commit', 'abort', 'release'))
        await p.step(ctx=ctx, word=rng.randrange(65536), write=kind == 'write', stage=kind == 'stage',
                     index=len(p.staging[ctx]) % 4, commit=kind == 'commit', abort=kind == 'abort',
                     peek=rng.randrange(4), release=rng.randrange(1, 6) if kind == 'release' else 0,
                     pop=rng.randrange(4), push=rng.randrange(4), result=rng.randrange(65536),
                     clear=rng.randrange(91) == 0)


@cocotb.test()
async def test_host_payload_fifos(dut):
    """TEST-UNIT-008: staged writes, retained replies, and committed occupancy."""
    p = Payload(dut.payload_tb)
    for scenario in (occupancy_matrix, abort_and_boundaries, seeded_traffic):
        dut._log.info(scenario.__name__)
        await scenario(p)
