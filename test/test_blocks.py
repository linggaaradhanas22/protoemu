# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.triggers import Timer


async def tick(clk):
    clk.value = 1
    await Timer(5, unit="ns")
    clk.value = 0
    await Timer(5, unit="ns")


@cocotb.test()
async def test_cycle_timer_wrap(dut):
    """TEST-UNIT-005: synchronous reset and pre-edge counts across wrap."""
    clk = dut.timer_clk
    rst_n = dut.timer_rst_n
    clk.value = 0
    rst_n.value = 0
    await Timer(5, unit="ns")
    await tick(clk)
    rst_n.value = 1

    assert len(dut.cycle) == 24
    modulus = 1 << len(dut.short_cycle)
    mask = modulus - 1
    observed = []
    for edge in range(260):
        before = int(dut.short_cycle.value)
        observed.append(before)
        assert before == (edge & mask)
        assert int(dut.cycle.value) == edge
        await tick(clk)

    # Compare modular deltas with their positions in the observed future half.
    arm_edge = modulus - 2
    half = modulus // 2
    future = observed[arm_edge + 1:arm_edge + half]
    for offset in (0, 1, half - 1, half, mask):
        target = (arm_edge + offset) & mask
        delta = (target - observed[arm_edge]) & mask
        assert (0 < delta < half) == (target in future)
        guard_wait = future.index(target) + 1 if target in future else 0
        assert guard_wait == (offset if offset in (1, half - 1) else 0)
    assert ((observed[modulus + 1] - observed[modulus - 1]) & mask) == 2

    rst_n.value = 0
    await Timer(5, unit="ns")
    assert int(dut.cycle.value) == 260
    assert int(dut.short_cycle.value) == (260 & mask)
    await tick(clk)
    assert int(dut.cycle.value) == int(dut.short_cycle.value) == 0
    await tick(clk)
    assert int(dut.cycle.value) == int(dut.short_cycle.value) == 0
    rst_n.value = 1
    await tick(clk)
    assert int(dut.cycle.value) == int(dut.short_cycle.value) == 1


@cocotb.test()
async def test_program_store_visibility(dut):
    """TEST-UNIT-002: registered instructions and faults for committed images."""
    idle = (0, 0, None)
    fault = (1, 1, None)

    def instruction(word):
        return (1, 0, word)

    def response():
        valid = int(dut.fetch_rsp_valid.value)
        bad = int(dut.fetch_rsp_fault.value)
        word = int(dut.fetch_instruction.value) if valid and not bad else None
        return valid, bad, word

    clk = dut.prog_clk
    clk.value = 0
    dut.prog_rst_n.value = 0
    for name in (
        "prog_write_valid", "prog_write_index", "prog_write_word", "load_active",
        "image_valid", "running", "word_count", "fetch_req_valid", "fetch_pc",
    ):
        getattr(dut, name).value = 0
    await Timer(5, unit="ns")
    await tick(clk)
    previous = idle
    assert response() == previous

    async def step(expected=idle, **inputs):
        nonlocal previous
        for name, value in inputs.items():
            getattr(dut, name).value = value
        await Timer(5, unit="ns")
        assert response() == previous, "response changed before the clock edge"
        await tick(clk)
        assert response() == expected, f"wrong registered response for {inputs}"
        previous = expected

    words = [(0xFEDCBA - 0x011021 * pc) & 0xFFFFFF for pc in range(128)]
    await step(prog_rst_n=1, running=1, fetch_req_valid=1, fetch_pc=127)
    await step(running=0, load_active=1, prog_write_valid=1, word_count=128)
    for pc, word in enumerate(words):
        await step(prog_write_index=pc, prog_write_word=word, fetch_req_valid=1, fetch_pc=pc)
    await step(load_active=0, prog_write_index=0, prog_write_word=0)
    await step(image_valid=1, prog_write_valid=0, fetch_pc=0)
    for pc, word in enumerate(words):
        await step(instruction(word), running=1, fetch_pc=pc)
    await step(instruction(words[0]), fetch_pc=0, prog_write_valid=1,
               prog_write_index=0, prog_write_word=0)
    await step(load_active=1)
    await step(instruction(words[0]), load_active=0, prog_write_valid=0)
    await step(fetch_req_valid=0)

    # A late CRC failure leaves tentative words, but no committed image.
    await step(running=0, image_valid=0, load_active=1, word_count=1,
               prog_write_valid=1, prog_write_word=0xBADC0D)
    await step(load_active=0, prog_write_valid=0, fetch_req_valid=1)
    await step(running=1)
    await step(prog_rst_n=0, running=0)
    await step(prog_rst_n=1, fetch_req_valid=1, fetch_pc=127)

    replacement = 0x654321
    await step(load_active=1, prog_write_valid=1, prog_write_word=replacement)
    await step(load_active=0, prog_write_word=0, image_valid=1, fetch_pc=0)
    await step(instruction(replacement), running=1, prog_write_valid=0)
    await step(fault, fetch_pc=1)
    await step(fault, fetch_pc=127)
    await step(instruction(replacement), fetch_pc=0)
    await step(prog_rst_n=0)
    await step(prog_rst_n=1, image_valid=0, running=0, word_count=0)
