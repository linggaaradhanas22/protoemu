# EVAL-001 — Can each candidate meet the 60 MHz protocol benchmarks?
- Status: done
- Traces to: SPEC-UART-001, SPEC-UART-002, SPEC-SPI-001, SPEC-I2C-001, SPEC-I2C-002, SPEC-I2C-003, SPEC-PROG-003, REQ-PROTO-004, REQ-FLEX-001
- Compares: ARCH-A, ARCH-B, ARCH-C
- Model: `models/benchmarks/run_compare.py` (exploratory) and `models/benchmarks/run_encoded.py` (encoded), with shared pin simulation and monitors

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

The broad sweep above uses abstract operations. The encoded reruns below apply to selected critical cases only. B keeps a capture result per waiting context; neither model represents arbitration in a hardware capture FIFO. C's encoded I2C uses direct sequencer pin and wait instructions rather than a lane. The models use logical pin names, not a chip pin allocation.

### Encoded rerun (TASK-013)

All **33 of 33** cases passed: each candidate ran four 1 MHz SPI modes, one UART/SPI overlap case and six Fast-mode I2C cases. The same I2C image ran with no stretching, with 1, 5 and 10 µs stretches, and with an address or data NACK. NACKs exercised the program's branch to STOP. SPI retained a one-clock half-period margin in the overlap test. The 10 µs stretch case retained a two-clock margin on the tightest unstretched SCL period.

| Candidate | 1 MHz SPI mode 0 | UART/SPI overlap | Fast-mode I2C | Peak resource use |
|---|---:|---:|---:|---|
| A | 72 B, 18 words | 140 B, 15 + 20 words in separate banks | 248 B, 62/64 words | Both engines ran in overlap |
| B | 54 B, 18 words | 105 B, 35 shared words | 186 B, 62/128 shared words | Output queue reached 3/4 entries in overlap and 4/4 in the 10 µs I2C case; overlap had two captures outstanding |
| C | 54 B, 14 code + 4 descriptor words | 111 B, 29 code + 8 descriptor words | 186 B, 62/64 code words | Both lanes ran in overlap, with 4/16 descriptor words loaded per lane |

The sizes count the actual loaded program and descriptor bytes, not padding, entry pointers, or a host transfer header. A packs each instruction into a 32-bit word, including the unused high byte. B and C use 24-bit words. The model fetches from the packed image at the program counter: one fetch slot and one execute slot per instruction, plus one extra slot on a taken branch. C spends four additional slots loading each lane descriptor. B and C share the slots between contexts; A has one issue path per engine. The model limits each context to eight 16-bit registers and a two-deep return stack.

**Decision input:** No candidate was ruled out by these critical reruns. A and C have only two code words free for this I2C image; additional transaction or diagnostic features could require a denser program or more storage. B has more code space, but a full output queue back-pressures the core. C uses fewer issue slots in overlap (141 versus 626 for A or B), yet uses six more loaded bytes than B once descriptors are counted. These are model findings, not mapped cost or timing. EVAL-002 must check whether the proposed datapaths, queues, and lane logic fit in the 8×4 tile budget and meet the 60 MHz target.

The encoded runs do not test Standard-mode I2C, standalone UART tolerance, the non-target profiles, host loading, or timestamp wrap. These are test images, not a released host format or a final ISA. The chip-level requirements remain unverified.

```bash
python3 -B -m unittest -v models.benchmarks.test_compare models.benchmarks.test_encoded
python3 -B -m models.benchmarks.run_encoded --out design/evals/EVAL-001/encoded
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-001/encoded/results.json
```

See the [per-case results](EVAL-001/encoded/results.json), [packed images](EVAL-001/encoded/images/), and [raw traces](EVAL-001/encoded/traces.jsonl.gz). All 12 model tests passed. Tests also reject oversized banks and alter the encoded SPI data to verify that it changes the observed pin payload.
