"""C1: DXF import evaluation metrics (issue #76).

The evaluator (evals/dxf_import.py) measures what an imported DXF actually keeps: entities by
type, layers (names and content), dimensions-as-dimensions vs. downgraded notes, text-as-text vs.
leader notes, HATCH, frame / title-block handling, the lcad inspect CLI and whether one edit round
(move a dimension, change a note text) rebuilds with both operations verified. These tests build
small DXF fixtures with ezdxf in a temp directory, so they never depend on the user samples.
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
    msp.add_line((5, 5), (5, 5), dxfattribs={"layer": "DEGENERATE"})  # zero length: skipped
    msp.add_circle((50, 30), 10, dxfattribs={"layer": "OUTLINE"})
    msp.add_arc((10, 10), 5, 0, 90, dxfattribs={"layer": "OUTLINE"})
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 20)], dxfattribs={"layer": "OUTLINE"})
    msp.add_text("技术要求：去毛刺锐边。", height=3.5, dxfattribs={"layer": "TEXTLAYER"})
    msp.add_mtext("未注公差按 GB/T 1804-M", dxfattribs={"layer": "TEXTLAYER"})
    msp.add_text("%%c20", height=3.5, dxfattribs={"layer": "TEXTLAYER"})
    msp.add_text("重复", height=3.5, dxfattribs={"layer": "TEXTLAYER"})
    msp.add_text("重复", height=3.5, dxfattribs={"layer": "TEXTLAYER"})
    msp.add_text("图号 C1-001", height=3.5, dxfattribs={"layer": "TITLE_FRAME"})
    msp.add_line((0, 0), (100, 80), dxfattribs={"layer": "TITLE_FRAME"})  # the drawing frame
    msp.add_text("标题层文字 C1", height=3.5, dxfattribs={"layer": "\\U+56FE\\U+6846"})
    msp.add_linear_dim(base=(0, -10), p1=(0, 0), p2=(100, 0), dxfattribs={"layer": "DIM"}).render()
    msp.add_aligned_dim(p1=(0, 10), p2=(100, 10), distance=10, dxfattribs={"layer": "DIM"}).render()
    msp.add_linear_dim(
        base=(110, 30), p1=(50, 20), p2=(50, 40), angle=90, dxfattribs={"layer": "DIM"}
    ).render()
    msp.add_diameter_dim(center=(50, 30), radius=10, angle=45, dxfattribs={"layer": "DIM"}).render()
    msp.add_radius_dim(center=(50, 30), radius=10, angle=200, dxfattribs={"layer": "DIM"}).render()
    # no circle at this centre: the importer keeps the value as a fallback leader note
    msp.add_radius_dim(center=(500, 500), radius=20, angle=0, dxfattribs={"layer": "DIM"}).render()
    from ezdxf.entities import Dimension

    broken = Dimension.new(dxfattribs={"layer": "BROKEN_DIM"})
    broken.dxf.geometry = "Standard"
    broken.dxf.defpoint = (0, 0)
    broken.dxf.dimtype = 6  # ordinate: the importer does not support it
    broken.dxf.text = "30"
    msp.add_entity(broken)
    msp.add_spline([(0, 0), (5, 5), (10, 0)], dxfattribs={"layer": "OUTLINE"})
    msp.add_ellipse((30, 30), (10, 0), 0.5, dxfattribs={"layer": "OUTLINE"})
    hatch = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    hatch.paths.add_polyline_path([(0, 0), (10, 0), (10, 10), (0, 0)])
    msp.add_point((1, 1), dxfattribs={"layer": "OUTLINE"})
    block = doc.blocks.new("TITLE_BLOCK")
    block.add_attdef("图号", (0, 0))
    insert = msp.add_blockref("TITLE_BLOCK", (150, 100), dxfattribs={"layer": "TITLE_FRAME"})
    insert.add_auto_attribs({"图号": "C1-001"})
    from ezdxf.entities import Attrib

    msp.add_entity(
        Attrib.new(
            dxfattribs={
                "tag": "校对",
                "text": "45",
                "layer": "\\U+56FE\\U+6846",
                "insert": (151, 95),
            }
        )
    )
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
    assert set(entry) >= {"source", "import", "inspect", "metrics"}
    assert entry["inspect"]["ok"] is True
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
        "layer_names_preserved",
        "title_text_retention",
        "sheet_guess_available_rate",
        "sheet_guess_fits_rate",
        "edit_round_rate",
        "inspect_ok_rate",
    }


def test_entity_retention_by_type(report):
    by_type = report["files"][0]["metrics"]["entity_retention"]["by_type"]
    for kind in ("ARC", "CIRCLE", "LWPOLYLINE", "TEXT", "MTEXT", "SPLINE", "ELLIPSE"):
        assert by_type[kind]["rate"] == 1.0, (kind, by_type[kind])
    assert by_type["LINE"]["source"] == 4 and by_type["LINE"]["retained"] == 3  # one degenerate
    for kind in ("HATCH", "INSERT", "POINT"):
        assert by_type[kind]["rate"] == 0.0, (kind, by_type[kind])
    assert by_type["DIMENSION"]["source"] == 7 and by_type["DIMENSION"]["retained"] == 6
    totals = report["files"][0]["metrics"]["entity_retention"]["totals"]
    assert 0 < totals["rate"] < 1


def test_dimension_retention(report):
    dims = report["files"][0]["metrics"]["dimension_retention"]
    assert dims["source"] == 7
    assert dims["as_dimension"] == 5 and dims["as_note"] == 1 and dims["skipped"] == 1
    assert dims["rate"] == round(5 / 7, 4)


def test_text_retention_is_honest_about_notes(report):
    text = report["files"][0]["metrics"]["text_retention"]
    assert text["source"] == 7  # technical note, MTEXT, %%c20, two duplicates, two title texts
    assert text["as_text"] == 0  # importer has no regular text element yet (C2 target)
    assert text["rate"] == 0.0
    assert text["as_note"] == 7 and text["note_rate"] == 1.0


def test_hatch_retention_is_measured_as_zero(report):
    m = report["files"][0]["metrics"]
    assert m["hatch_retention"] == {"source": 1, "retained": 0, "rate": 0.0}


def test_dim_would_import_requires_the_defpoints():
    class FakeDXF:
        def __init__(self, attrs):
            self.attrs = attrs

        def hasattr(self, name):
            return name in self.attrs

    class FakeDim:
        dimtype = 0

        def __init__(self, attrs):
            self.dxf = FakeDXF(attrs)

    assert metrics._dim_would_import(FakeDim({"defpoint2", "defpoint3"})) is True
    assert metrics._dim_would_import(FakeDim({"defpoint2"})) is False


def test_layer_retention(report):
    m = report["files"][0]["metrics"]["layer_retention"]
    assert m["layers_with_content"] == 9
    assert m["layers_with_content_imported"] == 6  # HATCH / DEGENERATE / BROKEN_DIM-only stay out
    assert m["not_imported"] == ["BROKEN_DIM", "DEGENERATE", "HATCH"]
    assert m["rate"] == round(6 / 9, 4)
    assert m["names_preserved"] >= 2
    assert "OUTLINE" in m["names_preserved_list"]
    assert "TITLE_FRAME" in m["names_preserved_list"]  # the drawing frame is imported as edges


def test_frame_title_handling(report):
    m = report["files"][0]["metrics"]["frame_title"]
    assert m["sheet_guess"]["available"] is True and m["sheet_guess"]["fits"] is True
    assert m["frame_inserts"] == 1 and m["frame_inserts_retained"] == 0
    assert m["frame_edges"] == 1 and m["frame_edges_retained"] == 1
    assert m["title_attrib_fields"] == 2  # insert attribute + top-level ATTRIB with a free tag
    assert m["title_attrib_retained"] == 0
    assert m["title_layer_texts"] == 2 and m["title_layer_texts_retained"] == 2


def test_inspect_is_part_of_the_report(report):
    insp = report["files"][0]["inspect"]
    assert insp["ok"] is True and insp["maps_to"] and insp["sheet"]
    assert insp["maps_match"] is True and insp["sheet_match"] is True
    assert insp["entities"]["DIMENSION"] == 7


def test_edit_round_verifies_both_operations(report):
    round_ = report["files"][0]["metrics"]["edit_round"]
    assert round_["ok"] is True, round_
    assert round_["build_ok"] is True
    assert round_["moved_dim"].startswith("D.")
    assert round_["move_args"] and set(round_["move_args"]) & {"dx", "dy"}
    assert round_["changed_note"].startswith("N.")


def test_summary_aggregates(report):
    s = report["summary"]
    assert s["files"] == 1
    assert s["entities"]["retained"] < s["entities"]["source"]
    assert s["text_retention"]["rate"] == 0.0 and s["text_retention"]["note_rate"] == 1.0
    assert s["hatch_retention"] == 0.0
    assert s["layer_names_preserved"] >= 1
    assert s["sheet_guess_available_rate"] == 1.0 and s["sheet_guess_fits_rate"] == 1.0
    assert s["edit_round_rate"] == 1.0 and s["inspect_ok_rate"] == 1.0
    assert s["inspect_match_rate"] == 1.0
    assert s["frame_edges"]["source"] == 1 and s["frame_edges"]["rate"] == 1.0


def test_move_candidates_prefer_the_side_normal():
    model = {
        "elements": [
            {"id": "D.right", "placement": {"side": "right"}},
            {"id": "D.bottom", "placement": {"side": "bottom"}},
        ]
    }
    candidates = metrics._move_candidates(model)
    assert candidates[0][0] == "D.right" and candidates[0][1] == "dx"
    assert any(c[0] == "D.bottom" and c[1] == "dy" for c in candidates)


def test_edit_round_moves_a_right_side_dimension_with_dx(tmp_path):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    msp = doc.modelspace()
    msp.add_line((0, 0), (0, 60), dxfattribs={"layer": "OUTLINE"})
    msp.add_linear_dim(base=(100, 30), p1=(0, 0), p2=(0, 60), angle=90).render()
    msp.add_text("备注", height=3.5)
    path = tmp_path / "right.dxf"
    doc.saveas(path)
    round_ = metrics.evaluate_file(path)["metrics"]["edit_round"]
    assert round_["ok"] is True, round_
    assert round_["move_args"] and "dx" in round_["move_args"], round_


def test_text_retention_matches_regular_text_content(tmp_path):
    doc = ezdxf.new("R2018", setup=True)
    msp = doc.modelspace()
    msp.add_text("A")
    msp.add_mtext("B")

    class FakeText:
        kind = "text"
        _intent = {"text": "A"}

    got = metrics.text_retention(doc, None, [FakeText()])
    assert got["as_text"] == 1 and got["rate"] == 0.5
    FakeText._intent = {"text": "Z"}  # content does not match any source text
    assert metrics.text_retention(doc, None, [FakeText()])["as_text"] == 0


def test_clean_text_conversion_is_part_of_the_reading(tmp_path):
    doc = ezdxf.new("R2018", setup=True)
    text = doc.modelspace().add_text("%%c20")
    assert metrics._source_text(text) == "Φ20"


def test_sheet_fits_rejects_a_sheet_that_cannot_hold_the_extents():
    assert metrics._sheet_fits(100, 60, "A4", "1:1") is True
    assert metrics._sheet_fits(2000, 2000, "A4", "1:1") is False


def test_uppercase_dxf_suffix_is_evaluated(tmp_path):
    make_fixture_dxf(tmp_path / "UPPER.DXF")
    rep = metrics.evaluate_dir(tmp_path)
    assert rep["ok"] is True and rep["files"][0]["file"] == "UPPER.DXF"


def test_cli_writes_json(tmp_path):
    make_fixture_dxf(tmp_path / "fixture.dxf")
    out = tmp_path / "report.json"
    assert metrics.main([str(tmp_path), "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["ok"] is True and len(data["files"]) == 1


def test_cli_missing_dir_fails(tmp_path):
    assert metrics.main([str(tmp_path / "nope")]) == 1
