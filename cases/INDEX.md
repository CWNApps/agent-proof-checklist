# Case pack index, pack 0.1.0 (profile agent-proof-checklist/0.1)

Every case is a small edit of 1 baseline filing. Each `expected.json` was written by hand by the author before the
checker ran on the case (design 9.3), then compared with the checker and with a blind second derivation; the
differences and how they were settled are in `DERIVATION_LOG.md`. A wrong answer found after freeze is fixed by a new
pack version listed here, never by a silent edit (design 9.4).

## Baseline (`base-baseline`)

A purchase of 1 item `sku1` for 50.00 USD at `shopA`, disputed by the merchant. The case binding is the network
transaction id `ntid-1`. All times are 2026-11-01 UTC unless shown; `filed_at` is 2026-11-03T12:00:00Z.

| Record | Kind | Maker (party_role / signer) | Bound | Key values |
| --- | --- | --- | --- | --- |
| `auth-1` | authorization | psp / psp | directly, `ntid-1` | 10:05:30, charge `ch-1` 50.00 USD at shopA; `link_tokens` agentkey-9, mandate-m1, req-7, log-3, order-9, status-m1 |
| `id-1` | identity | network / network | via auth-1 (`agentkey-9`) | 10:04:00, agent `agent-A` |
| `m1` | mandate | credentials_provider / person | via auth-1 | 09:00, person `person-P`, agent `agent-A`, sku1 x 1 at 50.00, cap 50.00 per purchase USD, sellers [shopA], expires 2026-11-08, revocable by credentials_provider |
| `req-7` | payment_request | psp / psp | via auth-1 | 10:05:00, request `req-7`, 50.00 USD at shopA |
| `log-3` | attempt_log | psp / psp | via auth-1 | first request 10:05:00, closed 10:06:00, requests [req-7], charges [ch-1 50.00 USD] |
| `order-9` | order | merchant / merchant | via auth-1 | 10:05:10, sku1 x 1 at 50.00 USD at shopA; `link_tokens` trk-77, claim-3 |
| `del-1` | delivery | carrier / carrier | via order-9 (depth 2) | 2026-11-02 15:00, delivered |
| `claim-3` | agent_claim | agent / agent, runs_agent true, check none | via order-9 (depth 2) | 2026-11-02 16:00, delivered |
| `st-m1` | status | credentials_provider / credentials_provider | via auth-1 | as of 10:07:00, m1 active since 09:00 |

Every record except `claim-3` is `verified_by_other`, with both flags `"false"`. `keepers` is empty (every key
`unsure`). Action time 10:05:00, last payment 10:05:30. Answers: every line PRESENT and AP-4 NOT_REQUIRED.

## Cases

`base-*` are the baseline and the 19 rows of the conformance outline (4.1). The last column says where an answer
differs from the outline's prototype answers, and why. `f-*` cover the review findings (design 9.2) and the
derivation findings D-2.

| Case | Change from baseline | Lines not PRESENT | Changed from the outline on purpose |
| --- | --- | --- | --- |
| `base-baseline` | baseline | AP-4 NOT_REQUIRED |  |
| `base-person-link-missing` | no mandate (and so no status record) | AP-1 NOT_CAPTURED; AP-2 NOT_CAPTURED; AP-3 NOT_CAPTURED; AP-4 NOT_CAPTURED; AP-8 NOT_CAPTURED |  |
| `base-agent-only-attempts` | payment request held only by the agent; no attempt log | AP-4 NOT_CAPTURED; AP-5 SELF_REPORT_ONLY |  |
| `base-agent-only-no-keeper` | as base-agent-only-attempts, keepers AP-5.attempts = none | AP-4 NOT_CAPTURED; AP-5 NO_OUTSIDE_SOURCE |  |
| `base-failed-signature` | mandate check failed (signature_invalid) | AP-1 UNVERIFIABLE; AP-2 UNVERIFIABLE; AP-3 UNVERIFIABLE; AP-4 NOT_CAPTURED | AP-8 PRESENT (was NOT_CAPTURED): the status record is outside and checked on its own |
| `base-asked-1-got-2` | order quantity 2 | AP-2 DISAGREES; AP-4 NOT_CAPTURED | AP-2 DISAGREES added: quantity differs between mandate and order (6.11.1) |
| `base-records-conflict` | a second checked authorization says 60 for the same charge | AP-4 NOT_CAPTURED; AP-6 DISAGREES |  |
| `base-claim-versus-outcome` | agent claims returned | AP-4 NOT_REQUIRED; AP-7 DISAGREES |  |
| `base-expired-mandate` | mandate expired before action time | AP-4 NOT_CAPTURED; AP-8 NOT_ACTIVE | AP-4 NOT_CAPTURED (was NOT_REQUIRED): AP-8 must be PRESENT (8.2) |
| `base-withdrawn-permission` | status record says revoked, effective before action time | AP-4 NOT_CAPTURED; AP-8 NOT_ACTIVE | AP-4 NOT_CAPTURED (was NOT_REQUIRED) (8.2) |
| `base-over-cap-approved` | charge 250, person-signed approval before action time | all PRESENT |  |
| `base-over-cap-escalated-only` | charge 250, no approval record | AP-4 NOT_CAPTURED |  |
| `base-over-cap-late-approval` | charge 250, approval signed after action time | AP-4 SELF_REPORT_ONLY | AP-4 SELF_REPORT_ONLY (was NOT_CAPTURED): the late approval is person held (6.11.3) |
| `base-retries` | 2 related charges of 30 against a cap of 50 | AP-4 NOT_CAPTURED |  |
| `base-fulfillment-not-arrived` | no delivery record | AP-4 NOT_CAPTURED; AP-6 NOT_CAPTURED; AP-7 DISAGREES | AP-7 DISAGREES added: the agent claims delivered and no delivery record exists (6.11.2) |
| `base-merchant-runs-agent` | order record runs_agent true | AP-4 NOT_CAPTURED; AP-6 SELF_REPORT_ONLY | AP-6.delivery NOT_CAPTURED too: the agent-run order is not a supporting anchor |
| `base-unbound-mandate` | mandate bound to another purchase | AP-1 NOT_CAPTURED; AP-2 NOT_CAPTURED; AP-3 NOT_CAPTURED; AP-4 NOT_CAPTURED; AP-8 NOT_CAPTURED |  |
| `base-unsupported-aep-version` | mandate check not_run (unsupported_version) | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED | AP-1, AP-2, AP-3 SELF_REPORT_ONLY (was UNVERIFIABLE), AP-8 PRESENT: the mandate is person signed, so the outside-only UNVERIFIABLE rule does not apply (6.11.3) |
| `base-precedence` | 2 checked status records: revoked inside the window and active | AP-4 NOT_CAPTURED; AP-8 NOT_ACTIVE | AP-8 NOT_ACTIVE (was DISAGREES), AP-4 NOT_CAPTURED (8.2); revoked inside the window wins |
| `base-self-checked-charge` | authorization check none (the anchor every other record binds through) | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED; AP-5 NOT_CAPTURED; AP-6 UNVERIFIABLE; AP-8 NOT_CAPTURED | AP-1, AP-2, AP-3 SELF_REPORT_ONLY, AP-5 and AP-8 NOT_CAPTURED too: every record binds through the unchecked authorization, so none is supported (6.0) |
| `f-b1-unchecked-request-sets-action-time` | B1: unchecked request at 10:04:30 sets action time; mandate 10:04:45 is late | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED; AP-5 DISAGREES |  |
| `f-b1-attempt-log-earlier` | B1: attempt log first_request_at 10:04:00 is earlier than the authorization | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED |  |
| `f-b1-step-up-late` | B1: approval after a first declined request is late | AP-4 SELF_REPORT_ONLY |  |
| `f-b2-order-without-unit-price` | B2: order has no unit_price, mandate has one: no conflict | AP-4 NOT_REQUIRED |  |
| `f-b2-price-times-quantity-differs` | B2: 2 x 20.00 = 40 but total 50 (not compared) | AP-4 NOT_REQUIRED |  |
| `f-b2-cumulative-cap` | B2: cumulative cap makes AP-4 required | AP-4 NOT_CAPTURED |  |
| `f-b3-ntid-prefix` | B3: anchor bound by ntid-10, case is ntid-1: nothing binds | AP-1 NOT_CAPTURED; AP-2 NOT_CAPTURED; AP-3 NOT_CAPTURED; AP-4 NOT_CAPTURED; AP-5 NOT_CAPTURED; AP-6 NOT_CAPTURED; AP-7 NOT_CAPTURED; AP-8 NOT_CAPTURED |  |
| `f-b3-agent-side-anchor` | B3: mandate bound via an agent-side payment request | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED |  |
| `f-b3-wrong-binding-kind` | B3: second authorization uses value ntid-1 under kind charge_id: unbound | AP-4 NOT_REQUIRED |  |
| `f-b4-revoked-after-window` | B4: revoked effective after last payment, with active_since: PRESENT | AP-4 NOT_REQUIRED |  |
| `f-b4-revoked-inside-window` | B4: revoked effective 10:05:15, between action time and last payment | AP-4 NOT_CAPTURED; AP-8 NOT_ACTIVE |  |
| `f-b4-status-role-not-revoker` | B4: status from a psp, mandate revocable only by credentials_provider | AP-4 NOT_CAPTURED; AP-8 NOT_CAPTURED |  |
| `f-b4-active-since-after-action` | B4: active status but active_since after action time | AP-4 NOT_CAPTURED; AP-8 NOT_CAPTURED |  |
| `f-b4-unchecked-revoked-token` | B4: unchecked revoked token status still makes AP-8 NOT_ACTIVE | AP-4 NOT_CAPTURED; AP-8 NOT_ACTIVE |  |
| `f-b5-repeated-record-id` | B5: 2 records share an id: INVALID | INVALID: DUPLICATE_RECORD_ID |  |
| `f-b6-approval-below-total` | B6: approval of 200 against a total of 250 | AP-4 SELF_REPORT_ONLY |  |
| `f-b6-approval-no-order` | B6: approval but no order record | AP-4 SELF_REPORT_ONLY; AP-6 NOT_CAPTURED; AP-7 NOT_CAPTURED |  |
| `f-b7-mandate-other-agent` | B7: mandate names agent-B, identity says agent-A | AP-1 DISAGREES; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED |  |
| `f-b7-token-other-agent` | B7: a bound token names agent-B | AP-1 DISAGREES; AP-4 NOT_CAPTURED |  |
| `f-b7-approval-other-person` | B7: approval for person-Q, mandate for person-P | AP-1 DISAGREES; AP-4 SELF_REPORT_ONLY |  |
| `f-b7-identity-agent-side-only` | B7: the only identity record is agent side | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED |  |
| `f-b8-charge-listed-twice` | B8: PSP and network both report ch-1 for 50.00: counted once | AP-4 NOT_REQUIRED |  |
| `f-b8-50-vs-50-00` | B8: attempt log says 50, authorization 50.00: equal | AP-4 NOT_REQUIRED |  |
| `f-b8-unlisted-authorization` | B8: second authorization ch-2 not in the attempt log | AP-4 NOT_CAPTURED; AP-5 DISAGREES |  |
| `f-b8-split-charge-under-cap` | B8: split charge 30 + 20 under a 50 cap | AP-4 NOT_REQUIRED |  |
| `f-m2-failed-auth-next-to-good` | M2: a failed network authorization next to a good PSP one | AP-4 NOT_CAPTURED; AP-6 UNVERIFIABLE |  |
| `f-m2-failed-runs-agent-unknown` | M2: failed authorization also marked runs_agent unknown | AP-4 NOT_CAPTURED; AP-6 UNVERIFIABLE |  |
| `f-m3-two-permissions` | M3: mandate and token, each with an active status: 2 AP-8 parts | AP-4 NOT_REQUIRED |  |
| `f-m4-expired-inside-window` | M4: mandate expires 10:05:20, between action time and last payment | AP-4 NOT_CAPTURED; AP-8 NOT_ACTIVE |  |
| `f-m5-person-signed-delivery` | M5: delivery record signed by the person | AP-4 NOT_CAPTURED; AP-6 SELF_REPORT_ONLY |  |
| `f-m6-bad-time` | M6: 31 November | INVALID: TYPE |  |
| `f-m6-leap-second` | M6: second 60 | INVALID: TYPE |  |
| `f-m6-duplicate-json-key` | M6: a duplicate key in case.json | INVALID: DUPLICATE_KEY |  |
| `f-m6-json-boolean-runs-agent` | M6: runs_agent given as JSON true | INVALID: ENUM |  |
| `f-p1-time-from-kind-field` | P1: mandate time is issued_at (10:05:10, late), not its earlier not_before | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED |  |
| `f-request-missing-from-log` | a second payment request not listed in the attempt log | AP-4 NOT_CAPTURED; AP-5 DISAGREES |  |
| `f-in-transit-then-delivered` | carrier in_transit, then delivered: earlier status superseded | AP-4 NOT_REQUIRED |  |
| `f-claim-total-on-split` | agent claims the total 50.00 on a 30 + 20 split charge | AP-4 NOT_REQUIRED |  |
| `f-per-request-identity-at-last-payment` | identity verified at 10:05:30, the supported last payment time | AP-4 NOT_REQUIRED |  |
| `f-r3-unchecked-token-no-status` | round 3: unchecked token with no status record | AP-4 NOT_CAPTURED; AP-8 NOT_CAPTURED |  |
| `f-r3-weakened-anchor-expired-mandate` | round 3: unchecked order anchor still binds an expired mandate | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED; AP-6 UNVERIFIABLE; AP-8 NOT_ACTIVE |  |
| `f-r3-agent-log-earlier-no-revive` | round 3: agent-side earlier attempt log does not revive a revoked mandate | AP-4 NOT_CAPTURED; AP-8 NOT_ACTIVE |  |
| `f-r3-agent-delivered-not-hide-returned` | round 3: later agent-side delivered does not hide the carrier's returned | AP-4 NOT_REQUIRED; AP-7 DISAGREES |  |
| `f-seller-a-request-seller-b-charge` | request at shopA, charge at shopB | AP-4 NOT_CAPTURED; AP-6 DISAGREES |  |
| `f-tax-total-differs` | unit price 46.00 x 1, total 50.00 with tax: AP-4 still NOT_REQUIRED | AP-4 NOT_REQUIRED |  |
| `f-clock-skew-2min` | identity verified 2 minutes after the last payment: fails closed | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED |  |
| `f-d2-nonqualifying-payment-does-not-move-bound` | D-2: an outside authorization with signer none at 10:08 does not move the AP-1.agent bound | AP-1 SELF_REPORT_ONLY; AP-2 SELF_REPORT_ONLY; AP-3 SELF_REPORT_ONLY; AP-4 NOT_CAPTURED; AP-8 NOT_CAPTURED |  |
