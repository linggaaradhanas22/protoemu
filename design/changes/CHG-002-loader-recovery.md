# CHG-002 — Define SPI loader recovery
- Status: proposed
- Size: medium
- Affects: BLK-HOST, BLK-PADS, TEST-UNIT-007, TEST-INT-002, TEST-SYS-010

## Reason

A missing or invalid reply does not tell the RP2350 whether the ASIC executed a command. A second payload write could enqueue the same word twice. A lost `START` reply could leave protocol traffic running. This proposal keeps the approved SPI wiring and frame format.

## Proposed change

**Recommendation:** Reset and reload after an uncertain transfer. Do not add automatic replay, transaction IDs, or an ASIC watchdog in this revision. A replay cache could preserve a running program, but it adds state and needs separate evidence for duplicate handling and reset.

### ASIC behavior

| Event | Proposed response |
|---|---|
| Request ends early, has extra bits, has bad length, or fails CRC | Reject on synchronized `CS` rising and queue a framed error reply. Do not execute the command. If halted, invalidate the image and abandon the load. Tentative writes to the halted program store can remain, but no fetch can read them. A malformed request does not stop an already running program. |
| Request stops clocking while `CS` stays low | Do not execute a command or queue a reply. Keep counters bounded and wait for `CS` to rise or for reset. Only tentative halted `DATA` writes can occur before the frame closes. |
| Reply ends early or has extra bits | Keep `READY` asserted and retain the same reply. A new reply frame starts at its first bit. Ignore MOSI during a reply frame. Do not execute the original command twice. |
| Reply ends at its exact bit count | Clear `READY` on synchronized `CS` rising. The ASIC cannot tell whether the RP2350 sampled the reply correctly. It does not retain consumed replies for replay. |
| Reset or synchronized deselect | Discard the active frame and pending reply. Invalidate the image and clear execution, payload, and timed work. On resumption, observe synchronized `CS` high before accepting a new falling edge. Do not treat the rest of an old frame as a request. |

For an exact request, check the complete bit count, length and CRC at frame close before executing its command. Keep the existing `STOP` contract: the protocol pads go safe on the edge after the validated frame closes.

### RP2350 behavior

| Host deadline, provisional | Start of measurement | Deadline |
|---|---|---:|
| Request frame | Host asserts `CS` for a request | 20 ms to finish transfer and release `CS` |
| Reply ready | Host releases `CS` after its request | 5 ms to observe `READY` high |
| Reply frame | Host asserts `CS` to read the reply | 20 ms to finish transfer and release `CS` |

Use an elapsed-time check that still runs if SPI stops transferring. The largest request is 389 bytes, which takes 12.448 ms at 250 kHz before the two 2 µs guards. The 5 ms `READY` limit allows for firmware polling. Confirm both margins on the board. The 1 s load requirement still applies to the full load, including its replies. These per-phase limits do not restart that clock.

Keep `CS` low across the reply header, body and CRC. Read the header first. Read only the body length allowed for that command, up to two bytes for the current reply set. A reply is successful only after its length, CRC and expected status have all passed. A valid error status is not a transfer failure. Acknowledge it to the caller without resending the command. Keep normal `FULL` and `EMPTY` handling for payload flow control.

If a deadline expires, the reply is malformed, or the outcome is uncertain:

1. Abort the SPI transfer. Set `CS` high and leave SCK low.
2. Report the interrupted operation as failed with unknown outcome. Do not resend it automatically.
3. With the ASIC clock running, assert `rst_n` low for at least four rising clock edges. Keep `CS` high during reset and for at least 2 µs after release so the ASIC can sample idle `CS`.
4. Require `READY` low before sending a fresh `BEGIN`. If `READY` remains high after 5 ms, stop and report recovery failure.
5. Reload and commit before issuing another explicit `START`. Do not automatically restart protocol traffic. Reset cannot undo external actions that already occurred.

This is not a hardware fail-safe for a stopped ASIC clock or an RP2350 that never issues reset. If the clock cannot run, report recovery failure rather than treating inactive `READY` as proof of reset.

## Proposed checks

| Test plan | Add these cases |
|---|---|
| `TEST-UNIT-007` | End requests one bit and one byte early, and one bit late. Leave `CS` low with SCK stopped. Check command side effects and fetch gating. Interrupt a reply for a destructive payload read, then check its bit-zero restart and confirm that exactly one word was removed. Reset with a reply or partial frame pending. Check that the next request needs a fresh `CS` falling edge. |
| `TEST-INT-002` | Lose a valid `START` reply after execution and corrupt a valid payload-write reply. Confirm that the RP2350 does not repeat either command. Assert reset while a pad update is due. Check safe outputs, cleared work and successful reload. |
| `TEST-SYS-010` | Force each host timeout. Check that the driver aborts without automatic replay, reports failure if it cannot recover, and can load again after a qualified reset. Measure normal load time on the documented driver path. |

## Impact and approval

This proposal changes the recovery contract, not the pin map, architecture or requirements. It needs Lingga's approval before the block drafts and test plans adopt it. Measure real polling and abort behavior before locking the timeout values. No recovery model, RTL or firmware tests ran for this proposal.
