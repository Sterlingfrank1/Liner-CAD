"""M1 C8/C10: every L1 / L2 case builds with zero check errors; geometry compared when
build123d is installed (CI 3d job)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

import run as evals  # noqa: E402

CASES = evals.discover()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case):
    r = evals.run_case(case)
    assert "error" not in r, r.get("error")
    assert r["errors"] == 0, [f for f in r["findings"] if f["severity"] == "error"]
    for view, g in r.get("geo", {}).items():
        assert g["pass"], (view, g)


def test_summary_counts():
    s = evals.summary([{"errors": 0, "warnings": 1, "passed": True, "rounds": 0}, {"errors": 1, "warnings": 0, "passed": False, "rounds": 3}])
    assert s["cases"] == 2 and s["zero_error_rate"] == 0.5 and s["mean_rounds"] == 1.5 and s["first_pass_rate"] == 0.5
