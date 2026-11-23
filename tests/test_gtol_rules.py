"""E4 (issue #82): T.syntax / T.target / T.hier read GB/T 1182 data (res/gtol.toml)."""

from __future__ import annotations

import pytest

from linercad import Drawing, Param, checks
from linercad.layout import layout


def run(d):
    layout(d)
    return checks.run(d)


def by_rule(found, rule):
    return [f for f in found if f["rule"] == rule]


@pytest.fixture
def shaft():
    d = Drawing(sheet="A3")
    P = d.params(L=Param(120), l1=Param(40), D=Param(30), D2=Param(40))
    f = d.view("front")
    f.turned("b", [(0, P.D / 2), (P.l1, P.D / 2), (P.l1, P.D2 / 2, "collar"), (P.L, P.D2 / 2)])
    f.dim.dia("D", (20, P.D / 2), (20, -P.D / 2), value=P.D, side="inside")
    f.dim.dia("D2", (80, P.D2 / 2), (80, -P.D2 / 2), value=P.D2, side="inside")
    f.dim.linear("l1", (0, -15), (P.l1, -20), dir="h", value=P.l1, side="bottom")
    f.circle((0, 0), 10, name="hole")
    d.general_tol("m")
    return d, P, f


def _ids(d):
    dim = next(e.id for e in d._els.values() if e.kind == "dim" and e._intent["type"] == "dia")
    circle = next(
        e.id for e in d._els.values() if e.kind == "edge" and e._intent.get("shape") == "circle"
    )
    line = next(
        e.id for e in d._els.values() if e.kind == "edge" and e._intent.get("shape") == "line"
    )
    return dim, circle, line


def test_syntax_is_data_driven_for_zones_and_datums(shaft):
    d, _P, f = shaft
    dim, circle, _line = _ids(d)
    f.datum("A", ref=dim)
    f.gtol("co", "concentricity", 0.02, datums=["A"], ref=dim)  # axis, no zone
    found = by_rule(run(d), "gtol_syntax")
    assert [x for x in found if x["id"] == "G.co"]
    d["G.co"].set(zone="dia")
    assert not [x for x in by_rule(run(d), "gtol_syntax") if x["id"] == "G.co"]
    # circularity on an axis is a T.target problem, not a syntax problem
    f.gtol("cir", "circularity", 0.02, ref=dim)
    assert not [x for x in by_rule(run(d), "gtol_syntax") if x["id"] == "G.cir"]
    # a required datum may not be silently dropped (mutate the intent, as a broken front-end would)
    f.gtol("perp", "perpendicularity", 0.02, datums=["A"], ref=circle)
    assert not by_rule(run(d), "gtol_syntax")
    d["G.perp"]._intent["datums"] = []
    d["G.perp"]._intent["datum_refs"] = []
    bad = by_rule(run(d), "gtol_syntax")
    assert any(x["id"] == "G.perp" and x["severity"] == "error" for x in bad)


def test_syntax_rejects_modifiers_outside_the_characteristic_data(shaft):
    d, _P, f = shaft
    _dim, circle, _line = _ids(d)
    f.datum("A", ref=circle)
    f.gtol("p", "perpendicularity", 0.02, datums=["A"], ref=circle)
    assert not [x for x in by_rule(run(d), "gtol_syntax") if x["id"] == "G.p"]
    d["G.p"]._intent["modifiers"] = ["M"]  # M belongs to the unread GB/T 16671 data
    bad = by_rule(run(d), "gtol_syntax")
    assert any(x["id"] == "G.p" for x in bad)


def test_target_nature_matches_the_characteristic(shaft):
    d, _P, f = shaft
    dim, circle, _line = _ids(d)
    f.datum("A", ref=dim)
    f.gtol("cir", "circularity", 0.02, ref=dim)  # axis: circularity is an integral circle
    bad = by_rule(run(d), "gtol_target")
    assert [x for x in bad if x["id"] == "G.cir"]
    d["G.cir"].suppress()
    f.gtol("cir2", "circularity", 0.02, ref=circle)  # circular edge: integral circle
    assert not [x for x in by_rule(run(d), "gtol_target") if x["id"] == "G.cir2"]
    f.gtol("flat", "flatness", 0.02, ref=circle)  # flatness wants a surface
    bad = by_rule(run(d), "gtol_target")
    assert [x for x in bad if x["id"] == "G.flat"]


def test_target_datums_follow_the_datum_field(shaft):
    d, _P, f = shaft
    dim, circle, _line = _ids(d)
    f.datum("A", ref=circle)
    f.gtol("per", "perpendicularity", 0.02, datums=["A"], ref=circle)
    assert not by_rule(run(d), "gtol_target")
    d["DT.A"]._intent["target"] = "axis"  # axis datum must point at a feature of size
    bad = by_rule(run(d), "gtol_target")
    assert any(x["id"] == "DT.A" for x in bad)


def test_hierarchy_shape_orientation_location(shaft):
    d, _P, f = shaft
    dim, _circle, _line = _ids(d)
    f.datum("A", ref=dim)
    f.gtol("st", "straightness", 0.06, ref=dim)
    f.gtol("perp", "perpendicularity", 0.02, datums=["A"], ref=dim, zone="dia")
    bad = by_rule(run(d), "gtol_hier")
    assert [x for x in bad if x["id"] == "G.st"]
    d["G.st"].set(value=0.01)
    assert not [x for x in by_rule(run(d), "gtol_hier") if x["id"] in ("G.st", "G.perp")]


def test_runout_accepts_a_revolved_feature_reference(shaft):
    d, _P, f = shaft
    dim, _circle, _line = _ids(d)
    f.datum("A", ref=dim)
    f.gtol("run", "circular_runout", 0.02, datums=["A"], ref="F.front.b")
    bad = by_rule(run(d), "gtol_target")
    assert not [x for x in bad if x["id"] == "G.run"]


def test_hierarchy_groups_a_feature_and_its_edge_references(shaft):
    d, _P, f = shaft
    dim, _circle, _line = _ids(d)
    f.datum("A", ref=dim)
    edge = next(
        e.id
        for e in d._els.values()
        if e.kind == "edge" and e._intent.get("feature") == "F.front.b"
    )
    f.gtol("flat", "flatness", 0.06, ref="F.front.b")
    f.gtol("perp", "perpendicularity", 0.02, datums=["A"], ref=edge, zone="dia")
    bad = by_rule(run(d), "gtol_hier")
    assert [x for x in bad if x["id"] == "G.flat"]


def test_profile_rows_are_selected_by_datum_and_direction():
    from linercad import res
    from linercad.rules import _target_row

    data = res.gtol("profile_line")
    row, _target, _nature = _target_row(data, "surface", None, True, False)
    assert row["id"] == "location.profile_line"
    row, _t, _n = _target_row(data, "surface", None, True, True)
    assert row["id"] == "orientation.profile_line"


def test_integral_plane_condition_is_not_satisfied_by_an_axis(shaft):
    d, _P, f = shaft
    dim, _circle, _line = _ids(d)
    f.datum("A", ref=dim)
    f.gtol("pos", "position", 0.02, datums=["A"], ref=dim)
    d["G.pos"]._intent["modifiers"] = ["UZ"]  # only legal for an integral plane target
    bad = by_rule(run(d), "gtol_syntax")
    assert [x for x in bad if x["id"] == "G.pos"]


def test_runout_needs_a_circular_or_revolved_reference(shaft):
    d, _P, f = shaft
    dim, circle, line = _ids(d)
    f.datum("A", ref=dim)
    linear = d["D.l1"]
    f.gtol("run", "circular_runout", 0.02, datums=["A"], ref=linear.id)
    bad = by_rule(run(d), "gtol_target")
    assert [x for x in bad if x["id"] == "G.run"]
    d["G.run"].suppress()
    f.gtol("run2", "circular_runout", 0.02, datums=["A"], ref=dim)
    assert not [x for x in by_rule(run(d), "gtol_target") if x["id"] == "G.run2"]


def test_surface_form_does_not_accept_an_axis_target(shaft):
    d, _P, f = shaft
    dim, _circle, _line = _ids(d)
    f.gtol("flat", "flatness", 0.02, ref=dim)
    bad = by_rule(run(d), "gtol_target")
    assert [x for x in bad if x["id"] == "G.flat"]


def test_hierarchy_groups_a_dimension_and_its_underlying_circle(tmp_path):
    d = Drawing(sheet="A3")
    f = d.view("front")
    c = f.circle((0, 0), 20, name="bore")
    dim = f.dim.dia("D", circle=c, value=40, tol="H7")
    f.datum("A", ref=dim.id)
    f.gtol("circ", "circularity", 0.03, ref=c.id)
    f.gtol("run", "circular_runout", 0.02, datums=["A"], ref=dim.id)
    bad = by_rule(run(d), "gtol_hier")
    assert [x for x in bad if x["id"] == "G.run"]
    d["G.run"].set(value=0.03)
    assert not [x for x in by_rule(run(d), "gtol_hier") if x["id"] == "G.run"]


def test_hierarchy_runout_must_not_be_tighter_than_the_covered_tolerance(shaft):
    d, _P, f = shaft
    dim, _circle, _line = _ids(d)
    f.datum("A", ref=dim)
    f.gtol("co", "concentricity", 0.03, datums=["A"], ref=dim, zone="dia")
    f.gtol("run", "total_runout", 0.02, datums=["A"], ref=dim)
    bad = by_rule(run(d), "gtol_hier")
    assert [x for x in bad if x["id"] == "G.run"]
    d["G.run"].set(value=0.03)
    assert not [x for x in by_rule(run(d), "gtol_hier") if x["id"] == "G.run"]


def test_opportunities_are_independent_checks(shaft):
    d, _P, f = shaft
    dim, circle, _line = _ids(d)
    f.datum("A", ref=dim)
    f.gtol("co", "concentricity", 0.02, datums=["A"], ref=dim, zone="dia")
    layout(d)
    found = checks.run(d)
    opp = found.opportunities
    assert opp["gtol_syntax"] >= 2  # datum rule + zone shape + datum ref + Phi
    assert opp["gtol_target"] >= 1
    for f in by_rule(found, "gtol_syntax") + by_rule(found, "gtol_target"):
        assert f["std"] and f["clause"] and "GB/T 1182-2018" in f["clause"]
