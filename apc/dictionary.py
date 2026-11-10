"""Field dictionary loader and filing validation (design sections 4, 5 and 6.1). Fails closed: any error means INVALID."""
import calendar
import functools
import json
import re
from pathlib import Path

from . import PROFILE_ID

ROOT = Path(__file__).resolve().parent.parent
TOP_REQUIRED = ("profile", "case_id", "case_binding", "aep_bundle", "filed_by", "filed_at", "keepers",
                "records_complete", "records")
TOP_OUTPUT = ("action_time", "lines", "unbound_record_ids")
RECORD_FIELDS = ("id", "party", "party_role", "runs_agent", "operator_affiliated", "kind", "signer", "binding", "ref",
                 "check", "fields")
RECORD_OPTIONAL = ("check_detail",)
ORDER_PAIRS = (("not_before", "expires_at", "lt"), ("active_since", "status_as_of", "le"),
               ("active_since", "effective_at", "lt"), ("first_request_at", "closed_at", "le"))
# Time fields that state when something was observed or done, so they cannot be after the filing (design 4).
# expires_at, not_before and effective_at state future validity and are exempt (see cases/DERIVATION_LOG.md, D-1).
NOT_OBSERVED = ("expires_at", "not_before", "effective_at")


@functools.lru_cache(maxsize=1)
def load_dictionary() -> dict:
    with open(ROOT / "fields.json", encoding="utf-8") as fh:
        return json.load(fh)


def _rx(name):
    return re.compile(load_dictionary()["types"][name])


def parse_time(value) -> int | None:
    """RFC 3339 with offset -> UTC nanoseconds since epoch, or None. Own parser: no datetime.fromisoformat leniency."""
    if not isinstance(value, str):
        return None
    m = _rx("time").match(value)
    if not m or m.end() != len(value):
        return None
    y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
    frac, off = m.group(7), m.group(8)
    if not 1 <= mo <= 12 or y < 1 or not 1 <= d <= calendar.monthrange(y, mo)[1]:
        return None
    if h > 23 or mi > 59 or s > 59:
        return None
    offset = 0
    if off != "Z":
        oh, om = int(off[1:3]), int(off[4:6])
        if oh > 23 or om > 59:
            return None
        offset = (oh * 60 + om) * 60 * (1 if off[0] == "+" else -1)
    days = _days_from_civil(y, mo, d)
    secs = days * 86400 + h * 3600 + mi * 60 + s - offset
    nanos = int((frac[1:] + "000000000")[:9]) if frac else 0
    return secs * 1_000_000_000 + nanos


def _days_from_civil(y, m, d):
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def format_time(ns: int | None) -> str | None:
    if ns is None:
        return None
    secs, nanos = divmod(ns, 1_000_000_000)
    days, rem = divmod(secs, 86400)
    y, m, d = _civil_from_days(days)
    h, rem = divmod(rem, 3600)
    mi, s = divmod(rem, 60)
    out = f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}"
    if nanos:
        out += "." + f"{nanos:09d}".rstrip("0")
    return out + "Z"


def _civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return y + (m <= 2), m, d


def is_token(v) -> bool:
    return isinstance(v, str) and bool(_rx("token").fullmatch(v))


def type_ok(t: str, v, ids: set) -> bool:
    d = load_dictionary()
    if t in ("token", "decimal", "integer", "currency"):
        return isinstance(v, str) and bool(_rx(t).fullmatch(v))
    if t == "time":
        return parse_time(v) is not None
    if t.startswith("enum:"):
        return isinstance(v, str) and v in d["enums"][t[5:]]
    if t == "token_list":
        return isinstance(v, list) and len(v) >= 1 and all(is_token(x) for x in v) and len(set(v)) == len(v)
    if t == "role_list":
        roles = d["enums"]["party_role"]
        return isinstance(v, list) and len(v) >= 1 and all(isinstance(x, str) and x in roles for x in v) \
            and len(set(v)) == len(v)
    if t == "record_ref":
        return is_token(v)
    if t == "charge_list":
        if not isinstance(v, list) or not v:
            return False
        seen = set()
        for c in v:
            if not isinstance(c, dict) or set(c) != {"charge_id", "amount", "currency"}:
                return False
            if not (is_token(c["charge_id"]) and type_ok("decimal", c["amount"], ids) and type_ok("currency", c["currency"], ids)):
                return False
            if c["charge_id"] in seen:
                return False
            seen.add(c["charge_id"])
        return True
    raise ValueError(f"unknown type {t}")


def cond(expr: str, fields: dict) -> bool:
    """The only condition forms allowed in fields.json (design 5.4)."""
    if expr == "always":
        return True
    if expr == "never":
        return False
    if not expr.startswith("when "):
        raise ValueError(f"bad condition {expr}")
    body = expr[5:]
    if body.startswith("has any "):
        return any(n in fields for n in body[8:].split(","))
    if body.startswith("has "):
        return all(n in fields for n in body[4:].split(","))
    if "!=" in body:
        k, v = body.split("!=", 1)
        return k in fields and fields[k] != v
    if "=" in body:
        k, v = body.split("=", 1)
        return k in fields and fields[k] == v
    raise ValueError(f"bad condition {expr}")


def derived_parts(rec: dict) -> list[str]:
    spec = load_dictionary()["kinds"][rec["kind"]]
    out = []
    for p in spec["parts"]:
        if cond(p["when"], rec["fields"]):
            out.append(p["part"].replace("{permission_of}", str(rec["fields"].get("permission_of", ""))))
    return out


def record_time(rec: dict) -> int:
    return parse_time(rec["fields"][load_dictionary()["kinds"][rec["kind"]]["time_field"]])


def validate(filing: object, *, filed: bool) -> list[str]:
    d = load_dictionary()
    errs: list[str] = []
    E = errs.append
    if not isinstance(filing, dict):
        return ["TYPE:filing"]
    allowed_top = set(TOP_REQUIRED) | (set(TOP_OUTPUT) if filed else set())
    for k in filing:
        if k in TOP_OUTPUT and not filed:
            E(f"FIELD_NOT_ALLOWED_IN_CASE:{k}")
        elif k not in allowed_top:
            E(f"UNKNOWN_FIELD:{k}")
    for k in TOP_REQUIRED + (TOP_OUTPUT if filed else ()):
        if k not in filing:
            E(f"MISSING_FIELD:{k}")
    if "profile" in filing and filing["profile"] != PROFILE_ID:
        E("PROFILE_UNSUPPORTED")
    if "case_id" in filing and not is_token(filing["case_id"]):
        E("TYPE:case_id")
    cb = filing.get("case_binding")
    if "case_binding" in filing:
        if not isinstance(cb, dict) or set(cb) != {"kind", "value"}:
            E("TYPE:case_binding")
            cb = None
        else:
            if cb["kind"] not in d["enums"]["binding_kind"]:
                E("ENUM:case_binding.kind")
            if not is_token(cb["value"]):
                E("TYPE:case_binding.value")
    if "aep_bundle" in filing and filing["aep_bundle"] is not None:
        ab = filing["aep_bundle"]
        if not isinstance(ab, dict) or set(ab) != {"chain_id", "sealed_bundle_hash", "spec_version"} \
                or not all(is_token(v) for v in ab.values()):
            E("TYPE:aep_bundle")
        elif isinstance(cb, dict) and cb.get("kind") == "chain_id" and ab["chain_id"] != cb.get("value"):
            E("AEP_CHAIN_MISMATCH")
    if "filed_by" in filing and filing["filed_by"] not in d["enums"]["filed_by"]:
        E("ENUM:filed_by")
    filed_at = parse_time(filing.get("filed_at"))
    if "filed_at" in filing and filed_at is None:
        E("TYPE:filed_at")
    if "keepers" in filing:
        kp = filing["keepers"]
        if not isinstance(kp, dict):
            E("TYPE:keepers")
        else:
            for k, v in kp.items():
                if k not in d["part_keys"]:
                    E(f"KEEPERS_KEY:{k}")
                elif v not in d["enums"]["keeper"]:
                    E(f"ENUM:keepers.{k}")
    if "records_complete" in filing and filing["records_complete"] is not True:
        E("RECORDS_NOT_COMPLETE")
    if filed:
        at = filing.get("action_time")
        if "action_time" in filing and at is not None and parse_time(at) is None:
            E("TYPE:action_time")
        if "lines" in filing and not isinstance(filing["lines"], list):
            E("TYPE:lines")
        if "unbound_record_ids" in filing and not isinstance(filing["unbound_record_ids"], list):
            E("TYPE:unbound_record_ids")
    recs = filing.get("records")
    if "records" in filing:
        if not isinstance(recs, list) or not recs:
            E("TYPE:records")
            recs = []
    else:
        recs = []
    ids, kinds_by_id = [], {}
    for i, r in enumerate(recs):
        if isinstance(r, dict) and is_token(r.get("id")):
            ids.append(r["id"])
            kinds_by_id.setdefault(r["id"], r.get("kind"))
    for x in sorted({x for x in ids if ids.count(x) > 1}):
        E(f"DUPLICATE_RECORD_ID:{x}")
    idset = set(ids)
    for i, r in enumerate(recs):
        errs.extend(_validate_record(r, i, idset, kinds_by_id, filed_at, d))
    return sorted(set(errs))


def _validate_record(r, i, idset, kinds_by_id, filed_at, d) -> list[str]:
    errs: list[str] = []
    if not isinstance(r, dict):
        return [f"TYPE:records[{i}]"]
    rid = r["id"] if is_token(r.get("id")) else f"records[{i}]"
    E = errs.append
    for k in r:
        if k not in RECORD_FIELDS and k not in RECORD_OPTIONAL:
            E(f"UNKNOWN_FIELD:{rid}.{k}")
    for k in RECORD_FIELDS:
        if k not in r:
            E(f"MISSING_FIELD:{rid}.{k}")
    if "id" in r and not is_token(r["id"]):
        E(f"TYPE:{rid}.id")
    for k in ("party", "ref"):
        if k in r and not is_token(r[k]):
            E(f"TYPE:{rid}.{k}")
    for k, enum in (("party_role", "party_role"), ("runs_agent", "tristate"), ("operator_affiliated", "tristate"),
                    ("kind", "kind"), ("signer", "signer"), ("check", "check")):
        if k in r and (not isinstance(r[k], str) or r[k] not in d["enums"][enum]):
            E(f"ENUM:{rid}.{k}")
    if "check_detail" in r:
        if r.get("check") not in ("failed", "not_run"):
            E(f"CHECK_DETAIL_NOT_ALLOWED:{rid}")
        elif r["check_detail"] not in d["enums"]["check_detail"]:
            E(f"ENUM:{rid}.check_detail")
    b = r.get("binding")
    if "binding" in r:
        if not isinstance(b, dict) or set(b) != {"kind", "value", "via"}:
            E(f"TYPE:{rid}.binding")
        else:
            if b["kind"] not in d["enums"]["binding_kind"]:
                E(f"ENUM:{rid}.binding.kind")
            if not is_token(b["value"]):
                E(f"TYPE:{rid}.binding.value")
            if b["via"] is not None:
                if not is_token(b["via"]):
                    E(f"TYPE:{rid}.binding.via")
                elif b["via"] not in idset:
                    E(f"DANGLING_REF:{rid}.binding.via")
    kind = r.get("kind")
    fields = r.get("fields")
    if not isinstance(kind, str) or kind not in d["kinds"] or "fields" not in r:
        return errs
    if not isinstance(fields, dict):
        E(f"TYPE:{rid}.fields")
        return errs
    spec = d["kinds"][kind]
    for name, v in fields.items():
        fs = spec["fields"].get(name)
        if fs is None:
            E(f"UNKNOWN_FIELD:{rid}.fields.{name}")
            continue
        if not cond(fs.get("allowed", "always"), fields):
            E(f"UNKNOWN_FIELD:{rid}.fields.{name}")
            continue
        if not type_ok(fs["type"], v, idset):
            E(f"{'ENUM' if fs['type'].startswith('enum:') else 'TYPE'}:{rid}.fields.{name}")
            continue
        if fs["type"] == "record_ref":
            if v not in idset:
                E(f"DANGLING_REF:{rid}.fields.{name}")
            elif kinds_by_id.get(v) not in fs.get("ref_kinds", []):
                E(f"REF_WRONG_KIND:{rid}.fields.{name}")
    for name, fs in spec["fields"].items():
        if name not in fields and cond(fs["req"], fields):
            E(f"MISSING_FIELD:{rid}.fields.{name}")
    if spec["require_any"] and not any(n in fields for n in spec["require_any"]):
        E(f"MISSING_FIELD:{rid}.fields")
    times = {n: parse_time(v) for n, v in fields.items() if spec["fields"].get(n, {}).get("type") == "time"}
    for a, bname, op in ORDER_PAIRS:
        ta, tb = times.get(a), times.get(bname)
        if ta is not None and tb is not None and not (ta < tb if op == "lt" else ta <= tb):
            E(f"ORDER:{rid}.fields.{a}")
    if filed_at is not None:
        for n, t in times.items():
            if t is not None and n not in NOT_OBSERVED and t > filed_at:
                E(f"AFTER_FILED_AT:{rid}.fields.{n}")
    return errs
