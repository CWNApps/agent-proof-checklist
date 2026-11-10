"""Puts the repo root on sys.path so `import apc` works when pytest runs from the repo root."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "cases"


def load_case(case_id: str) -> dict:
    return json.loads((CASES / case_id / "case.json").read_text(encoding="utf-8"))


@pytest.fixture
def base():
    """A fresh copy of the baseline filing (cases/base-baseline/case.json)."""
    return copy.deepcopy(load_case("base-baseline"))
