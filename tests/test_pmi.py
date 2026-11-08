"""M1 C3: semantic PMI (tolerances, datums, geometric tolerances, roughness) and the
dimension system (aligned, angle, chamfer, reference, chains) — SPEC §3."""

import json

import pytest

from linercad import Drawing, Param, errors
from linercad.dxfout import model_dict
from linercad.layout import Circle, Line, Solid, Text, layout


def texts(el):
    return [p.text for p in el._prims if isinstance(p, Text)]


@pytest.fixture
def shaft():
    d = Drawing(sheet="A3")
    P = d.params(D=Param(30, label="轴颈"), L=Param(120), l1=Param(40), D2=Param(40))
    f = d.view("front")
    f.turned(
        "body",
        [(0, P.D / 2, "journal"), (P.l1, P.D / 2), (P.l1, P.D2 / 2, "collar"), (P.L, P.D2 / 2)],
    )
    return d, P, f


def dia(f, P, **kw):
    return f.dim.dia("D", (20, P.D / 2), (20, -P.D / 2), value=P.D, side="inside", **kw)


# ---- size tolerances ------------------------------------------------------------------------


def test_fit_code_looked_up_and_structured(shaft):
    d, P, f = shaft
    el = dia(f, P, tol="k6")
    t = el.intent["tolerance"]
    assert t["kind"] == "fit" and t["code"] == "k6"
    assert (t["upper"], t["lower"]) == (pytest.approx(0.015), pytest.approx(0.002))
    assert "1800" in t["std"] and el.intent["tol_show"] == "code"
    assert el.text == "Φ30k6"


def test_fit_follows_parameter_value():
    d = Drawing()
    P = d.params(D=Param(50))
    f = d.view("front")
    f.turned("b", [(0, P.D / 2), (60, P.D / 2)])
    el = f.dim.dia("D", (10, P.D / 2), (10, -P.D / 2), value=P.D, tol="k6", side="inside")
    assert el.intent["tolerance"]["upper"] == pytest.approx(0.018)


def test_three_display_modes(shaft):
    d, P, f = shaft
    el = dia(f, P, tol="H7", tol_show="dev")
    layout(d)
    assert texts(el)[:3] == ["Φ30", "+0.021", "0"]
    el.set(tol_show="both")
    layout(d)
    assert texts(el)[0] == "Φ30H7(" and texts(el)[1:3] == ["+0.021", "0"] and ")" in texts(el)
    el.set(tol="±0.1")
    assert el.intent["tolerance"] == {
        "kind": "sym",
        "upper": 0.1,
        "lower": -0.1,
        "envelope": False,
        "std": None,
        "code": None,
    }
    assert el.text == "Φ30±0.1"
    el.set(tol="+0.02/-0.01")
    assert (el.intent["tolerance"]["upper"], el.intent["tolerance"]["lower"]) == (0.02, -0.01)


def test_bad_tolerances_are_rejected_with_hints(shaft):
    d, P, f = shaft
    with pytest.raises(errors.InvalidArgument) as e:
        dia(f, P, tol="k66")
    assert e.value.candidates
    with pytest.raises(errors.InvalidArgument):
        dia(f, P, tol="-0.02/+0.01")  # upper below lower


def test_fit_alias_envelope_and_reference(shaft):
    d, P, f = shaft
    el = dia(f, P)
    el.fit = "h6"
    assert el.intent["tolerance"]["code"] == "h6"
    el.set(envelope=True)
    assert el.intent["tolerance"]["envelope"] is True
    layout(d)
    assert any(isinstance(p, Circle) for p in el._prims)  # the circled E
    r = f.dim.linear("Lr", (0, -20), (120, -20), value=P.L, reference=True, side="bottom")
    assert r.text == "(120)" and r.intent["reference"] is True


# ---- new dimension types ---------------------------------------------------------------------


def test_aligned_dimension():
    d = Drawing()
    f = d.view("front")
    f.polygon([(0, 0), (40, 0), (40, 30)], name="tri")
    el = f.dim.aligned("hyp", (0, 0), (40, 30), side="top")
    assert el.type == "aligned" and el.intent["measured"] == pytest.approx(50)
    layout(d)
    t = [p for p in el._prims if isinstance(p, Text)][0]
    assert t.rot == pytest.approx(36.8699, abs=1e-3)


def test_angle_dimension_text_horizontal():
    d = Drawing()
    f = d.view("front")
    a = f.line((0, 0), (40, 0), name="a")
    b = f.line((0, 0), (20, 20), name="b")
    el = f.dim.angle("ang", a, b)
    assert el.intent["measured"] == pytest.approx(45) and el.text == "45°"
    layout(d)
    assert all(p.rot == 0 for p in el._prims if isinstance(p, Text))
    assert any(p.__class__.__name__ == "Arc" for p in el._prims)


def test_chamfer_dimension(shaft):
    d = Drawing()
    f = d.view("front")
    f.turned("b", [(0, 9), (1, 10), (30, 10)])
    edge = d.q.lines(view="front").where(dir=None).near(0.5, 9.5).one()
    el = f.dim.chamfer("c1", edge)
    assert el.text == "C1" and el.intent["size"] == pytest.approx(1)
    f.turned("k", [(40, 8), (42, 10 + 0.0), (60, 10)])
    e2 = d.q.lines(view="front").where(dir=None).near(41, 9).one()
    assert f.dim.chamfer("c2", e2).text == "C2"
    f.turned("t", [(70, 8), (72, 8 + 2 / 3**0.5), (90, 8 + 2 / 3**0.5)])
    e3 = d.q.lines(view="front").where(dir=None).near(71, 9).one()
    assert f.dim.chamfer("c3", e3).text == "2×30°"


# ---- datums, geometric tolerances, roughness --------------------------------------------------


def test_datum_on_dimension_is_an_axis(shaft):
    d, P, f = shaft
    dia(f, P, tol="k6")
    dt = f.datum("A", ref="D.D")
    assert dt.id == "DT.A" and dt.intent["target"] == "axis" and "D.D" in dt.refs
    layout(d)
    assert any(isinstance(p, Solid) for p in dt._prims) and "A" in texts(dt)


def test_datum_on_named_edge_is_a_surface(shaft):
    d, P, f = shaft
    dt = f.datum("B", ref="E.front.body.collar")
    assert dt.intent["target"] == "surface"


def test_gtol_fields_and_datum_system(shaft):
    d, P, f = shaft
    dia(f, P, tol="k6")
    f.datum("A", ref="D.D")
    f.datum("B", ref="E.front.body.collar")
    g = f.gtol("run", "circular_runout", 0.02, datums=["A-B"], ref="E.front.body.collar")
    i = g.intent
    assert i["char"] == "circular_runout" and i["value"] == 0.02 and i["zone"] is None
    assert i["datums"] == [{"letters": ["A", "B"], "common": True, "modifiers": []}]
    assert i["target"] == "surface" and "E.front.body.collar" in g.refs
    assert "1182" in i["std"]
    layout(d)
    assert "0.02" in texts(g) and "A-B" in texts(g)


def test_gtol_syntax_errors(shaft):
    d, P, f = shaft
    with pytest.raises(errors.InvalidArgument):
        f.gtol("x", "flatness", 0.01, datums=["A"], ref="E.front.body.collar")  # form: no datum
    with pytest.raises(errors.InvalidArgument):
        f.gtol("y", "perpendicularity", 0.01, ref="E.front.body.collar")  # needs a datum
    with pytest.raises(errors.InvalidArgument) as e:
        f.gtol("z", "runoutt", 0.01, datums=["A"], ref="E.front.body.collar")
    assert "circular_runout" in e.value.candidates
    with pytest.raises(errors.InvalidArgument):
        f.gtol("w", "position", 0.1, datums=["A"], ref="E.front.body.collar", modifiers=["E"])


def test_gtol_on_dimension_targets_axis(shaft):
    d, P, f = shaft
    dia(f, P)
    g = f.gtol("cyl", "cylindricity", 0.005, ref="D.D")
    assert g.intent["target"] == "axis"


def test_roughness_fields_and_symbol(shaft):
    d, P, f = shaft
    r = f.rough("j", 0.8, ref="E.front.body.journal", process="磨")
    i = r.intent
    assert (i["param"], i["value"], i["removal"], i["process"]) == ("Ra", 0.8, "required", "磨")
    assert "131" in i["std"] and "E.front.body.journal" in r.refs
    d.rough_default(6.3)
    layout(d)
    assert "Ra 0.8" in texts(r) and "磨" in texts(r)
    rd = d["R.default"]
    assert rd.intent["default"] is True and "Ra 6.3" in texts(rd)
    assert (
        len([p for p in rd._prims if isinstance(p, Line)]) >= 6
    )  # symbol + bracketed basic symbol


def test_roughness_on_bottom_face_uses_leader(shaft):
    d, P, f = shaft
    r = f.rough("lo", 3.2, ref="E.front.body.collar_lo")
    layout(d)
    assert r._resolved["mode"] == "leader"
    up = f.rough("up", 3.2, ref="E.front.body.collar")
    layout(d)
    assert up._resolved["mode"] == "direct"


# ---- chains, general tolerance ------------------------------------------------------------------


def test_dimension_chain_worst_case_and_rss(shaft):
    d, P, f = shaft
    f.dim.linear("L", (0, -20), (120, -20), value=P.L, tol="±0.1", side="bottom", row=2)
    f.dim.linear("l1", (0, -15), (40, -20), dir="h", value=P.l1, tol="±0.05", side="bottom")
    k = d.chain("rest", closing="l2", increase=["D.L"], decrease=["D.l1"])
    layout(d)
    r = k._resolved["result"]
    assert r["nominal"] == pytest.approx(80)
    assert (r["wc"]["upper"], r["wc"]["lower"]) == (pytest.approx(0.15), pytest.approx(-0.15))
    t = (0.2**2 + 0.1**2) ** 0.5
    assert (r["rss"]["upper"], r["rss"]["lower"]) == (pytest.approx(t / 2), pytest.approx(-t / 2))


def test_chain_uses_general_tolerance(shaft):
    d, P, f = shaft
    d.general_tol("m")
    f.dim.linear("L", (0, -20), (120, -20), value=P.L, side="bottom", row=2)
    f.dim.linear("l1", (0, -15), (40, -20), dir="h", value=P.l1, side="bottom")
    k = d.chain("rest", closing="l2", increase=["D.L"], decrease=["D.l1"], require=(-0.5, 0.5))
    layout(d)
    r = k._resolved["result"]
    assert r["wc"]["upper"] == pytest.approx(0.6)  # m: 120 and 40 both in 30–120 → ±0.3
    assert r["ok"] is False
    note = [e for e in d.q.notes() if e.intent.get("gentol")]
    assert note and "1804" in note[0].text


# ---- model.json carries the semantics ----------------------------------------------------------


def test_model_json_has_separate_pmi_fields(shaft):
    d, P, f = shaft
    dia(f, P, tol="k6")
    f.datum("A", ref="D.D")
    f.gtol("run", "circular_runout", 0.02, datums=["A"], ref="E.front.body.collar")
    f.rough("j", 0.8, ref="E.front.body.journal")
    layout(d)
    m = json.loads(json.dumps(model_dict(d)))
    els = {e["id"]: e for e in m["elements"]}
    assert els["D.D"]["intent"]["tolerance"]["lower"] == pytest.approx(0.002)
    assert els["DT.A"]["kind"] == "datum" and els["DT.A"]["intent"]["letter"] == "A"
    assert els["G.run"]["kind"] == "gtol" and els["G.run"]["intent"]["datums"][0]["letters"] == [
        "A"
    ]
    assert els["R.j"]["kind"] == "rough" and els["R.j"]["intent"]["value"] == 0.8
    for i in ("DT.A", "G.run", "R.j"):
        assert els[i]["refs"], i


def test_review_fixes_float_noise_and_gtol_datum_refs():
    d = Drawing()
    f = d.view("front")
    f.turned("b", [(0, 10), (40, 10)])
    el = f.dim.linear("L", (2.7, 10), (32.7, 10), dir="h", tol="h7", side="top")
    assert el.intent["tolerance"]["lower"] == pytest.approx(-0.021)  # 18–30 band, not 30–50
    f.datum("A", ref="E.front.b.1")
    g = f.gtol("p", "parallelism", 0.02, datums=["A"], ref="E.front.b.2")
    g.set(datums=["B"])
    assert g.intent["datum_refs"] == ["DT.B"]
