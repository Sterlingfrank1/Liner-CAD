"""E6: only-primitive (DXF-only) score vector for arbitrary DXF files (issue #80)."""

from __future__ import annotations

from pathlib import Path

import ezdxf
from ezdxf import units

from linercad import dxfonly

REPO = Path(__file__).resolve().parents[1]
M3_BASELINE = REPO / "tests" / "data" / "dxf" / "sample_part.dxf"


def _doc():
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    return doc


def _frame(msp, w=420.0, h=297.0):
    for a, b in (
        ((0, 0), (w, 0)),
        ((w, 0), (w, h)),
        ((w, h), (0, h)),
        ((0, h), (0, 0)),
    ):
        msp.add_line(a, b, dxfattribs={"layer": "FRAME"})


def make_good_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    _frame(msp)
    msp.add_circle((120, 150), 20, dxfattribs={"layer": "OUTLINE"})
    msp.add_text("第一段", height=5, dxfattribs={"layer": "TEXT"}).set_placement((30, 40))
    msp.add_text("第二段", height=5, dxfattribs={"layer": "TEXT"}).set_placement((30, 60))
    for angle in (45.0, 45.0):
        h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
        h.set_pattern_fill("ANSI31", scale=1.0, angle=angle)
        h.paths.add_polyline_path([(200, 100), (240, 100), (240, 130), (200, 100)])
    msp.add_linear_dim(base=(0, -15), p1=(0, 0), p2=(100, 0)).render()
    doc.saveas(path)
    return path


def make_bad_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    _frame(msp)
    # overlapping texts
    msp.add_text("重叠甲", height=5).set_placement((30, 40))
    msp.add_text("重叠乙", height=5).set_placement((31, 40))
    # geometry outside the frame
    msp.add_line((-20, -20), (-10, -10), dxfattribs={"layer": "OUTLINE"})
    # inconsistent section hatches
    for angle in (45.0, 0.0):
        h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
        h.set_pattern_fill("ANSI31", scale=1.0, angle=angle)
        h.paths.add_polyline_path([(200, 100), (240, 100), (240, 130), (200, 100)])
    dim = msp.add_linear_dim(base=(0, -15), p1=(0, 0), p2=(100, 0))
    dim.render()
    # break the dimension: no text, no arrowheads
    block = doc.blocks.get(dim.dimension.dxf.geometry)
    for e in list(block):
        if e.dxftype() in ("SOLID", "TEXT", "MTEXT", "INSERT"):
            block.delete_entity(e)
    dim.dimension.dxf.text = ""
    doc.saveas(path)
    return path


def make_no_frame_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    msp.add_line((0, 0), (50, 0))
    msp.add_text("说明", height=5).set_placement((10, 10))
    doc.saveas(path)
    return path


def test_good_dxf_scores_full_vector(tmp_path):
    r = dxfonly.score_file(make_good_dxf(tmp_path / "good.dxf"))
    assert r["mode"] == "dxf-only"
    assert r["families"]["G"]["score"] == 1.0, r["families"]
    assert r["families"]["D"]["score"] == 1.0, r["families"]
    assert r["families"]["T"]["score"] is None
    assert r["families"]["A"]["score"] is None
    assert r["rules"]["dxf_out_of_frame"]["opportunities"] > 0
    assert r["rules"]["dxf_text_overlap"]["opportunities"] == 2
    assert r["rules"]["dxf_section_hatch_consistency"]["opportunities"] == 1
    assert r["unavailable"], "intent-dependent rules must be listed as unavailable"


def test_bad_dxf_scores_are_deducted(tmp_path):
    r = dxfonly.score_file(make_bad_dxf(tmp_path / "bad.dxf"))
    assert r["rules"]["dxf_text_overlap"]["violations"] >= 1
    assert r["rules"]["dxf_out_of_frame"]["violations"] >= 1
    assert r["rules"]["dxf_section_hatch_consistency"]["violations"] == 1
    assert r["rules"]["dxf_dim_text_present"]["violations"] == 1
    assert r["rules"]["dxf_dim_arrows"]["violations"] == 1
    assert r["families"]["G"]["score"] < 1.0
    assert r["families"]["D"]["score"] < 1.0


def test_no_frame_file_reports_the_rule_as_not_applicable(tmp_path):
    r = dxfonly.score_file(make_no_frame_dxf(tmp_path / "noframe.dxf"))
    rule = r["rules"]["dxf_out_of_frame"]
    assert rule["opportunities"] == 0
    assert "no sheet frame" in rule["note"].lower()
    assert r["families"]["G"]["score"] == 1.0  # text overlap still judges


def test_arbitrary_m3_baseline_dxf_gets_a_vector():
    r = dxfonly.score_file(M3_BASELINE)
    assert r["ok"] is True
    assert r["families"]["G"]["score"] is not None
    assert r["families"]["D"]["score"] is not None
    assert r["families"]["T"]["score"] is None
    assert any(u["rule"].startswith(("D.", "T.", "A.")) for u in r["unavailable"])


def test_rule_table_marks_intent_rules_unavailable():
    table = dxfonly.RULE_TABLE
    assert table["dxf_out_of_frame"]["judgeable"] is True
    assert table["dxf_section_hatch_consistency"]["family"] == "G"
    unavailable = {u["rule"] for u in dxfonly.unavailable_rules()}
    assert {"D.complete", "D.value", "T.syntax", "A.place"} <= unavailable
