"""C1: DXF import evaluation metrics (issue #76).

The evaluator (evals/dxf_import.py) measures what an imported DXF actually keeps: entities by
type, layers, dimensions-as-dimensions, text-as-text, HATCH, frame / title-block handling and
whether one edit round (move a dimension, change a note text) rebuilds. These tests build small
DXF fixtures with ezdxf in a temp directory, so they never depend on the user samples.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ezdxf
import pytest
from ezdxf import units

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "evals"))

import dxf_import as metrics  # noqa: E402


def make_fixture_dxf(path):
    """One small DXF with every bucket the importer distinguishes."""
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((0, 10), (100, 10), dxfattribs={"layer": "HIDDEN", "linetype": "HIDDEN"})
    msp.add_circle((50, 30), 10, dxfattribs={"layer": "OUTLINE"})
    msp.add_arc((10, 10), 5, 0, 90, dxfattribs={"layer": "OUTLINE"})
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 10)], dxfattribs={"layer": "OUTLINE"})
    msp.add_text("技术要求：去毛刺锐边。", height=3.5, dxfattribs={"layer": "TEXTLAYER"})
    msp.add_mtext("未注公差按 GB/T 1804-M", dxfattribs={"layer": "TEXTLAYER"})
    msp.add_text("图号 C1-001", height=3.5, dxfattribs={"layer": "TITLE_FRAME"})
    msp.add_linear_dim(base=(0, -10), p1=(0, 0), p2=(100, 0), dxfattribs={"layer": "DIM"}).render()
    msp.add_aligned_dim(p1=(0, 10), p2=(100, 10), distance=10, dxfattribs={"layer": "DIM"}).render()
    msp.add_diameter_dim(center=(50, 30), radius=10, angle=45, dxfattribs={"layer": "DIM"}).render()
    msp.add_radius_dim(center=(50, 30), radius=10, angle=200, dxfattribs={"layer": "DIM"}).render()
    msp.add_spline([(0, 0), (5, 5), (10, 0)], dxfattribs={"layer": "OUTLINE"})
    msp.add_ellipse((30, 30), (10, 0), 0.5, dxfattribs={"layer": "OUTLINE"})
    hatch = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    hatch.paths.add_polyline_path([(0, 0), (10, 0), (10, 10), (0, 0)])
    msp.add_point((1, 1), dxfattribs={"layer": "OUTLINE"})
    block = doc.blocks.new("TITLE_BLOCK")
    block.add_attdef("图号", (0, 0))
    insert = msp.add_blockref("TITLE_BLOCK", (150, 100), dxfattribs={"layer": "TITLE_FRAME"})
    insert.add_auto_attribs({"图号": "C1-001"})
    doc.saveas(path)
    return path


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    folder = tmp_path_factory.mktemp("dxf")
    make_fixture_dxf(folder / "fixture.dxf")
    return metrics.evaluate_dir(folder)


def test_report_shape(report):
    assert report["ok"] is True
    assert report["files"] and len(report["files"]) == 1
    entry = report["files"][0]
    assert entry["file"] == "fixture.dxf"
    assert entry["bytes"] > 0 and len(entry["sha256"]) == 64
    assert set(entry) >= {"source", "import", "metrics"}
    for key in (
        "entity_retention",
        "layer_retention",
        "dimension_retention",
        "text_retention",
        "hatch_retention",
        "frame_title",
        "edit_round",
    ):
        assert key in entry["metrics"], key
    assert set(report["summary"]) >= {
        "files",
        "entities",
        "by_type",
        "dimension_retention",
        "text_retention",
        "hatch_retention",
        "layer_content_retention",
        "title_text_retention",
        "sheet_guess_rate",
        "edit_round_rate",
    }


def test_entity_retention_by_type(report):
    by_type = report["files"][0]["metrics"]["entity_retention"]["by_type"]
    for kind in ("LINE", "ARC", "CIRCLE", "LWPOLYLINE", "TEXT", "MTEXT", "SPLINE", "ELLIPSE"):
        assert by_type[kind]["rate"] == 1.0, (kind, by_type[kind])
    for kind in ("HATCH", "INSERT", "POINT"):
        assert by_type[kind]["rate"] == 0.0, (kind, by_type[kind])
    assert by_type["DIMENSION"]["rate"] == 1.0
    totals = report["files"][0]["metrics"]["entity_retention"]["totals"]
    assert 0 < totals["rate"] < 1


def test_dimension_and_text_retention(report):
    m = report["files"][0]["metrics"]
    dims = m["dimension_retention"]
    assert dims["source"] == 4 and dims["as_dimension"] == 4 and dims["rate"] == 1.0
    text = m["text_retention"]
    assert text["source"] == 3 and text["retained_as_note"] == 3 and text["rate"] == 1.0


def test_hatch_retention_is_measured_as_zero(report):
    m = report["files"][0]["metrics"]
    assert m["hatch_retention"] == {"source": 1, "retained": 0, "rate": 0.0}


def test_layer_retention(report):
    m = report["files"][0]["metrics"]["layer_retention"]
    assert m["names_preserved"] == 0  # the model keeps no layer field (documented by design)
    assert m["source_layers"] >= m["layers_with_content"] >= 2
    assert m["layers_with_content_imported"] == m["layers_with_content"] - 1
    assert m["not_imported"] == ["HATCH"]
    assert 0 < m["rate"] < 1


def test_frame_title_handling(report):
    m = report["files"][0]["metrics"]["frame_title"]
    assert m["sheet_guess"]["ok"] is True
    assert m["sheet_guess"]["sheet"] in ("A4", "A3", "A2", "A1", "A0")
    assert m["frame_inserts"] == 1 and m["frame_inserts_retained"] == 0
    assert m["title_attrib_fields"] == 1 and m["title_attrib_retained"] == 0
    assert m["title_layer_texts"] == 1 and m["title_layer_texts_retained"] == 1


def test_edit_round(report):
    round_ = report["files"][0]["metrics"]["edit_round"]
    assert round_["ok"] is True, round_
    assert round_["build_ok"] is True
    assert round_["moved_dim"].startswith("D.")
    assert round_["changed_note"].startswith("N.")


def test_summary_aggregates(report):
    s = report["summary"]
    assert s["files"] == 1
    assert s["entities"]["retained"] < s["entities"]["source"]
    assert s["hatch_retention"] == 0.0
    assert s["edit_round_rate"] == 1.0 and s["sheet_guess_rate"] == 1.0


def test_cli_writes_json(tmp_path):
    make_fixture_dxf(tmp_path / "fixture.dxf")
    out = tmp_path / "report.json"
    assert metrics.main([str(tmp_path), "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["ok"] is True and len(data["files"]) == 1


def test_cli_missing_dir_fails(tmp_path):
    assert metrics.main([str(tmp_path / "nope")]) == 1
