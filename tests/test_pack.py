"""Case pack: every case reproduces expected.json, manifest matches, case floor, case ids (design 9 and 7.2)."""
import json
import shutil

import pytest

from conftest import CASES
from apc import MIN_CASES, PACK_VERSION
from apc.pack import first_difference, manifest_ok, pack_ok, run_case, run_pack, write_manifest

CASE_DIRS = sorted(p for p in CASES.iterdir() if p.is_dir())


@pytest.mark.parametrize("case_dir", CASE_DIRS, ids=[p.name for p in CASE_DIRS])
def test_case_reproduces_expected(case_dir):
    r = run_case(case_dir)
    assert r == {"case_id": case_dir.name, "result": "PASS", "first_difference": None}


def test_case_ids_equal_folder_names():
    for d in CASE_DIRS:
        raw = (d / "case.json").read_bytes()
        if b'"case_id": "' + d.name.encode() + b'"' not in raw:
            pytest.fail(d.name)


def test_manifest_matches():
    assert manifest_ok(CASES)


def test_case_floor_and_base_count():
    assert len(CASE_DIRS) >= MIN_CASES
    assert sum(d.name.startswith("base-") for d in CASE_DIRS) == 20
    assert sum(d.name.startswith("f-") for d in CASE_DIRS) >= 34


def test_run_pack_report():
    rep = run_pack(CASES)
    assert pack_ok(rep)
    assert rep["summary"] == f"Passed {rep['pass_count']} of {rep['case_count']} cases, pack {PACK_VERSION}, profile 0.1."
    assert rep["level"] == "reference"


def test_index_lists_every_case():
    index = (CASES / "INDEX.md").read_text(encoding="utf-8")
    for d in CASE_DIRS:
        assert f"`{d.name}`" in index, d.name


@pytest.fixture
def tmp_cases(tmp_path):
    dst = tmp_path / "cases"
    dst.mkdir()
    for name in ("base-baseline", "f-m6-bad-time"):
        shutil.copytree(CASES / name, dst / name)
    write_manifest(dst)
    return dst


def test_manifest_detects_change_missing_and_unlisted(tmp_cases):
    assert manifest_ok(tmp_cases)
    p = tmp_cases / "base-baseline" / "expected.json"
    p.write_bytes(p.read_bytes() + b" ")
    assert not manifest_ok(tmp_cases)
    write_manifest(tmp_cases)
    (tmp_cases / "extra.txt").write_text("x")
    assert not manifest_ok(tmp_cases)
    (tmp_cases / "extra.txt").unlink()
    assert manifest_ok(tmp_cases)
    (tmp_cases / "f-m6-bad-time" / "expected.json").unlink()
    assert not manifest_ok(tmp_cases)


def test_missing_expected_and_case_id_mismatch(tmp_cases):
    (tmp_cases / "f-m6-bad-time" / "expected.json").unlink()
    assert run_case(tmp_cases / "f-m6-bad-time")["first_difference"] == "missing_expected"
    moved = tmp_cases / "renamed"
    (tmp_cases / "base-baseline").rename(moved)
    assert run_case(moved)["first_difference"] == "CASE_ID_MISMATCH"


def test_invalid_expectations(tmp_cases):
    d = tmp_cases / "f-m6-bad-time"
    (d / "expected.json").write_text(json.dumps({"invalid": True, "error_codes": ["ORDER"]}))
    assert run_case(d)["first_difference"] == "invalid"
    b = tmp_cases / "base-baseline"
    (b / "expected.json").write_text(json.dumps({"invalid": True, "error_codes": ["TYPE"]}))
    assert run_case(b)["first_difference"] == "invalid"
    exp = json.loads((CASES / "base-baseline" / "expected.json").read_text())
    (d / "expected.json").write_text(json.dumps(exp))
    assert run_case(d)["first_difference"] == "invalid:TYPE"


def test_pack_fails_below_floor(tmp_cases):
    rep = run_pack(tmp_cases)
    assert rep["pass_count"] == rep["case_count"] == 2 and rep["manifest_ok"]
    assert not pack_ok(rep)


@pytest.mark.parametrize("path,value,want", [
    (("action_time",), "x", "action_time"),
    (("unbound_record_ids",), ["x"], "unbound_record_ids"),
    (("lines", 3, "result"), "PRESENT", "AP-4"),
    (("lines", 4, "line_codes"), ["DISAGREES"], "AP-5/line_codes"),
    (("lines", 4, "parts", 1, "part"), "AP-5.other", "AP-5/parts"),
    (("lines", 5, "parts", 2, "reason"), "NOT_CAPTURED", "AP-6/AP-6.delivery"),
    (("lines", 5, "parts", 0, "record_ids"), [], "AP-6/AP-6.charge/record_ids"),
])
def test_first_difference_order(path, value, want):
    exp = json.loads((CASES / "base-baseline" / "expected.json").read_text())
    got = json.loads(json.dumps(exp))
    assert first_difference(exp, got) is None
    tgt = exp
    for k in path[:-1]:
        tgt = tgt[k]
    tgt[path[-1]] = value
    assert first_difference(exp, got) == want


@pytest.mark.parametrize("case_dir", CASE_DIRS, ids=[p.name for p in CASE_DIRS])
def test_record_order_does_not_change_answers(case_dir):
    """Change-brief class 4: the answer is the same whatever order the records are listed in."""
    from apc.jsonio import StrictJSONError, load_strict
    from apc.procedure import InvalidFiling, derive
    try:
        f = load_strict((case_dir / "case.json").read_bytes())
        out = derive(f)
    except (StrictJSONError, InvalidFiling):
        return
    f["records"].reverse()
    assert derive(f) == out
    f["records"] = f["records"][1::2] + f["records"][0::2]
    assert derive(f) == out
