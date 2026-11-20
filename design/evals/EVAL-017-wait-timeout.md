# EVAL-017 — Timeout for input waits (I2C clock stretching)
- Status: planned
- Traces to: SPEC-I2C-003, BLK-CORE, BLK-CAPTURE, BLK-HOST
- Compares: host stop only, software polling, timed wait instruction, per-context watchdog
- Model: `models/benchmarks/g4_suite.py` (I2C programs), new probes as listed below

## Question

`wait_save`, `edge_save` and `edge_delta` wait without limit ([EVAL-016](EVAL-016-program-suite.md)). In I2C, the controller waits on SCL during clock stretching. A target that holds SCL low therefore stalls the controller context until the host sends `STOP`, which also stops the other context. Should the chip detect a stuck wait itself, and how, without breaking legitimate stretching?

No requirement asks for a timeout. SPEC-I2C-003 requires correct completion with stretches up to 10 µs. SMBus-style buses use a 25–35 ms clock-low timeout, which gives a reference scale (not a project requirement).

## Options

| ID | Option | How a stuck SCL is handled |
|---|---|---|
| A | Host stop only (today) | Host firmware times out and sends `STOP`. Both contexts stop; the image must be reloaded. |
| B | Software polling with today's ISA | Replace `wait_save SCL` with a loop: `cap` SCL every N cycles and count down. On zero, release the bus, report a status word and halt or retry. |
| C | Timed wait instruction | Give `wait_save` (6 spare bits) a timeout: for example, a latest-observation deadline from a register. On expiry, complete without a match and set a flag the program can branch on. |
| D | Per-context watchdog | A counter per context faults the context if one operation stays blocked longer than a configured limit. The CHG-008 fault path stops the chip and records the cause. |

## Method

1. **B, software polling.** Add a polling variant to the I2C programs in `g4_suite.py`. Sweep the poll interval (for example 4, 8, 16, 32 cycles). Replay all 28 EVAL-016 I2C cases plus stuck-SCL cases. Measure the SCL high-time and bit-period margins, which must still pass. Also measure program words, issue slots used while polling, and detection latency.
2. **C, timed wait.** Define the semantics in the model: deadline source, the result when it expires, interaction with the CHG-007 guard and the CHG-008 fault path. Replay the same cases. Check the encoding fits the spare bits. Map the extra capture-slot comparator and state to IHP cells, as in EVAL-013.
3. **D, watchdog.** Model a blocked-cycle counter per context with a host-set limit. Replay the same cases, including a legitimate 10 µs stretch next to a stuck one. Map one counter per context to IHP cells.
4. **A** needs no model. Record the host recovery time from the CHG-002 deadlines and its effect on the other context.

**Stuck cases:** SCL held low forever after the address byte; held for 10 µs (must pass); held for 30 ms (must time out with a 25 ms limit); held during a repeated START. Run each at 100 and 400 kHz, with the other context running SPI (overlap pin map) to check isolation.

**Criteria:**
- All existing I2C cases still pass.
- Legitimate stretches up to 10 µs are never cut off.
- Stuck SCL is detected within the configured limit.
- The other context is unaffected (B, C) or the stop is reported (D).
- Also compare: area, program words, issue bandwidth, ISA encoding impact, and the effort to specify and verify.

## Expected decision

A DEC or CHG, depending on the result. B needs no hardware change. C changes the ISA and BLK-CAPTURE. D changes BLK-CORE and the host configuration. A stays the fallback in every case.

## Results

Not run yet ([TASK-047](../tasks.md)).
