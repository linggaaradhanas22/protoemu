# EVAL-025 — Place the agreed schedule at 60 MHz
- Status: done
- Traces to: BLK-CORE, BLK-DRIVE, BLK-CAPTURE, BLK-PADS, SPEC-PHY-001
- Compares: ARCH-B
- Model: `models/physical/full_core_probe.v`, `models/physical/full_core_host.v`

## Question

The G4 decisions keep the same-cycle retry contract. Earlier placements measured either a registered-retry variant or an older writeback path. Can the agreed schedule, with the faster separate writeback, reach 60 MHz after clock-tree synthesis and repair? Does a registered host boundary change the hold result?

## Variants

- `OPT=10`: same-cycle retry selection and fault edge, with the separate ALU, host and shift writeback path from EVAL-021. Fresh commands use fetch then execute. A retry commits on the same edge it is selected.
- `OPT=10` plus `full_core_host`: the same core, with the start, stop, image-valid, entry-PC, count, ownership, open-drain and enable inputs sampled into registers. This stands in for BLK-HOST's committed `start_cfg` and `run_ctl` flops and removes the synthetic input path from the core timing.

Both variants keep the agreed fault ordering: detection on F, safe on F+1, no late pad update, and the last legal admission edge remains usable.

## Method

Same PDK, corners and constraints as EVAL-021: 60 MHz, 0.25 ns clock uncertainty, placement-estimated parasitics. Placement, then clock-tree synthesis with the PDK buffer list and a propagated clock, then setup repair at 0.1 ns margin and hold repair at 0.08 ns margin. No routing or extraction.

The directed checks for `OPT=10` cover retry across wrap, a deadline that expires with no credit, the last legal admission edge, guarded waits, fault F/F+1 ordering, arithmetic writeback and a malformed host instruction with an available word. The protocol replay is the same 124-case Fast-mode I2C and UART/SPI matrix used in EVAL-020 to EVAL-023. The replay runs on the core, not on the host wrapper.

## Results

**Bare core, `OPT=10` same-cycle retry.** The placement started 3.212 ns short on the worst internal path. Clock-tree synthesis made hold worse, then repair recovered it. The repaired probe passes hold and misses slow setup by 0.023 ns.

| Stage | Slow setup | Slow internal setup | Fast hold | Fast internal hold | Cell area |
|---|---:|---:|---:|---:|---:|
| Placed | −3.212 ns | −3.212 ns | −0.201 ns | −0.054 ns | 385,839 µm² |
| After clock tree | −3.278 ns | −3.278 ns | −0.561 ns | −0.085 ns | 439,110 µm² |
| After setup and hold repair | −0.023 ns | −0.023 ns | +0.078 ns | +0.081 ns | 511,920 µm² |

The repaired critical path runs through the run-control cloud: a flop on the start and stop path to a flop on the payload-eligibility path. It is no longer the ALU writeback. Repair added about 126,000 µm² of cells, 33% above placement.

**Registered host boundary, `OPT=10` with `full_core_host`.** Registering the start, stop, entry-PC, count, ownership and enable inputs gives repair slightly more room.

| Stage | Slow setup | Slow internal setup | Fast hold | Fast internal hold | Cell area |
|---|---:|---:|---:|---:|---:|
| Placed | −4.201 ns | −4.201 ns | −0.208 ns | −0.055 ns | 389,256 µm² |
| After clock tree | −4.202 ns | −4.202 ns | −0.576 ns | −0.086 ns | 442,293 µm² |
| After setup and hold repair | +0.037 ns | +0.037 ns | +0.080 ns | +0.080 ns | 517,017 µm² |

The registered boundary is the better model of BLK-HOST driving committed configuration from flops. It also removes the earlier −0.014 ns overall-hold result that came from the synthetic `entry1` input. That earlier miss was a probe artifact. The internal hold miss between the pin synchronizer stages was real and repair fixes it in both variants.

## Conclusion

The agreed schedule is buildable at 60 MHz in this probe, but without useful margin. The two repaired results are −0.023 ns and +0.037 ns of setup, which is 23 to 37 ps. Routing, extraction and the real clock tree will consume more than that. Do not claim timing closure from this experiment.

The limiter is the run-control and payload-eligibility cloud, not the timed-I/O or writeback paths. For G5, optimize that cloud in RTL, then run the integrated, routed check. Registering `done` or the fault output would change host-visible timing and needs a change request, so it is not proposed here.

Use the registered host boundary in future probes. It matches the BLK-HOST contract and avoids synthetic input paths in the timing report.

## Limits

This is a core probe. It excludes the SPI loader, host FIFOs and the physical pad ring. Placement parasitics are estimates, and the repaired area is not a full-chip fit prediction. A pass here does not sign off routed timing.
