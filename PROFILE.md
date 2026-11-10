# Agent Proof Checklist, version 0.1 (DRAFT): a missing-proof profile for AI-agent purchase disputes

Draft of 2026-11-03 (revision 5, built with the reference checker). Not yet published. Licensed under the Apache License
2.0 (see `LICENSE`). Profile id `agent-proof-checklist/0.1`.

## 1. What this is

When an AI agent buys something for a person and the person later disputes it, a reviewer needs answers to 8 questions
(AP-1 to AP-8). This profile names those questions, says exactly what proof answers each one, and gives each question 1
result: `PRESENT`, `NOT_REQUIRED` (AP-4 only), or a why code that says why the proof is missing.

A filing indexes evidence that already exists. It does not replace AEP or any network format. It is meant to be filled
in from an A-Comm Evidence Protocol (AEP) DisputeBundle first, and also from processor logs, bank records, carrier
records and the agent's own log.

Analogy: AEP is a sealed evidence box. This profile is the inspection sheet clipped to the outside of the box: "a reviewer
needs these 8 things; these are in the box; these are missing, and here is why."

Version 0.1 is normative in 3 parts, together: this text, the field dictionary `fields.json`, and the case pack under
`cases/`. The reference checker in `apc/` applies the rules exactly. If any 2 of them disagree, that is a defect, fixed
by a new version. The key words MUST, MUST NOT and MAY are used as in RFC 2119.

Two principles hold everywhere, and a test proves them on every case:

1. **Parts come from the records, never from the filer.** What a record can prove follows from its kind and fields
   (section 4.3). A filer does not choose it.
2. **A weaker filing never gets a better answer.** Rules that can make an answer better use only records that qualify.
   Rules that can only make an answer worse use every record bound to the purchase, whoever made it and however it was
   checked. So adding a record that does not qualify, or weakening a record's own claims (a lower `check`, an
   affiliation flag set to `unknown`, `signer` set to `agent`), never turns a line into `PRESENT`. It also never turns a
   required approval into `NOT_REQUIRED`.

## 2. Relation to AEP

AEP (A-Comm Technologies, Apache 2.0, github.com/A-Comm-Tech/a-comm-evidence-protocol, read at v1.0.3-rc.2 of 2026-07-02) is
an open evidence specification for agentic commerce. It is a signed, hash-chained record of a purchase from discovery
through payment, fulfillment and refund, exported as a DisputeBundle mapped to card-network evidence fields. AEP section
numbers are written "AEP §n".

- Section 6 names, for every line, the AEP artifacts and fields that answer it.
- Section 7 lists 4 places where AEP has no field for a question (gaps A to D), with the AEP features they build on.
- This profile adds a per-question "present or missing, and why" result. AEP reports per-envelope verification and a
  chain-level evidence tier (AEP §3.9.12, §5). It does not answer per dispute question.
- When a record comes from an AEP chain, the AEP terms that govern its use still apply. These include the AEP §6.5
  safe-harbor term: artifacts a platform emitted under AEP must not be presented as evidence against that platform in
  disputes between that platform and merchants or consumers. They also include the AEP §6.5 labeling rule for
  unverified platform attribution.

## 3. Terms

| Term | Meaning |
| --- | --- |
| Person | The human or business the agent acts for (cardholder, account holder, customer). |
| Agent operator | Whoever runs the agent: its developer, the platform that hosts it, or a merchant or wallet that runs its own agent. |
| Filer | Whoever fills in a filing: merchant, PSP, issuer, dispute firm, agent platform, or a tool acting for one. |
| Reviewer | Whoever decides the dispute: merchant, issuer, card network or arbitrator. |
| Record | 1 piece of evidence, in the shape of section 8.2. |
| Part | A named piece of a line, for example `AP-1.person`. |
| Case binding | The identifier of the disputed purchase (`binding_kind` and value), for example a network transaction id. |
| Agent side | A record made by the agent or its operator, or by a party not stated to be unaffiliated (4.2.1). |
| Person held | A record that is not agent side and that the person made or signed (4.2.1). |
| Outside | Every record that is neither agent side nor person held. |
| Anchor | A record of kind `authorization`, `payment_request`, `attempt_log` or `order` that other records bind through (4.2.2). |
| Bound | Tied to this purchase by the binding rule (4.2.2). Unbound records are listed and then ignored. |
| Supported | Bound directly, or through an anchor that is itself supported, outside and checked (4.2.2). |
| Checked | `check` is `verified_by_other` or `recomputed`. |
| Qualifies | Supported, has the part, outside (or person held where allowed), checked, meets the signer rule, early enough, and passes the line's own tests (4.2.7). |
| Action time | The earliest payment time of the purchase (4.2.5). The payment window runs from action time to the last payment time. |
| Keeper | An outside party that usually keeps a record for a part (Appendix A). The filing's `keepers` says whether one exists. |
| Total | The sum of the purchase's distinct charges (5.4). |
| Cap | The smallest spending cap of any bound mandate or token (5.4). |
| Supporting view | Only the records that qualify. Used for steps that can make an answer better. |
| Blocking view | Every bound record, of any side and any check. Used for steps that can only make an answer worse. |
| Mandate | A signed permission from the person to the agent, for example an AP2 checkout or payment mandate (AEP §3.9.7) or a Mastercard Verifiable Intent credential (AEP §3.9.15). |

## 4. The procedure

### 4.1 Results and codes

Each line gets exactly 1 result: `PRESENT`, `NOT_REQUIRED` (AP-4 only), or 1 code. When more than 1 code applies, the
earliest in this order wins:

| Order | Code | Meaning in 1 line |
| --- | --- | --- |
| 1 | `DISAGREES` | Bound records conflict on something that matters, or the agent's claim does not match the outside record. |
| 2 | `NOT_ACTIVE` | A permission the purchase relied on was revoked, suspended, expired or not yet valid during the payment window (AP-8 only). |
| 3 | `UNVERIFIABLE` | A bound record for the part failed its check, or an outside one was not checked. |
| 4 | `SELF_REPORT_ONLY` | For a missing part, only the agent side or the person has a record, and an outside party in this setup usually keeps 1. |
| 5 | `NO_OUTSIDE_SOURCE` | Same, and the filer declares that no outside party in this setup keeps 1 (`keepers` = `none`). |
| 6 | `NOT_CAPTURED` | For a missing part, no usable record was found. |

A code describes the state of the evidence. It is not a finding of fraud or fault, and a filing MUST NOT present it that
way.

### 4.2 Record tests

1. **Side.** A record is **agent side** when any of these holds: `party_role` is `agent` or `agent_operator`;
   `runs_agent` is not `"false"`; `operator_affiliated` is not `"false"`; `signer` is `agent`. So `"unknown"` counts as
   agent side. A record is **person held** when it is not agent side and its `party_role` or `signer` is `person`. A
   person-held record can qualify only for `AP-1.person`, `AP-2.request` and `AP-3.limits` (from a mandate) and
   `AP-4.approval`. For any other part it counts as agent side. Every other record is **outside**. `party_role` is the
   role of the party that made the record, not of whoever supplies it. A merchant filing the PSP's authorization keeps
   `party_role: psp`.
2. **Bound and supported.**
   - Directly: `binding.kind` and `binding.value` equal the case binding exactly (case-sensitive tokens). This is link
     depth 0.
   - Through an anchor: `binding.via` names an anchor at depth 0 or 1 whose `fields.link_tokens` contains this record's
     `binding.value`. Depth is the anchor's depth plus 1, at most 2. `binding.kind` is not compared on a `via` binding.
     Binding is computed outward from the directly bound records. A `via` naming a non-anchor, or a cycle, leaves the
     record unbound.
   - A `status` record whose `permission_of` names a bound mandate or token is also bound. This counts only for blocking
     steps: to prove the permission was active, a status record needs its own direct or anchor binding.
   - A record is **supported** when it is bound directly, or through an anchor that is itself supported, outside and
     checked. Only supported records can qualify.
   - Example: the PSP authorization is bound by the network transaction id. Its `link_tokens` carry the tokens of the
     mandate, the payment request, the agent identity record, the merchant order, the attempt log and the status
     record, and each of those binds via the authorization. The order's `link_tokens` carry the tracking number and
     the agent's claim, and the carrier record and the claim bind via the order.
3. **Time.** A record's time is its kind's time field in `fields.json` (for example `issued_at` for a mandate,
   `status_as_of` for a status record).
4. **Checked.** `check` is `verified_by_other` or `recomputed`. In 0.1, `check` is the filer's statement: signatures,
   hashes and key revocation are not verified by this profile. Any bound record with `check: failed`, of any side,
   blocks every part it has. Examples: an AEP cart-to-payment hash failure is filed as `failed` with detail
   `hash_mismatch` on the authorization; a key revoked before the record was made is `failed` with `key_revoked`.
5. **Action time.** Action time is the earliest time of every bound `payment_request` and `authorization`, and of the
   `first_request_at` of every bound `attempt_log`, of any side and any check. The last payment time is the latest of
   the same times. If there is none, nothing in AP-1 to AP-4 qualifies and AP-8 cannot be `PRESENT`.
6. **Early enough.** `AP-1.person`, `AP-2.request`, `AP-3.limits` and `AP-4.approval` need a time strictly before
   action time. A step-up approval made after a first declined request is late in 0.1. `AP-1.agent` needs a time at or
   before the supported last payment time, which is the latest time of a payment record that itself qualifies
   (`AP-5.attempts` for a payment request, `AP-6.charge` for an authorization). A record that does not qualify cannot
   move this bound. There is no clock-skew tolerance in 0.1. An honest filing with skewed clocks fails closed.
7. **Qualifies.** A record qualifies for a part when it meets all of these:
   - it is supported;
   - it has the part;
   - it is outside, or person held for the parts allowed in 4.2.1;
   - it is checked;
   - it meets the signer rule (4.4);
   - it is early enough (4.2.6);
   - it passes the line's own tests (section 5).

### 4.3 Parts come from kinds and fields

| Kind | Parts |
| --- | --- |
| `identity` | `AP-1.agent` |
| `mandate` | `AP-1.person`; `AP-2.request` when it has `item_id` and `quantity`; `AP-3.limits` when it has any of `cap`, `allowed_sellers`, `expires_at` |
| `token` | `AP-3.limits` |
| `approval` | `AP-4.approval` |
| `payment_request` | `AP-5.attempts` |
| `attempt_log` | `AP-5.attempts`, `AP-5.related` |
| `authorization` | `AP-6.charge` |
| `order` | `AP-6.order` |
| `delivery` | `AP-6.delivery` |
| `status` | `AP-8.status:<permission_of>` |
| `agent_claim` | `AP-7.claim` |
| `refund`, `other` | none |

A mandate never approves going over a limit in 0.1. Only an `approval` record can.

### 4.4 Signer rules

| Part | Requirement |
| --- | --- |
| AP-1.agent | `signer` is `network`, `issuer`, `psp`, `merchant` or `other` |
| AP-1.person, AP-2.request, AP-3.limits | `signer` is `person`, `credentials_provider` or `issuer` |
| AP-4.approval | `signer` is `person`, `credentials_provider`, `issuer` or `wallet` |
| AP-5.attempts, AP-5.related | `signer` is `psp`, `network`, `issuer` or `merchant` |
| AP-6.charge | `signer` and `party_role` each `psp`, `network` or `issuer` |
| AP-6.order | `signer` is `merchant` or `psp` |
| AP-6.delivery | `signer` is `carrier` or `merchant` |
| AP-7.claim | none |
| AP-8.status | `party_role` in the permission's `revocable_by` (default `issuer`, `credentials_provider`, `psp`, `token_service`) |

### 4.5 Part reasons and line results

For each part, the first match wins:

1. `UNVERIFIABLE` when a bound record with the part has `check: failed`.
2. `PRESENT` when at least 1 record qualifies.
3. `UNVERIFIABLE` when a bound, outside record with the part has `check` `not_run` or `none`.
4. When a bound agent-side or person-held record has the part: `NO_OUTSIDE_SOURCE` if `keepers` says `none` for the
   part's key, else `SELF_REPORT_ONLY`. A person-held record with `not_run` or `none` lands here, not in step 3.
5. Else `NOT_CAPTURED`.

A line's result is the earliest code (4.1) among its line codes (section 5: conflicts and other line-level checks) and
its part reasons. It is `PRESENT` when there is no code. `line_codes` lists only the line-level codes; a part reason is
never repeated there. AP-4, AP-7 and AP-8 follow the special rules in section 5.

### 4.6 Filing rules

1. **Complete listing.** The filer MUST list every record it holds for the purchase and MUST set `records_complete:
   true`. A filer holding an AEP bundle MUST reference it.
2. **Fail closed.** A filing that breaks any rule of section 8 is INVALID and gets no answers.
3. **1 form per identifier.** Identifiers must be in 1 shared form across the filing. The filer maps a DID and a key id,
   or a merchant id and a domain, to 1 token, or they disagree.
4. **What a filing cannot prove.** The following rest on the filer's statement and cannot be detected by a checker
   reading the filing:
   - that the records listed are complete;
   - that a party is really unaffiliated;
   - that each record's kind, time and binding are true;
   - that `check` is true.

   Leaving out an optional field is the same as leaving out a record. A filer can hide a failed check by leaving the
   record out. Principle 2 makes sure a filer gains nothing by weakening a statement. It cannot stop a filer from
   leaving a record out or relabeling a payment record as `other`.

## 5. The 8 lines: rules

Steps run in this order: record tests (they read only fields and the blocking view, never line results), then AP-1,
AP-2, AP-3, AP-5, AP-6, AP-7, AP-8, then AP-4. The rules here say which conflicts and line-level checks give
`DISAGREES`. Comparisons are typed: decimals by value (`50` equals `50.00`), integers by value, tokens exactly.

### AP-1. Who sent the agent, and for whom?

- Parts: `AP-1.agent` and `AP-1.person`.
- The case agent is the set of `agent_identity` values of identity records that qualify for `AP-1.agent`. The case
  person is the set of `person_identity` values of mandates that qualify for `AP-1.person`.
- A mandate qualifies for `AP-1.person`, `AP-2.request` or `AP-3.limits` only when its `agent_identity` is in the case
  agent. A token qualifies for `AP-3.limits` only when it has no `agent_identity`, or that identity is in the case agent.
  An approval qualifies only when its `person_identity` is in the case person. An empty case set means these do not
  qualify. That leads to a part reason, never to `DISAGREES`.
- `DISAGREES` when bound identity, mandate and token records together carry more than 1 distinct `agent_identity`, or
  bound mandates and approvals carry more than 1 distinct `person_identity`. Every bound record counts, qualified or not.

### AP-2. What did the person ask for?

- Part: `AP-2.request`, from a mandate with `item_id` and `quantity`.
- `DISAGREES` when `item_id`, `quantity` or `unit_price` differs between any 2 bound mandate, approval or order records
  that carry it and at least 1 of them is a mandate. Without a mandate, the conflict lands on AP-6.

### AP-3. What was the agent allowed to do?

- Part: `AP-3.limits`, from a mandate with limits, or a token. Caps are never compared with each other: the smallest
  one counts (5.4).

### AP-4. Did a person approve it when it went over a limit?

AP-4 is decided after the other lines. It is `NOT_REQUIRED` (part reason `NOT_REQUIRED`) when every item below holds. A
missing value means the item fails:

1. AP-1, AP-2, AP-3, AP-5, AP-6 and AP-8 are `PRESENT`.
2. Total and cap are defined, the cap is not cumulative, the cap currency equals the charges' currency, and the total
   is at most the cap.
3. When allowed sellers is defined, the seller set is not empty and lies inside it.
4. At least 1 bound order exists, and at least 1 bound mandate has `AP-2.request`. Every `item_id`, `quantity` and
   `unit_price` on any bound mandate, approval or order is the same wherever it appears, so the purchase is 1 item.
   The total is not compared with `unit_price` times `quantity`, because of tax and shipping. The cap bounds the money.

Otherwise AP-4 is required and its part follows 4.5. An approval qualifies only when all of these hold, besides 4.2.7:

- the total is defined;
- the approval's `amount` is at least the total;
- its `currency` equals the charges' currency;
- at least 1 bound order exists and every bound order has the approval's `item_id`;
- when the approval has `quantity`, every bound order has that quantity.

Two ids for 1 real charge (such as a PSP id and a network id) count twice and make AP-4 required. This fails closed and
is documented.

### AP-5. What did the agent try, in order?

- Parts: `AP-5.attempts` (a payment request or attempt log) and `AP-5.related` (an attempt log).
- `DISAGREES` when at least 1 attempt log qualifies for `AP-5.attempts` and a bound payment request's `request_id` is
  missing from all of their `request_ids`.
- `DISAGREES` when at least 1 record qualifies for `AP-5.related` and a bound authorization's `charge_id` is missing
  from all of their `charges`.
- `DISAGREES` when 2 bound records of the same kind and the same entity key (5.3) differ on a material field.

### AP-6. What happened, according to someone other than the agent?

- Parts: `AP-6.charge`, `AP-6.order`, `AP-6.delivery`.
- `DISAGREES` when any of these holds:
  - the same `charge_id` appears with 2 amounts or currencies;
  - `seller` differs between any 2 bound payment requests, authorizations and orders;
  - `currency` differs between any 2 of those or any attempt log charge;
  - `item_id`, `quantity` or `unit_price` differs between bound approvals and orders when no mandate is involved;
  - 2 bound records of the same kind and entity key differ on a material field.
- Delivery records are not compared with each other. The **open delivery statuses** are the statuses of every bound
  delivery record that no later qualifying delivery record supersedes. A later agent-side "delivered" does not hide the
  carrier's "returned".

### AP-7. What did the agent say it did?

- Part: `AP-7.claim`, the agent's own account, signed or not. It never makes another line present.
- The result is only `DISAGREES`, `PRESENT` or `NOT_CAPTURED`, and the part takes the same value. The result is
  `DISAGREES` when a bound claim carries a field whose matching value is undefined, or when any of these holds:
  - its `seller` differs from any seller of a bound payment request or authorization;
  - its `amount` differs from the total, or from the supporting total (the sum over distinct charges of records that
    qualify for `AP-6.charge` or `AP-5.related`);
  - its `currency` differs from the charges' currency;
  - its `delivery_status` differs from any open delivery status;
  - its `item_id` or `quantity` differs from any bound order.

  Otherwise it is `PRESENT` when a bound claim exists (with no side, check or signer test), else `NOT_CAPTURED`.
- If the claim comes from an AEP artifact a platform emitted, the AEP §6.5 safe-harbor term applies to its use against
  that platform.

### AP-8. Was the permission still active when the agent paid?

- Parts: 1 part `AP-8.status:<id>` for each bound mandate or token, sorted by id. With none, 1 part `AP-8.status`
  that cannot be `PRESENT`.
- **Inactive in the window** (blocking view): a bound status record for the permission says it was not `active` with
  `effective_at` at or before the last payment time. Or the permission's `expires_at` is at or before the last payment
  time. Or its `not_before` is after action time. Validity is `[not_before, expires_at)` and must cover the whole payment
  window. A record of any side or check counts here.
- **Active evidence**: a status record that is supported, outside, checked, from a role in `revocable_by`, with
  `active_since` at or before action time, and either `permission_status: active` as of the last payment time or later,
  or a non-active status with `effective_at` after the last payment time.
- Per part: `NOT_ACTIVE` when the permission was inactive in the window. `PRESENT` when there is active evidence. Else
  the part reason from 4.5, where "a record qualifies" means "a record gives active evidence".
- `NOT_ACTIVE` appears only on AP-8. A revoked mandate still answers AP-1, AP-2 and AP-3, because those ask who, what
  and which limits, not whether the permission was still active.

## 6. Where the AEP evidence is

| Line | AEP artifacts and fields |
| --- | --- |
| AP-1 | Agent identity: `agent_identity` (Visa TAP, §3.9.6), `web_bot_auth` (§3.9.18), `kya_identity` (§3.9.16). Link to the person: `consumer_authorization` (AP2, §3.9.7) or `mastercard_verifiable_intent` (§3.9.15, PROVISIONAL in AEP). AEP notes agent identity alone is "agent-attributable", "NOT user-authorized" (§3.9.12). |
| AP-2 | AP2 checkout mandate signed with the person's key (§3.9.7); Verifiable Intent `constraints_captured` (§3.9.15); the Intent artifact (§3.3) when it carries the person's signature. AEP keeps only a salted hash of the person's words (`query_hash`), by design. |
| AP-3 | AP2 open mandate constraints (§3.9.7); a person-signed closed mandate whose exact cart is the limit; ACP shared payment token `max_amount`, `expires_at` (§3.9.11 rule 6); `kya_payment` amount (§3.9.17); `pre_execution_attestation.policy_bounds` (§3.9.21) when `issuer_relationship` is `independent` or `psp_operated`. The Policy artifact (§3.4) is the merchant's risk decision, not the person's permission. |
| AP-4 | Partly: Policy `outcome: escalated` (§3.4) shows an approval was needed, not that it was given. |
| AP-5 | Partly: `seq` (§2.7) and `idempotency_key` (§8.4). AEP folds repeated requests with 1 key into 1 artifact, and a retry that made a second charge is a second chain. |
| AP-6 | Authorization (§3.6), Cart (§3.5), Fulfillment (§3.7), Refund (§3.10). `chain_complete: false` (§5) before fulfillment arrives. |
| AP-7 | None. |
| AP-8 | Partly: expiry fields (AP2 mandate `exp`, ACP token `expires_at`, `kya_payment` expiry, attestation `expires_at`). AEP does not record a permission withdrawn before it expired. |

## 7. What AEP covers, and the 4 gaps

| Line | Covered by AEP today | Gap, and the AEP features it builds on |
| --- | --- | --- |
| AP-1 | Yes, with a delegation sub-wrapper | none |
| AP-2 | Yes, with a person-signed mandate | none |
| AP-3 | Yes, with a delegation sub-wrapper | none |
| AP-4 | Partly | A. who resolved an escalation, and when. Builds on Policy `escalated` (§3.4) and `pre_execution_attestation` (§3.9.21). |
| AP-5 | Partly | B. a link between attempts, retries and the chains or charges they created. Builds on `intent_id` (§3.3), `mandate_setup_chain_id` (§3.6) and `customerHistory` (§6.1). |
| AP-6 | Yes, once fulfillment arrives | none |
| AP-7 | No | C. the agent's report back to the person. Must respect the §6.5 safe-harbor term. |
| AP-8 | Partly (expiry) | D. a permission withdrawn before it expired, from the party able to revoke it. |

## 8. Filing format

The field dictionary `fields.json` is the exact, machine-readable form of this section: every kind, field, type,
requirement and time field. A filing is UTF-8 JSON without a byte-order mark, with no duplicate keys and no NaN or
Infinity.

### 8.1 Filing

Top-level fields, no others allowed:

| Field | Type |
| --- | --- |
| `profile` | exactly `"agent-proof-checklist/0.1"` |
| `case_id` | token |
| `case_binding` | `{"kind": binding_kind, "value": token}` |
| `aep_bundle` | `null` or `{"chain_id", "sealed_bundle_hash", "spec_version"}` (tokens); when the case binding kind is `chain_id`, `chain_id` must equal it |
| `filed_by` | `merchant`, `psp`, `issuer`, `dispute_firm`, `agent_platform` or `other` |
| `filed_at` | time; every record's own time, and every other time field that records something observed, must be at or before it. `expires_at`, `not_before` and `effective_at` state validity and may be later. |
| `keepers` | object; keys from the part keys; values `exists`, `none` or `unsure`; a missing key means `unsure` |
| `records_complete` | JSON `true` |
| `records` | array of 1 or more records |
| `action_time`, `lines`, `unbound_record_ids` | the answers (section 9), required in a filed filing; not allowed in a case input |

`binding_kind` is 1 of `network_transaction_id`, `charge_id`, `chain_id`, `cart_hash`, `order_id`, `tracking_id`,
`mandate_ref`, `request_ref`.

### 8.2 Record

| Field | Type |
| --- | --- |
| `id` | token, unique in the filing |
| `party` | token naming the party that made the record |
| `party_role` | `agent`, `agent_operator`, `merchant`, `psp`, `network`, `issuer`, `credentials_provider`, `token_service`, `wallet`, `carrier`, `person` or `other` |
| `runs_agent`, `operator_affiliated` | the strings `"true"`, `"false"` or `"unknown"` |
| `kind` | a kind from `fields.json` |
| `signer` | `person`, `credentials_provider`, `issuer`, `wallet`, `merchant`, `psp`, `network`, `token_service`, `carrier`, `agent`, `other` or `none` |
| `binding` | `{"kind": binding_kind, "value": token, "via": record id or null}` |
| `ref` | token: an AEP path or external id, never raw personal data, never used for binding |
| `check` | `verified_by_other`, `recomputed`, `failed`, `not_run` or `none` |
| `check_detail` | only with `failed` or `not_run`: `signature_invalid`, `hash_mismatch`, `key_revoked`, `unsupported_version` or `other`; informative only |
| `fields` | per kind, as `fields.json` says; strings, arrays and objects only, no free text |

### 8.3 Types, entity keys and validation

- Types: token (1 to 128 printable ASCII characters, no spaces), decimal (`50`, `50.00`, up to 6 places), integer,
  currency (3 capital letters), time, token list, role list, record reference and charge list.
- A time is RFC 3339 with an offset. It must be a real calendar date, with hour 00-23, minute and second 00-59 (no leap
  second), and an offset up to 23:59. It is compared as a UTC instant.
- An enum field holds 1 of its listed strings. Any other value, of any JSON type (a JSON `true` included), is `ENUM`.
- The entity key says which real-world thing a record describes, and is used for conflicts. Mandates, tokens,
  approvals and attempt logs are keyed by record id. Payment requests use `request_id`, authorizations `charge_id`,
  orders `order_id`, refunds `refund_id` and status records `permission_of`. Identity, delivery, claim and other
  records have no key.
- Validation fails closed. Error codes: `PROFILE_UNSUPPORTED`, `UNKNOWN_FIELD`, `MISSING_FIELD`,
  `FIELD_NOT_ALLOWED_IN_CASE`, `TYPE`, `ENUM`, `ORDER` (for example `not_before` not before `expires_at`),
  `AFTER_FILED_AT`, `RECORDS_NOT_COMPLETE`, `DUPLICATE_RECORD_ID`, `DANGLING_REF`, `REF_WRONG_KIND`,
  `CHECK_DETAIL_NOT_ALLOWED`, `KEEPERS_KEY`, `AEP_CHAIN_MISMATCH`, `JSON_INVALID`, `DUPLICATE_KEY`. Any error means
  INVALID: no answers.

## 9. Answers

```json
{"action_time": "2026-11-01T10:05:00Z",
 "unbound_record_ids": [],
 "lines": [{"id": "AP-1", "result": "PRESENT", "line_codes": [],
            "parts": [{"part": "AP-1.agent", "reason": "PRESENT", "record_ids": ["id-1"]}]}]}
```

- All 8 lines appear in order, and each lists every part it has in 4.3, in that order, whether or not a record has it.
  AP-8 parts are sorted by permission id.
- `record_ids` are the sorted ids of the bound records that have the part. For the fallback `AP-8.status`, they are
  the bound status records whose permission is not bound.
- Times are given in UTC with `Z`, with fractional seconds only when they are not zero. `action_time` may be `null`.
- A checker conforms at the reference level when it reproduces every case in `cases/` (README).

## 10. Out of scope on purpose

- A new evidence format, hash chain or signature scheme.
- How a tool finds records, matches records to a purchase beyond the binding rule, weighs records, or chooses which
  record to fetch next.
- Whether 2 outside parties count as independent of each other.
- Pass marks, seals, tiers or certification. Who pays.
- In 0.1: verifying signatures, hashes or key revocation; purchases of more than 1 item id; cumulative caps (both make
  AP-4 required, failing closed).

## 11. Open questions

1. Independence between outside parties, including whether a checker the filer pays counts as "other".
2. Clock-skew tolerance between parties' clocks (0.1 is strict).
3. Multi-item purchases and structured item descriptions; cumulative caps with a spent-so-far record.
4. Signature and bundle verification through AEP's own verifier.
5. A mandate signed by the person and held by a credentials provider is person held, so an unverified signature gives
   `SELF_REPORT_ONLY`, not `UNVERIFIABLE` (cases `base-unsupported-aep-version`, `base-over-cap-late-approval`).
   Should 0.2 treat such a record as outside?
6. Informative mapping to existing network dispute codes, building on AEP Appendix C.
7. Business-to-business agent buying.

## Appendix A. Usual keepers (guides the `keepers` entry)

| Part | Outside parties that usually keep it |
| --- | --- |
| AP-1.agent | Card network agent registry; edge network verifying signed requests; a merchant that does not run the agent |
| AP-1.person, AP-2.request, AP-3.limits | Credentials provider or issuer holding the mandate or token |
| AP-4.approval | Issuer, wallet or credentials provider that ran the approval |
| AP-5.attempts, AP-5.related | PSP; a merchant that does not run the agent |
| AP-6.charge | PSP, network, issuer |
| AP-6.order | A merchant that does not run the agent |
| AP-6.delivery | Carrier |
| AP-8.status | The party able to revoke |

A filer sets `keepers` to `none` for a part only when none of the listed parties exists outside the agent side in this
setup. For example, `AP-6.order` can be `none` when the merchant runs the agent and no marketplace or other party holds
the order. Otherwise the value is `exists` or `unsure`, and both lead to `SELF_REPORT_ONLY`.
