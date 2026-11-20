# 02 — Specification

Requirements turned into **exact, testable statements**. Stage G2.

**How to write a SPEC**
- One measurable statement per item, using "shall" and numbers with units
  (e.g. "within ±1.0 %", "at 100 kHz and 400 kHz", "≤ 2 clock cycles").
- `- Traces to:` at least one REQ.
- Say how it will be checked (simulation, formal, measurement, review) in the text.
- Every SPEC needs at least one TEST in `06_verif_plan.md` that verifies it (checked at gate G2).
- A SPEC describes behaviour seen from outside the chip (pins, host, timing), not the design.
  Design choices come later (ARCH/DEC/BLK).

Example (inside a code fence, so the checker ignores it):

```markdown
### SPEC-UART-001 — UART TX bit timing
- Status: draft
- Traces to: REQ-PROTO-001, REQ-RULE-004
The TX bit period shall be within ±1.0 % of nominal for 9600, 19200, 38400, 57600 and 115200
baud with a 60 MHz clock. Checked by system simulation: measure edge times on the TX pin.
```

---

## Pins and electrical
<!-- SPEC-PIN-NNN -->

## Clock, reset and power-down
<!-- SPEC-RST-NNN -->

### SPEC-RST-001 — Reset convergence
- Status: draft
- Traces to: REQ-RULE-005
With a 60 MHz clock, the chip shall reach a deterministic reset state by the fourth rising edge of `clk` with `rst_n` held low.
The state before reset shall not affect pin behavior or host responses after reset under the same inputs.
Check reset convergence in system simulation and prove independence from initial state with formal analysis.

### SPEC-RST-002 — Reload after reselection
- Status: draft
- Traces to: REQ-RULE-006
After reselection, the chip shall accept and run a new program through the documented host loader without relying on any state from before deselection.
Check in system simulation at 60 MHz. Model the loss of state by starting a fresh DUT before the second load.
The host transfer format and timing limits belong to TASK-007.

## Host interface and program loading
<!-- SPEC-HOST-NNN -->

## Programmability
<!-- SPEC-PROG-NNN -->

## Protocols
<!-- SPEC-UART-NNN, SPEC-SPI-NNN, SPEC-I2C-NNN, ... -->

These drafts define the baseline at a 60 MHz chip clock. Baseline SPI and I2C tests use the chip as controller. Target roles and concurrent protocols remain separate `Should` requirements.

### SPEC-UART-001 — UART transmit timing
- Status: draft
- Traces to: REQ-PROTO-001
The UART TX example shall send 8N1 frames (8 data bits, no parity, 1 stop bit) at 9600, 19200, 38400, 57600, and 115200 baud.
The line shall idle high. Each frame shall start low, send the least significant bit first, and end with a high stop bit.
The duration of each transmitted bit shall be within ±1% of the nominal bit period. Check frame contents and edge timing in system simulation.

### SPEC-UART-002 — UART receive tolerance
- Status: draft
- Traces to: REQ-PROTO-001
The UART RX example shall receive consecutive 8N1 frames without extra idle bits at each rate in `SPEC-UART-001`.
It shall deliver every byte once and in order for any start-edge phase relative to `clk` and peer baud error within ±2% of nominal.
Check in system simulation. The rate list and error limits are proposed project targets.

### SPEC-SPI-001 — SPI controller modes and clock rate
- Status: draft
- Traces to: REQ-PROTO-002
The SPI example shall exchange MSB-first bytes on MOSI and MISO at 100 kHz and 1 MHz in modes 0 through 3. These are proposed project rates.
For modes 0 and 1, SCLK shall idle low. For modes 2 and 3, SCLK shall idle high.
The receiver shall sample on the first edge of each clock cycle in modes 0 and 2, and on the second edge in modes 1 and 3.
Each active SCLK half-period within the transfer shall be within one `clk` period of its nominal duration: 5 µs at 100 kHz or 0.5 µs at 1 MHz.
Active-low chip select shall stay low across a two-byte transaction with exactly 16 sampling edges. Check both directions and pin timing in system simulation.

### SPEC-I2C-001 — I2C clock and bus timing
- Status: draft
- Traces to: REQ-PROTO-003
The I2C example shall generate Standard-mode and Fast-mode timing as the sole bus controller. The chip shall drive SDA and SCL low or release them to the external pull-ups. It shall not drive either line high.
With no stretching and ideal pull-ups in system simulation, apply the following limits to the resolved bus signals:

| Quantity | Standard-mode | Fast-mode |
|---|---:|---:|
| Unstretched SCL bit rate | 95–100 kHz | 380–400 kHz |
| SCL low time, minimum | 4.7 µs | 1.3 µs |
| SCL high time, minimum | 4.0 µs | 0.6 µs |
| SDA data setup time, minimum | 250 ns | 100 ns |
| START and repeated START hold time, minimum | 4.0 µs | 0.6 µs |
| Repeated START setup time, minimum | 4.7 µs | 0.6 µs |
| STOP setup time, minimum | 4.0 µs | 0.6 µs |
| Bus free time from STOP to next START, minimum | 4.7 µs | 1.3 µs |

Source: [NXP UM10204, I2C-bus specification and user manual](https://www.nxp.com/docs/en/user-guide/UM10204.pdf), Table 11 for Standard-mode and Fast-mode. The lower bounds on bit rate are project targets. Check board rise and fall times separately against the same source before claiming electrical conformance.

### SPEC-I2C-002 — I2C transfers and ACK/NACK
- Status: draft
- Traces to: REQ-PROTO-003
At both rates, the I2C example shall perform 7-bit addressed writes and reads, including a write followed by a read with a repeated START and no intervening STOP.
The controller shall test the target's ACK/NACK on the ninth clock after each address or written byte. On NACK it shall end the transaction with STOP and report failure without sending another byte.
The controller shall ACK nonfinal read bytes and NACK the last byte before STOP. Check pin activity and results in system simulation.

### SPEC-I2C-003 — I2C target clock stretching
- Status: draft
- Traces to: REQ-PROTO-003
At both rates, the I2C controller shall wait for the observed SCL line to rise when the target holds it low.
It shall complete the transaction correctly for a stretch of up to 10 µs after the controller releases SCL. The 10 µs verification limit is a proposed project target.
Stretching shall extend only the low phase. After SCL rises, the high phase shall still meet the minimum in `SPEC-I2C-001`. Check with a stretching target model in system simulation.

## Area and timing
<!-- SPEC-PHY-NNN -->

### SPEC-PHY-001 — Timing at 60 MHz
- Status: draft
- Traces to: REQ-RULE-004
At the board clock of 60 MHz, the routed design shall meet setup and hold timing at every corner required by the shuttle flow.
Check `project.clock_hz` in `info.yaml` and run static timing analysis on the routed design.
The `clk` constraint shall use a period no longer than 50/3 ns.

## Deliverables
<!-- SPEC-DEL-NNN -->
