# Derivation log, pack 0.1.0

The design calls for 3 derivations of each answer (9.3): the author's hand-written `expected.json`, a blind second
derivation, and the checker. Every difference between them, and every place where the build had to read the design
text one way, is logged here with how it was settled. The design text itself is frozen under its review record, so a
settlement changes PROFILE.md, `fields.json`, the code or the cases, never the design. Items marked **founder** were
reported to the founder.

## How the derivations were run (2026-11-03)

1. **Author.** 66 cases were written with their `expected.json` before the checker ran on any of them.
2. **Checker against author.** All answers agreed on the first run. 1 case failed with an unexpected `DANGLING_REF`:
   `f-b6-approval-no-order` deleted the order but left 2 records with `via: order-9`. This was a mistake in building
   the case, not in its answer. Fixed by giving those 2 records `via: null`, which leaves them unbound, as the answer
   already said.
3. **Blind deriver.** A fresh reviewer saw only the design's sections 4 to 7 (filing, dictionary, rules, output
   shape), `fields.json` and the 66 `case.json` files, never the answers or the code. It wrote its own helper from the
   text and then hand-checked every case. Result: all 61 non-INVALID answers agree with the author on `action_time`,
   `unbound_record_ids`, every line result, every part reason and every `record_ids`. There were 2 kinds of
   difference, D-4 and D-5 below.
4. **Mutation gate** (`tests/test_monotone.py`). It found D-2, a real checker bug, and D-3, a mistake in how the test
   was built. After the fixes it passes on every case.
5. Case `f-d2-nonqualifying-payment-does-not-move-bound` was added after step 4 to pin D-2. Its answer was written by
   hand before the fixed checker ran on it; the old checker gives AP-1.agent PRESENT there.

## Entries

**D-1. `filed_at` and future validity times (founder).** Design section 4 says "every record time and every time field
must be at or before" `filed_at`. Read literally, any mandate whose `expires_at` is after the filing date is INVALID,
including the baseline. The blind deriver found the same problem and made the same choice. Settled: only fields that
record something observed must be at or before `filed_at`. `expires_at`, `not_before` and `effective_at` state
validity, which may lie in the future, so they are exempt (`apc/dictionary.py` `NOT_OBSERVED`). This is pinned by
`test_6_1_future_validity_fields_may_be_after_filed_at`. A record's own time (its T field) is always checked.

**D-2. Supported last payment time (checker bug, found by the mutation gate; founder).** Design 6.5 defines the
AP-1.agent bound as the latest "supported, outside, checked" payment record. It then says "an added record that does
not qualify cannot move this bound". Those 2 sentences disagree. The mutation gate showed the harm: adding an outside
authorization with `signer: none` at `filed_at` moved the bound later, and AP-1, AP-2 and AP-3 went from
SELF_REPORT_ONLY to PRESENT in `f-clock-skew-2min`. Settled for the stated invariant: only a payment record that
qualifies for its own part (AP-5.attempts for a payment request, AP-6.charge for an authorization) counts. This is
pinned by the new case `f-d2-nonqualifying-payment-does-not-move-bound` and by
`test_6_5_nonqualifying_payment_record_does_not_move_agent_bound`. The blind deriver used the first sentence (its note
8), and no case at that point told the readings apart.

**D-3. Changing `failed` to `none` is not a weakening (test construction; founder).** The design's mutation list sets
`check` to `none`, `not_run` or `failed` on every record. On a record that is already `failed`, setting `none` hides a
failure. In `f-m2-*` that turned AP-6 from UNVERIFIABLE to PRESENT. That change makes the record's statement stronger,
not weaker. It has the same power as leaving the record out, which section 8.3 already lists as something a filing
cannot prevent. Settled: the gate only lowers a check, in the order verified_by_other or recomputed, then not_run or
none, then failed (`CHECK_RANK` in the test). The limit is stated in PROFILE.md: a filer can hide a failed check by
leaving the record out, and that is not detectable from the filing.

**D-4. AP-8 `NOT_ACTIVE` in `line_codes` (blind vs author; 8 cases).** Design 7.1 says `line_codes` hold the line-level
codes "from 6.6, 6.7, 6.9 and 6.11". The blind deriver put AP-8's NOT_ACTIVE there. The author and checker treat
NOT_ACTIVE as a part reason, as 6.9 states ("Per part ... NOT_ACTIVE"). The only line-level code 6.9 defines is the
AP-8 DISAGREES, and that cannot be reached (D-6). The line result is the same either way. Settled: author reading.
PROFILE.md now says that `line_codes` never repeat a part reason.

**D-5. A JSON boolean where an enum string is due (blind vs author; 1 case).** For `runs_agent: true` the blind deriver
expected `TYPE` and the author expected `ENUM`. Settled: `ENUM`, because the field is defined as an enum and any value
that is not one of its strings is outside the enum. PROFILE.md states this. The case `f-m6-json-boolean-runs-agent`
lists `ENUM`.

**D-6. The AP-8 DISAGREES branch cannot be reached.** Any record that "makes the permission inactive in the window" has
already made the part NOT_ACTIVE, and NOT_ACTIVE is checked first. The blind deriver found the same (its note 4).
`base-precedence` is therefore NOT_ACTIVE, as design 8.2 intends. The checker keeps no dead branch. PROFILE.md lists
the AP-8 outcomes as NOT_ACTIVE, PRESENT, then the part reasons.

**D-7. Answers that differ from the outline's prototype.** The outline's answers came from a prototype of the older
profile text and were marked "a starting point". 10 `base-*` answers differ under the reviewed rules. Each is listed in
`INDEX.md` with the rule that causes it. 3 of them were planned in design 8.2 (`base-expired-mandate`,
`base-withdrawn-permission`, `base-precedence`). The other 7 follow from rules the review added:

- `base-self-checked-charge`: an unchecked anchor supports nothing bound through it.
- `base-unsupported-aep-version`: person-held records never get UNVERIFIABLE for `not_run` or `none`.
- `base-over-cap-late-approval`: a late person-held approval is SELF_REPORT_ONLY.
- `base-fulfillment-not-arrived`: a claim with nothing to compare against disagrees.
- `base-asked-1-got-2`: the item conflict lands on AP-2 when a mandate is involved.
- `base-failed-signature`: the status record is judged on its own.
- `base-merchant-runs-agent`: an agent-run anchor supports nothing bound through it.

The 2 person-held results (`base-unsupported-aep-version` and `base-over-cap-late-approval`) are reported to the
**founder** as candidates for 0.2. A mandate signed by the person and held by a credentials provider is common.
Calling its unverified signature "self report only" is fail-closed and consistent, but it reads oddly.

**D-8. The blind deriver's other notes.** The excerpt it was given began at section 4, so it did not see the code
precedence in section 1. It ordered NO_OUTSIDE_SOURCE before SELF_REPORT_ONLY, but no case has both on 1 line, so no
answer changed. PROFILE.md states the order next to the line rule. Its notes 6, 7, 12, 13 and 14 match the author's
answers and are recorded in INDEX.md, D-7 or the tests.
