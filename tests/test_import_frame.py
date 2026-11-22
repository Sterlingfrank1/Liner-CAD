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
    blk.add_text("标题栏", height=3.5, dxfattribs={"layer": "FRAME"})
    blk.add_attdef("PARTNAME", insert=(0, 0), height=3.5, dxfattribs={"layer": "FRAME"})
    msp.add_blockref("PC_TITLE_BLOCK", (20, 20), dxfattribs={"layer": "FRAME"})
    # frame border: ordinary geometry on the frame layer
    for a, b in (
        ((0, 0), (100, 0)),
        ((100, 0), (100, 60)),
        ((100, 60), (0, 60)),
        ((0, 60), (0, 0)),
    ):
        msp.add_line(a, b, dxfattribs={"layer": "FRAME"})
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
    assert not any(e._intent.get("dxf", {}).get("layer") == "FRAME" for e in edges)
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
    assert not any(el["intent"].get("dxf", {}).get("layer") == "FRAME" for el in edges)
