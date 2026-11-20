# BLK-CORE — Shared issue core
- Status: draft
- Traces to: DEC-001, SPEC-PROG-001, SPEC-PROG-002, SPEC-PROG-003, REQ-PROTO-004

## Purpose

Run two contexts through one fetch/execute path. Each context owns its PC, registers, flags, return stack and pending operation. Protocol policy stays in the loaded program.

## Interface

| Signal group | Dir | Width | Meaning |
|---|---|---|---|
| `fetch_req`, `fetch_rsp` | Out, In | `valid` + 7-bit PC, `valid` + 24-bit instruction or fault | One outstanding fetch; retain its context tag locally |
| `start_cfg`, `run_ctl`, `run_status` | In, In, Out | Two 7-bit entry PCs, context enable bits and ownership masks; run/flush and status bits | Loader supplies committed configuration; the core reports halt/fault |
| `cycle` | In | `W` | Issue-cycle timebase |
| `drive_req/status`, `capture_req/status` | Out/In | See BLK-DRIVE and BLK-CAPTURE | Requests are owned by the issuing context |
| `payload` | In/Out | Draft `ready/valid` plus 16-bit word per direction and context tag | Buffered host data; waiting affects only the requesting context |

Draft schedule: a registered fetch slot followed by an execute slot. A taken branch adds a redirect slot in the current model; keep that cost for the first replay. The evaluated state size is eight 16-bit registers and two return addresses per context. Decode/ISA, scratch allocation, and address/stack fault rules need a G4 decision before RTL.

## Captured time

[DEC-003](../04_decisions/DEC-003-isa-timestamps.md) adds one 24-bit saved timestamp and a valid bit per context, separate from the general registers. When a capture consume explicitly requests a timestamp save, it copies that context's stored observation timestamp into the register. A consume without a save leaves the saved timestamp unchanged. Reset, start and global flush clear timestamp validity.

Timed drive and sample instructions can use `saved_timestamp + offset`, reduced modulo `2^24`, as an absolute deadline. An instruction that requests an invalid timestamp faults without issuing a timed request. Apply the BLK-TIMER half-range rule at admission. Instruction encodings, offset widths, long offsets and access to multiple saved times remain open.

Use round-robin selection between runnable contexts at a free issue boundary; waiting on capture, payload or output credit must not hold the shared path. Save the decoded request and its original operands (including any capture-derived absolute deadline) on first block. Retry as that context's next operation when eligible, without a second fetch or recomputing the deadline. A waiting output request becomes eligible to report an invalid deadline even if no queue space opens. Advance PC and write architectural state only on successful retirement. An invalid operation requests a global fault stop; it does not retire. On global fault, flush, or halt both contexts lose pending operations. A context's normal completion does not cancel its already accepted output updates; global stop is a separate action.

## Implementation options and budget

The draft `host_get` and `host_put` operate only on the issuing context's FIFOs. A blocked read retains its destination register. A blocked write retains the source word. On the successful handshake, retire the instruction and transfer one word. Do not advance the PC, change the destination, or modify a FIFO while blocked. The other context can issue. See [CHG-005](../changes/CHG-005-host-payload.md).

[DEC-004](../04_decisions/DEC-004-hybrid-pad-isa.md) selects compact `pad`/`pad2` and vector `drivev` for the [draft ISA](isa-draft.md). Decode either format into the same absolute deadline, mask, value and output enable request. Separate `shift_pin` and `shift_pair` keep all eight pin indices usable. Change the shift source register only when its request is admitted. On block, retain the decoded request and defer the register update. On reject, leave the register unchanged.

Compare saved requests with re-fetch/retry; re-fetch costs issue bandwidth and risks recomputing a relative deadline. Quantify runnable service bound, retries and actual deadline slack against EVAL-001's critical cases; round-robin is not a proof of schedulability. Planning allowance: 0.150 mm² of cell area; not measured for this block.

## Unit-test plan and RTL

With stubbed endpoints, check independent context state, branch cost, blocked issue, retry identity, no duplicate retirement, and fault handling. Planned file: `src/issue_core.v`.
