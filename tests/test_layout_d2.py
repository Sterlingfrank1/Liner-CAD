"""D2: multi-layer dimension avoidance — concentric dims, nesting, outline, keyway text, PMI.

G2 (first commit of the D2 PR): these tests failed on the D1 state and are made to pass by the
layout / pmi_layout changes.  They state the acceptance of issue #84: same-side nesting (small
inside / large outside), multi-layer dimension lines not crossing each other or the outline,
text clear of its own line, the crowded right side of the pulley (PMI leaders vs dimension
lines), and the two D1 review minors (concentric arcs are not inherent; collinear PMI
attachment is reported instead of silent).
"""

import math

import pytest

from linercad import Drawing, place, txn
from linercad.layout import Text, _crosses, layout
from linercad.runtime import build


def _eval_case(case_id):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
    import run as evals

    return next(c for c in evals.discover() if c["id"] == case_id)


def _build_eval(tmp_path, case_id):
    case = _eval_case(case_id)
    if case.get("source") == "3d":  # 3D 来源需要可选依赖：CI 上没装 build123d 就跳过该参数
        pytest.importorskip("build123d")
    (tmp_path / "drawing.py").write_text(case["drawing_src"], encoding="utf-8")
    if case.get("source") == "3d" and case.get("dir"):
        for f in case["dir"].iterdir():
            if f.is_file() and f.suffix in (".py", ".step", ".stp") and f.name != "drawing.py":
                (tmp_path / f.name).write_bytes(f.read_bytes())
    return build(tmp_path, dxf=False).d


def _ids(findings):
    return {f["id"] for f in findings}


def test_concentric_diameter_pair_does_not_cross_on_a_circular_view():
    d = Drawing()
    v = d.view("left")
    v.circle((0, 0), 30, name="outer")
    v.circle((0, 0), 15, name="bore")
    v.dim.dia("Do", circle="E.left.outer.1", at=45)
    v.dim.dia("Di", circle="E.left.bore.1", at=135)
    layout(d)
    found, _ = place.place_dim_cross(d)
    assert not ({"D.Do", "D.Di"} & _ids(found))


@pytest.mark.parametrize(
    "case_id, ids",
    [
        ("L2/box/bearing_seat", {"D.Db", "D.dp"}),
        ("L2/fork/bearing_support", {"D.D", "D.d"}),
        ("L2/fork/link", {"D.D1", "D.d1", "D.D2", "D.d2"}),
    ],
)
def test_concentric_diameters_in_the_eval_set_do_not_cross(tmp_path, case_id, ids):
    d = _build_eval(tmp_path, case_id)
    found, _ = place.place_dim_cross(d)
    assert not (ids & _ids(found))


@pytest.mark.parametrize("case_id", ["L2/disc/pulley", "L2/box/gear_pump_body"])
def test_automatic_dimension_lines_do_not_cross_the_outline(tmp_path, case_id):
    """Written side=inside dimensions stay where they were written (DESIGN §4.6.2); the
    automatic ones must keep their dimension line clear of the outline."""
    d = _build_eval(tmp_path, case_id)
    found, _ = place.place_dim_outline(d)
    auto = [f["id"] for f in found if d[f["id"]]._layout.get("side") is None]
    assert auto == []


@pytest.mark.parametrize(
    "case_id, ids",
    [
        ("L2/box/bearing_seat", {"D.Hc"}),
        ("L2/box/gearbox_base", {"D.Hc", "D.Ai"}),
    ],
)
def test_small_dimension_inside_large_one_on_the_same_side(tmp_path, case_id, ids):
    d = _build_eval(tmp_path, case_id)
    found, _ = place.place_nesting(d)
    assert not (ids & _ids(found))


def test_keyway_tolerance_text_does_not_overlap_its_own_line(tmp_path):
    d = _build_eval(tmp_path, "L1/keyway_d28")
    found, _ = place.place_text_overlap(d)
    assert "D.kd" not in _ids(found)


def _pmi_leader_crossings(d):
    """PMI structural leaders cutting another dimension's *dimension line*.

    The leader segments are read from ``placement.resolved["leader"]``; taking the longest
    Line primitive would pick a shoulder or frame edge and hide a real crossing.
    """
    dims = {}
    for e in d._els.values():
        info = place._dim_info(e)
        if info is None:
            continue
        dims[e.id] = [(seg.p, seg.q) for seg in place._dim_segments(info[1])]
    out = set()
    for e in d._els.values():
        if e.kind not in ("datum", "gtol", "rough"):
            continue
        for seg in e._resolved.get("leader") or ():
            a, b = tuple(seg[0]), tuple(seg[1])
            for oid, osegs in dims.items():
                if oid == e._intent.get("ref"):
                    continue
                if any(_crosses(a, b, p, q) for p, q in osegs):
                    out.add((e.id, oid))
    return out


def test_pulley_right_side_leaders_do_not_cross_dimension_lines(tmp_path):
    p = tmp_path / "pulley"
    txn.init(p, from_="pulley")
    d = build(p, dxf=False).d
    assert _pmi_leader_crossings(d) == set()


def test_coincident_pmi_attachment_is_reported(tmp_path):
    p = tmp_path / "bearing_support"
    txn.init(p, from_="bearing_support")
    d = build(p, dxf=False).d
    resolved = d["G.par"].placement["resolved"]
    assert resolved.get("coincident_with_ref"), resolved
    assert any(
        item["with"] == "D.d" and item["length"] > 2.0 for item in resolved["coincident_with_ref"]
    )


def test_multi_layer_layout_is_deterministic(tmp_path):
    snaps = []
    for name in ("p1", "p2"):
        p = tmp_path / name
        txn.init(p, from_="pulley")
        d = build(p, dxf=False).d
        snaps.append(
            {
                e.id: (repr(e._prims), {k: repr(v) for k, v in sorted(e._resolved.items())})
                for e in d._els.values()
            }
        )
    assert snaps[0] == snaps[1]


def test_written_view_at_is_not_moved_by_the_frame_clamp():
    d = Drawing()
    v = d.view("front")
    v.circle((0, 0), 20, name="c")
    v.dim.dia("D", circle="E.front.c.1", at=45)
    v.place(at=(360, 25))
    layout(d)
    assert v._resolved["origin"] == [360.0, 25.0]


def test_written_at_on_a_secondary_view_is_absolute_too():
    d = Drawing()
    front = d.view("front")
    front.rect((0, 0), 80, 40, name="b")
    left = d.view("left")
    left.rect((0, 0), 40, 20, name="c")
    left.place(at=(300, 100))
    layout(d)
    assert left._resolved["origin"] == [300.0, 100.0]


def _text_centres(d, eid):
    out = []
    for p in d[eid]._prims:
        if isinstance(p, Text):
            out.append(((p.box[0] + p.box[2]) / 2, (p.box[1] + p.box[3]) / 2))
    return out


def _inside_hatch(d, pt):
    from linercad.layout import Hatch, _point_in_poly

    for e in d._els.values():
        if e.kind != "hatch":
            continue
        loops = [lp for pr in e._prims if isinstance(pr, Hatch) for lp in pr.loops]
        k = 0
        for lp in loops:
            if lp and lp[0] == "circle":
                k += 1 if math.dist(pt, lp[1]) <= lp[2] else 0
            else:
                k += 1 if _point_in_poly(pt, lp) else 0
        if k % 2 == 1:
            return True
    return False


def test_text_inside_section_lining_is_moved_out_but_keeps_its_written_fields():
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 120, 60, name="body")
    f.hatch("h", loops=["F.front.body"])
    f.dim.linear("inside", (20, 20), (100, 20), value=80, side="inside")
    layout(d)
    (centre,) = _text_centres(d, "D.inside")
    assert not _inside_hatch(d, centre)  # the text is legible: it left the lining
    assert d["D.inside"]._layout == {"side": "inside"}  # written field untouched


def test_text_clear_of_the_lining_is_not_shifted():
    def build(with_hatch):
        d = Drawing(sheet="A3")
        f = d.view("front")
        f.rect((0, 0), 120, 60, name="body")
        if with_hatch:
            f.hatch("h", loops=["F.front.body"])
        f.dim.linear("t", (20, 55), (100, 55), value=80, side="top")
        layout(d)
        return d

    with_hatch, without = build(True), build(False)
    assert _text_centres(with_hatch, "D.t") == _text_centres(without, "D.t")


def test_repair_passes_do_not_move_written_elements(tmp_path, monkeypatch):
    import linercad.layout as L

    def snap(d):
        out = {}
        for e in d._els.values():
            fixed = any(e._layout.get(f) is not None for f in getattr(e, "LAYOUT", ()))
            if fixed:
                out[e.id] = (repr(e._prims), {k: repr(v) for k, v in sorted(e._resolved.items())})
        return out

    p = tmp_path / "a"
    txn.init(p, from_="end_cover")
    normal = snap(build(p, dxf=False).d)
    monkeypatch.setattr(L._ViewLayout, "_repair_pmi_leaders", lambda self: None)
    monkeypatch.setattr(L._ViewLayout, "_repair_dim_overlaps", lambda self: None)
    monkeypatch.setattr(L._Layout, "_nudge_texts", lambda self: None)
    q = tmp_path / "b"
    txn.init(q, from_="end_cover")
    plain = snap(build(q, dxf=False).d)
    assert normal == plain


def test_concentric_arc_is_not_an_inherent_crossing():
    from linercad.layout import Arc, _Obstacles

    ob = _Obstacles()
    ob.kinds["E.arc"] = "edge"
    ob.add_prims("E.arc", [Arc((0.0, 0.0), 10.0, 0.0, 180.0, "thick")])
    cand = {"cross": [((0.0, -20.0), (0.0, 20.0))], "cross_centre": (0.0, 0.0)}
    assert ob.contour_crossings("D.x", cand) == ["E.arc"]
