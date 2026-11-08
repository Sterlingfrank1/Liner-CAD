"""M1 C8: HLR projection and geometry comparison (needs linercad[3d]; skipped otherwise)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("build123d")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

import geocmp  # noqa: E402
from build123d import Cylinder, Pos, Rot  # noqa: E402

from linercad import Drawing, hlr  # noqa: E402


def sleeve_model():
    x = Rot(0, 90, 0)
    return Pos(25, 0, 0) * x * Cylinder(20, 50) - Pos(25, 0, 0) * x * Cylinder(10, 50)


def sleeve_drawing(bore=10):
    d = Drawing()
    d.view("front").turned("s", [(0, 20), (50, 20)], bore=[(0, bore), (50, bore)], cut="full")
    return d


def test_view_axes_match_the_drawing_convention():
    m = Pos(5, 0, 0) * Rot(0, 90, 0) * Cylinder(3, 10)  # x 0..10
    for view, (lo, hi) in (("front", (0, 10)), ("top", (0, 10)), ("left", (-3, 3))):
        pts = [p for pl in hlr.project(m, view)["visible"] for p in pl]
        assert min(p[0] for p in pts) == pytest.approx(lo, abs=1e-6), view
        assert max(p[0] for p in pts) == pytest.approx(hi, abs=1e-6), view


def test_correct_section_passes_and_wrong_one_fails():
    proj = hlr.section_project(sleeve_model(), "front", "full")
    ok = geocmp.compare(sleeve_drawing(10), "front", proj)
    assert ok["pass"], ok
    bad = geocmp.compare(sleeve_drawing(11), "front", proj)
    assert not bad["pass"] and bad["unmatched_drawing"]


def test_removed_section_slice_uses_section_axes():
    m = sleeve_model()
    d = Drawing()
    d.view("front").turned("s", [(0, 20), (50, 20)], bore=[(0, 10), (50, 10)])
    sec = d.removed_section("A", parent="front", through=[(25, -25), (25, 25)])
    sec.circle((0, 0), 20, name="o")
    sec.circle((0, 0), 10, name="i")
    v = sec._intent
    res = geocmp.compare(d, "A", hlr.slice_view(m, "front", v["trace"], v["axes"]))
    assert res["pass"], res
