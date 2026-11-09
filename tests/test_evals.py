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
    if case.get("source") == "3d":
        pytest.importorskip("build123d")
    r = evals.run_case(case)
    assert "error" not in r, r.get("error")
    assert r["errors"] == 0, [f for f in r["findings"] if f["severity"] == "error"]
    for view, g in r.get("geo", {}).items():
        assert g["pass"], (view, g)
    if case.get("source") == "3d":  # S6: dimensions inferred from the model are all on the drawing
        assert r["completeness"]["pass"], r["missing"]


def test_summary_counts():
    s = evals.summary(
        [
            {"errors": 0, "warnings": 1, "passed": True, "rounds": 0},
            {"errors": 1, "warnings": 0, "passed": False, "rounds": 3},
        ]
    )
    assert (
        s["cases"] == 2
        and s["zero_error_rate"] == 0.5
        and s["mean_rounds"] == 1.5
        and s["first_pass_rate"] == 0.5
    )


TINY_MODEL = """
from build123d import Box, Cylinder, Pos

def model():
    return (Box(40, 30, 10) - Pos(10, 0, 0) * Cylinder(3, 12)) - Pos(-10, 0, 0) * Cylinder(4.5, 12)
"""

TINY_DRAWING = """
from linercad import Drawing
d = Drawing(sheet="A3")
d.model("model.py")
top = d.view("top")
top.project()
top.center_mark((10, 0), 3, name="h1")
top.center_mark((-10, 0), 4.5, name="h2")
top.dim.linear("L", (-20, -15), (20, -15), value=40, role="overall", side="bottom")
top.dim.linear("W", (20, -15), (20, 15), dir="v", value=30, role="overall", side="right")
top.dim.dia("d6", circle=d.q.circles(view="top", r=3).one())
{more}
front = d.view("front")
front.project()
front.dim.linear("H", (20, 0), (20, 10), dir="v", value=10, role="overall", side="right")
"""


def _tiny(tmp_path, more):
    pytest.importorskip("build123d")
    from linercad.runtime import build
    from linercad.source3d import load_shape

    (tmp_path / "model.py").write_text(TINY_MODEL, encoding="utf-8")
    (tmp_path / "drawing.py").write_text(TINY_DRAWING.format(more=more), encoding="utf-8")
    d = build(tmp_path).d
    return d, load_shape(d, "M.main")


def test_completeness_lists_the_missing_diameter(tmp_path):
    import completeness

    d, shape = _tiny(tmp_path, "")
    out = completeness.compare(d, shape)
    assert [r["name"] for r in out["required"]] == ["Φ6", "Φ9", "L", "W", "H"]
    assert [r["name"] for r in out["missing"]] == ["Φ9"] and not out["pass"]


def test_completeness_passes_once_every_diameter_is_dimensioned(tmp_path):
    import completeness

    d, shape = _tiny(tmp_path, 'top.dim.dia("d9", circle=d.q.circles(view="top", r=4.5).one())')
    out = completeness.compare(d, shape)
    assert out["missing"] == [] and out["pass"]
