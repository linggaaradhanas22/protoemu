# EVAL-001 — Can each candidate meet the 60 MHz protocol benchmarks?
- Status: running
- Traces to: SPEC-UART-001, SPEC-UART-002, SPEC-SPI-001, SPEC-I2C-001, SPEC-I2C-002, SPEC-I2C-003, SPEC-PROG-003, REQ-PROTO-004, REQ-FLEX-001
- Compares: ARCH-A, ARCH-B, ARCH-C
- Model: `models/benchmarks/cycle.py`, `models/benchmarks/run_compare.py` and their peer/monitor modules

## Method

1. Build one independent peer/monitor set from [the seven profiles](../../models/benchmarks/README.md). Drive the same stimuli and apply the same checks to each model. Preserve sub-cycle input edge times for UART phase/tolerance cases. Test each monitor with a known-good trace and a deliberately bad trace before using it for scoring.
2. Model loads, instruction/event latency, finite storage and queues, input synchronization, and registered output changes. Use only the candidate instruction or configuration image to select a protocol. Track pin drive and output enable separately and judge I2C and 1-Wire at the resolved bus.
3. Start with 1 MHz SPI and stretched Fast-mode I2C, then run overlapping UART/SPI. These expose short scheduling deadlines, dependency on sampled feedback, and event contention. Run the rest of every profile before scoring. When a baseline fails, keep the trace and distinguish a model defect from an architectural limit.
4. Record pass/fail per case, worst timing margin in clocks and the edge that produced it, payload, image bytes, pin use and engine/lane/queue high-water marks. Save raw stimulus and pin traces under `design/evals/EVAL-001/`. Add the exact commands, fixture revision and model commit when the cases actually run.

## Decision use

A baseline UART, SPI or I2C failure excludes the evaluated design point unless a revised candidate reruns the same cases and passes. The concurrency and non-target profiles separate viable candidates on Should goals. These models do not verify silicon timing, board electrical behavior, or the protocol selected after RTL freeze.

## Results

The exploratory run passed **754 of 754 cases per candidate** (2,262 total). Each candidate ran 8 SPI cases, 14 I2C cases, 1 concurrent UART/SPI case, 5 UART TX cases, 720 UART RX cases, and 6 non-target cases. The UART RX sweep used 9 peer baud errors and 16 start phases at each nominal baud. It is a finite sweep, not a proof for every phase.

| Candidate | UART/SPI overlap | 10 µs stretched Fast-mode I2C | Observed resource use in overlap |
|---|---|---|---|
| A | Pass; SPI half-period margin 1 clock | Pass; worst margin 2 clocks on an unstretched SCL bit period | 33 UART and 104 SPI issue operations on separate engines |
| B | Pass; SPI half-period margin 1 clock | Pass; worst margin 2 clocks on an unstretched SCL bit period | 137 issue operations on one core; output queue reached its four-entry limit; two captures outstanding |
| C | Pass; SPI half-period margin 1 clock | Pass; worst margin 2 clocks on an unstretched SCL bit period | 19 sequencer issue operations; both lanes active |

C handles the repetitive SPI and UART work in its lanes, which reduces sequencer issue count in this model. It did not use a lane for I2C: all three candidates issued 283 abstract operations in the longest Fast-mode stretch case. B back-pressured when its queue filled and still met the selected deadlines. The tested overlap does not establish headroom for a busier workload. An issue count is a runtime work count, not program size.

### Reproduce

Run from the repository root with Python 3.11 or newer:

```bash
python3 -B -m unittest -v models.benchmarks.test_compare
python3 -B -m models.benchmarks.run_compare --out design/evals/EVAL-001
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-001/results.jsonl.gz
```

The last command identifies the saved run's fixture and model revision. The [per-case results](EVAL-001/results.jsonl.gz) and [pin traces](EVAL-001/traces.jsonl.gz) are gzip-compressed JSON Lines. Fractional clocks are exact `numerator/denominator` strings. Traces include the raw DUT and peer drives, resolved edges, sample cycles, and output reports. The eight model sanity tests passed, including injected timing or data faults and a comparison of idle skipping against cycle-by-cycle execution.

### Limits and next evidence

These are pin-level scheduling models driven by decoded Python operations. They model two-flop input synchronization and registered outputs, but not binary encoding, program-bank limits, branch or instruction fetch latency, counter wrap, the host loader, or mapped timing. B's capture slots keep a result per waiting context; they do not model arbitration in a hardware capture FIFO. C assumes its sequencer can schedule pin and wait operations directly for I2C and 1-Wire. Neither assumption has been checked against a concrete encoding or circuit. The model uses logical pin names, not a chip pin allocation.

The exploratory protocol checks did not rule out a candidate. Keep this evaluation open until representative images have been encoded and rerun with their real storage and latency limits. Use EVAL-002 to compare mapped area and critical paths against the 8×4 and 60 MHz constraints. Do not treat these results as RTL verification or select an architecture from them alone.
