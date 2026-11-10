"""P-B gate (design 1.1 and 10.2): weakening a record or adding a non-qualifying record never makes an answer better.

For every case that is not INVALID, each mutation below is applied and checked: no line goes from non-PRESENT to
PRESENT, and AP-4 never goes from required (anything but NOT_REQUIRED) to NOT_REQUIRED. Every mutated filing must
pass validation (an INVALID mutation is a test failure). Deterministic, no randomness. The build is not done until
this passes on the full pack.
"""
import copy
import json
from decimal import Decimal

import pytest

from conftest import CASES
from apc.dictionary import NOT_OBSERVED, format_time, load_dictionary, parse_time, validate
from apc.procedure import derive

MIN = 60 * 1_000_000_000
SEC = 1_000_000_000


def _case_ids():
    out = []
    for d in sorted(p for p in CASES.iterdir() if p.is_dir()):
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        if not exp.get("invalid"):
            out.append(d.name)
    return out


def _filing(cid):
    return json.loads((CASES / cid / "case.json").read_text(encoding="utf-8"))


def _field_types(kind):
    return {n: s["type"] for n, s in load_dictionary()["kinds"][kind]["fields"].items()}


def _last_payment(f):
    ts = []
    for r in f["records"]:
        if r["kind"] == "payment_request":
            ts.append(parse_time(r["fields"]["logged_at"]))
        elif r["kind"] == "authorization":
            ts.append(parse_time(r["fields"]["authorized_at"]))
        elif r["kind"] == "attempt_log":
            ts.append(parse_time(r["fields"]["first_request_at"]))
    return max(ts) if ts else None


# ---- weakening mutations -------------------------------------------------------------------------------------------
# A weakening only LOWERS a record's check: verified_by_other/recomputed > not_run/none > failed (fail closed: a failed
# check is the worst statement). Turning `failed` into `none` hides a failure; it has the same power as leaving the
# record out, which 8.3 states as a limit, so it is not a weakening (DERIVATION_LOG D-3).
CHECK_RANK = {"verified_by_other": 2, "recomputed": 2, "not_run": 1, "none": 1, "failed": 0}


def weakenings(f):
    for i, r in enumerate(f["records"]):
        for chk in ("none", "not_run", "failed"):
            if CHECK_RANK[chk] > CHECK_RANK[r["check"]] or chk == r["check"]:
                continue
            g = copy.deepcopy(f)
            g["records"][i]["check"] = chk
            if chk == "none":
                g["records"][i].pop("check_detail", None)
            yield f"{r['id']}:check={chk}", g
        g = copy.deepcopy(f)
        g["records"][i]["runs_agent"] = "unknown"
        yield f"{r['id']}:runs_agent=unknown", g
        g = copy.deepcopy(f)
        g["records"][i]["signer"] = "agent"
        yield f"{r['id']}:signer=agent", g


# ---- adding mutations ----------------------------------------------------------------------------------------------
SIDES = {
    "agent": {"party_role": "agent", "runs_agent": "true", "operator_affiliated": "true", "check": "none"},
    "outside": {"party_role": "other", "signer": "none", "runs_agent": "false", "operator_affiliated": "false",
                "check": "verified_by_other"},
}


def _double(fields, types):
    out = copy.deepcopy(fields)
    for n, v in out.items():
        if types.get(n) == "decimal":
            out[n] = str(Decimal(v) * 2)
        elif types.get(n) == "charge_list":
            for c in v:
                c["amount"] = str(Decimal(c["amount"]) * 2)
    return out


def _suffix(v):
    return (v + "-x")[:128] if len(v) + 2 > 128 else v + "-x"


def _tokens(fields, types, only=None):
    out = copy.deepcopy(fields)
    for n, v in out.items():
        if types.get(n) == "token" and (only is None or n == only):
            out[n] = _suffix(v)
    return out


def _shift(fields, types, kind, delta, filed_at):
    out = copy.deepcopy(fields)
    for n, v in out.items():
        if types.get(n) == "time":
            t = parse_time(v) + delta
            if n not in NOT_OBSERVED:
                t = min(t, filed_at)
            out[n] = format_time(t)
    return out


def additions(f):
    d = load_dictionary()
    filed_at = parse_time(f["filed_at"])
    last = _last_payment(f)
    for r in f["records"]:
        kind = r["kind"]
        types = _field_types(kind)
        tf = d["kinds"][kind]["time_field"]
        rt = parse_time(r["fields"][tf])
        ek = d["kinds"][kind]["entity_key"]
        variants = [("same", r["fields"]), ("double", _double(r["fields"], types)),
                    ("tokens", _tokens(r["fields"], types))]
        if ek not in (None, "@id") and types.get(ek) == "token":
            variants.append(("entity", _tokens(r["fields"], types, only=ek)))
        targets = [("-1m", -MIN), ("+1m", MIN), ("to_filed_at", filed_at - rt)]
        if last is not None:
            targets.append(("after_last", last + SEC - rt))
        for name, delta in targets:
            variants.append((f"time{name}", _shift(r["fields"], types, kind, delta, filed_at)))
        for side, attrs in SIDES.items():
            for vname, fields in variants:
                g = copy.deepcopy(f)
                c = copy.deepcopy(r)
                c.pop("check_detail", None)
                c["id"] = r["id"] + "-m"
                c.update(attrs)
                c["fields"] = copy.deepcopy(fields)
                g["records"].append(c)
                yield f"add {r['id']}-m {side} {vname}", g


def _results(out):
    return {ln["id"]: ln["result"] for ln in out["lines"]}


def _better(before, after):
    bad = []
    for ln, res in before.items():
        if ln == "AP-4":
            if res != "NOT_REQUIRED" and after[ln] == "NOT_REQUIRED":
                bad.append(f"AP-4 {res} -> NOT_REQUIRED")
            if res not in ("PRESENT", "NOT_REQUIRED") and after[ln] == "PRESENT":
                bad.append(f"AP-4 {res} -> PRESENT")
        elif res != "PRESENT" and after[ln] == "PRESENT":
            bad.append(f"{ln} {res} -> PRESENT")
    return bad


@pytest.mark.parametrize("case_id", _case_ids())
def test_monotone(case_id):
    f = _filing(case_id)
    before = _results(derive(f))
    failures, count = [], 0
    for label, g in list(weakenings(f)) + list(additions(f)):
        count += 1
        errs = validate(g, filed=False)
        if errs:
            failures.append(f"{label}: INVALID mutation {errs[:3]}")
            continue
        bad = _better(before, _results(derive(g)))
        if bad:
            failures.append(f"{label}: {bad}")
    assert count > 0
    assert not failures, f"{case_id}: {len(failures)} of {count} mutations broke P-B:\n" + "\n".join(failures[:20])


def test_mutation_list_is_not_empty_for_baseline():
    f = _filing("base-baseline")
    assert sum(1 for _ in weakenings(f)) >= 3 * len(f["records"])
    assert sum(1 for _ in additions(f)) >= 2 * 7 * len(f["records"])


def test_case_list_covers_pack():
    assert len(_case_ids()) >= 55
