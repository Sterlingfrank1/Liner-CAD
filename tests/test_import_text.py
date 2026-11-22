"""C2: TEXT / MTEXT import as plain text elements (issue #77).

Imported text must become a plain text element (no leader), keeping position, height, rotation,
alignment and style; MTEXT keeps its line breaks. These tests build their own DXFs with ezdxf.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import ezdxf
import pytest
from ezdxf import units

from linercad import Drawing, importdxf
from linercad.layout import layout

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "evals"))


def lcad(dir, *args):
    r = subprocess.run(
        [sys.executable, "-m", "linercad", "-C", str(dir), *args], capture_output=True
    )
    return r.returncode, json.loads(r.stdout.decode("utf-8"))


def make_text_dxf(path):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    msp = doc.modelspace()
    msp.add_line((0, 0), (120, 0), dxfattribs={"layer": "OUTLINE"})
    msp.add_text(
        "技术要求：去毛刺。",
        height=5.0,
        rotation=30.0,
        dxfattribs={"layer": "TEXT", "style": "Standard"},
    ).set_placement((20, 30))
    msp.add_mtext("第一行\\n第二行", dxfattribs={"layer": "TEXT", "style": "Standard"}).set_location(
        (60, 50)
    )
    doc.saveas(path)
    return path


def imported(path, unit_factor=1.0):
    d = Drawing(sheet="A3")
    imp = importdxf.import_dxf(d, str(path))
    layout(d)
    texts = [e for e in d._els.values() if e.kind == "text"]
    return d, imp, texts


@pytest.fixture
def text_dxf(tmp_path):
    return make_text_dxf(tmp_path / "text.dxf")


def test_text_becomes_a_plain_text_element(text_dxf):
    d, _imp, texts = imported(text_dxf)
    assert len(texts) == 2
    first = next(e for e in texts if e.text.startswith("技术要求"))
    assert first.kind == "text"
    assert first._intent["view"] == "front"
    # no leader: only Text primitives, no Line / Solid arrow
    from linercad.layout import Text as TextPrim

    assert first._prims and all(isinstance(p, TextPrim) for p in first._prims)
    assert first._resolved.get("bbox")


def test_position_height_rotation_alignment_and_style_are_kept(text_dxf):
    _d, _imp, texts = imported(text_dxf)
    first = next(e for e in texts if e.text.startswith("技术要求"))
    at = first._intent["at"]
    assert abs(at[0] - 20.0) <= 0.01 and abs(at[1] - 30.0) <= 0.01
    assert abs(first._intent["height"] - 5.0) <= 0.01
    assert abs(first._intent["rotation"] - 30.0) <= 0.01
    assert first._intent["halign"] == 0 and first._intent["valign"] == 0
    assert first._intent["style"] == "Standard"
    assert first._intent["layer"] == "TEXT"


def test_mtext_keeps_line_breaks(text_dxf):
    _d, _imp, texts = imported(text_dxf)
    mtext = next(e for e in texts if "第一行" in e.text)
    assert mtext.text == "第一行\n第二行"
    from linercad.layout import Text as TextPrim

    line_prims = [p for p in mtext._prims if isinstance(p, TextPrim)]
    assert len(line_prims) == 2
    assert line_prims[0].text == "第一行" and line_prims[1].text == "第二行"


def test_import_counts_report_texts(text_dxf):
    _d, imp, _texts = imported(text_dxf)
    assert imp.counts["texts"] == 2


def test_c1_metric_as_text_rises_and_notes_do_not(text_dxf):
    import dxf_import as metrics

    entry = metrics.evaluate_file(text_dxf)
    text = entry["metrics"]["text_retention"]
    assert text["source"] == 2
    assert text["as_text"] == 2 and text["as_note"] == 0
    assert text["rate"] == 1.0 and text["note_rate"] == 0.0
    assert entry["metrics"]["entity_retention"]["by_type"]["TEXT"]["rate"] == 1.0
    assert entry["metrics"]["entity_retention"]["by_type"]["MTEXT"]["rate"] == 1.0


def test_edit_an_imported_text_and_rebuild(tmp_path):
    src = make_text_dxf(tmp_path / "text.dxf")
    d = tmp_path / "part"
    code, out = lcad(tmp_path, "init", str(d), "--from-dxf", str(src))
    assert code == 0, out
    model = json.loads((d / ".linercad/build/model.json").read_text(encoding="utf-8"))
    texts = [e["id"] for e in model["elements"] if e["kind"] == "text"]
    assert texts, model["elements"][:3]
    script = d / ".linercad/tmp/edit_text.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "def apply(d):\n" f'    d["{texts[0]}"].set(text="改过的导入文字")\n', encoding="utf-8"
    )
    code, out = lcad(d, "edit", str(script), "-m", "改一段导入文字")
    assert code == 0, out
    model = json.loads((d / ".linercad/build/model.json").read_text(encoding="utf-8"))
    changed = next(e for e in model["elements"] if e["id"] == texts[0])
    assert changed["intent"]["text"] == "改过的导入文字"
    assert (d / ".linercad/build/drawing.dxf").is_file()
