"""C4: the source sheet frame / title block is not stacked into the new sheet (issue #79)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import ezdxf
from ezdxf import units

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "evals"))

import dxf_import as metrics  # noqa: E402

from linercad import Drawing, importdxf  # noqa: E402
from linercad.layout import layout  # noqa: E402


def _doc():
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    return doc


def make_frame_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    # title block definition, inserted on the frame layer (as in the user samples)
    blk = doc.blocks.new("PC_TITLE_BLOCK")
    blk.add_text("标题栏", height=3.5, dxfattribs={"layer": "TITLE_FRAME"})
    blk.add_attdef("PARTNAME", insert=(0, 0), height=3.5, dxfattribs={"layer": "TITLE_FRAME"})
    ref = msp.add_blockref("PC_TITLE_BLOCK", (20, 20), dxfattribs={"layer": "TITLE_FRAME"})
    ref.add_attrib("PARTNAME", "磨头", (22, 22), dxfattribs={"layer": "TITLE_FRAME"})
    # frame border: ordinary geometry on the frame layer
    for a, b in (
        ((0, 0), (100, 0)),
        ((100, 0), (100, 60)),
        ((100, 60), (0, 60)),
        ((0, 60), (0, 0)),
    ):
        msp.add_line(a, b, dxfattribs={"layer": "TITLE_FRAME"})
    msp.add_text("技术要求", height=3.5, dxfattribs={"layer": "MODEL"}).set_placement((10, 10))
    msp.add_line((10, 20), (90, 20), dxfattribs={"layer": "OUTLINE"})
    doc.saveas(path)
    return path


def imported(path):
    d = Drawing(sheet="A3")
    imp = importdxf.import_dxf(d, str(path))
    layout(d)
    return d, imp


def test_frame_geometry_is_absorbed_not_imported(tmp_path):
    src = make_frame_dxf(tmp_path / "frame.dxf")
    d, imp = imported(src)
    frame = imp.counts["frame"]
    assert frame["absorbed"].get("LINE") == 4, frame
    assert any("FRAME" in layer.upper() for layer in frame["layers"])
    assert "PC_TITLE_BLOCK" in frame["blocks"]
    edges = [e for e in d._els.values() if e.kind == "edge"]
    assert not any(e._intent.get("dxf", {}).get("layer") == "TITLE_FRAME" for e in edges)
    frames = [e for e in d._els.values() if e.kind == "frame"]
    assert len(frames) == 1  # the template frame is the only frame


def test_inspect_reports_the_frame_and_title(tmp_path):
    src = make_frame_dxf(tmp_path / "frame.dxf")
    out = importdxf.inspect(src)
    assert out["frame"]["entities"].get("LINE") == 4
    assert out["frame"]["absorbed"].get("LINE") == 4
    assert any("FRAME" in layer.upper() for layer in out["frame"]["layers"])
    assert "PC_TITLE_BLOCK" in out["title"]["blocks"]


def test_c1_reports_a_single_frame_and_no_regression(tmp_path):
    src = make_frame_dxf(tmp_path / "frame.dxf")
    entry = metrics.evaluate_file(src)
    f = entry["metrics"]["frame_title"]
    assert f["single_frame_ok"] is True
    assert f["model_frames"] == 1
    assert f["frame_edges_retained"] == 0
    assert f["frame_edges_absorbed"] == 4
    # frame absorption must not change the entity / layer / title readings
    e = entry["metrics"]["entity_retention"]
    assert e["by_type"]["LINE"]["rate"] == 1.0
    lay = entry["metrics"]["layer_retention"]
    assert lay["layers_with_content_imported"] == lay["layers_with_content"]
    assert lay["not_imported"] == []
    # title block template texts stay a documented boundary (not silently imported)
    assert f["title_text_rate"] == 0.0


def test_frame_absorption_keeps_edit_round(tmp_path):
    src = make_frame_dxf(tmp_path / "frame.dxf")
    entry = metrics.evaluate_file(src)
    round_ = entry["metrics"]["edit_round"]
    assert round_["ok"] is True, round_


def test_cli_inspect_reports_frame_and_title(tmp_path):
    src = make_frame_dxf(tmp_path / "frame.dxf")
    r = subprocess.run(
        [sys.executable, "-m", "linercad", "inspect", str(src)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["frame"]["entities"].get("LINE") == 4
    assert out["frame"]["absorbed"].get("LINE") == 4
    assert "PC_TITLE_BLOCK" in out["title"]["blocks"]


def test_ordinary_frame_like_layer_names_are_not_absorbed(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "FRAME_MEMBER"})
    msp.add_line((10, 0), (10, 10), dxfattribs={"layer": "TITLE_BAR"})
    src = tmp_path / "ordinary.dxf"
    doc.saveas(src)
    d, imp = imported(src)
    assert imp.counts["frame"]["absorbed"] == {}
    layers = {e._intent.get("dxf", {}).get("layer") for e in d._els.values() if e.kind == "edge"}
    assert {"FRAME_MEMBER", "TITLE_BAR"} <= layers


def test_hidden_frame_layer_is_not_absorbed(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    frame_layer = doc.layers.add("TITLE_FRAME")
    frame_layer.off()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "TITLE_FRAME"})
    src = tmp_path / "hidden.dxf"
    doc.saveas(src)
    entry = metrics.evaluate_file(src)
    assert entry["import"]["counts"]["frame"]["absorbed"] == {}
    assert entry["metrics"]["frame_title"]["frame_edges_absorbed"] == 0
    assert entry["metrics"]["frame_title"]["single_frame_ok"] is False


def test_raw_frame_geometry_is_not_counted_as_absorbed(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    msp.add_ellipse((0, 0), major_axis=(10, 0), ratio=0.5, dxfattribs={"layer": "TITLE_FRAME"})
    src = tmp_path / "raw.dxf"
    doc.saveas(src)
    entry = metrics.evaluate_file(src)
    assert entry["import"]["counts"]["frame"]["absorbed"] == {}
    assert entry["metrics"]["entity_retention"]["by_type"]["ELLIPSE"]["rate"] == 1.0
    # a retained raw frame element still means the sheet is not "one frame"
    assert entry["metrics"]["frame_title"]["frame_raw_retained"] == 1
    assert entry["metrics"]["frame_title"]["single_frame_ok"] is False


def test_inspect_counts_attached_title_attribs(tmp_path):
    src = make_frame_dxf(tmp_path / "frame.dxf")
    out = importdxf.inspect(src)
    assert out["title"]["attribs"] >= 1


def test_declared_frame_layer_aliases_are_absorbed(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "SHEET_FRAME"})
    msp.add_line((0, 0), (0, 10), dxfattribs={"layer": "标题层"})
    src = tmp_path / "aliases.dxf"
    doc.saveas(src)
    d, imp = imported(src)
    assert imp.counts["frame"]["absorbed"].get("LINE") == 2, imp.counts["frame"]
    assert not [e for e in d._els.values() if e.kind == "edge"]


def test_chinese_frame_word_inside_an_ordinary_layer_is_not_absorbed(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "图框_MEMBER"})
    src = tmp_path / "reverse.dxf"
    doc.saveas(src)
    d, imp = imported(src)
    assert imp.counts["frame"]["absorbed"] == {}
    layers = {e._intent.get("dxf", {}).get("layer") for e in d._els.values() if e.kind == "edge"}
    assert "图框_MEMBER" in layers


def test_foreign_block_attrib_is_not_reported_as_title(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    blk = doc.blocks.new("DETAIL_PART")
    blk.add_attdef("SCALE", insert=(0, 0), height=2.5)
    ref = msp.add_blockref("DETAIL_PART", (0, 0), dxfattribs={"layer": "DETAIL"})
    ref.add_attrib("SCALE", "1:2", (1, 1), dxfattribs={"layer": "DETAIL"})
    src = tmp_path / "detail.dxf"
    doc.saveas(src)
    out = importdxf.inspect(src)
    assert out["title"]["blocks"] == []
    assert out["title"]["attribs"] == 0
    assert out["frame"]["absorbed"] == {}


def test_zero_length_frame_edge_is_not_counted_as_absorbed(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (0, 0), dxfattribs={"layer": "TITLE_FRAME"})
    src = tmp_path / "zero.dxf"
    doc.saveas(src)
    entry = metrics.evaluate_file(src)
    assert entry["import"]["counts"]["frame"]["absorbed"] == {}
    f = entry["metrics"]["frame_title"]
    assert f["frame_edges"] == 0 and f["frame_edges_absorbed"] == 0
    assert f["single_frame_ok"] is True


def test_detail_part_block_on_the_frame_layer_is_not_a_title_block(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    blk = doc.blocks.new("DETAIL_PART")
    blk.add_attdef("SCALE", insert=(0, 0), height=2.5)
    ref = msp.add_blockref("DETAIL_PART", (0, 0), dxfattribs={"layer": "TITLE_FRAME"})
    ref.add_attrib("SCALE", "1:2", (1, 1), dxfattribs={"layer": "TITLE_FRAME"})
    src = tmp_path / "detail_on_frame.dxf"
    doc.saveas(src)
    out = importdxf.inspect(src)
    assert out["title"]["blocks"] == []
    assert out["title"]["attribs"] == 0


def test_c1_title_block_detection_is_strict(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    blk = doc.blocks.new("FRAME_MEMBER")
    blk.add_text("not a title", height=2.5)
    msp.add_blockref("FRAME_MEMBER", (0, 0), dxfattribs={"layer": "TITLE_BAR"})
    src = tmp_path / "ordinary_title.dxf"
    doc.saveas(src)
    f = metrics.evaluate_file(src)["metrics"]["frame_title"]
    assert f["frame_inserts"] == 0 and f["title_attrib_fields"] == 0


def test_part_geometry_on_a_sheet_layer_is_not_absorbed(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "SHEET"})
    msp.add_line((0, 0), (0, 10), dxfattribs={"layer": "FRAME"})
    src = tmp_path / "sheet.dxf"
    doc.saveas(src)
    d, imp = imported(src)
    assert imp.counts["frame"]["absorbed"] == {}
    layers = {e._intent.get("dxf", {}).get("layer") for e in d._els.values() if e.kind == "edge"}
    assert {"SHEET", "FRAME"} <= layers  # bare single-word layers stay ordinary geometry


def test_zero_length_only_frame_layer_is_not_in_absorbed_layers(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (0, 0), dxfattribs={"layer": "TITLE_FRAME"})
    src = tmp_path / "zero_layer.dxf"
    doc.saveas(src)
    lay = metrics.evaluate_file(src)["metrics"]["layer_retention"]
    assert lay["absorbed_layers"] == []
    assert "TITLE_FRAME" in lay["not_imported"]


def test_build_has_one_frame_and_no_source_frame_copy(tmp_path):
    src = make_frame_dxf(tmp_path / "frame.dxf")
    d = tmp_path / "part"
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "linercad",
            "-C",
            str(tmp_path),
            "init",
            str(d),
            "--from-dxf",
            str(src),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    assert out["ok"] is True
    model = json.loads((d / ".linercad/build/model.json").read_text(encoding="utf-8"))
    frames = [el for el in model["elements"] if el["kind"] == "frame"]
    assert len(frames) == 1
    edges = [el for el in model["elements"] if el["kind"] == "edge"]
    assert not any(el["intent"].get("dxf", {}).get("layer") == "TITLE_FRAME" for el in edges)
    built = ezdxf.readfile(d / ".linercad/build/drawing.dxf")
    assert "TITLE_FRAME" not in {layer.dxf.name for layer in built.layers}
