# BLK-PADS — Tiny Tapeout pad adapter
- Status: draft
- Traces to: DEC-001, REQ-RULE-003, REQ-RULE-007, REQ-PROTO-004, SPEC-RST-001, SPEC-I2C-001

## Purpose

Synchronize external inputs and drive protocol pads from registers. Map logical protocol pins and host signals onto the Tiny Tapeout ports. This block includes the wrapper boundary; it does not interpret host commands.

## Interface

| Signal group | Dir | Width | Meaning |
|---|---|---|---|
| Tiny Tapeout ports | In/Out | 8 each for `ui_in`, `uo_out`, `uio_in`, `uio_out`, `uio_oe`; `clk`, `rst_n`, `ena` are single bits | Standard digital boundary |
| `pad_update`, `pad_mode` | In | `P` bits each for mask/value/OE, `P` open-drain mode bits | Draft `P=8`; apply only on a 60 MHz clock edge |
| `pin_sample`, `selected` | Out | `P`, 1 | Second-stage protocol samples and synchronized selection |
| `host_link` | In/Out | TBD | Synchronized inbound signals and registered outbound signals |
| `safe` | In | 1 | Force protocol output enables and drive values to zero at the sampling edge |

Use two flop stages on external inputs used by the design other than clock and reset. Capture reads the second stage. In push-pull mode a masked update sets drive value and OE; in open-drain mode `uio_out` stays zero and an update requesting high releases the pad. Reset and `safe` override a coincident pad update. Host status can report a fault after the protocol pads go safe; reset still clears both. Non-driven pins need an external pull-up or pull-down wherever the board connection requires a defined idle level.

## Implementation options and budget

Start with fixed host pins and eight programmable bidirectional protocol pins. Check the proposed split against load signaling and the five-pin concurrent case before freezing the map. Check the first-stage input hold path after CTS and routing. Planning allowance: 0.040 mm² of cell area; not measured for this block.

## Unit-test plan and RTL

Check synchronizer depth, registered outputs, open drain, independent mask bits, and reset/stop precedence. Planned file: Tiny Tapeout wrapper in `src/`, with a separate pad module only if useful.
