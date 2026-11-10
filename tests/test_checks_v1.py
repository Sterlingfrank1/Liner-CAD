"""M1 C7: Checks v1 — five rule packs, severities, standard numbers, accept() (SPEC §7)."""

import pytest

from linercad import Drawing, Param, checks
from linercad.layout import layout


def run(d):
    layout(d)
    return checks.run(d)


def rules(found):
    return {(f["rule"], f["id"]) for f in found}


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
    f.dim.linear(
        "L", (0, -15), (P.L, -20), dir="h", value=P.L, role="overall", side="bottom", row=2
    )
    d.general_tol("m")
    return d, P, f


def test_findings_carry_pack_severity_and_std(shaft):
    d, P, f = shaft
    for x in run(d):
        assert x["pack"] in ("drafting", "dimensioning", "tolerancing", "surface", "layout")
        assert x["severity"] in ("error", "warn") and x["std"]


def test_clean_shaft_has_no_errors(shaft):
    d, *_ = shaft
    assert [x for x in run(d) if x["severity"] == "error"] == []


def test_closed_loop_and_missing(shaft):
    d, P, f = shaft
    f.dim.linear("l2", (P.l1, -20), (P.L, -20), value=P.L - P.l1, side="bottom")
    found = run(d)
    assert ("closed_loop", "D.l2") in rules(found)
    d["D.l2"].set(reference=True)
    assert not by_rule(run(d), "closed_loop")
    d["D.l1"].suppress()
    d["D.l2"].suppress()
    miss = by_rule(run(d), "missing")
    assert miss and miss[0]["id"] == "F.front.b" and "x=40" in miss[0]["message"]


def test_duplicate_and_param_cover(shaft):
    d, P, f = shaft
    f.dim.dia("D_again", (25, P.D / 2), (25, -P.D / 2), value=P.D, side="inside")
    found = run(d)
    assert ("duplicate", "D.D_again") not in rules(found)  # another place on the same cylinder
    f.dim.linear("l1b", (0, -15), (P.l1, -20), dir="h", value=P.l1, side="bottom", row=3)
    assert ("duplicate", "D.l1b") in rules(run(d))
    d2 = Drawing()
    d2.params(X=Param(5))
    d2.view("front").rect((0, 0), 10, 10, name="r")
    assert ("param_cover", "P.X") in rules(run(d2))


def test_gtol_datum_must_exist_and_rough_rules(shaft):
    d, P, f = shaft
    f.gtol("run", "circular_runout", 0.02, datums=["A"], ref="E.front.b.collar")
    found = run(d)
    assert [x for x in by_rule(found, "gtol_syntax") if x["severity"] == "error"]
    f.datum("A", ref="D.D")
    assert not by_rule(run(d), "gtol_syntax")
    f.rough("r1", 3.0, ref="E.front.b.collar")  # not in the GB/T 1031 series
    found = run(d)
    assert by_rule(found, "rough_syntax")
    assert by_rule(found, "rough_default")
    d["R.r1"].set(value=3.2)
    d.rough_default(6.3)
    found = run(d)
    assert not by_rule(found, "rough_syntax") and not by_rule(found, "rough_default")


def test_rough_fit_and_general_tol():
    d = Drawing()
    P = d.params(D=Param(30))
    f = d.view("front")
    f.turned("b", [(0, P.D / 2, "j"), (50, P.D / 2)])
    f.dim.dia("D", (20, P.D / 2), (20, -P.D / 2), value=P.D, tol="k6", side="inside")
    f.dim.linear("L", (0, -15), (50, -15), value=50, side="bottom")
    found = run(d)
    assert ("rough_fit", "D.D") in rules(found)
    assert by_rule(found, "general_tol")
    f.rough("j", 0.8, ref="E.front.b.j")
    assert ("rough_fit", "D.D") not in rules(run(d))


def test_conv_dim_and_section_ref():
    d = Drawing()
    f = d.view("front")
    f.turned("b", [(0, 10), (40, 10)])
    f.thread("m20", "M20", 0, 30)
    assert ("conv_dim", "F.front.m20") in rules(run(d))
    f.dim.thread("t", "F.front.m20")
    assert ("conv_dim", "F.front.m20") not in rules(run(d))


def test_center_mark_and_text_height():
    d = Drawing()
    left = d.view("left")
    left.circle((0, 0), 20, name="o")
    assert ("center_mark", "E.left.o") in rules(run(d)) or ("center_mark", "F.left.o") in rules(
        run(d)
    )
    left.center_mark((0, 0), 20, name="ax")
    found = run(d)
    assert not by_rule(found, "center_mark") and not by_rule(found, "text_height")


def test_chain_limit_error(shaft):
    d, P, f = shaft
    d.chain("rest", closing="l2", increase=["D.L"], decrease=["D.l1"], require=(-0.1, 0.1))
    assert [x for x in by_rule(run(d), "chain_limit") if x["severity"] == "error"]


def test_accept_any_rule(shaft):
    d, P, f = shaft
    d2 = Drawing()
    d2.params(X=Param(5))
    d2.view("front").rect((0, 0), 10, 10, name="r")
    d2.accept("param_cover", "P.X", "派生参数，不标注")
    assert not by_rule(run(d2), "param_cover")


def test_discouraged_datum_letter_warns(shaft):
    d, P, f = shaft
    f.datum("I", ref="D.D")
    assert [x["severity"] for x in by_rule(run(d), "datum_letter")] == ["warn"]


def test_datum_letter_outside_gb_17851_note_is_allowed(shaft):
    # GB/T 17851-2010 6.2 note 2 names only I, O, Q, X; the old E F J L M P R list is not applied
    d, P, f = shaft
    f.datum("E", ref="D.D")
    assert not by_rule(run(d), "datum_letter")


def test_coaxiality_on_axis_needs_dia_zone(shaft):
    d, P, f = shaft
    f.datum("A", ref="D.D")
    f.gtol("co", "concentricity", 0.03, datums=["A"], ref="D.D2")
    assert ("gtol_syntax", "G.co") in rules(run(d))
    d["G.co"].set(zone="dia")
    assert ("gtol_syntax", "G.co") not in rules(run(d))
