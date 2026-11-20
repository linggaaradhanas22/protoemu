# EVAL-009 — Replay generic host payload instructions
- Status: done
- Traces to: BLK-CORE, BLK-HOST, SPEC-HOST-001, SPEC-PROG-002, REQ-PROTO-004
- Model: `models/benchmarks/g4_payload.py`

## Method

Add two candidate instructions to the 24-bit model. `host_get Rd` pops one 16-bit word from the issuing context's ingress FIFO and writes `Rd`. `host_put Rs` copies one 16-bit word into that context's egress FIFO. The context comes from the scheduler, not from an instruction field. Empty ingress or full egress blocks only the issuer. The core retains the decoded operation and retries without refetching. No FIFO or register changes until the operation retires.

Remove the fixture `report` opcode from this decoder. Replace the overlap program's fixed SPI transmit load with `host_get`. Replace its reports with `host_put`. The UART program uses bit 8 on an error word to distinguish it from a received byte. This is a choice in the example program, not a hardware status field.

Use the existing loader model to load, commit and start the image. Preload two SPI words with host `WRITE`. Run the UART and SPI peers without host service during the transfer. Drain both contexts with host `READ` after the run. Adapt those drained words for the existing peer checks. The monitors still check the external pin traces independently of the program.

## Results

| Measure | Result |
|---|---|
| Concurrent UART/SPI cases | 96/96 passed: 48 from zero and 48 starting 500 cycles before 24-bit wrap |
| Program size | 37 of 128 words, one more than EVAL-007's compact overlap image |
| Minimum time from drive admission to deadline | 13 cycles, unchanged from EVAL-007 |
| Minimum time from sample arm to deadline | 48 cycles |
| Payload per run | Two SPI input words consumed. Two SPI results and three UART bytes returned in context order. |

Each group sweeps 16 UART start phases and three SPI start offsets. With depth-one FIFOs in a directed test, context 0 stalls first on an empty ingress and then on a full egress. Context 1 completes its own exchange before context 0 receives input. Context 0 resumes after each host action and transfers exactly one word in each direction without refetch. A separate check supplies a different SPI transmit word and confirms that the pin monitor detects the change from its expected data. All 41 Python model checks passed.

## Limits and recommendation

Carry the blocking, context-local pair into ISA review. Software must preload enough input and leave room for results before deadline-sensitive work. This probe reuses the exploratory SPI transport and loader. In the directed retry test, completed host commands arrive at chosen model cycles. This does not settle hardware arbitration for simultaneous host and core access, final FIFO depth, reset and flush behavior, or RTL timing. No production RTL, firmware or registered verification tests changed.

## Reproduce

```bash
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-009/results.json
python3 -B -m models.benchmarks.g4_payload --out design/evals/EVAL-009/results.json
python3 -B -m unittest models.benchmarks.test_g4_payload models.benchmarks.test_g4_pad_encoding models.benchmarks.test_g4_isa models.benchmarks.test_g4_timestamp models.benchmarks.test_g4_loader models.benchmarks.test_g4_timing models.benchmarks.test_compare models.benchmarks.test_encoded
```

The Git command identifies the probe revision for the [per-case results](EVAL-009/results.json).
