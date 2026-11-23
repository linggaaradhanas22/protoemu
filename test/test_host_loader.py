# SPDX-License-Identifier: Apache-2.0

from binascii import crc_hqx

import cocotb
from cocotb.triggers import Timer

from test_blocks import tick


BEGIN, DATA, COMMIT, START, STOP, WRITE, READ, READN, WRITEN = range(1, 10)
OK, COMPLETE, BAD, STATE, FULL, EMPTY = range(6)


def frame(code, body=b''):
    payload = bytes([code]) + len(body).to_bytes(2, 'little') + body
    return payload + crc_hqx(payload, 0xFFFF).to_bytes(2, 'little')


def bits(data):
    return [byte >> i & 1 for byte in data for i in range(7, -1, -1)]


def words(values):
    return b''.join(value.to_bytes(2, 'little') for value in values)


class SPI:
    def __init__(self, dut):
        self.dut = dut

    def get(self, name):
        return int(getattr(self.dut, name).value)

    async def edge(self, **inputs):
        for name, value in inputs.items():
            getattr(self.dut, name).value = value
        await Timer(1, unit='ns')
        bit = self.get('host_miso')
        if self.get('rst_n') and self.get('selected'):
            if self.get('prog_write_valid'):
                self.image_writes.append((self.get('prog_write_index'), self.get('prog_write_word')))
            self.starts += self.get('start')
        await tick(self.dut.clk)
        return bit

    async def reset(self, cs=1):
        self.image_writes, self.starts = [], 0
        self.dut.clk.value = 0
        await self.edge(rst_n=0, selected=1, host_cs_n=cs, host_sck=0, host_mosi=0,
                        core_done=0, core_faulted=0, core_fault_safe=0, core_fault_ctx=0,
                        core_fault_pc=0, core_fault_cause=0, ingress_pop=0, egress_push=0, egress_word=0)
        await self.edge(rst_n=1)
        assert not self.get('host_ready') and not self.get('image_valid')

    async def transfer(self, stream, *, close=True):
        await self.edge(host_cs_n=0, host_sck=0)
        reply = []
        for bit in stream:
            reply.append(await self.edge(host_sck=1, host_mosi=bit))
            await self.edge(host_sck=0)
        if close:
            await self.edge(host_cs_n=1)
        return reply

    async def wait_reply(self):
        for _ in range(20):
            if self.get('host_ready'):
                return
            await self.edge()
        raise AssertionError('expected framed reply')

    async def reply(self, code, body=b'', *, extra=0):
        await self.wait_reply()
        expected = bits(frame(code, body))
        if extra < 0:
            expected = expected[:extra]
        incoming = await self.transfer([1] * (len(expected) + max(0, extra)))
        assert incoming[:len(expected)] == expected, (code, body, ''.join(map(str, incoming)))
        assert self.get('host_ready') == bool(extra)

    async def command(self, op, response=OK, *, body=b'', returned=b''):
        await self.transfer(bits(frame(op, body)))
        await self.reply(response, returned)

    async def load(self, count=2):
        data = [(0xABCDEF - i * 0x20413) & 0xFFFFFF for i in range(count)]
        await self.command(BEGIN, body=bytes((count, 3, 0, count - 1, 0x0F, 0xF0, 0x80)))
        self.image_writes.clear()
        await self.command(DATA, body=b''.join(word.to_bytes(3, 'little') for word in data))
        assert self.image_writes == list(enumerate(data))
        assert not self.get('image_valid') and not self.get('running')
        await self.command(COMMIT, COMPLETE)
        assert self.get('image_valid') and not self.get('running')

    async def pop(self, ctx, expected):
        assert self.get('ingress_ready') & (1 << ctx)
        assert (self.get('ingress_words') >> (16 * ctx)) & 0xFFFF == expected
        await self.edge(ingress_pop=1 << ctx)
        await self.edge(ingress_pop=0)

    async def push(self, ctx, word):
        await self.edge(egress_push=1 << ctx, egress_word=word)
        await self.edge(egress_push=0)


async def image_and_run(s):
    await s.reset()
    await s.command(START, STATE)
    for cfg in ((1, 1, 1, 0, 1, 0, 0), (2, 3, 0, 1, 1, 1, 0), (2, 1, 0, 1, 1, 0, 0),
                (1, 1, 0, 0, 1, 0, 2), (0, 1, 0, 0, 1, 0, 0)):
        await s.command(BEGIN, BAD, body=bytes(cfg))
        assert not s.get('load_active')
    await s.command(BEGIN, body=bytes((1, 1, 0, 0, 1, 0, 0)))
    corrupt = bytearray(frame(DATA, b'\x12\x34\x56'))
    corrupt[-1] ^= 1
    await s.transfer(bits(corrupt))
    await s.reply(BAD)
    assert s.image_writes == [(0, 0x563412)] and not s.get('load_active')
    await s.command(COMMIT, BAD)
    await s.command(BEGIN, body=bytes((2, 1, 0, 0, 1, 0, 0)))
    await s.transfer(bits(frame(DATA, b'\x01\x02\x03\x04\x05\x06'))[:-24])
    await s.reply(BAD)
    await s.command(COMMIT, BAD)
    await s.load(128)
    assert (s.get('enable_ctx'), s.get('entry1'), s.get('owner0'), s.get('owner1'),
            s.get('open_drain'), s.get('word_count')) == (3, 127, 15, 240, 128, 128)
    await s.command(WRITE, body=b'\x01\xcd\xab')
    await s.command(START)
    assert s.get('running') and s.starts == 1
    await s.pop(1, 0xABCD)
    await s.command(START, STATE)
    for op, body in ((BEGIN, bytes((1, 1, 0, 0, 1, 0, 0))), (DATA, bytes(384)), (COMMIT, b'')):
        await s.command(op, STATE, body=body)
    assert len(s.image_writes) == 128 and s.get('running') and s.starts == 1

    await s.transfer(bits(frame(STOP)), close=False)
    assert not s.get('safe') and s.get('running')
    await s.edge(host_cs_n=1)
    assert s.get('flush') and s.get('safe') and not s.get('host_ready') and s.get('image_valid')
    await s.edge()
    assert not s.get('safe') and not s.get('image_valid') and not s.get('running')
    await s.reply(OK, b'\x01\0\0\0')
    await s.load()


async def malformed_and_recovery(s):
    await s.reset()
    correct = bits(frame(BEGIN, bytes((1, 1, 0, 0, 1, 0, 0))))
    for packet in (correct[:-1], correct[:-8], correct + [1], bits(b'\x01\xff\xff' + bytes(400))):
        await s.transfer(packet)
        await s.reply(BAD)
        assert not s.get('load_active')
    await s.transfer(correct[:19], close=False)
    for _ in range(64):
        await s.edge()
    assert not s.get('load_active') and not s.get('host_ready')
    await s.edge(rst_n=0, host_cs_n=0)
    await s.edge(rst_n=1)
    await s.transfer(correct)
    assert not s.get('host_ready') and not s.get('load_active')
    await s.command(BEGIN, body=bytes((1, 1, 0, 0, 1, 0, 0)))
    await s.transfer(bits(frame(COMMIT)))
    await s.wait_reply()
    await s.edge(rst_n=0)
    await s.edge(rst_n=1)
    assert not s.get('host_ready') and not s.get('image_valid')
    await s.load()
    await s.command(START)
    await s.edge(selected=0)
    assert s.get('safe') and not s.get('running') and not s.get('image_valid')
    await s.edge(selected=1, host_cs_n=0)
    await s.transfer(bits(frame(START)))
    assert not s.get('host_ready')
    await s.load()


async def payload_commands(s):
    await s.reset()
    await s.load()
    await s.command(START)
    for used in range(9):
        for count in range(1, 5):
            ctx = (used + count) % 2
            core = 1 << ctx
            prefix = bytes([ctx])
            sent = list(range(0x1000, 0x1000 + count))
            initial = list(range(0x8000, 0x8000 + used))
            for word in initial:
                await s.command(WRITE, body=prefix + words([word]))
                await s.push(ctx, word)
            n = min(8 - used, count)
            await s.command(WRITEN, OK if n == count else FULL, body=prefix + words(sent), returned=bytes([n]))
            for word in initial + sent[:n]:
                await s.pop(ctx, word)
            assert not s.get('ingress_ready')
            if used:
                n = min(used, count)
                await s.command(READN, body=prefix + bytes([count]), returned=words(initial[:n]))
                for word in initial[n:]:
                    await s.command(READ, body=prefix, returned=words([word]))
            else:
                await s.command(READN, EMPTY, body=prefix + bytes([count]))
            await s.command(READ, EMPTY, body=prefix)
            assert s.get('egress_ready') & core

    for value in (0x1122, 0x3344, 0x5566):
        await s.push(0, value)
    await s.transfer(bits(frame(READN, b'\x00\x02')))
    for extra in (-1, 1, 0):
        await s.reply(OK, words([0x1122, 0x3344]), extra=extra)
    await s.command(READ, body=b'\x00', returned=words([0x5566]))
    await s.command(READ, EMPTY, body=b'\x00')
    await s.push(1, 0x7856)
    await s.push(1, 0xBC9A)
    await s.transfer(bits(frame(READ, b'\x01')))
    await s.reply(OK, words([0x7856]), extra=-8)
    await s.reply(OK, words([0x7856]))
    await s.command(READ, body=b'\x01', returned=words([0xBC9A]))
    await s.command(READ, EMPTY, body=b'\x01')

    bad = bytearray(frame(WRITEN, b'\x00' + words([0x1234, 0x5678])))
    bad[-1] ^= 0x80
    await s.transfer(bits(bad), close=False)
    assert not s.get('ingress_ready')
    await s.edge(host_cs_n=1, ingress_pop=1)
    await s.edge(ingress_pop=0)
    await s.reply(BAD)
    assert s.get('running') and not s.get('ingress_ready')

    # A last-moment core pop frees a slot before validation, but not on the same edge.
    for i in range(8):
        await s.command(WRITE, body=b'\x00' + words([i]))
    await s.transfer(bits(frame(WRITE, b'\x00' + words([8]))), close=False)
    await s.edge(host_cs_n=1, ingress_pop=1)
    await s.edge(ingress_pop=0)
    await s.reply(FULL)
    await s.command(WRITE, body=b'\x00' + words([0]))
    await s.transfer(bits(frame(WRITEN, b'\x00' + words([9, 10]))), close=False)
    await s.edge(ingress_pop=1)
    await s.edge(host_cs_n=1, ingress_pop=0)
    await s.reply(FULL, b'\x01')
    for i in (*range(2, 8), 0, 9):
        await s.pop(0, i)
    await s.transfer(bits(frame(WRITE, b'\x00' + words([0x1234]))), close=False)
    await s.edge(host_cs_n=1, ingress_pop=1)
    await s.edge(ingress_pop=0)
    await s.reply(OK)
    await s.pop(0, 0x1234)

    await s.transfer(bits(frame(READ, b'\x00')), close=False)
    await s.edge(host_cs_n=1, egress_push=1, egress_word=0x3456)
    await s.edge(egress_push=0)
    await s.reply(EMPTY)
    await s.command(READ, body=b'\x00', returned=words([0x3456]))

    for i in range(8):
        await s.push(1, i)
    await s.transfer(bits(frame(READN, b'\x01\x04')))
    await s.wait_reply()
    expected = bits(frame(OK, words(range(4))))
    assert await s.transfer([0] * len(expected), close=False) == expected
    await s.edge(host_cs_n=1, egress_push=2, egress_word=0xFFFF)
    await s.edge(egress_push=0)
    assert s.get('egress_ready') == 3
    await s.command(READN, body=b'\x01\x04', returned=words(range(4, 8)))
    await s.command(READ, EMPTY, body=b'\x01')


async def completion_and_fault(s):
    for fault in (False, True):
        await s.reset()
        await s.load()
        await s.command(START)
        for ctx in (0, 1):
            await s.command(WRITE, body=bytes([ctx]) + words([0x1010 + ctx]))
            await s.push(ctx, 0x2020 + ctx)
        if fault:
            await s.edge(core_fault_safe=1, core_fault_pc=0x80, core_fault_ctx=1, core_fault_cause=5)
            assert s.get('safe') and s.get('ingress_ready') == 3
            await s.edge(core_fault_safe=0, core_faulted=1)
            status = b'\x03\x01\x80\x05'
        else:
            await s.edge(core_done=1)
            assert not s.get('safe')
            status = b'\x02\x00\x00\x00'
        assert not s.get('running') and s.get('image_valid') and s.get('ingress_ready') == 3
        await s.command(START, STATE)
        for ctx in (0, 1):
            await s.command(READ, body=bytes([ctx]), returned=words([0x2020 + ctx]))
        await s.command(STOP, returned=status)
        assert not s.get('image_valid') and not s.get('ingress_ready')
        await s.edge(core_done=0, core_faulted=0)
        await s.load()

    await s.command(START)
    await s.transfer(bits(frame(STOP)), close=False)
    await s.edge(host_cs_n=1)
    assert s.get('safe') and not s.get('host_ready')
    await s.edge(core_fault_safe=1, core_fault_ctx=0, core_fault_cause=4, core_fault_pc=37)
    await s.edge(core_fault_safe=0, core_faulted=1)
    await s.reply(OK, bytes((3, 0, 37, 4)))


@cocotb.test()
async def test_loader_commit_and_start(dut):
    """TEST-UNIT-007: SPI framing, load/commit/start/stop, and payload recovery."""
    s = SPI(dut.loader_tb)
    for scenario in (image_and_run, malformed_and_recovery, payload_commands, completion_and_fault):
        dut._log.info(scenario.__name__)
        await scenario(s)
