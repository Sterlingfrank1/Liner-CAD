"""D2: multi-layer dimension avoidance — concentric dims, nesting, outline, keyway text, PMI.

G2 (first commit of the D2 PR): these tests fail on the D1 state and are made to pass by the
layout / pmi_layout changes.  They state the acceptance of issue #84: same-side nesting (small
inside / large outside), multi-layer dimension lines not crossing each other or the outline,
text clear of its own line, the crowded right side of the pulley (PMI leaders vs dimensions),
and the two D1 review minors (concentric arcs are not inherent; collinear PMI attachment is
reported instead of silent).
"""

import math

import pytest

from linercad import Drawing, place, txn
from linercad.layout import Line, _crosses, layout
from linercad.runtime import build


def _eval_case(case_id):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
    import run as evals

    return next(c for c in evals.discover() if c["id"] == case_id)


def _build_eval(tmp_path, case_id):
    case = _eval_case(case_id)
    (tmp_path / "drawing.py").write_text(case["drawing_src"], encoding="utf-8")
    return build(tmp_path, dxf=False).d


def _cross_ids(findings):
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
    assert not ({"D.Do", "D.Di"} & _cross_ids(found))


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
    assert not (ids & _cross_ids(found))


@pytest.mark.parametrize(
    "case_id, ids",
    [
        ("L2/disc/pulley", {"D.tw"}),
        ("L2/box/gear_pump_body", {"D.Rc2"}),
    ],
)
def test_dimension_lines_do_not_cross_the_outline(tmp_path, case_id, ids):
    d = _build_eval(tmp_path, case_id)
    found, _ = place.place_dim_outline(d)
    assert not (ids & _cross_ids(found))


@pytest.mark.parametrize(
    "case_id, ids",
    [
        ("L2/box/bearing_seat", {"D.Hc"}),
        ("L2/shaft/shaft", {"D.L"}),
    ],
)
def test_small_dimension_inside_large_one_on_the_same_side(tmp_path, case_id, ids):
    d = _build_eval(tmp_path, case_id)
    found, _ = place.place_nesting(d)
    assert not (ids & _cross_ids(found))


def test_keyway_tolerance_text_does_not_overlap_its_own_line(tmp_path):
    d = _build_eval(tmp_path, "L1/keyway_d28")
    found, _ = place.place_text_overlap(d)
    assert "D.kd" not in _cross_ids(found)


def _pmi_leader_crossings(d):
    dims = {
        e.id: [p for p in e._prims if isinstance(p, Line)]
        for e in d._els.values()
        if e.kind == "dim"
    }
    out = set()
    for e in d._els.values():
        if e.kind not in ("datum", "gtol", "rough"):
            continue
        lines = [p for p in e._prims if isinstance(p, Line)]
        if not lines:
            continue
        leader = max(lines, key=lambda p: math.dist(p.p, p.q))
        for oid, osegs in dims.items():
            if oid == e._intent.get("ref"):
                continue
            if any(_crosses(leader.p, leader.q, o.p, o.q) for o in osegs):
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


def test_concentric_arc_is_not_an_inherent_crossing():
    from linercad.layout import Arc, _Obstacles

    ob = _Obstacles()
    ob.kinds["E.arc"] = "edge"
    ob.add_prims("E.arc", [Arc((0.0, 0.0), 10.0, 0.0, 180.0, "thick")])
    cand = {"cross": [((0.0, -20.0), (0.0, 20.0))], "cross_centre": (0.0, 0.0)}
    assert ob.contour_crossings("D.x", cand) == ["E.arc"]
