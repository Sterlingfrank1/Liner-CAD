"""M1 C2: revolved sections, section paths, auxiliary views (removed section, detail, oblique),
wavy lines, thin-outline hatches, per-view scale (SPEC §4 turned, §5)."""

import math

import pytest

from linercad import Drawing, Param
from linercad.layout import Arc, Circle, Hatch, Line, Poly, Text, layout


def area(pts):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def hatch_area(d, hid):
    return sum(area([tuple(p) for p in lp["points"]]) for lp in d[hid]._intent["loops"])


def vlines(d, fid, x, role="thick"):
    """y-intervals of vertical edges of a feature at x."""
    out = []
    for e in d[fid].edges:
        i = e._intent
        if e.shape == "line" and i["role"] == role and abs(i["p1"][0] - x) < 1e-6:
            if abs(i["p2"][0] - x) < 1e-6:
                out.append(tuple(sorted((i["p1"][1], i["p2"][1]))))
    return sorted(out)


def covers(intervals, lo, hi):
    pos = lo
    for a, b in sorted(intervals):
        if a > pos + 1e-6:
            return False
        pos = max(pos, b)
    return pos >= hi - 1e-6


def hlines(d, fid, y, role="thick"):
    return [
        e
        for e in d[fid].edges
        if e.shape == "line"
        and e._intent["role"] == role
        and abs(e._intent["p1"][1] - y) < 1e-6
        and abs(e._intent["p2"][1] - y) < 1e-6
    ]


# ---- revolved parts: bore, full / half section, axial holes, grooves -------------------------


def sleeve(cut, **kw):
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.turned("s", [(0, 20), (50, 20)], bore=[(0, 10), (50, 10)], cut=cut, **kw)
    return d


def test_full_section_sleeve():
    d = sleeve("full")
    assert d["F.front.s"]._intent["hatch"] == "H.front.s"
    assert hatch_area(d, "H.front.s") == pytest.approx(1000)
    # end faces: one visible line across the whole height (far half of the end face)
    assert covers(vlines(d, "F.front.s", 0), -20, 20)
    assert covers(vlines(d, "F.front.s", 50), -20, 20)
    assert hlines(d, "F.front.s", 10) and hlines(d, "F.front.s", -10)
    assert not [e for e in d["F.front.s"].edges if e._intent["role"] == "hidden"]


def test_half_section_upper_cut_lower_exterior():
    d = sleeve("half")
    loops = d["H.front.s"]._intent["loops"]
    assert hatch_area(d, "H.front.s") == pytest.approx(500)
    assert all(p[1] >= -1e-9 for lp in loops for p in lp["points"])
    assert hlines(d, "F.front.s", 10) and not hlines(
        d, "F.front.s", -10
    )  # bore only in the cut half
    assert not [e for e in d["F.front.s"].edges if e._intent["role"] == "hidden"]
    assert covers(vlines(d, "F.front.s", 0), -20, 20)


def test_exterior_with_hidden_bore():
    d = sleeve(None)
    hidden = [e for e in d["F.front.s"].edges if e._intent["role"] == "hidden"]
    assert {round(e._intent["p1"][1], 6) for e in hidden if e.dir == "h"} == {10, -10}
    assert "hatch" not in d["F.front.s"]._intent or d["F.front.s"]._intent["hatch"] is None
    d2 = sleeve(None, hidden=False)
    assert not [e for e in d2["F.front.s"].edges if e._intent["role"] == "hidden"]


def test_stepped_bore_far_edges_visible_across_hollow():
    d = Drawing()
    f = d.view("front")
    f.turned("b", [(0, 30), (40, 30)], bore=[(0, 10), (15, 10), (15, 18), (40, 18)], cut="full")
    # the bore step at x=15 shows a line across the hollow plus the cut edge: [-18, 18]
    assert covers(vlines(d, "F.front.b", 15), -18, 18)
    assert hatch_area(d, "H.front.b") == pytest.approx(2 * (15 * 20 + 25 * 12))


def test_axial_holes_cut_out_of_section():
    d = Drawing()
    f = d.view("front")
    f.turned(
        "fl",
        [(0, 60), (15, 60), (15, 30), (40, 30)],
        bore=[(0, 15), (40, 15)],
        cut="full",
        holes=[{"name": "bolt", "r": 45, "d": 12, "x0": 0, "x1": 15}],
    )
    assert hatch_area(d, "H.front.fl") == pytest.approx(2 * (15 * 45 + 25 * 15 - 15 * 12))
    for y in (39, 51, -39, -51):
        assert hlines(d, "F.front.fl", y), y
    centers = [e for e in d.q.centers(view="front")]
    assert any(abs(c._intent.get("p1", [0, 0])[1] - 45) < 1e-6 for c in centers)


def test_groove_spliced_into_profile():
    d = Drawing()
    f = d.view("front")
    body = f.turned(
        "sh",
        [(0, 10), (30, 10), (30, 15), (60, 15)],
        grooves=[{"name": "u1", "x": 30, "w": 3, "d": 17}],
    )
    prof = [tuple(p) for p in body._intent["profile"]]
    assert prof == [(0, 10), (27, 10), (27, 8.5), (30, 8.5), (30, 15), (60, 15)]
    g = d["F.front.u1"]
    assert g.type == "groove" and g._intent["x0"] == 27 and g._intent["x1"] == 30
    assert "F.front.sh" in g.refs


def test_named_profile_segments_stable_under_grooves():
    d = Drawing()
    f = d.view("front")
    f.turned(
        "sh",
        [(0, 10, "j1"), (30, 10), (30, 15, "d2"), (60, 15)],
        grooves=[{"name": "u1", "x": 30, "w": 3, "d": 17}],
    )
    top, lo = d["E.front.sh.d2"]._intent, d["E.front.sh.d2_lo"]._intent
    assert (top["p1"], top["p2"]) == ([30, 15], [60, 15])
    assert (lo["p1"], lo["p2"]) == ([30, -15], [60, -15])
    assert d["E.front.sh.j1"]._intent["p2"] == [27, 10]


def test_turned_m0_edge_numbering_unchanged():
    d = Drawing()
    f = d.view("front")
    f.turned("b", [(0, 10), (20, 10), (20, 15), (40, 15)])
    e = d["E.front.b.1"]._intent
    assert (e["p1"], e["p2"]) == ([0, 10], [20, 10])


# ---- section paths ---------------------------------------------------------------------------------


@pytest.fixture
def block():
    d = Drawing(sheet="A3")
    P = d.params(L=Param(80))
    f = d.view("front")
    t = d.view("top")
    f.rect((0, 0), P.L, 30, name="body")
    t.rect((0, -20), P.L, 40, name="body")
    return d, f, t


def section_strokes(el):
    return [p for p in el._prims if isinstance(p, Line) and p.layer == "section"]


def letters(el):
    return [p.text for p in el._prims if isinstance(p, Text)]


def test_stepped_section_symbols(block):
    d, f, t = block
    s = d.section(
        "A", view="front", cut_in="top", through=[(-5, -10), (40, -10), (40, 10), (85, 10)]
    )
    assert s._intent["kind"] == "stepped"
    layout(d)
    assert len(section_strokes(s)) == 2 + 2 * 2  # two ends + an L at each of the two bends
    assert letters(s).count("A") == 4 and "A-A" in letters(s)


def test_aligned_section_kind():
    d = Drawing()
    f = d.view("front")
    left = d.view("left")
    f.rect((0, -40), 20, 80, name="body")
    left.circle((0, 0), 40, name="disc")
    s = d.section("A", view="front", cut_in="left", through=[(0, 45), (0, 0), (39, -22.5)])
    assert s._intent["kind"] == "aligned"
    full = d.section("B", view="front", cut_in="left", through=[(-45, 0), (45, 0)], look="up")
    assert full._intent["kind"] == "full"


# ---- auxiliary views ----------------------------------------------------------------------------------


@pytest.fixture
def shaft():
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.turned(
        "body",
        [(0, 10), (30, 10), (30, 15), (90, 15)],
        grooves=[{"name": "u1", "x": 30, "w": 3, "d": 17}],
    )
    return d, f


def test_removed_section_below_on_cut_line(shaft):
    d, f = shaft
    sec = d.removed_section("B", parent="front", through=[(60, -20), (60, 20)])
    assert sec.id == "V.B" and sec._intent["aux"] == "section"
    assert d["S.B"]._intent["view"] == "B"
    assert sec._intent["axes"]["v"] == [0, 1] and sec._intent["axes"]["depth"] in (1, -1)
    sec.circle((0, 0), 15, name="cut")
    layout(d)
    cx = sec.to_sheet(0, 0)[0]
    assert cx == pytest.approx(f.to_sheet(60, 0)[0])
    assert sec.bbox[3] < f.bbox[1]
    assert "B-B" in letters(d["S.B"])


def test_removed_section_depth_axis_follows_look(shaft):
    d, _ = shaft
    a = d.removed_section("C", parent="front", through=[(60, -20), (60, 20)], look="left")
    b = d.removed_section("D", parent="front", through=[(70, -20), (70, 20)], look="right")
    assert a._intent["axes"]["depth"] == -b._intent["axes"]["depth"]


def test_detail_view_clips_scales_and_labels(shaft):
    d, f = shaft
    det = d.detail("I", parent="front", center=(30, 10), r=5, scale="4:1")
    assert det.scale == 4 and det._intent["aux"] == "detail"
    det.dim.linear("gw", (27, 8.5), (30, 8.5), side="bottom")
    layout(d)
    c = det.to_sheet(30, 10)
    for p in det._prims:
        if isinstance(p, Line) and p.layer in ("thick", "hatch"):  # not the label's rule
            assert math.dist(p.p, c) <= 5 * 4 + 1e-6 and math.dist(p.q, c) <= 5 * 4 + 1e-6, p
    assert any(
        isinstance(p, Poly) and p.layer == "thin" for p in det._prims
    )  # wavy edge in material
    assert {"I", "4:1"} <= set(letters(det))
    marker = d["S.I"]
    assert any(isinstance(p, Circle) and p.r == pytest.approx(5 * d.scale) for p in marker._prims)
    assert "I" in letters(marker)
    dim_line = [p for p in d["D.gw"]._prims if isinstance(p, Line)]
    assert d["D.gw"].text == "3"
    assert max(math.dist(p.p, p.q) for p in dim_line) >= 12 - 1e-6


def test_detail_hatch_regenerated_as_lines():
    d = Drawing()
    f = d.view("front")
    f.turned("s", [(0, 20), (50, 20)], bore=[(0, 10), (50, 10)], cut="full")
    det = d.detail("II", parent="front", center=(0, 15), r=6, scale="2:1")
    layout(d)
    hl = [p for p in det._prims if isinstance(p, Line) and p.layer == "hatch"]
    assert hl and not [p for p in det._prims if isinstance(p, Hatch)]
    c = det.to_sheet(0, 15)
    assert all(math.dist(p.p, c) <= 12 + 1e-6 and math.dist(p.q, c) <= 12 + 1e-6 for p in hl)


def test_oblique_view_marker_and_label(shaft):
    d, f = shaft
    obl = d.oblique("E", parent="front", at=(80, 20), look=-60, rotate=True)
    obl.rect((-10, -5), 20, 10, name="face")
    layout(d)
    m = d["S.E"]
    assert "E" in letters(m) and any(p.layer == "thin" for p in m._prims if isinstance(p, Line))
    assert "E" in letters(obl) or "E" in letters(m)
    assert any(isinstance(p, Arc) for p in d["S.E"]._prims + obl._prims)  # rotation symbol


def test_aux_view_place_at(shaft):
    d, f = shaft
    sec = d.removed_section("B", parent="front", through=[(60, -20), (60, 20)])
    sec.circle((0, 0), 15, name="cut")
    sec.place(at=(300, 60))
    layout(d)
    assert sec._resolved["origin"] == pytest.approx([300, 60])


# ---- wavy lines, coincident sections ----------------------------------------------------------------


def test_wavy_line(shaft):
    d, f = shaft
    w = f.wavy("brk", [(50, -15), (50, 15)])
    assert w.id == "W.front.brk"
    layout(d)
    polys = [p for p in w._prims if isinstance(p, Poly)]
    assert len(polys) == 1 and polys[0].layer == "thin" and len(polys[0].pts) > 10
    x0 = f.to_sheet(50, 0)[0]
    assert all(abs(p[0] - x0) <= d.std["wavy"]["amplitude"] + 1e-6 for p in polys[0].pts)


def test_hatch_outline_thin(shaft):
    d, f = shaft
    h = f.hatch("rs", loops=[[(40, -5), (45, -5), (45, 5), (40, 5)]], outline="thin")
    layout(d)
    assert len([p for p in h._prims if isinstance(p, Line) and p.layer == "thin"]) == 4


def test_aux_views_record_and_replay(tmp_path):
    from linercad import txn
    from linercad.runtime import build

    p = tmp_path / "s"
    txn.init(p, from_="shaft")
    script = p / ".linercad/tmp/aux.py"
    script.write_text(
        "def apply(d):\n"
        "    sec = d.removed_section('B', parent='front', through=[(100, -25), (100, 25)])\n"
        "    sec.circle((0, 0), 18, name='cut')\n"
        "    d.detail('I', parent='front', center=(30, 12.5), r=4, scale='4:1')\n"
        "    d.view('front').wavy('brk', [(150, -15), (150, 15)])\n",
        encoding="utf-8",
    )
    out = txn.edit(p, script, "加断面和放大图")
    assert out["ok"], out
    d = build(p).d
    for i in ("V.B", "S.B", "F.B.cut", "V.I", "S.I", "W.front.brk"):
        assert i in d, i
