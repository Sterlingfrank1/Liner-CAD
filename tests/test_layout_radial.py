"""D1: radial diameter / radius leaders pick candidates by cost, not just by overlap.

Regression for the v0.1.0 known gap "放射状直径引线避让": an automatically placed
diameter/radius leader on a circular view must not cut another dimension line, must not run
along another line, and must not cross the part outline where the candidate set offers a clean
direction.  Inherent crossings are accepted and, when they are unavoidable, reported in
`placement.resolved` (violations / corridors / crossing objects) per DESIGN §4.6.3.
"""

import math

import pytest

from linercad import txn
from linercad.layout import Arc, Circle, Line, Solid, _cross_point, collinear_overlap
from linercad.runtime import build

EXAMPLES = ["flange", "end_cover", "pulley", "gear_cover", "bearing_support"]


def _segments(pr):
    if isinstance(pr, Line):
        return [(pr.p, pr.q)]
    if isinstance(pr, Circle):
        n = 72
        pts = [
            (
                pr.c[0] + pr.r * math.cos(2 * math.pi * k / n),
                pr.c[1] + pr.r * math.sin(2 * math.pi * k / n),
            )
            for k in range(n + 1)
        ]
        return list(zip(pts, pts[1:]))
    if isinstance(pr, Arc):
        sweep = (pr.a1 - pr.a0) % 360 or 360
        n = max(6, int(math.ceil(sweep / 5)))
        pts = [
            (
                pr.c[0] + pr.r * math.cos(math.radians(pr.a0 + sweep * k / n)),
                pr.c[1] + pr.r * math.sin(math.radians(pr.a0 + sweep * k / n)),
            )
            for k in range(n + 1)
        ]
        return list(zip(pts, pts[1:]))
    if isinstance(pr, Solid):
        pts = list(pr.pts)
        return list(zip(pts, pts[1:] + pts[:1]))
    return []


def _centre(d, e):
    ends = e._resolved.get("ends") or []
    if not ends:
        return None
    ox, oy = d.view(e._intent["view"])._resolved.get("origin", (0.0, 0.0))
    return (
        (ends[0][0] + ends[1][0]) / 2 + ox,
        (ends[0][1] + ends[1][1]) / 2 + oy,
    )


def _avoidable(d, eid):
    """Crossings that a clean candidate direction should have avoided.

    Inherent: another dimension crossing at the shared centre of concentric diameters, circles
    concentric with the dimensioned one (a diametral line always crosses them), and the
    referenced circle itself.
    """
    e = d[eid]
    centre = _centre(d, e)
    if centre is None:
        return {}
    leaders = [(p.p, p.q) for p in e._prims if isinstance(p, Line)]
    dims, outlines, coincident = set(), set(), set()
    for o in d._els.values():
        if o.id == eid or o.id == e._intent.get("circle"):
            continue
        if o.kind == "dim":
            kind = "dim"
        elif o.kind == "edge":
            prims = o._prims
            if prims and all(
                isinstance(pr, (Circle, Arc)) and math.dist(pr.c, centre) < 1e-6 for pr in prims
            ):
                continue  # concentric: inherent
            kind = "outline"
        else:
            continue
        for p, q in leaders:
            for pr in o._prims:
                for r, s in _segments(pr):
                    pt = _cross_point(p, q, r, s)
                    if pt is not None and math.dist(pt, centre) > 0.25:
                        (dims if kind == "dim" else outlines).add(o.id)
                    if o.kind != "edge" and collinear_overlap((p, q), (r, s)) > 0.5:
                        coincident.add(o.id)
    return {
        key: sorted(value)
        for key, value in (("dims", dims), ("outlines", outlines), ("coincident", coincident))
        if value
    }


@pytest.mark.parametrize("name", ["flange", "end_cover", "pulley", "gear_cover", "bearing_support"])
def test_written_angles_are_kept(name, tmp_path):
    if name == "gear_cover":  # 3D-source example: the CI jobs without the optional extra skip it
        pytest.importorskip("build123d")
    p = tmp_path / name
    txn.init(p, from_=name)
    d = build(p).d
    fixed = [
        (e.id, e._layout["at"], e._resolved.get("at"))
        for e in d._els.values()
        if e.kind == "dim" and e._intent.get("circle") and e._layout.get("at") is not None
    ]
    assert all(resolved == written for _id, written, resolved in fixed), fixed


@pytest.mark.parametrize("name", ["flange", "end_cover", "pulley", "gear_cover", "bearing_support"])
def test_auto_radial_leaders_do_not_cut_other_dimensions(name, tmp_path):
    if name == "gear_cover":
        pytest.importorskip("build123d")
    p = tmp_path / name
    txn.init(p, from_=name)
    d = build(p).d
    radial = [
        e
        for e in d._els.values()
        if e.kind == "dim" and e._intent.get("circle") and e._layout.get("at") is None
    ]
    if not radial:
        pytest.skip("this example has no automatically placed circular-view leader")
    bad = {e.id: _avoidable(d, e.id).get("dims") for e in radial if _avoidable(d, e.id).get("dims")}
    assert bad == {}


def _case(case_id):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
    import run as evals

    return next(c for c in evals.discover() if c["id"] == case_id)


def test_gear_blank_pcd_leader_stays_clean(tmp_path):
    case = _case("L2/disc/gear_blank")
    (tmp_path / "drawing.py").write_text(case["drawing_src"], encoding="utf-8")
    d = build(tmp_path).d
    e = d["D.pcd"]
    assert e.placement["auto"] == ["at"]
    assert _avoidable(d, "D.pcd") == {}
    assert "crossings" not in e.placement["resolved"]


def test_unavoidable_crossings_are_reported(tmp_path):
    p = tmp_path / "b"
    txn.init(p, from_="bearing_support")
    d = build(p).d
    e = d["D.dh"]
    resolved = e.placement["resolved"]
    assert "crossings" in resolved and resolved["crossings"]
    assert {v["kind"] for v in resolved["violations"]} == {"outline"}
    assert set(resolved["corridors"]) == {"left", "right", "up", "down"}
    assert "不可避免的交叉" in e.placement["reason"]


def test_pmi_is_placed_around_the_automatic_radial_leaders(tmp_path):
    """PMI on geometry goes first, so a circular leader cannot crowd it afterwards."""
    p = tmp_path / "b"
    txn.init(p, from_="bearing_support")
    res = build(p)
    assert [f for f in res.findings if f["rule"] == "overlap"] == []
    dh = [pr.box for pr in res.d["D.dh"]._prims if hasattr(pr, "box")]
    end = [pr.box for pr in res.d["R.end"]._prims if hasattr(pr, "box")]
    assert dh and end
    assert all(
        not (a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])
        for a, b in ((a, b) for a in dh for b in end)
    )


def test_pmi_on_an_unplaced_dimension_waits_for_it(tmp_path):
    """A leader attached to an automatic circular dimension is placed after that dimension."""
    case = _case("L2/disc/bearing_cap")
    (tmp_path / "drawing.py").write_text(case["drawing_src"], encoding="utf-8")
    res = build(tmp_path)
    assert [f for f in res.findings if f["rule"] == "overlap"] == []


def test_radial_layout_is_deterministic(tmp_path):
    p = tmp_path / "f"
    txn.init(p, from_="flange")
    d1 = build(p).d
    d2 = build(p).d
    for e in d1._els.values():
        if e.kind == "dim":
            assert repr(e._prims) == repr(d2[e.id]._prims), e.id
            assert e._resolved == d2[e.id]._resolved, e.id


# ---- candidate set, inherent crossings and structured reporting (round-2/3 review fixes) ---------


def test_candidate_directions_cover_the_fifteen_degree_grid():
    from linercad.layout import DIA_ANGLES, DIA_ANGLES_MORE

    angles = sorted({*DIA_ANGLES, *DIA_ANGLES_MORE})
    assert angles == list(range(0, 360, 15))
    for wanted in (0, 90, 180, 210, 240, 270, 300, 330):
        assert wanted in angles


def test_contour_crossings_are_analytic_for_circles_and_arcs():
    from linercad.layout import Arc, Circle, _Obstacles

    ob = _Obstacles()
    ob.kinds["E.c"] = "edge"
    ob.add_prims("E.c", [Circle((10.0, 0.0), 2.0, "thick")])
    cand = {"cross": [((-5.0, 0.0), (15.0, 0.0))], "cross_centre": (-50.0, 0.0)}
    # the line cuts the circle through its 0°/180° vertices of any chord approximation
    assert ob.contour_crossings("D.x", cand) == ["E.c"]

    ob2 = _Obstacles()
    ob2.kinds["E.a"] = "edge"
    ob2.add_prims("E.a", [Arc((0.0, 0.0), 10.0, 0.0, 360.0, "thick")])
    cand2 = {"cross": [((-20.0, 0.0), (20.0, 0.0))], "cross_centre": (0.0, 0.0)}
    assert ob2.contour_crossings("D.x", cand2) == []  # concentric arc: inherent

    # a line that only touches an arc end point is not a proper cut (same rule as Line ends)
    ob3 = _Obstacles()
    ob3.kinds["E.q"] = "edge"
    ob3.add_prims("E.q", [Arc((0.0, 0.0), 10.0, 0.0, 90.0, "thick")])
    cand3 = {"cross": [((-20.0, 0.0), (20.0, 0.0))], "cross_centre": (-50.0, 0.0)}
    assert ob3.contour_crossings("D.x", cand3) == []


def test_shared_centre_exemption_only_for_circular_dimensions():
    from linercad.layout import _Obstacles

    ob = _Obstacles()
    ob.ann.add("D.lin")
    ob.add("D.lin", segs=[((0.0, -5.0), (0.0, 5.0))])
    ob.centres["D.lin"] = (0.0, 0.0)
    cand = {"cross": [((-5.0, 0.0), (5.0, 0.0))], "cross_ignore": [((0.0, 0.0), 0.5)]}
    # a linear dimension crossing at the centre is not an inherent concentric-dimension crossing
    assert ob.crossings("D.circ", cand) == ["D.lin"]
    ob.radial.add("D.lin")  # only circular dimensions share the inherent centre
    assert ob.crossings("D.circ", cand) == []


def test_space_conflicts_are_reported_on_the_radial_dimension(monkeypatch):
    from linercad import Drawing
    from linercad import layout as layout_mod

    original = layout_mod._Obstacles.conflicts

    def conflicts(self, owner, cand, clearance):
        if owner == "D.D":
            return [("T.frame", 1.5)]
        return original(self, owner, cand, clearance)

    monkeypatch.setattr(layout_mod._Obstacles, "conflicts", conflicts)
    d = Drawing()
    v = d.view("left")
    v.circle((0.0, 0.0), 10.0, name="c")
    v.dim.dia("D", circle="E.left.c.1")
    layout_mod.layout(d)
    resolved = d["D.D"].placement["resolved"]
    assert [v["kind"] for v in resolved["violations"]] == ["overlap"]
    assert resolved["violations"][0]["with"] == "T.frame"
    assert set(resolved["corridors"]) == {"left", "right", "up", "down"}


def test_fixed_pmi_is_placed_before_automatic_dimensions(monkeypatch):
    from linercad import Drawing
    from linercad import layout as layout_mod

    order = []
    original = layout_mod._ViewLayout.choose

    def spy(self, el, cands, auto_fields):
        order.append(el._id)
        return original(self, el, cands, auto_fields)

    monkeypatch.setattr(layout_mod._ViewLayout, "choose", spy)
    d = Drawing()
    v = d.view("front")
    v.rect((0.0, 0.0), 40.0, 20.0, name="b")
    v.datum("A", ref="E.front.b.1", at=0, length=8)
    v.dim.linear("x", (0.0, 0.0), (40.0, 0.0))
    layout_mod.layout(d)
    assert d["DT.A"].placement["resolved"]["at"] == 0
    assert d["D.x"].placement["resolved"]["side"] == "bottom"
    assert order.index("DT.A") < order.index("D.x")
