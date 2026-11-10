"""CLI exit codes and formats (design 7.2), run as a subprocess the way a user runs it."""
import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import CASES, ROOT

FIX = Path(__file__).resolve().parent / "fixtures"


def run(*args):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run([sys.executable, "-m", "apc", *map(str, args)], capture_output=True, text=True, env=env,
                          cwd=str(ROOT.parent), timeout=300)


def test_derive_prints_answers():
    p = run("derive", CASES / "base-baseline" / "case.json")
    assert p.returncode == 0
    assert json.loads(p.stdout) == json.loads((CASES / "base-baseline" / "expected.json").read_text())


def test_derive_invalid_exit_2_sorted_stderr():
    p = run("derive", CASES / "f-m6-bad-time" / "case.json")
    assert p.returncode == 2 and p.stdout == ""
    assert p.stderr.splitlines() == ["TYPE:id-1.fields.verified_at"]


def test_derive_duplicate_key_exit_2():
    p = run("derive", CASES / "f-m6-duplicate-json-key" / "case.json")
    assert p.returncode == 2 and p.stderr.strip() == "DUPLICATE_KEY"


def test_check_pass():
    p = run("check", FIX / "cli_pass.json")
    assert p.returncode == 0 and p.stdout.strip() == "PASS"


def test_check_fail_first_difference():
    p = run("check", FIX / "cli_fail.json")
    assert p.returncode == 1 and p.stdout.strip() == "first_difference: AP-7"


def test_check_invalid():
    p = run("check", FIX / "cli_invalid.json")
    assert p.returncode == 2
    lines = p.stderr.splitlines()
    assert lines == sorted(lines) and "PROFILE_UNSUPPORTED" in lines and "RECORDS_NOT_COMPLETE" in lines


def test_check_needs_output_keys():
    p = run("check", CASES / "base-baseline" / "case.json")
    assert p.returncode == 2 and "MISSING_FIELD:lines" in p.stderr.splitlines()


def test_pack_exit_0_and_out(tmp_path):
    out = tmp_path / "pack.json"
    p = run("pack", CASES, "--out", out)
    assert p.returncode == 0, p.stdout + p.stderr
    rep = json.loads(out.read_text())
    assert rep["pass_count"] == rep["case_count"] and rep["manifest_ok"]


def test_pack_exit_1_on_small_pack(tmp_path):
    d = tmp_path / "cases"
    d.mkdir()
    import shutil
    shutil.copytree(CASES / "base-baseline", d / "base-baseline")
    assert run("manifest", d).returncode == 0
    p = run("pack", d)
    assert p.returncode == 1 and json.loads(p.stdout)["case_count"] == 1
