# CHG-010 — Payload FIFO same-edge rule and depth
- Status: done
- Size: medium
- Affects: BLK-HOST, BLK-CORE, TEST-UNIT-001, TEST-UNIT-007

## Reason

CHG-005 left simultaneous host and core access to one payload FIFO open. BLK-HOST used depth 8 as an unmeasured sizing trial. [EVAL-014](../evals/EVAL-014-payload-fifo.md) measured the area, the host drain rate and the demand of the specified tests.

## Proposed change

**Same-edge rule (registered status):**
- Each FIFO decides acceptance from its count before the edge. A push needs count < depth; a pop needs count > 0.
- A push and a pop on one edge both take effect when the queue is neither full nor empty.
- When full, a push waits even if a pop happens on the same edge. When empty, a pop waits even if a push happens on the same edge. There is no pass-through.
- Effects: `host_get` and `host_put` stall and retry as they do today. A host `WRITE` to a full ingress replies `FULL`, and a host `READ` from an empty egress replies `EMPTY`, without changing the queue.
- The host side touches a FIFO only on the edge that validates its request frame: one push or pop per frame.

**Depth:** 8 words of 16 bits for each context and direction (four queues), confirmed rather than provisional.

**Documented limit:** with the 250 kHz loader, the host drains about 2,100 words per second. Continuous UART receive is sustainable up to 19,200 baud. At depth 8, a receiver absorbs back-to-back bursts of 17 bytes at 38,400 baud, 13 at 57,600 and 10 at 115,200 when the host polls continuously. Programs must bound longer bursts. Standard-speed 1-Wire needs the host to poll during the ROM read, or the program to pack presence into a ROM word.

Item updates after approval:
- **BLK-HOST:** the rule, the confirmed depth, the drain rate and the burst limit. Remove "final depth and behavior on simultaneous host and core access remain open".
- **BLK-CORE:** `host_get`/`host_put` eligibility comes from the registered status. No same-cycle path from host frame decode to issue.
- **TEST-UNIT-007:** push and pop on one edge at full, empty and in between, from both sides; check order, count, and `FULL`/`EMPTY` replies.
- **TEST-UNIT-001:** a stalled `host_get` on an empty ingress that the host fills on the same edge retires on a later edge, once.
- **ISA draft:** update the payload gap row.

## Impact

No SPEC or REQ changes; SPEC-UART-002's six-frame test fits. The ready/valid signal meaning is fixed but its width is unchanged. Area: 45,197 µm² for four depth-8 queues (3.7 % of the tile, 50 % of BLK-HOST's allowance); bypass would add 1,185 µm². Timing is not measured. All blocks are draft, so nothing becomes `suspect`.

Rejected alternatives: bypass (larger, couples host decode to issue, and saves at most one cycle on a 468 µs transaction). Depth 6 (saves 10,039 µm², but no spare word for WS2812 or the UART test, and 8-byte bursts at 115,200 baud).

Open for Lingga, not part of this change: raise the burst limit with a faster loader clock (changes DEC-002) or a multi-word `READ` (changes BLK-HOST)? [EVAL-015](../evals/EVAL-015-host-rate.md) models both. A 1 MHz clock with 4-word transfers sustains 115,200 baud in both directions at depth 8.

## Approval

Lingga approved the same-edge rule and depth 8 on 2026-11-20. For the burst limit, Lingga chose the 1 MHz loader with four-word transfers ([CHG-011](CHG-011-loader-rate.md), [DEC-005](../04_decisions/DEC-005-loader-rate.md)).

## Close-out

Updated BLK-HOST, BLK-CORE, TEST-UNIT-001, TEST-UNIT-007, the ISA draft and the G4 review list. The documented burst limit in BLK-HOST uses the CHG-011 rates. Reviewed the items below them in `trace.md`; nothing stays `suspect`. Blocks remain draft and tests remain planned.
