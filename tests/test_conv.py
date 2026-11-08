"""M1 C4: conventional representations — threads, tapped holes, center holes, grooves,
keyways, splines — and their designation dimensions (SPEC §4)."""

import math

import pytest

from linercad import Drawing, errors
from linercad.layout import Text, layout


def lines(d, fid, role=None):
    return [e for e in d[fid].edges if e.shape == "line" and (role is None or e.role == role)]


def texts(el):
    return [p.text for p in el._prims if isinstance(p, Text)]


@pytest.fixture
def shaft():
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.turned("body", [(0, 9), (1, 10), (30, 10), (30, 14), (80, 14)])
    return d, f


def test_external_thread_lines(shaft):
    d, f = shaft
    t = f.thread("m20", "M20x1.5", 0, 26)
    i = t.intent
    assert (i["d"], i["P"], i["kind"]) == (20, 1.5, "ext") and "196" in i["std"]
    thin = lines(d, "F.front.m20", "thin")
    assert {round(abs(e.start[1]), 3) for e in thin} == {round(i["d1"] / 2, 3)}
    term = [e for e in lines(d, "F.front.m20", "thick") if e.dir == "v"]
    assert len(term) == 1 and term[0].start[0] == 26 and term[0].length == pytest.approx(20)
    assert all("conv" in e.tags for e in d["F.front.m20"].edges)


def test_minor_line_keeps_min_gap_on_paper():
    d = Drawing(scale="1:2")
    f = d.view("front")
    f.turned("b", [(0, 3), (20, 3)])
    t = f.thread("m6", "M6x0.5", 0, 15)
    y = max(abs(e.start[1]) for e in lines(d, "F.front.m6", "thin"))
    assert (3 - y) * d.scale >= 0.7 - 1e-9  # GB/T 4457.4 gap between parallel lines
    assert t.intent["d1"] / 2 > y  # drawn below the true root because of the gap


def test_thread_class_validated(shaft):
    d, f = shaft
    with pytest.raises(errors.InvalidArgument) as e:
        f.thread("bad", "M20", 0, 20, cls="9z")
    assert e.value.candidates


def test_thread_end_view_three_quarter_arc():
    d = Drawing()
    left = d.view("left")
    t = left.thread_end("m20", (0, 0), "M20", kind="ext")
    shapes = {(e.shape, e.role) for e in t.edges}
    assert ("circle", "thick") in shapes and ("arc", "thin") in shapes
    arc = [e for e in t.edges if e.shape == "arc"][0]
    assert (arc.intent["end"] - arc.intent["start"]) % 360 == pytest.approx(270)
    ti = left.thread_end("m8", (40, 0), "M8", kind="int")
    assert [e.r for e in ti.edges if e.shape == "circle"][0] == pytest.approx(ti.intent["d1"] / 2)
    assert t.intent["mask"]  # the 3D chamfer circle is not drawn


def test_thread_designation_dimension(shaft):
    d, f = shaft
    f.thread("m20", "M20x1.5", 0, 26)
    el = f.dim.thread("t1", "F.front.m20")
    assert el.text == "M20×1.5-6g" and "F.front.m20" in el.refs
    f.thread("m28", "M28", 40, 70)
    assert f.dim.thread("t2", "F.front.m28").text == "M28-6g"


def test_tapped_holes_in_revolved_section():
    d = Drawing()
    f = d.view("front")
    th = {
        "name": "tap",
        "r": 40,
        "d": 6.647,
        "x0": 0,
        "x1": 20,
        "tip": True,
        "thread": "M8",
        "depth": 15,
    }
    f.turned("cv", [(0, 55), (25, 55)], bore=[(0, 20), (25, 20)], cut="full", holes=[th])
    fid = "F.front.cv"
    major = [
        e
        for e in d[fid].edges
        if e.role == "thin" and abs(abs(e.start[1]) - 40) == pytest.approx(4)
    ]
    assert len(major) == 4 and all("conv" in e.tags for e in major)
    tips = [e for e in d[fid].edges if e.shape == "line" and e.dir is None]
    assert len(tips) == 4  # 120° drill point, both halves
    for e in tips:
        dx, dy = abs(e.end[0] - e.start[0]), abs(e.end[1] - e.start[1])
        assert math.degrees(math.atan2(dx, dy)) == pytest.approx(30, abs=0.01)


def test_center_hole_designation(shaft):
    d, f = shaft
    c = f.center_hole("ch", on="F.front.body", end="left", type="A", d=2.5)
    assert c.intent["designation"] == "A2.5/5.3" and c.intent["keep"] is True
    layout(d)
    assert any("4459.5" in t and "A2.5/5.3" in t for t in texts(c))
    assert c.intent["mask"]


def test_groove_dimension(shaft):
    d = Drawing()
    f = d.view("front")
    f.turned(
        "b",
        [(0, 10), (30, 10), (30, 15), (60, 15)],
        grooves=[{"name": "u1", "x": 30, "w": 3, "d": 17}],
    )
    assert f.dim.groove("g", "F.front.u1").text == "3×Φ17"
    assert f.dim.groove("g2", "F.front.u1", fmt="wh").text == "3×1.5"


def test_keyway_and_removed_section(shaft):
    d, f = shaft
    kw = f.keyway("kw", x0=40, length=30, d=28)
    i = kw.intent
    assert (i["b"], i["t1"]) == (8, 4.0) and "1095" in i["std"]
    assert [e.shape for e in kw.edges].count("arc") == 2
    sec = d.removed_section("A", parent="front", through=[(55, -20), (55, 20)], look="left")
    cut = sec.shaft_cut("s", 28, keyway="F.front.kw")
    # keyway faces the front viewer; looking left that side is -u in the section
    xs = [p[0] for p in cut.intent["points"]]
    notch = [p for p in cut.intent["points"] if abs(p[1]) <= 4 + 1e-6 and p[0] < 0]
    assert min(xs) == pytest.approx(-(14 - 4.0) - 0.0, abs=14) and notch
    assert d[cut.intent["hatch"]].kind == "hatch"
    b = sec.dim.keyway("kb", "F.A.s", what="b")
    assert b.intent["tolerance"]["code"] == "N9" and b.value == 8
    dep = sec.dim.keyway("kd", "F.A.s", what="depth")
    assert dep.value == pytest.approx(24)


def test_hub_keyway_end_view():
    d = Drawing()
    left = d.view("left")
    k = left.keyway_end("hk", (0, 0), 30, kind="hub")
    i = k.intent
    assert (i["b"], i["t2"]) == (8, 3.3)
    ys = [max(e.start[1], e.end[1]) for e in k.edges if e.shape == "line"]
    assert max(ys) == pytest.approx(15 + 3.3)


def test_spline_axial_and_end():
    d = Drawing()
    f = d.view("front")
    left = d.view("left")
    f.turned("b", [(0, 13), (40, 13), (40, 16), (70, 16)])
    s = f.spline("sp", "6x23x26x6", 0, 30)
    thin = [e for e in s.edges if e.role == "thin"]
    assert {round(abs(e.start[1]), 3) for e in thin} == {11.5}
    assert s.intent["mask"]
    se = left.spline_end("spe", (0, 0), "6x23x26x6")
    assert len([e for e in se.edges if e.shape == "line"]) == 12  # two flanks per tooth
    assert len([e for e in se.edges if e.shape == "arc"]) == 12
    note = f.dim.spline("sd", "F.front.sp")
    assert "6×23f7×26a11×6d10" in note.text and "1144" in note.text
