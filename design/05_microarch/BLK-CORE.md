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

Draft schedule: a registered fetch slot followed by an execute slot. A taken branch adds a redirect slot in the current model; keep that cost for the first replay. The evaluated state size is eight 16-bit registers and two return addresses per context. Decode/ISA, scratch allocation, and address/stack fault rules need a G4 decision before RTL. In particular, the proposed 24-bit timestamp does not fit one 16-bit register. Compare paired registers with a dedicated timestamp operand, including the issue cost of scheduling from a capture result.

Use round-robin selection between runnable contexts at a free issue boundary; waiting on capture, payload or output credit must not hold the shared path. Save the decoded request and its original operands (including the absolute deadline) on first block. Retry as that context's next operation when eligible, without a second fetch or recomputing the deadline. A waiting output request becomes eligible to report an invalid deadline even if no queue space opens. Advance PC and write architectural state only on successful retirement. An invalid operation requests a global fault stop; it does not retire. On global fault, flush, or halt both contexts lose pending operations. A context's normal completion does not cancel its already accepted output updates; global stop is a separate action.

## Implementation options and budget

Compare saved requests with re-fetch/retry; re-fetch costs issue bandwidth and risks recomputing a relative deadline. Quantify runnable service bound, retries and actual deadline slack against EVAL-001's critical cases; round-robin is not a proof of schedulability. Planning allowance: 0.150 mm² of cell area; not measured for this block.

## Unit-test plan and RTL

With stubbed endpoints, check independent context state, branch cost, blocked issue, retry identity, no duplicate retirement, and fault handling. Planned file: `src/issue_core.v`.
