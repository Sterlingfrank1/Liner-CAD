"""D7: detail views expose their parent sources and keep assembly hatch style.

G2 first commit: `d.q.detail_sources` does not exist and detail hatch ignores the parent hatch's
angle/spacing, so these fail before the D7 implementation.
"""

from __future__ import annotations

import math

from linercad import Drawing
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
    src = d.q.detail_sources("II")
    assert "H.front.s" in src.ids()
