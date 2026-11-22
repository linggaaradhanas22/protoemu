# CHG-014 — Detect an expired drive retry on selection
- Status: rejected
- Size: medium
- Affects: BLK-CORE, BLK-DRIVE, TEST-UNIT-001, TEST-UNIT-003, TEST-INT-002

## Reason

[EVAL-022](../evals/EVAL-022-expired-retry.md) found that a registered retry faults one edge later than the confirmed schedule. An older admitted pad update could therefore become visible before the pins go safe. It also found that a registered retry cannot use a slot freed on the last legal admission edge.

[EVAL-023](../evals/EVAL-023-retry-and-timeout-alternatives.md) tested two bypass designs that recover the last edge. Both lost several nanoseconds of slow-corner setup, because the bypass sits on the shared fetch path. Neither is a viable way to keep the current edge behavior.

## Recommendation: do not apply

Do not adopt this change. Keep the same-cycle retry schedule already described in [BLK-CORE](../05_microarch/BLK-CORE.md) and [BLK-DRIVE](../05_microarch/BLK-DRIVE.md). That schedule keeps the fault-detection and slot-reuse edges that the agreed contracts depend on.

The measured 60 MHz shortfall is in the fresh instruction execute and writeback path, not in retry admission. Fix it there, or in the fetch/execute organization, without changing when a retry request is admitted or faulted.

## What this change would have done

If Lingga had accepted the extra lead time:

- At a free issue boundary, keep round-robin selection. If the selected context has an expired drive retry, record the fault on that edge F. Do not advance the PC, shift, transfer payload, enqueue a drive or arm capture.
- An admitted update due on F would still retire, and F+1 would remain the global safe edge.
- A blocked drive would become runnable at its deadline. It would not preempt a context that wins selection.
- Software would need one extra cycle of queue credit before the deadline. A retry whose slot frees only on the last legal edge would fault.

The alternatives are recorded for history: registered commit detection (pattern 5) permits an extra pad change; the last-edge bypass (pattern 8) and full drive bypass (pattern 9) recover the edge but miss slow setup by 7 to 9 ns.

## Approval

Not approved. Closed as a rejected proposal for the current design. No record changes unless the retry schedule is revisited.
