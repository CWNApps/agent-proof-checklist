"""One test per rule and bullet of design sections 6.0 to 6.11, on small edits of the baseline filing."""
import pytest

from apc.procedure import InvalidFiling, derive

D = "2026-11-01T"


def R(f, rid):
    return next(r for r in f["records"] if r["id"] == rid)


def res(f):
    return {ln["id"]: ln["result"] for ln in derive(f)["lines"]}


def part(f, name):
    for ln in derive(f)["lines"]:
        for p in ln["parts"]:
            if p["part"] == name:
                return p
    raise KeyError(name)


def line(f, lid):
    return next(ln for ln in derive(f)["lines"] if ln["id"] == lid)


def agent_side(r):
    r.update(party_role="agent", runs_agent="true", operator_affiliated="true", signer="agent")


def link(f, anchor, rec):
    f["records"].append(rec)
    R(f, anchor)["fields"]["link_tokens"].append(rec["binding"]["value"])


def mk(rid, kind, role, signer, fields, via="auth-1", value=None, check="verified_by_other"):
    return {"id": rid, "party": role + "-co", "party_role": role, "runs_agent": "false",
            "operator_affiliated": "false", "kind": kind, "signer": signer,
            "binding": {"kind": "request_ref", "value": value or rid, "via": via}, "ref": "r-" + rid,
            "check": check, "fields": fields}


def test_baseline(base):
    out = derive(base)
    assert out["action_time"] == D + "10:05:00Z"
    assert out["unbound_record_ids"] == []
    assert res(base) == {"AP-1": "PRESENT", "AP-2": "PRESENT", "AP-3": "PRESENT", "AP-4": "NOT_REQUIRED",
                         "AP-5": "PRESENT", "AP-6": "PRESENT", "AP-7": "PRESENT", "AP-8": "PRESENT"}


def test_derive_invalid_raises(base):
    base["records_complete"] = False
    with pytest.raises(InvalidFiling) as exc:
        derive(base)
    assert "RECORDS_NOT_COMPLETE" in exc.value.errors


def test_derive_strips_output_keys_of_a_filed_filing(base):
    out = derive(base)
    filed = dict(base, **out)
    assert derive(filed) == out


# ---- 6.0 terms ---------------------------------------------------------------------------------------------------
def test_6_0_direct_binding_needs_exact_kind_and_value(base):
    R(base, "auth-1")["binding"]["kind"] = "charge_id"
    assert derive(base)["unbound_record_ids"] == sorted(r["id"] for r in base["records"])


def test_6_0_via_binding_needs_value_in_link_tokens(base):
    R(base, "auth-1")["fields"]["link_tokens"].remove("agentkey-9")
    assert derive(base)["unbound_record_ids"] == ["id-1"]


def test_6_0_via_kind_not_compared(base):
    R(base, "id-1")["binding"]["kind"] = "cart_hash"
    assert derive(base)["unbound_record_ids"] == []


def test_6_0_via_non_anchor_leaves_unbound(base):
    R(base, "id-1")["fields"]  # identity is not an anchor kind
    R(base, "del-1")["binding"]["via"] = "id-1"
    assert "del-1" in derive(base)["unbound_record_ids"]


def test_6_0_depth_at_most_2(base):
    o = R(base, "order-9")
    o["binding"]["via"] = "req-7"
    R(base, "req-7")["fields"]["link_tokens"] = ["order-9"]
    # order is now depth 2; delivery via order would be depth 3
    assert set(derive(base)["unbound_record_ids"]) == {"claim-3", "del-1"}


def test_6_0_status_bound_through_permission_of_blocking_only(base):
    s = R(base, "st-m1")
    s["binding"] = {"kind": "mandate_ref", "value": "elsewhere", "via": None}
    assert derive(base)["unbound_record_ids"] == []
    assert part(base, "AP-8.status:m1")["reason"] == "NOT_CAPTURED"  # bound, but not supported


def test_6_0_supported_needs_supporting_anchor(base):
    R(base, "order-9")["check"] = "not_run"
    assert part(base, "AP-6.delivery")["reason"] == "NOT_CAPTURED"


def test_6_0_unbound_records_used_by_no_rule(base):
    base["records"].append(mk("auth-x", "authorization", "psp", "psp",
                              {"authorized_at": D + "10:05:40Z", "charge_id": "ch-1", "amount": "99.00",
                               "currency": "EUR", "seller": "shopZ"}, via=None, value="ntid-2"))
    out = derive(base)
    assert out["unbound_record_ids"] == ["auth-x"]
    assert res(base)["AP-6"] == "PRESENT"


# ---- 6.2 sides -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("change", [{"party_role": "agent_operator"}, {"runs_agent": "unknown"},
                                   {"operator_affiliated": "true"}, {"signer": "agent"}])
def test_6_2_agent_side(base, change):
    R(base, "del-1").update(change)
    assert part(base, "AP-6.delivery")["reason"] == "SELF_REPORT_ONLY"


def test_6_2_person_held_only_for_person_parts(base):
    R(base, "del-1").update(party_role="person", signer="person")
    assert part(base, "AP-6.delivery")["reason"] == "SELF_REPORT_ONLY"
    assert part(base, "AP-1.person")["reason"] == "PRESENT"  # m1 is person signed


def test_6_2_keeper_none_gives_no_outside_source(base):
    agent_side(R(base, "del-1"))
    base["keepers"] = {"AP-6.delivery": "none"}
    assert part(base, "AP-6.delivery")["reason"] == "NO_OUTSIDE_SOURCE"


# ---- 6.3 action time -----------------------------------------------------------------------------------------------
def test_6_3_unchecked_request_sets_action_time(base):
    link(base, "auth-1", mk("req-0", "payment_request", "psp", "psp",
                            {"logged_at": D + "10:01:00Z", "request_id": "req-0", "amount": "50.00", "currency": "USD",
                             "seller": "shopA"}, check="none"))
    assert derive(base)["action_time"] == D + "10:01:00Z"


def test_6_3_attempt_log_first_request_at_counts_closed_at_does_not(base):
    R(base, "log-3")["fields"]["first_request_at"] = D + "10:02:00Z"
    assert derive(base)["action_time"] == D + "10:02:00Z"


def test_6_3_no_payment_records_gives_null_action_time(base):
    base["case_binding"] = {"kind": "order_id", "value": "order-9"}
    R(base, "order-9")["binding"] = {"kind": "order_id", "value": "order-9", "via": None}
    out = derive(base)
    assert out["action_time"] is None
    assert part(base, "AP-6.order")["reason"] == "PRESENT"
    assert line(base, "AP-8")["result"] != "PRESENT"


def test_6_3_last_payment_time_widens_window(base):
    R(base, "auth-1")["fields"]["authorized_at"] = D + "10:08:00Z"  # after the status_as_of 10:07
    assert part(base, "AP-8.status:m1")["reason"] == "NOT_CAPTURED"


# ---- 6.4 signer rules ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("rid,signer,pname", [
    ("id-1", "person", "AP-1.agent"), ("m1", "merchant", "AP-1.person"), ("log-3", "carrier", "AP-5.related"),
    ("auth-1", "merchant", "AP-6.charge"), ("order-9", "carrier", "AP-6.order"), ("del-1", "psp", "AP-6.delivery"),
])
def test_6_4_signer_rule(base, rid, signer, pname):
    R(base, rid)["signer"] = signer
    assert part(base, pname)["reason"] != "PRESENT"


def test_6_4_charge_needs_payment_party_role(base):
    R(base, "auth-1")["party_role"] = "merchant"
    assert part(base, "AP-6.charge")["reason"] == "NOT_CAPTURED"


def test_6_4_status_role_must_be_in_revocable_by(base):
    R(base, "st-m1")["party_role"] = "issuer"
    assert part(base, "AP-8.status:m1")["reason"] == "NOT_CAPTURED"
    del R(base, "m1")["fields"]["revocable_by"]  # default includes issuer
    assert part(base, "AP-8.status:m1")["reason"] == "PRESENT"


# ---- 6.5 early enough ----------------------------------------------------------------------------------------------
def test_6_5_agent_identity_at_supported_last_payment_is_on_time(base):
    R(base, "id-1")["fields"]["verified_at"] = D + "10:05:30Z"
    assert part(base, "AP-1.agent")["reason"] == "PRESENT"
    R(base, "id-1")["fields"]["verified_at"] = D + "10:05:30.000000001Z"
    assert part(base, "AP-1.agent")["reason"] == "NOT_CAPTURED"


def test_6_5_nonqualifying_payment_record_does_not_move_agent_bound(base):
    R(base, "id-1")["fields"]["verified_at"] = D + "10:07:30Z"
    base["records"].append(mk("auth-z", "authorization", "other", "none",
                              {"authorized_at": D + "10:08:00Z", "charge_id": "ch-1", "amount": "50.00",
                               "currency": "USD", "seller": "shopA"}, via=None, value="ntid-1"))
    base["records"][-1]["binding"]["kind"] = "network_transaction_id"
    assert part(base, "AP-1.agent")["reason"] == "NOT_CAPTURED"


def test_6_5_person_parts_strictly_before_action_time(base):
    R(base, "m1")["fields"]["issued_at"] = D + "10:05:00Z"
    assert part(base, "AP-1.person")["reason"] == "SELF_REPORT_ONLY"


# ---- 6.6 identities ------------------------------------------------------------------------------------------------
def test_6_6_mandate_must_name_case_agent(base):
    R(base, "m1")["fields"]["agent_identity"] = "agent-B"
    assert line(base, "AP-1")["line_codes"] == ["DISAGREES"]
    assert part(base, "AP-2.request")["reason"] == "SELF_REPORT_ONLY"


def test_6_6_empty_case_agent_is_not_disagrees(base):
    R(base, "id-1")["check"] = "none"
    assert line(base, "AP-1")["line_codes"] == []
    assert part(base, "AP-1.person")["reason"] == "SELF_REPORT_ONLY"


def test_6_6_identity_conflict_counts_unqualified_records(base):
    link(base, "auth-1", dict(mk("id-2", "identity", "agent", "agent",
                                 {"verified_at": D + "10:04:00Z", "agent_identity": "agent-Z"}, check="none"),
                              runs_agent="true"))
    assert line(base, "AP-1")["result"] == "DISAGREES"


# ---- 6.7 aggregates ------------------------------------------------------------------------------------------------
def test_6_7_same_charge_id_different_amount_disagrees(base):
    R(base, "log-3")["fields"]["charges"][0]["amount"] = "51.00"
    assert line(base, "AP-6")["result"] == "DISAGREES"


def test_6_7_decimal_compare_by_value(base):
    R(base, "log-3")["fields"]["charges"][0]["amount"] = "50"
    assert res(base)["AP-4"] == "NOT_REQUIRED"


def test_6_7_smallest_cap_of_bound_records(base):
    link(base, "auth-1", mk("tok-1", "token", "issuer", "issuer",
                            {"issued_at": D + "09:30:00Z", "cap": "40.00", "cap_scope": "per_purchase",
                             "currency": "USD"}, check="none"))
    assert res(base)["AP-4"] != "NOT_REQUIRED"


def test_6_7_allowed_sellers_intersection(base):
    R(base, "m1")["fields"]["allowed_sellers"] = ["shopB"]
    assert res(base)["AP-4"] != "NOT_REQUIRED"


def test_6_7_request_missing_from_qualifying_log(base):
    R(base, "log-3")["fields"]["request_ids"] = ["req-other"]
    assert line(base, "AP-5")["line_codes"] == ["DISAGREES"]


def test_6_7_unlisted_charge(base):
    R(base, "log-3")["fields"]["charges"][0]["charge_id"] = "ch-9"
    assert line(base, "AP-5")["line_codes"] == ["DISAGREES"]


def test_6_7_rules_do_not_apply_without_qualifying_log(base):
    R(base, "log-3")["fields"]["request_ids"] = ["req-other"]
    R(base, "log-3")["check"] = "none"
    assert line(base, "AP-5")["line_codes"] == []


# ---- 6.8 AP-4 ------------------------------------------------------------------------------------------------------
def test_6_8_not_required_needs_other_lines_present(base):
    R(base, "del-1")["check"] = "none"
    assert res(base)["AP-4"] == "NOT_CAPTURED"


def test_6_8_cumulative_cap_requires_approval(base):
    R(base, "m1")["fields"]["cap_scope"] = "cumulative"
    assert res(base)["AP-4"] == "NOT_CAPTURED"


def test_6_8_one_item_purchase(base):
    R(base, "order-9")["fields"]["item_id"] = "sku2"
    assert res(base)["AP-4"] == "NOT_CAPTURED"


def _over_cap(f, approval_amount="250.00", at=D + "10:03:00Z"):
    for rid in ("auth-1", "req-7"):
        R(f, rid)["fields"]["amount"] = "250.00"
    R(f, "log-3")["fields"]["charges"][0]["amount"] = "250.00"
    for rid in ("m1", "order-9"):
        del R(f, rid)["fields"]["unit_price"]
    if approval_amount:
        link(f, "auth-1", mk("ap-1", "approval", "credentials_provider", "person",
                             {"approved_at": at, "person_identity": "person-P", "amount": approval_amount,
                              "currency": "USD", "item_id": "sku1"}))


def test_6_8_approval_test_passes(base):
    _over_cap(base)
    assert res(base)["AP-4"] == "PRESENT"


def test_6_8_approval_below_total(base):
    _over_cap(base, approval_amount="249.99")
    assert res(base)["AP-4"] == "SELF_REPORT_ONLY"


def test_6_8_approval_quantity_must_match_orders(base):
    _over_cap(base)
    R(base, "ap-1")["fields"]["quantity"] = "2"
    assert res(base)["AP-4"] != "PRESENT"


# ---- 6.9 AP-8 ------------------------------------------------------------------------------------------------------
def test_6_9_interval_end_exclusive(base):
    R(base, "m1")["fields"]["expires_at"] = D + "10:05:30Z"  # == last payment time
    assert part(base, "AP-8.status:m1")["reason"] == "NOT_ACTIVE"


def test_6_9_not_before_after_action_time(base):
    R(base, "m1")["fields"]["not_before"] = D + "10:05:01Z"
    assert part(base, "AP-8.status:m1")["reason"] == "NOT_ACTIVE"


def test_6_9_unchecked_revocation_still_blocks(base):
    s = R(base, "st-m1")
    s["check"] = "none"
    s["fields"].update(permission_status="suspended", effective_at=D + "10:00:00Z")
    assert part(base, "AP-8.status:m1")["reason"] == "NOT_ACTIVE"


def test_6_9_revoked_after_window_is_active_evidence(base):
    R(base, "st-m1")["fields"].update(permission_status="revoked", effective_at=D + "10:05:31Z")
    assert part(base, "AP-8.status:m1")["reason"] == "PRESENT"


def test_6_9_active_since_must_cover_action_time(base):
    R(base, "st-m1")["fields"]["active_since"] = D + "10:05:00.5Z"
    assert part(base, "AP-8.status:m1")["reason"] == "NOT_CAPTURED"


def test_6_9_one_part_per_permission_and_fallback(base):
    assert [p["part"] for p in line(base, "AP-8")["parts"]] == ["AP-8.status:m1"]
    base["records"] = [r for r in base["records"] if r["id"] not in ("m1", "st-m1")]
    assert line(base, "AP-8")["parts"] == [{"part": "AP-8.status", "reason": "NOT_CAPTURED", "record_ids": []}]


def test_6_9_revoked_mandate_still_supports_ap1_to_ap3(base):
    R(base, "st-m1")["fields"].update(permission_status="revoked", effective_at=D + "10:00:00Z")
    r = res(base)
    assert (r["AP-1"], r["AP-2"], r["AP-3"], r["AP-8"]) == ("PRESENT", "PRESENT", "PRESENT", "NOT_ACTIVE")


# ---- 6.10 checks ---------------------------------------------------------------------------------------------------
def test_6_10_failed_agent_side_blocks(base):
    link(base, "auth-1", dict(mk("del-x", "delivery", "agent", "agent",
                                 {"status_at": "2026-11-02T15:00:00Z", "delivery_status": "delivered"},
                                 check="failed"), runs_agent="true"))
    R(base, "del-x")["binding"]["via"] = "order-9"
    R(base, "order-9")["fields"]["link_tokens"].append("del-x")
    assert part(base, "AP-6.delivery")["reason"] == "UNVERIFIABLE"


def test_6_10_failed_beats_a_qualifying_record(base):
    R(base, "id-1")["check"] = "failed"
    assert part(base, "AP-1.agent")["reason"] == "UNVERIFIABLE"


# ---- 6.11 conflicts, part reasons, lines ---------------------------------------------------------------------------
def test_6_11_1_same_entity_material_field(base):
    link(base, "auth-1", mk("req-7b", "payment_request", "psp", "psp",
                            {"logged_at": D + "10:05:01Z", "request_id": "req-7", "amount": "51.00",
                             "currency": "USD", "seller": "shopA"}))
    R(base, "log-3")["fields"]["request_ids"] = ["req-7"]
    assert line(base, "AP-5")["line_codes"] == ["DISAGREES"]


def test_6_11_1_seller_differs_on_ap6(base):
    R(base, "req-7")["fields"]["seller"] = "shopB"
    assert line(base, "AP-6")["result"] == "DISAGREES"


def test_6_11_1_currency_differs_on_ap6(base):
    R(base, "order-9")["fields"]["currency"] = "EUR"
    assert line(base, "AP-6")["result"] == "DISAGREES"


def test_6_11_1_item_differs_with_mandate_on_ap2(base):
    R(base, "order-9")["fields"]["unit_price"] = "49.00"
    assert line(base, "AP-2")["result"] == "DISAGREES"
    assert line(base, "AP-6")["result"] == "PRESENT"


def test_6_11_1_caps_never_compared(base):
    link(base, "auth-1", mk("tok-1", "token", "issuer", "issuer",
                            {"issued_at": D + "09:30:00Z", "cap": "70.00", "cap_scope": "per_purchase",
                             "currency": "USD"}))
    assert line(base, "AP-3")["line_codes"] == []


def test_6_11_1_later_qualifying_delivery_supersedes(base):
    R(base, "del-1")["fields"]["delivery_status"] = "in_transit"
    R(base, "del-1")["fields"]["status_at"] = "2026-11-01T18:00:00Z"
    link(base, "order-9", dict(mk("del-2", "delivery", "carrier", "carrier",
                                  {"status_at": "2026-11-02T15:00:00Z", "delivery_status": "delivered"},
                                  via="order-9")))
    assert line(base, "AP-7")["result"] == "PRESENT"


def test_6_11_2_claim_amount_needs_both_totals(base):
    R(base, "claim-3")["fields"]["amount"] = "50.00"
    assert line(base, "AP-7")["result"] == "PRESENT"
    R(base, "auth-1")["signer"] = "merchant"  # no longer qualifies for AP-6.charge; log still AP-5.related
    R(base, "log-3")["signer"] = "carrier"    # nothing qualifies: supporting total undefined
    assert line(base, "AP-7")["result"] == "DISAGREES"


def test_6_11_2_claim_field_without_value_disagrees(base):
    R(base, "claim-3")["fields"]["item_id"] = "sku1"
    base["records"] = [r for r in base["records"] if r["kind"] != "order"]
    for rid in ("del-1", "claim-3"):
        R(base, rid)["binding"]["via"] = "auth-1"
    R(base, "auth-1")["fields"]["link_tokens"] += ["trk-77", "claim-3"]
    assert line(base, "AP-7")["result"] == "DISAGREES"


def test_6_11_3_order_of_part_reasons(base):
    m = R(base, "m1")
    m["check"] = "none"
    assert part(base, "AP-2.request")["reason"] == "SELF_REPORT_ONLY"  # person held, not outside
    m["signer"] = "credentials_provider"
    m["party_role"] = "credentials_provider"
    assert part(base, "AP-2.request")["reason"] == "UNVERIFIABLE"  # outside and unchecked


def test_6_11_4_line_takes_earliest_code(base):
    R(base, "del-1")["check"] = "none"
    R(base, "order-9")["fields"]["seller"] = "shopB"
    assert line(base, "AP-6")["result"] == "DISAGREES"


def test_6_11_5_ap7_no_side_test(base):
    assert part(base, "AP-7.claim") == {"part": "AP-7.claim", "reason": "PRESENT", "record_ids": ["claim-3"]}
    base["records"] = [r for r in base["records"] if r["id"] != "claim-3"]
    assert line(base, "AP-7")["result"] == "NOT_CAPTURED"


def test_7_1_shape(base):
    out = derive(base)
    assert [ln["id"] for ln in out["lines"]] == [f"AP-{i}" for i in range(1, 9)]
    assert [p["part"] for p in out["lines"][4]["parts"]] == ["AP-5.attempts", "AP-5.related"]
    assert [p["part"] for p in out["lines"][5]["parts"]] == ["AP-6.charge", "AP-6.order", "AP-6.delivery"]
