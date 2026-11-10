"""fields.json and filing validation (design 5 and 6.1)."""
import copy
import re

import pytest

from apc.dictionary import cond, derived_parts, format_time, load_dictionary, parse_time, validate
from apc.jsonio import StrictJSONError, load_strict

D = load_dictionary()
COND = re.compile(r"^(always|never|when has any [a-z_]+(,[a-z_]+)*|when has [a-z_]+(,[a-z_]+)*|when [a-z_]+!?=[a-z_]+)$")
TYPES = {"token", "decimal", "integer", "currency", "time", "token_list", "role_list", "record_ref", "charge_list"}


def test_every_kind_has_time_field_and_entity_key_entry():
    for name, k in D["kinds"].items():
        assert k["time_field"] in k["fields"], name
        assert k["fields"][k["time_field"]]["type"] == "time", name
        assert k["fields"][k["time_field"]]["req"] == "always", name
        assert "entity_key" in k, name
        assert k["entity_key"] in (None, "@id") or k["entity_key"] in k["fields"], name


def test_every_kind_is_in_the_kind_enum():
    assert set(D["kinds"]) == set(D["enums"]["kind"])


def test_every_type_and_enum_referenced_exists():
    for name, k in D["kinds"].items():
        for fname, fs in k["fields"].items():
            t = fs["type"]
            if t.startswith("enum:"):
                assert t[5:] in D["enums"], (name, fname)
            else:
                assert t in TYPES, (name, fname)
            if t == "record_ref":
                assert set(fs["ref_kinds"]) <= set(D["kinds"])


def test_every_condition_uses_an_allowed_form():
    for name, k in D["kinds"].items():
        for fname, fs in k["fields"].items():
            assert COND.match(fs["req"]), (name, fname, fs["req"])
            assert COND.match(fs.get("allowed", "always")), (name, fname)
        for p in k["parts"]:
            assert COND.match(p["when"]), (name, p)


def test_require_any_on_agent_claim(base):
    claim = next(r for r in base["records"] if r["kind"] == "agent_claim")
    claim["fields"] = {"claimed_at": claim["fields"]["claimed_at"]}
    assert "MISSING_FIELD:claim-3.fields" in validate(base, filed=False)
    claim["fields"]["seller"] = "shopA"
    assert validate(base, filed=False) == []


def test_every_part_key_is_derivable():
    made = set()
    for k in D["kinds"].values():
        for p in k["parts"]:
            made.add(p["part"].split(":")[0])
    assert made == set(D["part_keys"])


def test_mandate_parts_follow_fields(base):
    m = next(r for r in base["records"] if r["id"] == "m1")
    assert derived_parts(m) == ["AP-1.person", "AP-2.request", "AP-3.limits"]
    for f in ("item_id", "cap", "allowed_sellers", "expires_at"):
        del m["fields"][f]
    assert derived_parts(m) == ["AP-1.person"]


def test_status_part_names_its_permission(base):
    s = next(r for r in base["records"] if r["kind"] == "status")
    assert derived_parts(s) == ["AP-8.status:m1"]


@pytest.mark.parametrize("t,good,bad", [
    ("token", ["a", "x" * 128, "ntid-1"], ["", "x" * 129, "a b", "é"]),
    ("decimal", ["0", "50", "50.00", "0.123456"], ["050", "1.", "1.1234567", "-1", "1e3"]),
    ("integer", ["0", "12"], ["01", "-1", "1.0"]),
    ("currency", ["USD"], ["usd", "US", "USDX"]),
])
def test_type_regexes(t, good, bad):
    rx = re.compile(D["types"][t])
    for v in good:
        assert rx.fullmatch(v), v
    for v in bad:
        assert not rx.fullmatch(v), v


@pytest.mark.parametrize("v", ["2026-11-01T10:00:00Z", "2026-11-01T10:00:00.5+05:30", "2024-02-29T23:59:59-23:59",
                               "2026-11-01T10:00:00.123456789Z"])
def test_time_accepts(v):
    assert parse_time(v) is not None


@pytest.mark.parametrize("v", ["2026-11-01T10:04:60Z", "2026-11-31T10:00:00Z", "2025-02-29T10:00:00Z",
                               "2026-11-01T24:00:00Z", "2026-11-01T10:60:00Z", "2026-11-01T10:00:00+24:00",
                               "2026-11-01T10:00:00+05:60", "2026-11-01 10:00:00Z", "2026-11-01T10:00:00",
                               "2026-13-01T10:00:00Z", "0000-01-01T00:00:00Z", 5, None])
def test_time_rejects(v):
    assert parse_time(v) is None


def test_time_offsets_and_format():
    assert parse_time("2026-11-01T12:00:00+02:00") == parse_time("2026-11-01T10:00:00Z")
    assert format_time(parse_time("2026-11-01T10:00:00.500Z")) == "2026-11-01T10:00:00.5Z"
    assert format_time(parse_time("2026-11-01T10:00:00.000Z")) == "2026-11-01T10:00:00Z"
    assert format_time(None) is None


def test_cond_forms():
    f = {"a": "x", "b": "y"}
    assert cond("always", f) and not cond("never", f)
    assert cond("when has a,b", f) and not cond("when has a,c", f)
    assert cond("when has any c,b", f) and not cond("when has any c,d", f)
    assert cond("when a=x", f) and not cond("when a=y", f) and not cond("when c=x", f)
    assert cond("when a!=y", f) and not cond("when a!=x", f) and not cond("when c!=x", f)
    with pytest.raises(ValueError):
        cond("sometimes", f)


# ---- 6.1: one passing and one failing input per code ---------------------------------------------------------------
def _rec(f, rid):
    return next(r for r in f["records"] if r["id"] == rid)


def m_profile(f): f["profile"] = "agent-proof-checklist/0.2"
def m_unknown(f): f["note"] = "x"
def m_missing(f): del _rec(f, "id-1")["fields"]["agent_identity"]
def m_not_allowed(f): f["lines"] = []
def m_type(f): _rec(f, "auth-1")["fields"]["amount"] = "50.0000001"
def m_enum(f): _rec(f, "auth-1")["party_role"] = "bank"
def m_order(f): _rec(f, "m1")["fields"]["not_before"] = "2026-11-09T00:00:00Z"
def m_after(f): _rec(f, "del-1")["fields"]["status_at"] = "2026-11-04T00:00:00Z"
def m_complete(f): f["records_complete"] = "true"
def m_dup(f): _rec(f, "del-1")["id"] = "id-1"
def m_dangling(f): _rec(f, "st-m1")["fields"]["permission_of"] = "m9"
def m_wrong_kind(f): _rec(f, "st-m1")["fields"]["permission_of"] = "auth-1"
def m_detail(f): _rec(f, "auth-1")["check_detail"] = "hash_mismatch"
def m_keepers(f): f["keepers"] = {"AP-9.thing": "none"}


def m_chain(f):
    f["case_binding"] = {"kind": "chain_id", "value": "chain-1"}
    f["aep_bundle"] = {"chain_id": "chain-2", "sealed_bundle_hash": "h1", "spec_version": "1.0.2"}


CODES = {"PROFILE_UNSUPPORTED": m_profile, "UNKNOWN_FIELD": m_unknown, "MISSING_FIELD": m_missing,
         "FIELD_NOT_ALLOWED_IN_CASE": m_not_allowed, "TYPE": m_type, "ENUM": m_enum, "ORDER": m_order,
         "AFTER_FILED_AT": m_after, "RECORDS_NOT_COMPLETE": m_complete, "DUPLICATE_RECORD_ID": m_dup,
         "DANGLING_REF": m_dangling, "REF_WRONG_KIND": m_wrong_kind, "CHECK_DETAIL_NOT_ALLOWED": m_detail,
         "KEEPERS_KEY": m_keepers, "AEP_CHAIN_MISMATCH": m_chain}


@pytest.mark.parametrize("code", sorted(CODES))
def test_6_1_codes(base, code):
    assert validate(base, filed=False) == []
    bad = copy.deepcopy(base)
    CODES[code](bad)
    errs = validate(bad, filed=False)
    assert code in {e.split(":")[0] for e in errs}, errs


def test_6_1_JSON_INVALID():
    assert load_strict(b'{"a": "1"}') == {"a": "1"}
    for raw in (b'\xef\xbb\xbf{"a": "1"}', b'{"a": NaN}', b'{"a": Infinity}', b'{"a": "\xff"}', b'{"a": '):
        with pytest.raises(StrictJSONError) as exc:
            load_strict(raw)
        assert exc.value.code == "JSON_INVALID"


def test_6_1_DUPLICATE_KEY():
    assert load_strict(b'{"a": "1", "b": "2"}') == {"a": "1", "b": "2"}
    with pytest.raises(StrictJSONError) as exc:
        load_strict(b'{"a": "1", "a": "2"}')
    assert exc.value.code == "DUPLICATE_KEY"


def test_6_1_future_validity_fields_may_be_after_filed_at(base):
    """D-1: expires_at, not_before and effective_at state future validity, so they are exempt from AFTER_FILED_AT."""
    assert _rec(base, "m1")["fields"]["expires_at"] > base["filed_at"]
    assert validate(base, filed=False) == []


def test_6_1_filed_requires_output_keys(base):
    errs = validate(base, filed=True)
    assert {"MISSING_FIELD:action_time", "MISSING_FIELD:lines", "MISSING_FIELD:unbound_record_ids"} <= set(errs)


def test_6_1_record_id_suffix_and_index(base):
    _rec(base, "auth-1")["fields"]["amount"] = "x"
    base["records"][1]["id"] = ""
    errs = validate(base, filed=False)
    assert "TYPE:auth-1.fields.amount" in errs
    assert "TYPE:records[1].id" in errs
    assert errs == sorted(errs)


def test_6_1_json_boolean_is_not_a_tristate(base):
    _rec(base, "order-9")["runs_agent"] = True
    assert "ENUM:order-9.runs_agent" in validate(base, filed=False)


def test_6_1_no_json_numbers_in_fields(base):
    _rec(base, "auth-1")["fields"]["amount"] = 50
    assert "TYPE:auth-1.fields.amount" in validate(base, filed=False)


def _paths(obj, path=()):
    yield path
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _paths(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _paths(v, path + (i,))


def test_bad_data_never_crashes(base):
    """Change-brief class 5: any wrong JSON type anywhere is INVALID, never an exception from inside the checker."""
    from apc.procedure import InvalidFiling, derive
    paths = [p for p in _paths(base) if p]
    for p in paths:
        for bad in (None, 5, 1.5, True, [], {}, "", "x" * 200, [None], {"a": None}):
            f = copy.deepcopy(base)
            tgt = f
            for k in p[:-1]:
                tgt = tgt[k]
            tgt[p[-1]] = bad
            try:
                derive(f)
            except InvalidFiling:
                pass
    assert len(paths) > 100
