"""M3 S3: assembly drawings (needs linercad[3d]; skipped otherwise)."""

import textwrap

import pytest

pytest.importorskip("build123d")

from linercad import res, runtime  # noqa: E402

PARTS = {
    "base": (
        """
        from build123d import Box, Cylinder, Pos
        def model(L=60, W=40, H=20, D=20):
            return Pos(0, 0, H / 2) * Box(L, W, H) - Pos(0, 0, H / 2) * Cylinder(D / 2, H + 2)
        """,
        """
        from linercad import Drawing, Param
        d = Drawing()
        P = d.params(L=Param(60, min=40, max=100), D=Param(20, min=10, max=30))
        d.title(name="底座", drawing_no="T-01", material="HT200")
        """,
    ),
    "bush": (
        """
        from build123d import Cylinder, Pos
        def model(D=20, d=12, h=25):
            return Pos(0, 0, h / 2) * (Cylinder(D / 2, h) - Cylinder(d / 2, h + 2))
        """,
        """
        from linercad import Drawing, Param
        d = Drawing()
        P = d.params(D=Param(20, min=10, max=30), d=Param(12, min=6, max=20))
        d.title(name="轴套", drawing_no="T-02", material="ZCuSn10Pb1")
        """,
    ),
    "shaft": (
        """
        from build123d import Cylinder, Pos
        def model(d=12, l=45):
            return Pos(0, 0, l / 2 - 5) * Cylinder(d / 2, l)
        """,
        """
        from linercad import Drawing
        d = Drawing()
        d.title(name="轴", drawing_no="T-03", material="45")
        """,
    ),
}

ASM = """
from linercad import Drawing, Param
d = Drawing(kind="assembly")
P = d.params(D=Param(20, min=10, max=30))
d.component("parts/base", params={{"D": P.D}})
d.component("parts/bush", params={{"D": P.D}})
d.component("parts/shaft", solid=True)
d.std_part("GB/T 97.1", "6", name="washer", at=[(-22, 0, 20), (22, 0, 20)])
front = d.view("front")
front.project(cut="full", hidden=False)
d.view("top").project(hidden=False)
d.bom()
{extra}
"""


def make(tmp_path, extra="", D=20):
    for name, (model, drawing) in PARTS.items():
        p = tmp_path / "parts" / name
        p.mkdir(parents=True, exist_ok=True)
        (p / "model.py").write_text(textwrap.dedent(model), encoding="utf-8")
        (p / "drawing.py").write_text(textwrap.dedent(drawing), encoding="utf-8")
    src = ASM.format(extra=extra).replace("Param(20,", f"Param({D},")
    (tmp_path / "drawing.py").write_text(src, encoding="utf-8")
    return runtime.build(tmp_path)


def test_bom_rows_and_balloons(tmp_path):
    r = make(tmp_path)
    d = r.d
    rows = d["T.bom"].rows
    assert [x["name"] for x in rows] == ["底座", "轴套", "轴", "平垫圈 6"]
    assert rows[0]["code"] == "T-01" and rows[0]["material"] == "HT200"
    assert rows[3]["code"] == "GB/T 97.1" and rows[3]["qty"] == 2
    balloons = [e for e in d._els.values() if e.kind == "balloon"]
    assert [b.number for b in balloons] == [1, 2, 3, 4]
    assert all(b._prims for b in balloons)
    errs = [f for f in r.findings if f["severity"] == "error"]
    assert not errs, errs


def test_hatch_per_component_adjacent_differ_and_solid_not_cut(tmp_path):
    d = make(tmp_path).d
    hs = {e._intent["component"]: e for e in d._els.values() if e.kind == "hatch"}
    assert "A.shaft" not in hs, "solid parts are not cut in a longitudinal section"
    assert {"A.base", "A.bush"} <= set(hs)
    a, b = hs["A.base"]._intent, hs["A.bush"]._intent
    assert (a["angle"], a["spacing"]) != (b["angle"], b["spacing"])
    assert a["angle"] == 45 and b["angle"] == 135


def test_edges_attributed_and_contact_drawn_once(tmp_path):
    d = make(tmp_path).d
    es = [e for e in d._els.values() if e.kind == "edge" and e.view == "front"]
    assert {e._intent.get("component") for e in es} >= {"A.base", "A.bush", "A.shaft"}
    vertical = [
        e
        for e in es
        if e.shape == "line"
        and abs(e._intent["p1"][0] - 10) < 1e-6
        and abs(e._intent["p2"][0] - 10) < 1e-6
    ]
    spans = sorted(tuple(sorted((e._intent["p1"][1], e._intent["p2"][1]))) for e in vertical)
    assert len(spans) == len(set(spans)), "base bore and bush outside coincide: one line"


def test_param_sync_through_assembly(tmp_path):
    d = make(tmp_path, D=24).d
    assert d["A.base"]._intent["params"]["D"] == 24
    assert d["A.bush"]._intent["params"]["D"] == 24
    xs = {
        round(abs(x), 3)
        for e in d._els.values()
        if e.kind == "edge" and e.view == "front" and e.shape == "line"
        for x in (e._intent["p1"][0], e._intent["p2"][0])
    }
    assert 12 in xs and 10 not in xs


def test_std_part_resource_and_errors(tmp_path):
    b = res.std_part("GB/T 5782", "M10×90")
    assert b["s"] == 16 and b["k"] == 6.4 and b["l"] == 90 and b["std"] == "GB/T 5782-2016"
    with pytest.raises(Exception) as ei:
        res.std_part("GB/T 5782", "M7×20")
    assert "10" in ei.value.candidates


def test_component_unknown_param_reported(tmp_path):
    with pytest.raises(Exception) as ei:
        make(tmp_path, extra='d.component("parts/base", name="b2", params={"X": 1})')
    assert "X" in str(ei.value) or "L" in getattr(ei.value, "candidates", [])
