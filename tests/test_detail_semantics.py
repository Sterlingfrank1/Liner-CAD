"""D7: detail views expose their parent sources and keep assembly hatch style.

G2 first commit: `d.q.detail_sources` does not exist and detail hatch ignores the parent hatch's
angle/spacing, so these fail before the D7 implementation.
"""

from __future__ import annotations

import math

import pytest

from linercad import Drawing
from linercad.errors import InvalidArgument
from linercad.layout import Line


def _hatch_angles(prims):
    out = []
    for p in prims:
        if isinstance(p, Line) and p.layer == "hatch":
            a = math.degrees(math.atan2(p.q[1] - p.p[1], p.q[0] - p.p[0])) % 180
            out.append(round(a, 3))
    return out


def test_detail_sources_are_queryable():
    d = Drawing()
    f = d.view("front")
    f.line((0, 0), (40, 0), name="base")
    f.circle((20, 10), 5, name="hole")
    d.detail("I", parent="front", center=(20, 5), r=10, scale="2:1")
    from linercad.layout import layout

    layout(d)
    src = d.q.detail_sources("I")
    ids = set(src.ids())
    assert "E.front.base.1" in ids and "E.front.hole.1" in ids
    assert all(e._intent.get("view") == "front" for e in src)
    assert d["V.I"]._intent["detail_sources"]


def test_detail_hatch_keeps_the_parent_angle_and_spacing():
    d = Drawing()
    f = d.view("front")
    f.turned("s", [(0, 20), (50, 20)], bore=[(0, 10), (50, 10)], cut="full")
    h = d["H.front.s"]
    h._intent["angle"] = 30.0
    h._intent["spacing"] = 4.0
    det = d.detail("II", parent="front", center=(20, 15), r=6, scale="2:1")
    from linercad.layout import layout

    layout(d)
    angles = _hatch_angles(det._prims)
    assert angles and all(abs(a - 30.0) <= 1e-6 for a in angles), angles
    # the parent spacing is 4 mm: project midpoints on the hatch normal and check the gaps
    normal = (-math.sin(math.radians(30.0)), math.cos(math.radians(30.0)))
    offsets = sorted(
        {
            round(
                ((p.p[0] + p.q[0]) / 2) * normal[0] + ((p.p[1] + p.q[1]) / 2) * normal[1],
                6,
            )
            for p in det._prims
            if isinstance(p, Line) and p.layer == "hatch"
        }
    )
    gaps = [round(b - a, 6) for a, b in zip(offsets, offsets[1:])]
    assert gaps and all(abs(g - 4.0) <= 0.02 for g in gaps), gaps
    src = d.q.detail_sources("II")
    assert "H.front.s" in src.ids()


def test_detail_sources_before_layout_raises_a_helpful_error():
    d = Drawing()
    d.view("front").line((0, 0), (10, 0), name="base")
    d.detail("I", parent="front", center=(5, 0), r=4, scale="2:1")
    with pytest.raises(InvalidArgument, match="build/layout|没有裁剪结果"):
        d.q.detail_sources("I")
