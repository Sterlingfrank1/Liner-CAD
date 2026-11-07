import json

import pytest

from linercad import Drawing, Param, checks
from linercad.dxfout import APPID, model_dict, save_doc, to_doc, write_model
from linercad.layout import layout


def make():
    d = Drawing(sheet="A3")
    P = d.params(D=Param(120), d0=Param(30), T=Param(15), L=Param(40))
    fr, lf = d.view("front"), d.view("left")
    up = fr.polygon([(0, P.d0 / 2), (P.L, P.d0 / 2), (P.L, P.D / 2), (0, P.D / 2)], name="up")
    fr.polygon([(0, -P.D / 2), (P.L, -P.D / 2), (P.L, -P.d0 / 2), (0, -P.d0 / 2)], name="dn")
    fr.hatch("sec", loops=[up, "F.front.dn"])
    fr.centerline((0, 0), (P.L, 0), name="axis")
    lf.circle((0, 0), P.D / 2, name="outer")
    lf.circle((0, 0), P.d0 / 2, name="bore")
    fr.dim.linear("L", (0, -P.D / 2), (P.L, -P.D / 2), value=P.L)
    fr.dim.dia("D", (0, P.D / 2), (0, -P.D / 2), value=P.D, side="left")
    fr.dim.linear("t", (5, 40), (35, 40), side="inside")  # text sits inside the hatch
    d.section("A", view="front", cut_in="left", through=[(0, -70), (0, 70)])
    d.notes.tech(["调质处理 220~250HBW。"])
    d.title(name="法兰", material="45")
    layout(d)
    return d


def xid(e):
    data = e.get_xdata(APPID)
    return data[0].value, data[1].value


def test_every_entity_has_xdata_pointing_to_a_model_element():
    d = make()
    doc, index, fails = to_doc(d)
    assert not fails
    ents = list(doc.modelspace())
    assert ents
    for e in ents:
        eid, k = xid(e)
        assert eid in d
    counts = {}
    for e in ents:
        eid, k = xid(e)
        counts.setdefault(eid, []).append(k)
    for eid, ks in counts.items():
        assert ks == list(range(len(ks))), eid  # sub indexes are 0..n-1 in order
    assert {"D.L", "D.D", "S.A", "H.front.sec", "T.frame", "N.tech.1"} <= set(counts)


def test_dimension_is_several_entities_one_id():
    d = make()
    doc, index, _ = to_doc(d)
    types = sorted(e.dxftype() for e in index["D.L"])
    assert types.count("LINE") == 3 and types.count("SOLID") == 2 and types.count("TEXT") == 1
    assert all(xid(e)[0] == "D.L" for e in index["D.L"])


def test_layers_linetypes_and_style_from_std():
    d = make()
    doc, *_ = to_doc(d)
    for role, spec in d.std["lines"].items():
        if not isinstance(spec, dict):
            continue
        lay = doc.layers.get(spec["layer"])
        assert lay.color == spec["color"]
        assert lay.dxf.lineweight == round(spec["width"] * 100)
        assert lay.dxf.linetype == spec["linetype"]
    assert "LC_CENTER" in doc.linetypes and "LC_HIDDEN" in doc.linetypes
    assert doc.styles.get("LC").dxf.font == d.std["text"]["font"]
    assert doc.units == 4


def test_text_entities_follow_gb_height_rule():
    d = make()
    doc, index, _ = to_doc(d)
    (t,) = [e for e in index["N.tech.1"] if "调质" in e.dxf.text]
    assert t.dxf.height == pytest.approx(3.5 / d.std["text"]["cjk_em"])
    assert t.dxf.width == d.std["text"]["width_factor"] and t.dxf.style == "LC"
    (dt,) = [e for e in index["D.D"] if e.dxftype() == "TEXT"]
    assert dt.dxf.text == "Φ120" and dt.dxf.height == 3.5 and dt.dxf.rotation == 90


def test_centre_line_entity_ltscale():
    d = make()
    doc, index, _ = to_doc(d)
    (ln,) = index["C.front.axis"]
    assert ln.dxf.layer == "CENTER" and ln.dxf.ltscale != 1.0


def test_hatch_paths_and_text_island():
    d = make()
    doc, index, _ = to_doc(d)
    (h,) = index["H.front.sec"]
    assert h.dxftype() == "HATCH" and h.dxf.pattern_name == "ANSI31"
    assert len(h.paths) == 3  # two regions + one island around the text of D.t


def test_dxf_and_model_bytes_are_deterministic(tmp_path):
    outs = []
    for k in range(2):
        d = make()
        f = checks.run(d)
        doc, *_ = to_doc(d)
        save_doc(doc, tmp_path / f"a{k}.dxf")
        write_model(d, tmp_path / f"m{k}.json", f, "e3")
        outs.append(((tmp_path / f"a{k}.dxf").read_bytes(), (tmp_path / f"m{k}.json").read_bytes()))
    assert outs[0][0] == outs[1][0]
    assert outs[0][1] == outs[1][1]
    assert b"\r\n" not in outs[0][1]


def test_model_json_shape(tmp_path):
    d = make()
    f = checks.run(d)
    p = write_model(d, tmp_path / "model.json", f, "e2")
    m = json.loads(p.read_text(encoding="utf-8"))
    assert m["schema"] == "linercad.model/0"
    assert m["drawing"]["edit"] == "e2" and m["drawing"]["sheet"] == "A3" and m["drawing"]["scale"] == "1:1"
    assert set(m["drawing"]["views"]) == {"front", "left"}
    assert [p["name"] for p in m["params"]] == ["D", "d0", "T", "L"]
    rec = {e["id"]: e for e in m["elements"]}["D.L"]
    assert list(rec) == ["id", "kind", "intent", "placement", "refs", "covers", "tags", "src", "history", "status"]
    assert rec["placement"]["resolved"]["bbox"] and rec["covers"] == ["L"]
    assert m["findings"] == f
    assert model_dict(d, f, "e2") == m


def test_save_is_atomic_and_creates_dirs(tmp_path):
    d = make()
    doc, *_ = to_doc(d)
    p = save_doc(doc, tmp_path / "x" / "y" / "drawing.dxf")
    assert p.exists() and not list(p.parent.glob("*.tmp"))
