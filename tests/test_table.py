"""C3 (G2 RED -> GREEN): Semantic tables (`d.table`) — creation, 1-based cells, queries,
layout, checks (`table_overflow`, `out_of_frame`, `OWN_ZONE` title regression), reactive Expr,
Viewer/SVG picking, DXF export and `lcad edit` replay/suppress."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from linercad import Drawing, Param, checks, dxfout, errors, svgout
from linercad.commands import context
from linercad.layout import Line, Text, box_overlap, layout
from linercad.runtime import build
from linercad.txn import build_commit, edit_full
from linercad.txn import init as txn_init
from linercad.viewer import Viewer, label, ref_text


def _clean_part_with_table():
    """Complete A3 part drawing with a 5x4 parameter table (1 header row + 4 data rows)."""
    d = Drawing(sheet="A3")
    P = d.params(
        da=Param(88, min=40, max=200),
        m=Param(2, min=1, max=10),
        z=Param(42, min=10, max=100),
        b=Param(24, min=8, max=80),
    )
    f = d.view("front")
    f.turned(
        "gear",
        [
            (0, P.da / 2),
            (P.b, P.da / 2),
        ],
    )
    f.dim.dia("da", (12, P.da / 2), (12, -P.da / 2), value=P.da, side="inside")
    f.dim.linear("b", (0, -P.da / 2), (P.b, -P.da / 2), value=P.b, side="bottom")
    d.general_tol("m")
    d.notes.tech(["表面淬火 45~50HRC。", "未注倒角 C1。"])
    d.title(name="直齿圆柱齿轮", material="45", drawing_no="LC-G-01")
    d.table(
        "params",
        [
            ["模数 m", P.m, "GB/T 1357", "正常齿"],
            ["齿数 z", P.z, "-", ""],
            ["顶圆直径 da", P.da, "-", P.m * (P.z + 2)],
            ["齿宽 b", P.b, "-", "精加工"],
        ],
        headers=["参数", "数值", "标准", "说明"],
        title="齿轮参数表",
    )
    return d


# ---- 1. Creation, 1-based numbering, parameters & validation ------------------------------------


def test_table_creation_headers_1based_and_no_cell_method():
    d = _clean_part_with_table()
    t = d["T.params"]
    assert t.kind == "table"
    assert not hasattr(t, "cell"), (
        "Table must not expose .cell(r, c); use d.q.cells / d['T.<name>.<r>.<c>']"
    )
    assert t.nrows == 5 and t.ncols == 4
    assert t.title == "齿轮参数表"

    # Title-block cells carry table="title"
    assert d["T.title.name"].table == "title"

    # Row 1 is headers when headers= is given
    h1 = d["T.params.1.1"]
    assert h1.kind == "table.cell"
    assert h1.table == "params"
    assert (h1.row, h1.col) == (1, 1)
    assert h1.header is True and h1.text == "参数"

    # Data rows start at row 2..5
    c22 = d["T.params.2.2"]
    assert c22.header is False and c22.text == "2"
    assert c22.covers == ["m"]
    c44 = d["T.params.4.4"]
    assert c44.text == "88"
    assert sorted(c44.covers) == ["m", "z"]
    assert d["T.params.5.4"].text == "精加工"


def test_table_without_headers_uses_1based_rows():
    d = Drawing(sheet="A3")
    t = d.table("spec", [["A", "10"], ["B", "20"]], cols=[20, 25])
    assert t.nrows == 2 and t.ncols == 2 and t.cols == [20.0, 25.0]
    assert d["T.spec.1.1"].row == 1 and d["T.spec.1.1"].col == 1
    assert d["T.spec.1.1"].header is False and d["T.spec.1.1"].text == "A"
    assert d["T.spec.2.2"].text == "20"

    # Parameter name must be cols=, never col_widths=
    with pytest.raises(TypeError):
        d.table("bad_kw", [["A", "1"]], col_widths=[20, 20])


def test_table_creation_validation_errors():
    d = Drawing(sheet="A3")
    for reserved in ("title", "bom", "frame"):
        with pytest.raises(errors.InvalidArgument):
            d.table(reserved, [["a", "b"]])
    with pytest.raises(errors.InvalidArgument):
        d.table("empty", [])
    with pytest.raises(errors.InvalidArgument):
        d.table("bad_cols_len", [["a", "b"]], cols=[20])
    with pytest.raises(errors.InvalidArgument):
        d.table("bad_cols_val", [["a", "b"]], cols=[20, -5])
    with pytest.raises(errors.InvalidArgument):
        d.table("ragged", [["a", "b"], ["c"]])
    with pytest.raises(errors.InvalidArgument):
        d.table("bad_rh", [["a", "b"]], row_height=0)
    with pytest.raises(errors.InvalidArgument):
        d.table("bad_th", [["a", "b"]], text_height=-1)
    with pytest.raises(errors.InvalidArgument):
        d.table("bad_at", [["a", "b"]], at=(10,))

    d.table("dup", [["a", "b"]])
    with pytest.raises(errors.DuplicateId):
        d.table("dup", [["c", "d"]])


def test_queries_and_title_block_table_facet():
    d = _clean_part_with_table()
    assert [t.id for t in d.q.tables()] == ["T.params"]

    all_params = d.q.cells(table="params")
    assert len(all_params) == 20
    assert d.q.cells(table="params", row=1).ids() == [f"T.params.1.{c}" for c in range(1, 5)]
    assert d.q.cells(table="params", col=2).ids() == [f"T.params.{r}.2" for r in range(1, 6)]
    assert d.q.cells(table="params", header=True).ids() == [f"T.params.1.{c}" for c in range(1, 5)]

    # Correction #1: title-block cells carry table="title"
    title_cells = d.q.cells(table="title")
    assert len(title_cells) >= 5
    assert any(c.id == "T.title.name" and c.table == "title" for c in title_cells)
    assert d.q.cells(table="title", field="name").one().id == "T.title.name"


def test_table_oob_lookup_and_query_errors_provide_candidates():
    d = _clean_part_with_table()
    for bad_id in ("T.params.0.1", "T.params.6.1", "T.params.1.0", "T.params.2.5"):
        with pytest.raises(errors.NotFound) as exc:
            _ = d[bad_id]
        assert exc.value.candidates, bad_id
        assert any(c.startswith("T.params.") for c in exc.value.candidates), (
            bad_id,
            exc.value.candidates,
        )
        assert "1..5" in exc.value.message and "1..4" in exc.value.message

    # Unknown table name
    with pytest.raises(errors.NotFound) as exc:
        d.q.cells(table="unknown")
    assert "params" in exc.value.candidates and "title" in exc.value.candidates

    # Query OOB row/col must raise InvalidArgument with 1..N candidates, never []
    with pytest.raises(errors.InvalidArgument) as exc:
        d.q.cells(table="params", row=0)
    assert exc.value.candidates == [1, 2, 3, 4, 5]

    with pytest.raises(errors.InvalidArgument) as exc:
        d.q.cells(table="params", row=6)
    assert exc.value.candidates == [1, 2, 3, 4, 5]

    with pytest.raises(errors.InvalidArgument) as exc:
        d.q.cells(table="params", col=5)
    assert exc.value.candidates == [1, 2, 3, 4]

    with pytest.raises(errors.InvalidArgument) as exc:
        d.q.cells(table="title", row=1)
    assert "name" in exc.value.candidates


# ---- 2. Layout, right-aligned stacking, view avoidance, 5x4 check clean, DXF --------------------


def test_5x4_part_drawing_clean_and_layout_placement():
    d = _clean_part_with_table()
    layout(d)
    found = checks.run(d)
    assert [f for f in found if f["severity"] == "error"] == []
    assert list(found) == []

    t = d["T.params"]
    tb = d.template["title_block"]
    tb_right = tb["origin"][0] + tb["size"][0]
    tb_top = tb["origin"][1] + tb["size"][1]
    tech_top = max(e.bbox[3] for e in d.q.notes() if e._intent.get("tech"))

    assert t.bbox is not None
    assert t.at == pytest.approx(list(t.bbox[:2]), abs=0.1)
    assert t.bbox[2] == pytest.approx(tb_right, abs=0.5)
    assert t.bbox[1] >= max(tb_top, tech_top)

    # Row 1 is above row 2; title banner sits above row 1
    r1_y = d["T.params.1.1"]._resolved["cell_box"][1]
    r2_y = d["T.params.2.1"]._resolved["cell_box"][1]
    assert r1_y > r2_y
    title_prims = [p for p in t._prims if isinstance(p, Text) and p.text == "齿轮参数表"]
    assert title_prims and title_prims[0].box[1] >= d["T.params.1.1"]._resolved["cell_box"][3] - 0.1

    # Views avoid the table zone
    vb = d["V.front"].bbox
    assert (
        vb[2] <= t.bbox[0] + 1e-3
        or vb[0] >= t.bbox[2] - 1e-3
        or vb[1] >= t.bbox[3] - 1e-3
        or vb[3] <= t.bbox[1] + 1e-3
    )

    # Grid lines live on T.<name>._prims and texts live on cells' _prims
    assert any(isinstance(p, Line) for p in t._prims)
    assert all(isinstance(p, Text) for p in d["T.params.2.1"]._prims)

    # DXF export includes table lines & cell text
    doc, _idx, _raw = dxfout.to_doc(d)
    texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() in ("TEXT", "MTEXT")]
    assert any("模数" in txt for txt in texts) and any("齿轮参数表" in txt for txt in texts)


def test_explicit_at_move_and_wrap_row_growth():
    d = Drawing(sheet="A3")
    d.view("front").rect((0, 0), 40, 20, name="box")
    t = d.table(
        "notes_tbl",
        [["第一行", "较长的说明文字会自动换行并撑高行高"], ["第二行", "短"]],
        cols=[24, 24],
        at=(40, 180),
        wrap=True,
    )
    layout(d)
    assert t.bbox[0] == pytest.approx(40.0, abs=0.1)
    assert t.bbox[1] == pytest.approx(180.0, abs=0.1)
    assert t.at == pytest.approx([40.0, 180.0], abs=0.1)
    b1 = d["T.notes_tbl.1.2"]._resolved["cell_box"]
    b2 = d["T.notes_tbl.2.2"]._resolved["cell_box"]
    assert (b1[3] - b1[1]) > (b2[3] - b2[1])

    old_bbox = list(t.bbox)
    t.move(dx=15, dy=-20)
    assert t.at == pytest.approx([55.0, 160.0], abs=0.1)
    layout(d)
    assert t.bbox[0] == pytest.approx(old_bbox[0] + 15, abs=0.1)
    assert t.bbox[1] == pytest.approx(old_bbox[1] - 20, abs=0.1)
    assert t.at == pytest.approx([55.0, 160.0], abs=0.1)
    assert d["T.notes_tbl.1.2"]._resolved["cell_box"][0] == pytest.approx(b1[0] + 15, abs=0.1)
    t.place(at=(100, 150))
    assert t.at == pytest.approx([100.0, 150.0], abs=0.1)


# ---- 3. Checks: OWN_ZONE title regression, table_overflow, out_of_frame, view avoidance -------


def test_title_block_regression_with_own_zone_change():
    d = _clean_part_with_table()
    d.title(name="超长零件名称验证标题栏单元格不会误报溢出行", material="40Cr")
    layout(d)
    found = checks.run(d)
    assert [f for f in found if f["id"].startswith("T.title.")] == []
    assert not any(f["rule"] in ("out_of_frame", "table_overflow") for f in found)
    # Overlap between title-block cells must still be caught (OWN_ZONE regression)
    t_mat = d["T.title.material"]._prims[0]
    t_name = d["T.title.name"]._prims[0]
    d["T.title.name"]._prims = [
        Text(t_name.text, t_mat.at, t_name.height, t_name.rot, t_name.layer, t_mat.box)
    ]
    ov = [f for f in checks.run(d) if f["rule"] == "overlap" and f["id"] == "T.title.name"]
    assert ov and "T.title.material" in ov[0]["measured"]["with"]


def test_table_overflow_horizontal_vertical_and_title_candidates():
    d = Drawing(sheet="A3")
    d.view("front").rect((0, 0), 30, 20, name="r")
    t = d.table(
        "ov",
        [["代号", "非常长的参数内容超出狭窄列宽"], ["短", "OK"]],
        cols=[16, 12],
        at=(100, 180),
        wrap=False,
    )
    layout(d)
    found = checks.run(d)
    ov = [f for f in found if f["rule"] == "table_overflow"]
    assert ov and ov[0]["id"] == "T.ov.1.2"
    assert ov[0]["std"] == "DESIGN §4.2"
    assert ov[0]["clause"].startswith("DESIGN §4.2")
    assert ov[0]["violations"] == [] and ov[0]["corridors"] == {}
    assert ov[0]["candidates"], ov[0]
    assert not any(f["rule"] == "overlap" and f["id"] == "T.ov.1.2" for f in found)

    # Vertical overflow when fixed row_height is smaller than wrapped lines
    t.set(wrap=True, row_height=5.0)
    layout(d)
    found_v = checks.run(d)
    ov_v = [f for f in found_v if f["rule"] == "table_overflow" and f["id"] == "T.ov.1.2"]
    assert ov_v and ov_v[0]["measured"]["overflow_y"] > 0
    assert ov_v[0]["candidates"]

    # Title overflow against narrow explicit cols
    d2 = Drawing(sheet="A3")
    d2.view("front").rect((0, 0), 30, 20, name="r")
    d2.table(
        "tov",
        [["a", "1"], ["b", "2"]],
        cols=[12, 12],
        title="非常长的语义表格标题横幅说明",
        at=(100, 180),
    )
    layout(d2)
    ov_t = [f for f in checks.run(d2) if f["rule"] == "table_overflow" and f["id"] == "T.tov"]
    assert ov_t and ov_t[0]["std"] == "DESIGN §4.2"
    assert ov_t[0]["violations"] == [] and ov_t[0]["corridors"] == {}
    assert ov_t[0]["measured"]["overflow_x"] > 0
    assert ov_t[0]["expected"]["table_w"] == pytest.approx(24.0, abs=0.1)
    assert any("cols=" in c for c in ov_t[0]["candidates"])
    assert any("cols=None" in c for c in ov_t[0]["candidates"])


def test_table_out_of_frame_reported_on_table_with_actionable_candidates():
    d = Drawing(sheet="A3")
    d.view("front").rect((0, 0), 30, 20, name="r")
    d.rough_default(6.3)
    d.table("oob", [["参数", "值"], ["m", "2"]], at=(390, 270), cols=[25, 25])
    layout(d)
    found = checks.run(d)
    oof = [f for f in found if f["rule"] == "out_of_frame"]
    assert [f["id"] for f in oof] == ["T.oob"]
    assert oof[0]["candidates"]
    cand = oof[0]["candidates"][0]
    m = re.search(r"at=\(([^,]+),\s*([^)]+)\)", cand)
    assert m, cand
    assert float(m.group(2)) > d["R.default"].bbox[3]

    # Titled table with overhanging text: suggested place(at=...) accounts for left overhang
    d2 = Drawing(sheet="A3")
    d2.view("front").rect((0, 0), 30, 20, name="r")
    t2 = d2.table(
        "overhang",
        [["a", "1"]],
        cols=[12, 12],
        title="这是一个明显超出列宽的长标题",
        at=(395, 100),
    )
    layout(d2)
    oof2 = [f for f in checks.run(d2) if f["rule"] == "out_of_frame" and f["id"] == "T.overhang"]
    assert oof2 and oof2[0]["candidates"]
    m2 = re.search(r"at=\(([^,]+),\s*([^)]+)\)", oof2[0]["candidates"][0])
    assert m2, oof2[0]["candidates"]
    t2.place(at=(float(m2.group(1)), float(m2.group(2))))
    layout(d2)
    assert not [
        f for f in checks.run(d2) if f["rule"] == "out_of_frame" and f["id"] == "T.overhang"
    ]

    # Oversized title wider than the sheet frame: never suggest an impossible place(at=...)
    d3 = Drawing(sheet="A3")
    d3.view("front").rect((0, 0), 30, 20, name="r")
    d3.table("huge", [["a", "1"]], cols=[12, 12], title="标题" * 80, at=(200, 100))
    layout(d3)
    oof3 = [f for f in checks.run(d3) if f["rule"] == "out_of_frame" and f["id"] == "T.huge"]
    assert oof3 and oof3[0]["candidates"]
    assert not any(".place(at=" in c for c in oof3[0]["candidates"])


def test_explicit_at_and_moved_tables_avoid_auto_views():
    d = Drawing(sheet="A3")
    d.view("front").rect((0, 0), 40, 20, name="box")
    d.table("p", [["", ""]], cols=[20, 20], at=(200, 140))
    layout(d)
    assert d["T.p"].bbox[:2] == pytest.approx([200.0, 140.0], abs=0.1)
    assert box_overlap(d["V.front"].bbox, d["T.p"].bbox) == 0.0

    # Moving a default table onto the auto-view center pushes the auto view clear
    d2 = Drawing(sheet="A3")
    d2.view("front").rect((0, 0), 40, 20, name="box")
    t2 = d2.table("m", [["", ""]], cols=[20, 20])
    layout(d2)
    vcx = (d2["V.front"].bbox[0] + d2["V.front"].bbox[2]) / 2
    vcy = (d2["V.front"].bbox[1] + d2["V.front"].bbox[3]) / 2
    dx = vcx - (t2.bbox[0] + t2.bbox[2]) / 2
    dy = vcy - (t2.bbox[1] + t2.bbox[3]) / 2
    t2.move(dx=dx, dy=dy)
    layout(d2)
    assert box_overlap(d2["V.front"].bbox, t2.bbox) == 0.0


# ---- 4. Viewer/SVG picking, reactive Expr, context, and edit replay ------------------------------


def test_table_svg_viewer_pick_context_and_slider_preview(tmp_path):
    txn_init(tmp_path)
    src = """from linercad import Drawing, Param

d = Drawing(sheet="A3")
P = d.params(m=Param(2, min=1, max=10), z=Param(20, min=10, max=60))
f = d.view("front")
f.turned("g", [(0, P.m * P.z / 2), (10, P.m * P.z / 2)])
f.dim.dia("d", (5, P.m * P.z / 2), (5, -P.m * P.z / 2), value=P.m * P.z, side="inside")
d.general_tol("m")
d.title(name="齿轮", material="45")
d.table(
    "params",
    [["模数", P.m, ""], ["齿数", P.z, "标准"], ["分度圆", P.m * P.z, "computed"]],
    headers=["项目", "数值", "备注"],
)
"""
    (tmp_path / "drawing.py").write_text(src, encoding="utf-8")
    build_commit(tmp_path, msg="add table")
    res = build(tmp_path)
    d = res.d

    # Empty cell still emits SVG group with data-table and transparent hit rect
    groups = {eid: (kind, html) for eid, kind, html in svgout.svg_groups(d)}
    assert "T.params" in groups and groups["T.params"][0] == "table"
    empty_id = "T.params.2.3"
    assert empty_id in groups and 'data-table="params"' in groups[empty_id][1]
    assert 'class="cell-hit"' in groups[empty_id][1]
    assert 'data-table="title"' in groups["T.title.name"][1]

    # viewer.js only skips frame and table (title-block and semantic table cells are pickable)
    vjs = (
        Path(__file__).resolve().parents[1] / "src" / "linercad" / "viewer" / "viewer.js"
    ).read_text(encoding="utf-8")
    assert 'kind === "frame"' in vjs and 'kind === "table"' in vjs
    assert 'dataset.table === "title"' not in vjs

    # Viewer model + slider preview updates reactive Expr cells
    v = Viewer(tmp_path)
    model = v.model()
    by_id = {e["id"]: e for e in model["elements"]}
    assert empty_id in by_id
    assert by_id["T.params.4.2"]["intent"]["text"] == "40"
    assert by_id["T.params.4.2"]["intent"]["table"] == "params"
    assert by_id["T.params.4.2"]["intent"]["row"] == 4
    assert by_id["T.params.4.2"]["intent"]["col"] == 2
    assert label(d["T.params.2.2"]) == "2" and "T.params.2.2" in ref_text(d["T.params.2.2"])

    pv = v.do_preview({"m": 4})
    assert pv["ok"]
    pv_model = {e["id"]: e for e in v.model()["elements"]}
    assert pv_model["T.params.2.2"]["intent"]["text"] == "4"
    assert pv_model["T.params.4.2"]["intent"]["text"] == "80"
    assert "80" in v.preview["svg"]

    # lcad context overview + single element (snippet cols length matches table.ncols)
    ctx_all = context(tmp_path)
    assert "table" in ctx_all["elements"]
    ctx_tbl = context(tmp_path, ["T.params"])
    snip = ctx_tbl["items"][0]["snippet"]
    assert ctx_tbl["items"][0]["element"]["kind"] == "table" and snip
    cols_line = next(line for line in snip if "set(cols=" in line)
    m = re.search(r"cols=(\[[^\]]+\])", cols_line)
    assert m, cols_line
    parsed_cols = ast.literal_eval(m.group(1))
    assert len(parsed_cols) == d["T.params"].ncols == 3
    d["T.params"].set(cols=parsed_cols)
    ctx_cell = context(tmp_path, ["T.params.2.2"])
    assert (
        ctx_cell["items"][0]["element"]["kind"] == "table.cell" and ctx_cell["items"][0]["snippet"]
    )


def test_edit_replay_table_cell_move_and_suppress(tmp_path):
    txn_init(tmp_path)
    (tmp_path / "drawing.py").write_text(
        """from linercad import Drawing

d = Drawing(sheet="A3")
d.view("front").rect((0, 0), 30, 20, name="r")
d.title(name="零件", material="45")
""",
        encoding="utf-8",
    )
    build_commit(tmp_path, msg="base drawing")

    s1 = tmp_path / "e1.py"
    s1.write_text(
        """def apply(d):
    t = d.table("p", [["a", "1"], ["b", "2"]], headers=["k", "v"])
    d["T.p.2.2"].text = "99"
    t.move(dx=-10, dy=12)
""",
        encoding="utf-8",
    )
    out1, res1 = edit_full(tmp_path, s1, "add table and tweak")
    assert out1["ok"]
    assert res1.d["T.p.2.2"].text == "99"
    x0 = res1.d["T.p"].bbox[0]

    rebuilt = build(tmp_path)
    assert rebuilt.d["T.p.2.2"].text == "99"
    assert rebuilt.d["T.p"].bbox[0] == pytest.approx(x0, abs=0.05)

    with pytest.raises(errors.InvalidArgument):
        rebuilt.d["T.p.2.2"].suppress()

    s2 = tmp_path / "e2.py"
    s2.write_text(
        """def apply(d):
    d["T.p"].suppress()
""",
        encoding="utf-8",
    )
    out2, res2 = edit_full(tmp_path, s2, "suppress table")
    assert out2["ok"]
    assert "T.p" not in res2.d and "T.p.2.2" not in res2.d
