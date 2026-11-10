"""CLI (design 7.2): derive FILE | check FILE | pack CASES_DIR [--out PATH] | manifest CASES_DIR."""
import argparse
import json
import sys
from pathlib import Path

from .dictionary import validate
from .jsonio import StrictJSONError, load_strict
from .pack import first_difference, pack_ok, run_pack, write_manifest
from .procedure import InvalidFiling, derive


def _invalid(errors) -> int:
    for e in sorted(errors):
        print(e, file=sys.stderr)
    return 2


def _load(path):
    return load_strict(Path(path).read_bytes())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="apc")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("derive").add_argument("file")
    sub.add_parser("check").add_argument("file")
    p = sub.add_parser("pack")
    p.add_argument("cases_dir")
    p.add_argument("--out")
    sub.add_parser("manifest").add_argument("cases_dir")
    a = ap.parse_args(argv)

    if a.cmd in ("derive", "check"):
        try:
            filing = _load(a.file)
        except StrictJSONError as exc:
            return _invalid([exc.code])
        if a.cmd == "check":
            errs = validate(filing, filed=True)
            if errs:
                return _invalid(errs)
        try:
            got = derive(filing)
        except InvalidFiling as exc:
            return _invalid(exc.errors)
        if a.cmd == "derive":
            print(json.dumps(got, indent=2))
            return 0
        diff = first_difference(filing, got)
        if diff is None:
            print("PASS")
            return 0
        print(f"first_difference: {diff}")
        return 1
    if a.cmd == "pack":
        report = run_pack(Path(a.cases_dir))
        text = json.dumps(report, indent=2) + "\n"
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0 if pack_ok(report) else 1
    write_manifest(Path(a.cases_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
