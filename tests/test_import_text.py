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
    msp.add_mtext("第一行\n第二行", dxfattribs={"layer": "TEXT", "style": "Standard"}).set_location(
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


def make_alignment_dxf(path):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    msp = doc.modelspace()
    msp.add_line((0, 0), (120, 0))
    bottom = msp.add_mtext("bottom-left", dxfattribs={"layer": "TEXT"})
    bottom.dxf.attachment_point = 7
    bottom.set_location((60, 20))
    middle = msp.add_text("ABCD", height=4.0, dxfattribs={"layer": "TEXT"})
    middle.dxf.halign = 4  # MIDDLE: centred on the second alignment point
    middle.dxf.align_point = (80, 30)
    aligned = msp.add_text("WXYZ", height=4.0, dxfattribs={"layer": "TEXT"})
    aligned.dxf.halign = 3  # ALIGNED: stretched between the two points
    aligned.dxf.align_point = (40, 5)
    rotated = msp.add_mtext("direction", dxfattribs={"layer": "TEXT"})
    rotated.dxf.text_direction = (0, 1, 0)  # 90 degrees
    rotated.set_location((10, 90))
    escaped = msp.add_text("%%c20 \\U+4E2D", height=3.5, dxfattribs={"layer": "TEXT"})
    escaped.set_placement((5, 100))
    spaced = msp.add_mtext("line one\nline two", dxfattribs={"layer": "TEXT"})
    spaced.dxf.line_spacing_factor = 2.0
    spaced.set_location((10, 40))
    doc.saveas(path)
    return path


def test_mtext_attachment_top_left_anchor(tmp_path):
    src = make_text_dxf(tmp_path / "t.dxf")
    d, _imp, texts = imported(src)
    mtext = next(e for e in texts if "第一行" in e.text)
    ox, oy = d["V.front"]._resolved["origin"]
    box = mtext._prims[0].box
    assert abs(box[0] - ox - 60.0) <= 0.01  # left edge at the insertion point
    assert abs(box[3] - oy - 50.0) <= 0.01  # top edge at the insertion point


def test_mtext_attachments_keep_their_corner(tmp_path):
    src = make_alignment_dxf(tmp_path / "align.dxf")
    d, _imp, texts = imported(src)
    bottom = next(e for e in texts if e.text == "bottom-left")
    assert bottom._intent["halign"] == 0 and bottom._intent["valign"] == 1
    ox, oy = d["V.front"]._resolved["origin"]
    box = bottom._prims[0].box
    assert abs(box[0] - ox - 60.0) <= 0.01
    assert abs(box[1] - oy - 20.0) <= 0.01  # bottom edge at the insertion point


def test_text_middle_and_aligned_alignment(tmp_path):
    src = make_alignment_dxf(tmp_path / "align.dxf")
    d, _imp, texts = imported(src)
    ox, oy = d["V.front"]._resolved["origin"]
    middle = next(e for e in texts if e.text == "ABCD")
    box = middle._prims[0].box
    assert abs((box[0] + box[2]) / 2 - ox - 80.0) <= 0.01  # centred on align_point
    aligned = next(e for e in texts if e.text == "WXYZ")
    box = aligned._prims[0].box
    assert abs(box[2] - ox - 40.0) <= 0.6  # ends at the second alignment point
    assert abs(aligned._intent["rotation"] - 7.125) <= 0.01  # derived from the two points


def test_text_direction_rotation_and_unicode_escapes(tmp_path):
    src = make_alignment_dxf(tmp_path / "align.dxf")
    _d, _imp, texts = imported(src)
    rotated = next(e for e in texts if e.text == "direction")
    assert abs(rotated._intent["rotation"] - 90.0) <= 0.01
    escaped = next(e for e in texts if e.text.startswith("Φ"))
    assert escaped.text == "Φ20 中"


def test_mtext_line_spacing_factor(tmp_path):
    src = make_alignment_dxf(tmp_path / "align.dxf")
    _d, _imp, texts = imported(src)
    spaced = next(e for e in texts if e.text.startswith("line one"))
    assert spaced._intent["line_spacing"] == 2.0
    y = [p.at[1] for p in spaced._prims if hasattr(p, "text")]
    assert len(y) == 2, spaced.text
    expected = 2.5 * (5.0 / 3.0) * 2.0  # MTEXT default char height * DXF base spacing * factor
    assert abs((y[0] - y[1]) - expected) <= 0.01


def test_build_keeps_height_style_layer_and_position(tmp_path):
    src = make_text_dxf(tmp_path / "text.dxf")
    d = tmp_path / "part"
    code, out = lcad(tmp_path, "init", str(d), "--from-dxf", str(src))
    assert code == 0, out
    doc = ezdxf.readfile(d / ".linercad/build/drawing.dxf")
    texts = [e for e in doc.modelspace() if e.dxftype() == "TEXT"]
    first = next(e for e in texts if e.dxf.text.startswith("技术要求"))
    assert abs(first.dxf.height - 5.0) <= 0.01  # no GB character-height conversion
    assert abs(first.dxf.rotation - 30.0) <= 0.01
    assert first.dxf.style == "Standard"
    assert first.dxf.layer == "TEXT"
    # the model keeps the source insertion point; the sheet position is that point + the view origin
    m = json.loads((d / ".linercad/build/model.json").read_text(encoding="utf-8"))
    els = {e["id"]: e for e in m["elements"]}
    view = els["V.front"]
    ox, oy = (view.get("placement") or {}).get("resolved", {}).get("origin", [0.0, 0.0])
    want = els[
        next(
            i
            for i in els
            if i.startswith("T.")
            and els[i]["kind"] == "text"
            and els[i]["intent"]["text"].startswith("技术要求")
        )
    ]["intent"]
    assert abs(want["at"][0] - 20.0) <= 0.01 and abs(want["at"][1] - 30.0) <= 0.01
    p = first.dxf.insert
    assert abs(p[0] - (want["at"][0] + ox)) <= 0.01
    assert abs(p[1] - (want["at"][1] + oy)) <= 0.01


def test_moving_an_imported_text_moves_the_rebuilt_dxf(tmp_path):
    src = make_text_dxf(tmp_path / "text.dxf")
    d = tmp_path / "part"
    code, out = lcad(tmp_path, "init", str(d), "--from-dxf", str(src))
    assert code == 0, out
    model = json.loads((d / ".linercad/build/model.json").read_text(encoding="utf-8"))
    target = next(e["id"] for e in model["elements"] if e["kind"] == "text")
    before = ezdxf.readfile(d / ".linercad/build/drawing.dxf")
    b = next(
        e.dxf.insert for e in before.modelspace().query("TEXT") if e.dxf.text.startswith("技术要求")
    )
    script = d / ".linercad/tmp/move_text.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        f'def apply(d):\n    d["{target}"].move(dx=30.0, dy=15.0)\n', encoding="utf-8"
    )
    code, out = lcad(d, "edit", str(script), "-m", "移动导入文字")
    assert code == 0, out
    after = ezdxf.readfile(d / ".linercad/build/drawing.dxf")
    a = next(
        e.dxf.insert for e in after.modelspace().query("TEXT") if e.dxf.text.startswith("技术要求")
    )
    assert abs((a[0] - b[0]) - 30.0) <= 0.01  # the move reached the rebuilt DXF
    assert abs(a[1] - b[1]) > 0.01  # and the vertical part is not dropped either


def test_c1_edit_round_edits_a_text_when_there_is_no_note(tmp_path):
    import dxf_import as metrics

    src = make_text_dxf(tmp_path / "text.dxf")
    entry = metrics.evaluate_file(src)
    round_ = entry["metrics"]["edit_round"]
    assert round_["ok"] is True, round_
    assert round_["changed_element"].startswith("T.")


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
        f'def apply(d):\n    d["{texts[0]}"].set(text="改过的导入文字")\n', encoding="utf-8"
    )
    code, out = lcad(d, "edit", str(script), "-m", "改一段导入文字")
    assert code == 0, out
    model = json.loads((d / ".linercad/build/model.json").read_text(encoding="utf-8"))
    changed = next(e for e in model["elements"] if e["id"] == texts[0])
    assert changed["intent"]["text"] == "改过的导入文字"
    assert (d / ".linercad/build/drawing.dxf").is_file()
