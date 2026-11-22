# CHG-014 — Detect an expired drive retry on selection
- Status: proposed
- Size: medium
- Affects: BLK-CORE, BLK-DRIVE, TEST-UNIT-001, TEST-UNIT-003, TEST-INT-002

## Reason

[EVAL-022](../evals/EVAL-022-expired-retry.md) found that waiting an extra edge to reject a selected, expired retry can expose an older pad update. In the directed case, the update occurs on `D+1` with a registered retry but is suppressed by the same-cycle control. `D` is the original deadline of the expired request, not the deadline of the older update.

## Proposal for review

Use separate writeback from EVAL-021 and register the retry selection for valid retries. At a free issue boundary, keep the existing round-robin selection. If the context that wins has an expired drive retry, record the fault on that edge F instead of reserving a retry edge. Do not advance the PC, shift, transfer payload, enqueue a drive or arm capture. An already-admitted update due on F still retires. F+1 remains the global safe edge.

A blocked drive becomes runnable when its deadline expires, even with no queue credit. It does not preempt a context that wins selection. There is no guarantee of detection at the absolute deadline `D`. The queue still validates the original deadline at retry commit, since a request selected before `D` can expire before commit. It must not run late or recompute its deadline.

This schedule loses the last legal admission edge when credit first opens at `D−1`. The same-cycle control can admit on `D−1`. Both registered variants select on `D−1` and reject at commit on `D`. Approve the registered schedule only if this extra headroom is acceptable for software. If the last legal edge must remain usable, do not adopt this proposal as written.

The other option is to keep fault detection at registered retry commit for all retry types. That option keeps F+1 cleanup but permits the extra pad change observed in EVAL-022. An absolute deadline guarantee would need a different design and new evidence. Neither option changes the ISA encoding.

## After approval

Update the core record and sequence diagrams to distinguish selection, retry commit and F+1. Update the checks to cover an expired retry selected at `D`, arbitration where another context wins first, and a retry selected in the last legal cycle. Check the integrated host boundary and the routed design before sign-off. This proposal does not reapprove G4.
