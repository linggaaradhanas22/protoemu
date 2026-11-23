# CHG-015 — Specify the external pin interface
- Status: done
- Size: medium
- Affects: SPEC-PIN-001, SPEC-PIN-002, SPEC-PIN-003, BLK-PADS, TEST-SYS-014

## Reason

The G2 spec leaves “Pins and electrical” empty. The requirements cover the Tiny Tapeout pin budget and board voltage. [BLK-PADS](../05_microarch/BLK-PADS.md#pin-allocation) holds the selected pin map and pad behavior. Board and software users should be able to find both in the external spec.

## Proposed change

Add these three entries to [the specification](../02_spec.md#pins-and-electrical) after approval. The wording collects existing decisions from [DEC-005](../04_decisions/DEC-005-loader-rate.md), [BLK-PADS](../05_microarch/BLK-PADS.md), and [CHG-008](CHG-008-stop-ordering.md). The example protocol wiring stays in BLK-PADS.

```markdown
### SPEC-PIN-001 — Fixed host pins
- Status: draft
- Traces to: REQ-RULE-003, REQ-FLEX-003
The chip shall use these dedicated pins for the RP2350 loader. No loader signal shall use a bidirectional `uio` pad.

| Signal | Tiny Tapeout pin | Direction at the chip |
|---|---|---|
| `CS` (active low) | `ui_in[0]` | Input |
| `SCK` | `ui_in[1]` | Input |
| `MOSI` | `ui_in[2]` | Input |
| `MISO` | `uo_out[3]` | Output |
| `READY` | `uo_out[4]` | Output |

The chip shall ignore unused dedicated inputs and drive unused dedicated outputs low. Check the mapping with an RP2350 host model in system simulation.

### SPEC-PIN-002 — Programmable protocol pads
- Status: draft
- Traces to: REQ-RULE-003, REQ-RULE-007, REQ-FLEX-001
The chip shall make all eight `uio` pads available to loaded programs. Pad indices 0 through 7 shall map to `uio[0]` through `uio[7]`. Programs may sample any pad. The loaded configuration assigns output ownership to at most one context per pad and selects push-pull or open-drain drive for each owned pad. Those settings shall not change during a run.

A push-pull output shall drive low or high when enabled, and release when disabled. An open-drain output shall drive low only for an enabled low request. In all other cases it shall release the pad, never drive high. Check pad selection, drive values, and enables in system simulation. Check external pull-ups and 3.3 V board connections separately under `TEST-ACC-004`.

### SPEC-PIN-003 — Protocol pad release and hold
- Status: draft
- Traces to: REQ-RULE-005, REQ-RULE-006, REQ-FLEX-003
The chip shall release all eight protocol pads with `uio_oe = 0` on the following edges:

| Event | `clk` edge that releases the pads |
|---|---|
| Reset | First edge that samples `rst_n` low |
| Deselect while still clocked | First edge that samples synchronized `ena` low |
| Valid `STOP` request | First edge after the loader validates the frame close |
| Core fault | First edge after fault detection |

Release shall override a pad update due on the same edge. An update due on the fault-detection edge shall take effect unless another event releases the pads on that edge. On normal completion (`DONE`), the chip shall hold its last programmed pad values and enables until `STOP`, reset, or deselect. Check release edges and `DONE` hold in system simulation.
```

Add one system test to [the verification plan](../06_verif_plan.md#system-tests). Keep `TEST-ACC-003` for template port compliance and `TEST-ACC-004` for board wiring and electrical checks.

```markdown
### TEST-SYS-014 — External pin interface
- Status: planned
- Level: system
- Verifies: SPEC-PIN-001, SPEC-PIN-002, SPEC-PIN-003
- Run: test_external_pin_interface
Load and start over the specified dedicated pins. Check that the reply uses the specified `MISO` and `READY` pins. Check that loader traffic before `START` does not drive any `uio` pad. Toggle the unused dedicated inputs and check that they do not affect the run. Check that unused dedicated outputs stay low.

Load images that move the same sample-and-drive sequence across all eight pads. Check input sampling without output ownership. Check push-pull low, high and release, and open-drain low and release. Attempt a write without output ownership. Check that it does not drive the pad. Monitor the pin values and output enables.

Repeat with a pad update due on each release edge. Check that reset, synchronized deselect, `STOP`, and fault release override that update. For a fault on edge F, check an update on F and release on F + 1. Separately check that all pad values and enables hold after `DONE` until `STOP`. Compare the protocol pad trace with the reference model cycle by cycle.
```

## Impact

No requirements, pin assignments, RTL, or timing rules change. No area or timing impact is expected. After approval, add the SPECs and the planned system test. Add the new SPEC trace links to BLK-PADS and recheck the linked items, including the pad unit test and pad-boundary integration tests.

## Approval

Lingga approved adding the three pin specs and the planned system test to the baseline on 2026-11-23.

## Close-out

Added the approved pin specs and the planned system test. Linked all three specs from BLK-PADS. Rechecked TEST-INT-001 for the pin map and pad updates, TEST-INT-002 for the release edges, and TEST-UNIT-006 for drive modes and release priority. These test plans still match the pad contract and remain planned. No pin assignments, RTL, or timing rules changed.
