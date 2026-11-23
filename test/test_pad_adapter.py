# SPDX-License-Identifier: Apache-2.0

from itertools import product

import cocotb
from cocotb.triggers import Timer

from test_blocks import tick


PINS = ('selected', 'host_cs_n', 'host_sck', 'host_mosi', 'pin_sample')
OUTPUTS = ('uo_out', 'uio_out', 'uio_oe')


class Pads:
    def __init__(self, dut):
        self.dut = dut

    def read(self, names):
        return tuple(int(getattr(self.dut, name).value) for name in names)

    async def reset(self):
        self.dut.clk.value = 0
        for name in ('rst_n', 'ena', 'ui_in', 'uio_in', 'host_miso', 'host_ready',
                     'safe', 'open_drain', 'update_mask', 'update_value', 'update_oe'):
            getattr(self.dut, name).value = 0
        await Timer(3, unit='ns')
        await tick(self.dut.clk)
        assert self.read(PINS) == (0, 1, 0, 0, 0)
        assert self.read(OUTPUTS) == (0, 0, 0)

    async def step(self, **inputs):
        before = self.read(PINS + OUTPUTS)
        for name, value in inputs.items():
            getattr(self.dut, name).value = value
        await Timer(3, unit='ns')
        assert self.read(PINS + OUTPUTS) == before, 'a port changed without a sampling edge'
        await tick(self.dut.clk)
        assert self.read(('uo_out',))[0] & ~0x18 == 0
        return self.read(PINS), self.read(OUTPUTS)

    async def select(self, **inputs):
        await self.step(rst_n=1, ena=1, ui_in=1, **inputs)
        pins, outputs = await self.step()
        assert pins[0] == 1
        assert outputs == (0, 0, 0)


async def sync_and_host_mapping(p):
    await p.reset()
    pins, outputs = await p.step(rst_n=1, ena=1, ui_in=0xFE, uio_in=0x81, host_miso=1)
    assert pins == (0, 1, 0, 0, 0) and outputs == (0, 0, 0)
    pins, outputs = await p.step(ui_in=1, uio_in=0x42)
    assert pins == (1, 0, 1, 1, 0x81) and outputs == (0, 0, 0)
    pins, outputs = await p.step(ui_in=2, host_miso=1, host_ready=0)
    assert pins == (1, 1, 0, 0, 0x42) and outputs == (0x08, 0, 0)
    pins, outputs = await p.step(ui_in=4, host_miso=0, host_ready=1)
    assert pins == (1, 0, 1, 0, 0x42) and outputs == (0x10, 0, 0)
    pins, outputs = await p.step(ui_in=0xFC, update_mask=0x40, update_oe=0x40, update_value=0x40)
    assert pins == (1, 0, 0, 1, 0x42) and outputs == (0x10, 0x40, 0x40)
    pins, outputs = await p.step(update_mask=0, ui_in=5, host_miso=1, host_ready=1)
    assert pins == (1, 0, 0, 1, 0x42) and outputs == (0x18, 0x40, 0x40)
    pins, outputs = await p.step()
    assert pins == (1, 1, 0, 1, 0x42) and outputs == (0x18, 0x40, 0x40)

    pins, outputs = await p.step(ena=0)
    assert pins[0] == 1 and outputs == (0x18, 0x40, 0x40)
    pins, outputs = await p.step()
    assert pins[0] == 0 and outputs == (0x18, 0x40, 0x40)
    pins, outputs = await p.step(update_mask=0xFF, update_value=0xFF, update_oe=0xFF)
    assert pins[0] == 0 and outputs == (0, 0, 0)


async def masked_output_modes(p):
    await p.reset()
    await p.select(open_drain=0b11100000)
    _, outputs = await p.step(update_mask=0xFF, update_value=0x9E, update_oe=0xA3)
    assert outputs == (0, 0x1E, 0x23)
    _, outputs = await p.step(update_mask=0xE6, update_value=0x62, update_oe=0x46)
    assert outputs == (0, 0x1A, 0x07)
    _, outputs = await p.step(update_mask=0x80, update_value=0, update_oe=0x80)
    assert outputs == (0, 0x1A, 0x87)
    _, outputs = await p.step(update_mask=0x80, update_value=0, update_oe=0)
    assert outputs == (0, 0x1A, 0x07)
    # DONE supplies neither a pad update nor a safe pulse.
    _, outputs = await p.step(update_mask=0, update_value=0xFF, update_oe=0xFF)
    assert outputs == (0, 0x1A, 0x07)
    _, outputs = await p.step(safe=1, host_miso=1, host_ready=1)
    assert outputs == (0x18, 0, 0)


async def priority_cases(p):
    for reset, deselect, safe, due in product((False, True), repeat=4):
        await p.reset()
        await p.select()
        _, outputs = await p.step(update_mask=1, update_value=1, update_oe=1)
        assert outputs == (0, 1, 1)
        if deselect:
            await p.step(ena=0, update_mask=0)
            pins, outputs = await p.step()
            assert pins[0] == 0 and outputs == (0, 1, 1)
        _, outputs = await p.step(
            rst_n=not reset, safe=safe, update_mask=2 if due else 0,
            update_value=2, update_oe=2, host_miso=1, host_ready=1,
        )
        protocol = 0 if reset or deselect or safe else (3 if due else 1)
        host = 0 if reset or deselect else 0x18
        assert outputs == (host, protocol, protocol), (reset, deselect, safe, due)


@cocotb.test()
async def test_pad_sync_and_safe_drive(dut):
    """TEST-UNIT-006: pin mapping, two-stage sync, pad modes and safe priority."""
    p = Pads(dut.pad_tb)
    for check in (sync_and_host_mapping, masked_output_modes, priority_cases):
        dut._log.info(check.__name__)
        await check(p)
