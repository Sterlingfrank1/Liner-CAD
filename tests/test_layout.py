import math

import pytest

from linercad import Drawing, Param, checks, errors
from linercad.layout import Circle, Line, Solid, Text, layout, seg_in_box
from linercad.text import dxf_height, text_size


def texts(el):
    return [p for p in el._prims if isinstance(p, Text)]


def lines(el, layer=None):
    return [p for p in el._prims if isinstance(p, Line) and (layer is None or p.layer == layer)]


@pytest.fixture
def shaft():
    d = Drawing(sheet="A3")
    P = d.params(L=Param(120), D1=Param(30), D2=Param(40), l1=Param(40))
    f = d.view("front")
    f.turned("body", [(0, P.D1 / 2), (P.l1, P.D1 / 2), (P.l1, P.D2 / 2), (P.L, P.D2 / 2)])
    return d, P, f


# ---- text metrics -------------------------------------------------------------------------------


def test_cjk_text_height_rule(shaft):
    d, *_ = shaft
    std = d.std
    assert dxf_height("Φ30", 3.5, std) == 3.5
    assert dxf_height("技术要求", 3.5, std) == pytest.approx(3.5 / std["text"]["cjk_em"])
    w, h = text_size("技术要求", 5, std)
    assert w == pytest.approx(4 * 5 * std["text"]["width_factor"], rel=1e-3)


def test_width_estimate_not_below_ezdxf_measurement(shaft):
    from ezdxf.fonts import fonts

    d, *_ = shaft
    std = d.std
    if not fonts.font_manager.has_font(std["text"]["font"]):
        pytest.skip("simfang.ttf not installed")
    for s in ["技术要求", "Φ30h7", "4×Φ12 EQS", "调质处理220~250HBW。", "A-A", "R5", "1234567890"]:
        dh = dxf_height(s, 3.5, std)
        f = fonts.make_font(
            std["text"]["font"], cap_height=dh, width_factor=std["text"]["width_factor"]
        )
        assert text_size(s, 3.5, std)[0] >= f.text_width(s) - 1e-6, s


# ---- linear dimensions ----------------------------------------------------------------------------


def test_same_side_sorted_by_length_and_pushed_out(shaft):
    d, P, f = shaft
    f.dim.linear("L", (0, -P.D2 / 2), (P.L, -P.D2 / 2), value=P.L, role="overall", side="bottom")
    f.dim.linear("l1", (0, -P.D1 / 2), (P.l1, -P.D1 / 2), side="bottom")
    f.dim.linear("l2", (P.l1, -P.D2 / 2), (P.L, -P.D2 / 2), side="bottom")
    layout(d)
    L, l1, l2 = d["D.L"], d["D.l1"], d["D.l2"]
    assert (l1.row, l2.row) == (1, 1)  # chain dims share a row (open-interval rule)
    assert L.row == 2 and "第 2 排" in L.placement["reason"]
    assert L.placement["auto"] == ["row"]
    # dimension line of row 2 is row_pitch below row 1
    y1 = lines(l1, "dim")[-1].p[1]
    y2 = lines(L, "dim")[-1].p[1]
    assert y1 - y2 == pytest.approx(d.std["dim"]["row_pitch"])


def test_written_layout_is_kept(shaft):
    d, P, f = shaft
    f.dim.linear("l1", (0, -15), (40, -15), side="bottom", row=3, offset=1.5)
    layout(d)
    el = d["D.l1"]
    assert (el.side, el.row, el.offset) == ("bottom", 3, 1.5)
    assert el.placement["auto"] == []
    G_bottom = -20  # D2/2
    origin_y = d.view("front")._resolved["origin"][1]
    y = lines(el, "dim")[-1].p[1] - origin_y
    dm = d.std["dim"]
    assert y == pytest.approx(G_bottom - (dm["first_row"] + 2 * dm["row_pitch"] + 1.5))


def test_nearest_side_default(shaft):
    d, P, f = shaft
    f.dim.linear("top", (0, 15), (40, 15))
    f.dim.linear("bot", (0, -15), (40, -15))
    f.dim.linear("rgt", (120, -20), (120, 20))
    layout(d)
    assert (d["D.top"].side, d["D.bot"].side, d["D.rgt"].side) == ("top", "bottom", "right")


def test_inside_dia_text_avoids_axis(shaft):
    d, P, f = shaft
    f.dim.dia("D2", (80, P.D2 / 2), (80, -P.D2 / 2), value=P.D2, side="inside")
    layout(d)
    el = d["D.D2"]
    (t,) = texts(el)
    assert t.rot == 90
    axis = lines(d["C.front.body"])
    assert all(seg_in_box(a.p, a.q, t.box) == 0 for a in axis)
    assert "移位" in el.placement["reason"]
    assert not [x for x in checks.run(d) if x["id"] == "D.D2"]


def test_short_dim_text_goes_outside(shaft):
    d, P, f = shaft
    f.dim.linear("tiny", (0, 15), (3, 15), side="top")
    layout(d)
    el = d["D.tiny"]
    (t,) = texts(el)
    origin = d.view("front")._resolved["origin"]
    assert t.box[0] > origin[0] + 3  # right of the second extension line
    assert "界线外" in el.placement["reason"]


def test_vertical_dim_text_left_of_line(shaft):
    d, P, f = shaft
    f.dim.linear("h", (120, -20), (120, 20), side="right")
    layout(d)
    el = d["D.h"]
    (t,) = texts(el)
    dimline = lines(el, "dim")[-1]
    assert t.rot == 90 and t.box[2] < dimline.p[0]


# ---- circles, notes ------------------------------------------------------------------------------


def test_circle_dia_candidates_and_fixed_at():
    d = Drawing()
    v = d.view("left")
    c = v.circle((0, 0), 30, name="outer")
    v.dim.dia("Do", circle=c)
    v.dim.dia("Do2", circle=c, at=200)
    layout(d)
    assert d["D.Do"].at == 45 and d["D.Do"].placement["auto"] == ["at"]
    assert d["D.Do2"].at == 200 and d["D.Do2"].placement["auto"] == []
    sol = [p for p in d["D.Do"]._prims if isinstance(p, Solid)]
    assert len(sol) == 2


def test_note_direction_candidates(shaft):
    d, P, f = shaft
    f.note("c1", "C1", anchor="E.front.body.1:start")
    f.note("c2", "C1", anchor="E.front.body.1:start")
    layout(d)
    assert d["N.c1"].placement["resolved"]["dir"] == 45
    assert d["N.c2"].placement["resolved"]["dir"] != 45  # first direction now taken


def test_unavoidable_conflict_reported_with_corridors(shaft):
    d, P, f = shaft
    for k in range(8):  # more fixed-row dims than candidates can separate
        f.dim.linear(f"x{k}", (0, 20), (120, 20), side="top", row=1)
    layout(d)
    found = [x for x in checks.run(d) if x["rule"] == "overlap"]
    assert found
    f0 = found[0]
    assert f0["violations"] and set(f0["corridors"]) == {"left", "right", "up", "down"}
    assert d[f0["id"]].status == "warn"
    d.accept("overlap", f0["id"], "测试放行")
    assert all(x["id"] != f0["id"] for x in checks.run(d) if x["rule"] == "overlap")
    assert d[f0["id"]].status == "accepted(测试放行)"


# ---- centre lines ---------------------------------------------------------------------------------


def test_centre_lines_start_and_end_on_long_dash(shaft):
    d, P, f = shaft
    layout(d)
    pat = d.std["linetypes"]["LC_CENTER"]["pattern"]
    period, dash = sum(abs(x) for x in pat), pat[0]
    (axis,) = lines(d["C.front.body"])
    ext = d.std["center"]["extend"]
    L = math.dist(axis.p, axis.q)
    assert L == pytest.approx(120 + 2 * ext)
    units = L / axis.ltscale  # length in pattern units: k periods + one long dash
    assert (units - dash) / period == pytest.approx(round((units - dash) / period))


def test_center_mark_four_pieces_from_centre():
    d = Drawing()
    v = d.view("front")
    v.center_mark((0, 0), 5)
    layout(d)
    pieces = lines(d["C.front.1"])
    assert len(pieces) == 4 and len({p.p for p in pieces}) == 1  # all start at the centre


def test_circle_dim_leader_lengthens_to_clear_outline():
    d = Drawing()
    v = d.view("left")
    v.circle((0, 0), 60, name="outer")
    v.holes_on_circle("bolt", (0, 0), pcd=90, n=4, d=12)
    v.dim.dia("holes", circle="E.left.bolt.1", prefix="4×", suffix=" EQS")
    layout(d)
    assert not [x for x in checks.run(d) if x["id"] == "D.holes"]
    assert "加长" in d["D.holes"].placement["reason"]


# ---- views, frame, sections --------------------------------------------------------------------


@pytest.fixture
def three_views():
    d = Drawing(sheet="A3")
    fr, tp, lf = d.view("front"), d.view("top"), d.view("left")
    fr.rect((0, 0), 80, 60, name="body")
    tp.rect((0, 0), 80, 50, name="body")
    lf.rect((-50, 0), 50, 60, name="body")
    fr.dim.linear("L", (0, 0), (80, 0))
    fr.dim.linear("H", (0, 0), (0, 60))
    tp.dim.linear("W", (0, 0), (0, 50))
    return d


def test_first_angle_arrangement_and_alignment(three_views):
    d = three_views
    layout(d)
    o = {n: d.view(n)._resolved["origin"] for n in ("front", "top", "left")}
    assert o["top"][0] == pytest.approx(o["front"][0])  # 长对正
    assert o["left"][1] == pytest.approx(o["front"][1])  # 高平齐
    assert o["top"][1] < o["front"][1] and o["left"][0] > o["front"][0]
    vb = {n: d.view(n).bbox for n in ("front", "top", "left")}
    gap = d.std["views"]["gap"]
    assert vb["front"][1] - vb["top"][3] == pytest.approx(gap)
    assert vb["left"][0] - vb["front"][2] >= gap - 1e-9
    assert not [x for x in checks.run(d) if x["rule"] in ("out_of_frame", "view_align")]


def test_view_align_check(three_views):
    d = three_views
    d.view("top").rect((0, 0), 85, 10, name="extra")
    layout(d)
    f = [x for x in checks.run(d) if x["rule"] == "view_align"]
    assert f and f[0]["id"] == "V.top" and "长对正" in f[0]["message"]


def test_group_avoids_title_block_and_tech_notes(three_views):
    d = three_views
    d.notes.tech(["调质处理 220~250HBW。", "未注倒角 C1。"])
    d.title(name="支架", material="HT200")
    layout(d)
    assert not [x for x in checks.run(d) if x["rule"] == "out_of_frame"]
    n1 = d["N.tech.1"]
    tb = d.template["title_block"]
    assert n1.bbox[1] > tb["origin"][1] + tb["size"][1]
    assert texts(n1)[0].text == "技术要求" and texts(n1)[1].text.startswith("1. ")
    assert texts(d["T.title.name"])[0].text == "支架"


def test_view_offset_and_pin(three_views):
    d = three_views
    layout(d)

    def rel():
        return d.view("top")._resolved["origin"][1] - d.view("front")._resolved["origin"][1]

    base = rel()
    d.view("top").move(dy=-5)
    layout(d)
    assert rel() == pytest.approx(base - 5)  # offsets are relative to the arrangement
    d.view("front").place(at=(100, 200))
    layout(d)
    assert d.view("front")._resolved["origin"] == [100, 200]


def test_to_sheet_and_to_local(three_views):
    d = three_views
    with pytest.raises(errors.InvalidArgument):
        d.view("front").to_sheet(0, 0)
    layout(d)
    ox, oy = d.view("front")._resolved["origin"]
    assert d.view("front").to_sheet(10, 20) == (ox + 10, oy + 20)
    assert d.view("front").to_local(ox + 10, oy + 20) == pytest.approx((10, 20))


def test_section_symbols_and_label():
    d = Drawing()
    fr, lf = d.view("front"), d.view("left")
    up = fr.polygon([(0, 15), (20, 15), (20, 60), (0, 60)], name="upper")
    fr.polygon([(0, -60), (20, -60), (20, -15), (0, -15)], name="lower")
    fr.hatch("sec", loops=[up, "F.front.lower"])
    lf.circle((0, 0), 60, name="outer")
    lf.circle((0, 0), 15, name="bore")
    fr.dim.linear("T", (0, 60), (20, 60), side="top")
    d.section("A", view="front", cut_in="left", through=[(0, -70), (0, 70)])
    layout(d)
    s = d["S.A"]
    strokes = [p for p in s._prims if isinstance(p, Line) and p.layer == "section"]
    assert len(strokes) == 2
    lo = d.view("left")._resolved["origin"]
    for st in strokes:  # outside the circle, on the vertical through the centre
        assert (
            st.p[0] == pytest.approx(lo[0])
            and abs(st.p[1] - lo[1]) >= 60 + d.std["section"]["stroke_gap"] - 1e-9
        )
    heads = [p for p in s._prims if isinstance(p, Solid)]
    assert len(heads) == 2 and all(
        h.pts[0][0] < strokes[0].p[0] for h in heads
    )  # arrows point left
    label = [t for t in texts(s) if t.text == "A-A"]
    assert len(label) == 1
    assert label[0].box[1] > d["D.T"].bbox[3]
    letters = [t for t in texts(s) if t.text == "A"]
    assert len(letters) == 2
    h = d["H.front.sec"]._prims[0]
    assert len(h.loops) == 2


def test_hatch_text_is_not_a_conflict():
    d = Drawing()
    fr = d.view("front")
    up = fr.polygon([(0, 0), (60, 0), (60, 40), (0, 40)], name="blk")
    fr.hatch("s", loops=[up])
    fr.dim.linear("w", (5, 20), (55, 20), side="inside")
    layout(d)
    assert not [x for x in checks.run(d) if x["id"] == "D.w"]


def test_layout_is_deterministic(three_views):
    d = three_views
    layout(d)
    a = {e.id: list(e._prims) for e in d.elements}
    layout(d)
    b = {e.id: list(e._prims) for e in d.elements}
    assert a == b


def test_out_of_frame_check():
    d = Drawing(sheet="A4")
    d.view("front").rect((0, 0), 400, 50, name="huge")
    layout(d)
    f = [x for x in checks.run(d) if x["rule"] == "out_of_frame"]
    assert any(x["id"].startswith("E.front.huge") for x in f)


def test_stale_findings_and_accept():
    d = Drawing()
    stale = [
        {
            "edit": "e3",
            "line": 4,
            "op": "set",
            "id": "D.gone",
            "reason": "目标不存在",
            "candidates": ["D.g"],
        }
    ]
    f = checks.run(d, stale)
    assert f[0]["rule"] == "stale_op" and f[0]["edit"] == "e3" and f[0]["candidates"] == ["D.g"]
    d.accept("stale_op", "D.gone", "已知")
    assert checks.run(d, stale) == []
    with pytest.raises(errors.InvalidArgument):
        d.accept("nope", "D.gone", "x")
    with pytest.raises(errors.InvalidArgument):
        d.accept("overlap", "T.frame", "")


def test_circle_prims_scaled():
    d = Drawing(scale="1:2")
    v = d.view("front")
    v.circle((0, 0), 20, name="c")
    layout(d)
    (c,) = [p for p in d["E.front.c.1"]._prims if isinstance(p, Circle)]
    assert c.r == 10
