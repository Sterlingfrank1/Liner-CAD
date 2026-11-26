"""PR-1 R7: All 16 title-block cells (including empty fields) are pickable in SVG and Viewer."""

from __future__ import annotations

import re
from importlib import resources

import pytest

from linercad import Drawing, commands, dxfout, svgout, txn
from linercad.layout import layout
from linercad.viewer import Viewer, label, ref_text


@pytest.mark.parametrize("std", ["GB", "ISO"])
def test_all_16_title_cells_get_cell_box_and_svg_hit_rect(std):
    d = Drawing(sheet="A3", std=std)
    d.view("front").rect((0, 0), 30, 20, name="r")
    d.title(name="测试零件", material="45")
    layout(d)

    tb = d.template["title_block"]
    ox, oy = tb["origin"]
    fields = list(tb["fields"])
    assert len(fields) == 16

    groups = {eid: (kind, html) for eid, kind, html in svgout.svg_groups(d)}
    for field in fields:
        eid = f"T.title.{field}"
        cell = d[eid]
        x0, y0, x1, y1 = tb["fields"][field]["box"]
        assert cell._resolved.get("cell_box") == pytest.approx([ox + x0, oy + y0, ox + x1, oy + y1])
        if not cell.text:
            assert cell._prims == []
        assert eid in groups
        kind, html = groups[eid]
        assert kind == "table.cell"
        assert 'data-table="title"' in html
        assert 'class="cell-hit"' in html and 'data-k="hit"' in html

    # Empty title cells produce zero DXF text entities
    doc, idx, _raw = dxfout.to_doc(d)
    assert idx["T.title.company"] == []
    assert d["T.title.company"].text == ""


def test_empty_title_cell_is_in_viewer_model_selectable_and_editable(tmp_path):
    p = tmp_path / "t"
    txn.init(p)
    (p / "drawing.py").write_text(
        "from linercad import Drawing\n"
        "d = Drawing(sheet='A3', std='GB')\n"
        "d.view('front').rect((0, 0), 30, 20, name='r')\n"
        "d.title(name='底座')\n",
        encoding="utf-8",
    )
    txn.build_commit(p, msg="base")

    v = Viewer(p)
    model = v.model()
    by_id = {e["id"]: e for e in model["elements"]}
    title_ids = [eid for eid in by_id if eid.startswith("T.title.")]
    assert len(title_ids) == 16
    assert "T.title.company" in by_id
    comp_el = v.res.d["T.title.company"]
    assert label(comp_el) == ""
    assert ref_text(comp_el) == "@T.title.company"
    assert by_id["T.title.company"]["intent"]["field"] == "company"
    assert by_id["T.title.company"]["intent"]["label"] == "单位名称"

    sel = v.select(["T.title.company"])
    assert sel["ok"] is True and sel["ids"] == ["T.title.company"]
    ctx = commands.context(p, ["@sel"])
    assert [x["element"]["id"] for x in ctx["items"]] == ["T.title.company"]

    # Fill then clear back to empty
    s1 = p / ".linercad" / "tmp" / "fill.py"
    s1.parent.mkdir(parents=True, exist_ok=True)
    s1.write_text('def apply(d):\n    d["T.title.company"].text = "星际精密"\n', encoding="utf-8")
    assert txn.edit(p, s1, "填单位名称")["ok"]
    v2 = Viewer(p)
    assert v2.res.d["T.title.company"]._prims
    assert ref_text(v2.res.d["T.title.company"]) == "@T.title.company（星际精密）"

    s2 = p / ".linercad" / "tmp" / "clear.py"
    s2.write_text('def apply(d):\n    d["T.title.company"].text = ""\n', encoding="utf-8")
    assert txn.edit(p, s2, "清空单位名称")["ok"]
    v3 = Viewer(p)
    assert v3.res.d["T.title.company"]._prims == []
    assert "cell_box" in v3.res.d["T.title.company"]._resolved


def test_viewer_js_does_not_skip_title_cells():
    js = (resources.files("linercad.viewer") / "viewer.js").read_text(encoding="utf-8")
    assert 'dataset.table === "title"' not in js
    assert re.search(r'kind === "frame".*kind === "table"', js)
