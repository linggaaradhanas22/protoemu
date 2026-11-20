# EVAL-001 — Can each candidate meet the 60 MHz protocol benchmarks?
- Status: planned
- Traces to: SPEC-UART-001, SPEC-UART-002, SPEC-SPI-001, SPEC-I2C-001, SPEC-I2C-002, SPEC-I2C-003, SPEC-PROG-003, REQ-PROTO-004, REQ-FLEX-001
- Compares: ARCH-A, ARCH-B, ARCH-C
- Model: candidate cycle models and shared fixtures under `models/` (not yet implemented)

## Method

1. Build one independent peer/monitor set from [the seven profiles](../../models/benchmarks/README.md). Drive the same stimuli and apply the same checks to each model. Preserve sub-cycle input edge times for UART phase/tolerance cases. Test each monitor with a known-good trace and a deliberately bad trace before using it for scoring.
2. Model loads, instruction/event latency, finite storage and queues, input synchronization, and registered output changes. Use only the candidate instruction or configuration image to select a protocol. Track pin drive and output enable separately and judge I2C and 1-Wire at the resolved bus.
3. Start with 1 MHz SPI and stretched Fast-mode I2C, then run overlapping UART/SPI. These expose short scheduling deadlines, dependency on sampled feedback, and event contention. Run the rest of every profile before scoring. When a baseline fails, keep the trace and distinguish a model defect from an architectural limit.
4. Record pass/fail per case, worst timing margin in clocks and the edge that produced it, payload, image bytes, pin use and engine/lane/queue high-water marks. Save raw stimulus and pin traces under `design/evals/EVAL-001/`. Add the exact commands, fixture revision and model commit when the cases actually run.

## Decision use

A baseline UART, SPI or I2C failure excludes the evaluated design point unless a revised candidate reruns the same cases and passes. The concurrency and non-target profiles separate viable candidates on Should goals. These models do not verify silicon timing, board electrical behavior, or the protocol selected after RTL freeze.

## Results

Not run. No protocol or candidate has a score yet.
