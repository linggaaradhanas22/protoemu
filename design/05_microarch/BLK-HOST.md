# BLK-HOST — Loader and run control
- Status: draft
- Traces to: DEC-001, SPEC-HOST-001, SPEC-RST-001, SPEC-RST-002, SPEC-PROG-001

## Purpose

Accept an image and configuration from the RP2350 while halted. Publish completion separately from start, and buffer payload/status without putting the host in the pin timing loop.

## Interface

| Signal group | Dir | Width | Meaning |
|---|---|---|---|
| `host_link`, `selected` | In/Out, In | Transport TBD, 1 | Physical link via BLK-PADS; synchronized selection |
| `prog_write`, `image_state` | Out | See BLK-PROGRAM | Write complete words; own committed word count and validity |
| `start_cfg`, `run_ctl`, `run_status` | Out, Out, In | See BLK-CORE | Start both enabled contexts atomically; latch stop/fault status |
| `write_owner`, `pad_mode` | Out | Two `P`-bit masks, `P` bits | Committed output ownership and electrical modes, stable during a run |
| `payload` | In/Out | See BLK-CORE | Buffered ingress and egress; framing/depth TBD |
| `flush`, `safe` | Out | 1 each | Clear pending I/O and release protocol outputs on global stop/fault/reset |

Draft sequencing: reset/deselect disarms execution, invalidates the image and clears payload and timed work. `BEGIN` while halted clears validity before replacing any data. `COMMIT` succeeds only after exactly the declared 1–128 complete words arrive and enabled entry PCs and pin configuration validate, including disjoint write masks. A malformed frame or incomplete commit leaves the image invalid. While running, load commands have no effect; no start is accepted without a valid image. Starting uses the committed config and a clean execution/timed-I/O state. On the edge that samples `safe` and `flush`, no pad update takes effect and all timed work is discarded. For the first implementation, require a fresh load after a global stop/fault; the latency from deselect or fault detection to that safe edge is still open.

## Implementation options and budget

Compare dedicated nibble handshake versus a framed serial link. Check synchronization, acknowledgements, input stability and the 1 s load bound with an RP2350 driver model. Decide framing/integrity, result buffering and host pin allocation together. Planning allowance: 0.090 mm² of cell area; not measured for this block.

## Unit-test plan and RTL

Check complete vs short and malformed transactions, completion then start, write protection, warm reset, stop while work is pending and reload after selection is lost. Planned file: `src/host_loader.v`.
