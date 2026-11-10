"""Case pack runner (design 7.2 and 9). Standard library only."""
import hashlib
import json
from pathlib import Path

from . import MIN_CASES, PACK_VERSION, PROFILE_ID
from .jsonio import StrictJSONError, load_strict
from .procedure import InvalidFiling, derive

MANIFEST = "MANIFEST.sha256"


def first_difference(expected: dict, got: dict) -> str | None:
    """Comparison order of design 7.2; returns the first difference or None."""
    if expected.get("action_time") != got.get("action_time"):
        return "action_time"
    if expected.get("unbound_record_ids") != got.get("unbound_record_ids"):
        return "unbound_record_ids"
    el, gl = expected.get("lines"), got.get("lines")
    if not isinstance(el, list) or len(el) != len(gl):
        return "lines"
    for le, lg in zip(el, gl):
        if not isinstance(le, dict) or le.get("id") != lg["id"]:
            return "lines"
        ln = lg["id"]
        if le.get("result") != lg["result"]:
            return ln
        if le.get("line_codes") != lg["line_codes"]:
            return f"{ln}/line_codes"
        pe, pg = le.get("parts"), lg["parts"]
        if not isinstance(pe, list) or [p.get("part") if isinstance(p, dict) else None for p in pe] != \
                [p["part"] for p in pg]:
            return f"{ln}/parts"
        for a, b in zip(pe, pg):
            if a.get("reason") != b["reason"]:
                return f"{ln}/{b['part']}"
            if a.get("record_ids") != b["record_ids"]:
                return f"{ln}/{b['part']}/record_ids"
    return None


def _error_codes(errors):
    return sorted({e.split(":", 1)[0] for e in errors})


def run_case(case_dir: Path) -> dict:
    case_dir = Path(case_dir)
    cid = case_dir.name
    out = {"case_id": cid, "result": "FAIL", "first_difference": None}
    exp_path = case_dir / "expected.json"
    if not exp_path.is_file():
        out["first_difference"] = "missing_expected"
        return out
    expected = load_strict(exp_path.read_bytes())
    try:
        filing = load_strict((case_dir / "case.json").read_bytes())
        if isinstance(filing, dict) and filing.get("case_id") != cid:
            out["first_difference"] = "CASE_ID_MISMATCH"
            return out
        got = derive(filing)
    except (StrictJSONError, InvalidFiling) as exc:
        codes = [exc.code] if isinstance(exc, StrictJSONError) else _error_codes(exc.errors)
        if isinstance(expected, dict) and expected.get("invalid") is True:
            want = expected.get("error_codes") or []
            if want and set(want) <= set(codes):
                out["result"] = "PASS"
                return out
            out["first_difference"] = "invalid"
            return out
        out["first_difference"] = "invalid:" + ",".join(codes)
        return out
    if isinstance(expected, dict) and expected.get("invalid") is True:
        out["first_difference"] = "invalid"
        return out
    diff = first_difference(expected, got)
    if diff is None:
        out["result"] = "PASS"
    else:
        out["first_difference"] = diff
    return out


def _files(cases_dir: Path) -> list[str]:
    return sorted(p.relative_to(cases_dir).as_posix() for p in cases_dir.rglob("*")
                  if p.is_file() and p.relative_to(cases_dir).as_posix() != MANIFEST)


def manifest_text(cases_dir: Path) -> str:
    cases_dir = Path(cases_dir)
    lines = [f"{hashlib.sha256((cases_dir / rel).read_bytes()).hexdigest()}  {rel}" for rel in _files(cases_dir)]
    return "\n".join(lines) + "\n"


def write_manifest(cases_dir: Path) -> str:
    text = manifest_text(cases_dir)
    (Path(cases_dir) / MANIFEST).write_text(text, encoding="utf-8", newline="\n")
    return text


def manifest_ok(cases_dir: Path) -> bool:
    path = Path(cases_dir) / MANIFEST
    if not path.is_file():
        return False
    return path.read_text(encoding="utf-8") == manifest_text(cases_dir)


def run_pack(cases_dir: Path) -> dict:
    cases_dir = Path(cases_dir)
    results = [run_case(d) for d in sorted(p for p in cases_dir.iterdir() if p.is_dir())]
    passed = sum(r["result"] == "PASS" for r in results)
    return {"profile": PROFILE_ID, "pack_version": PACK_VERSION, "level": "reference", "case_count": len(results),
            "pass_count": passed, "manifest_ok": manifest_ok(cases_dir),
            "summary": f"Passed {passed} of {len(results)} cases, pack {PACK_VERSION}, profile 0.1.",
            "cases": results}


def pack_ok(report: dict) -> bool:
    return report["pass_count"] == report["case_count"] and report["manifest_ok"] and report["case_count"] >= MIN_CASES
