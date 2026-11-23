"""D6: GB/T 4459.1 screwed-connection representation (G2 first commit).

These tests fail on the pre-D6 state (View.thread_mesh / assembly.thread_engagement do not exist).
"""

from __future__ import annotations

import pytest

from linercad import Drawing
from linercad.errors import InvalidArgument


def _view():
    d = Drawing()
    return d.view("front")


def _feat(v):
    return v.thread_mesh("joint", "M10", screw=(0, 50), hole=(20, 70), outer=12)


def _edges(f):
    return [e._intent for e in f.edges]


def _at(edges, x, tol=1e-6):
    """Edges that span axial coordinate x (line p1/p2 x-range contains x)."""
    out = []
    for e in edges:
        xs = sorted((e["p1"][0], e["p2"][0]))
        if xs[0] - tol <= x <= xs[1] + tol:
            out.append(e)
    return out


def test_engaged_region_is_drawn_as_external_thread():
    v = _view()
    f = _feat(v)
    edges = _edges(f)
    d1 = f._intent["d1"]
    # free external thread 0..20: major thick, minor thin (no internal lines there)
    free = _at(edges, 10)
    assert [e["role"] for e in free if abs(abs(e["p1"][1]) - 5) < 1e-6] == ["thick", "thick"]
    assert [e["role"] for e in free if abs(abs(e["p1"][1]) - d1 / 2) < 1e-6] == ["thin", "thin"]
    # engaged 20..50: external thread only, no duplicated internal crest/root lines there
    eng = _at(edges, 35)
    assert sorted(e["role"] for e in eng if abs(abs(e["p1"][1]) - 5) < 1e-6) == ["thick", "thick"]
    assert sorted(e["role"] for e in eng if abs(abs(e["p1"][1]) - d1 / 2) < 1e-6) == [
        "thin",
        "thin",
    ]
    # unengaged internal 50..70: minor thick, major thin
    inner = _at(edges, 60)
    assert any(e["role"] == "thick" and abs(abs(e["p1"][1]) - d1 / 2) < 1e-6 for e in inner)
    assert any(e["role"] == "thin" and abs(e["p1"][1]) >= 5 - 1e-6 for e in inner)


def test_hole_end_face_line_stops_at_the_minor_diameter():
    v = _view()
    f = _feat(v)
    face = [
        e
        for e in _edges(f)
        if abs(e["p1"][0] - 20) < 1e-6 and abs(e["p2"][0] - 20) < 1e-6 and e["role"] == "thick"
    ]
    assert len(face) == 2  # one above, one below the axis
    d1 = f._intent["d1"]
    for e in face:
        inner = min(abs(e["p1"][1]), abs(e["p2"][1]))
        assert inner == pytest.approx(d1 / 2, abs=1e-6)
        assert max(abs(e["p1"][1]), abs(e["p2"][1])) == pytest.approx(12.0)


def test_engagement_is_the_axial_overlap_of_screw_and_hole():
    from linercad.assembly import thread_engagement

    assert thread_engagement((0, 50), (20, 70)) == (20, 50)
    with pytest.raises(InvalidArgument) as ei:
        thread_engagement((0, 10), (20, 70))
    assert ei.value.candidates


def test_hatch_loops_reach_the_external_thread_major_diameter():
    from linercad.assembly import thread_hatch_loops

    loops = thread_hatch_loops("M10", screw=(0, 50), hole=(20, 70), outer=12, axis=0)
    assert len(loops) == 2  # above and below the axis
    for loop in loops:
        ys = [p[1] for p in loop]
        # material starts at the external thread crest, not at the internal minor diameter
        assert min(abs(y) for y in ys) == pytest.approx(5.0)
        assert max(abs(y) for y in ys) == pytest.approx(12.0)


def test_thread_mesh_rejects_a_missing_engagement():
    from linercad.features import thread_mesh

    with pytest.raises(InvalidArgument):
        thread_mesh(_view(), "joint", "M10", screw=(0, 10), hole=(20, 40), outer=12)


def test_assembly_thread_connection_builds_and_draws_the_joint(tmp_path):
    drawing = """from linercad import Drawing
from linercad.assembly import thread_hatch_loops

d = Drawing(kind="assembly", sheet="A3")
v = d.view("front")
for y in (-12, 12):
    v.line((20, y), (70, y), name="nut_top" if y > 0 else "nut_bottom")
v.line((20, -12), (20, 12), name="nut_left")
v.line((70, -12), (70, 12), name="nut_right")
v.hatch("nut", loops=thread_hatch_loops("M10", screw=(0, 50), hole=(20, 70), outer=12))
v.thread_mesh("joint", "M10", screw=(0, 50), hole=(20, 70), outer=12)
v.dim.thread("t", "F.front.joint")
d.title(name="螺纹连接", drawing_no="LC-TH-01")
"""
    (tmp_path / "drawing.py").write_text(drawing, encoding="utf-8")
    from linercad import runtime

    r = runtime.build(tmp_path)
    errs = [f for f in r.findings if f["severity"] == "error"]
    assert not errs, errs
    f = r.d["F.front.joint"]
    assert f._intent["engaged"] == [20.0, 50.0]
    assert all(e._prims for e in f.edges)
    hatch = r.d["H.front.nut"]
    assert hatch._prims
    ys = [p[1] for loop in hatch._intent["loops"] for p in loop["points"]]
    assert min(abs(y) for y in ys) == pytest.approx(5.0)
    assert max(abs(y) for y in ys) == pytest.approx(12.0)
