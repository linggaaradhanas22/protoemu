# EVAL-017 — Timeout for input waits (I2C clock stretching)
- Status: done
- Traces to: SPEC-I2C-003, BLK-CORE, BLK-CAPTURE, BLK-HOST
- Compares: host stop only, software polling, timed wait instruction, per-context watchdog
- Model: `models/benchmarks/g4_timeout.py`, `models/physical/wait_timeout_probe.v`, `models/physical/watchdog_probe.v`

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

## What was run

- **Programs.** EVAL-016's I2C controller, with the status in R5 (0 OK, 1 NACK, 2 timeout) and a timeout path that releases both lines and reports. B replaces the SCL wait with a poll loop whose first poll lands where `wait_save` would observe the rise. C uses a prototype `wait_to pin, level, offset, Rt`: a level wait that expires `Rt × 64` cycles after its target and then sets `Rt` to 0. A and D keep the plain `wait_save`.
- **Regression:** the 14 I2C cases from EVAL-016 (7 at each rate), with the watchdog or timeout armed. A uses the unchanged program, already covered by EVAL-016.
- **Stuck bus:** I2C in context 0 and six SPI exchanges in context 1, spread over 1.5 × the limit. Per rate: SCL held forever at clock 10, held forever at clock 28 (repeated-START setup), held for 2 × the limit at clock 10, and a legitimate 10 µs hold at clock 28. The limit is 1 ms (60,000 cycles), plus one run per option with a 25 ms limit and a 30 ms hold.
- **Host stop (A):** the host stops the chip if the I2C result is missing at the limit. `STOP` at 1 MHz reaches its safe edge 2,643 cycles (44 µs) later.
- **Area:** the two wait slots without a timeout, with a guarded timeout (C1: the slot stores the timeout and reloads its deadline when the guard opens), and with an unguarded timeout (C2: the core computes the expiry with its deadline adder, and the slot reuses its deadline compare). Also the two-context watchdog with a shared ×64 prescaler. Each probe mode passed a directed testbench, and a seeded expiry bug was detected.

## Results

| Option | I2C regression | Stuck-bus cases (1 ms) | Detection vs limit (cycles) | Other context during a stuck bus | 25 ms run | Program (words) | Area |
|---|---:|---:|---|---|---|---:|---|
| A host stop | – (unchanged) | 8 / 8 | +2,643 | Stopped, 4–5 of 6 exchanges done | Pass | 76–77 | None |
| B poll every 16 | 13 / 14 | 1 / 8 | – | Stopped by a fault | Not possible: 93,750 polls exceed the 16-bit loop counter | 82–83 | None |
| B poll every 32 | 11 / 14 | 7 / 8 | −11 | Complete, except one SPI deadline miss | Pass | 82–83 | None |
| B poll every 64 | 10 / 14 | 7 / 8 | −75 | Complete, except one SPI deadline miss | Pass | 82–83 | None |
| **C timed wait** | **14 / 14** | **8 / 8** | **−18** | **Complete in every case** | **Pass** | **79–80** | **C1 +5,479 µm²; C2 below synthesis noise** |
| D watchdog | 14 / 14 | 8 / 8 | −288 to −72 | Stopped, 4–5 of 6 exchanges done | Pass | 76–77 | +6,753 µm² |

Negative numbers mean slightly before the limit: C counts in 64-cycle units, B in poll intervals, and D from the context's last issue.

**Why B fails.**
- Polling every 16 cycles is faster than the poll loop can issue once SPI shares the core, so a poll deadline passes and the chip faults.
- Polling every 32 or 64 cycles observes a stretched rise up to one interval late. That lengthens the next SCL clock past the bit-period window (161 to 193 clocks against 150–157 in Fast-mode, 633 to 653 against 600–631 in Standard-mode).
- The poll loop also used enough issue slots to make the SPI context miss a deadline during a legitimate 10 µs stretch in Standard-mode.

**C1 vs C2.** Storing a timeout and reloading the deadline costs 5,479 µm² for two slots, mostly the 24-bit adders. C2 adds two flops per slot (timed and expired flags). Its mapped area moved by less than synthesis noise (−187 µm²; the baseline itself moved about 20 µm² when only comments changed). The core's deadline adder needs one more operand (`Rt × 64`), which is not measured. C2 has no earliest-observation guard. That doesn't matter for I2C, where the chip holds SCL low until the release.

All 87 Python model checks passed (5 new). EVAL-006, EVAL-009 to EVAL-012 and EVAL-016 regenerate byte-identical results.

## Conclusion

Recommend **C2, an unguarded timed wait**. It is the only option that detects a stuck bus without stopping the other context and keeps all I2C timing. Its hardware cost is a slot mode bit plus an adder operand in the core. [CHG-013](../changes/CHG-013-timed-wait.md) proposes it. A host `STOP` (A) stays the fallback for everything else. B is not usable with another context running, and D stops the whole chip, like A, for 6,753 µm².

## Limits

- The C model expires `Rt × 64` cycles after the guard target. C2 computes the same expiry from the program timebase, so I2C behaves identically, but C2 itself is only probed for area.
- Typical-corner area after synthesis; no timing. The core adder operand and decode are not included.
- One stuck pattern per position; no SDA-stuck recovery (nine clocks) is modeled.
- No production RTL, agreed record or registered test changed.

## Reproduce

```bash
source scripts/env.sh
git log -1 --diff-filter=A --format=%H -- design/evals/EVAL-017/results.json
python3 -B -m models.benchmarks.g4_timeout --out design/evals/EVAL-017/results.json
python3 -B -m models.physical.run_timeout_probe \
  --pdk "$PDK_ROOT/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l" \
  --out design/evals/EVAL-017/area.json
python3 -B -m unittest models.benchmarks.test_g4_timeout
```

The sweep takes about 50 s.
