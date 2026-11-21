"""Can the numbers actually be read? (VISUAL-VERIFICATION §3)

The contract: a full-sheet render keeps every number above the marginal floor, and anything under
2.5 mm gets a focus crop before an agent is asked to believe it.
"""

from __future__ import annotations

from PIL import Image

from linercad.render import FOCUS_DPI, FULL_DPI, render_png
from linercad.visual import (
    MARGINAL_TEXT_PX,
    MIN_TEXT_PX,
    missing_glyphs,
    missing_text_glyphs,
    text_px,
)

from .conftest import EXAMPLES

# GB/T 14691 body sizes the examples use: notes 2.5 mm, dimensions 3.5 mm and up.
NOTE_HEIGHT = 2.5


def text_heights(doc) -> list[float]:
    out = []
    for layout in [doc.modelspace(), *doc.blocks]:
        for e in layout:
            if e.dxftype() == "TEXT":
                out.append(e.dxf.height)
            elif e.dxftype() == "MTEXT":
                out.append(e.dxf.char_height)
    return out


def test_full_sheet_keeps_every_number_above_the_marginal_floor(built):
    for name in EXAMPLES:
        doc = built[name][1].doc
        smallest = min(text_heights(doc))
        assert text_px(smallest, FULL_DPI) >= MARGINAL_TEXT_PX, (name, smallest)


def test_full_sheet_makes_standard_notes_trustworthy(built):
    """2.5 mm notes at 150 dpi are 14.8 px: exactly the floor where digits stop being guessed.
    If FULL_DPI or the page size ever change, this test is the tripwire."""
    for name in EXAMPLES:
        doc = built[name][1].doc
        heights = [h for h in text_heights(doc) if h >= NOTE_HEIGHT - 0.01]
        assert heights, name
        assert text_px(min(heights), FULL_DPI) >= MIN_TEXT_PX, name


def test_focus_crop_is_the_way_to_read_small_text(built, tmp_path):
    """A focus crop is rendered at FOCUS_DPI over a small bbox: >= 10 px/mm, so even a 2.5 mm
    note becomes >= 25 px and every tolerance in it is legible."""
    res = built["shaft"][1]
    d = res.d
    W, H = d.template["size"]
    dim = next(e for e in d._els.values() if e.kind == "dim" and e.bbox)
    b = dim.bbox
    m = 15.0
    bbox = (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
    png = render_png(res.doc, (W, H), tmp_path / "focus.png", focus_bbox=bbox, dpi=FOCUS_DPI)
    w, _ = Image.open(png).size
    ratio = w / (bbox[2] - bbox[0])
    assert ratio >= 10.0, ratio
    assert ratio * NOTE_HEIGHT >= MIN_TEXT_PX


def test_example_text_has_no_missing_glyphs(built):
    """Every character in the examples is drawable, checked against each text's own style font:
    a missing glyph renders as an empty box, so a "⌖" in a note would silently read as "no
    tolerance at all"."""
    for name in EXAMPLES:
        assert missing_text_glyphs(built[name][1].doc) == [], name


def test_glyph_guard_catches_a_known_missing_character():
    """The guard has teeth: the position symbol U+2316 is not in the raster font, which is exactly
    why GD&T frames are drawn as geometry and never as text."""
    assert "\u2316" in missing_glyphs(["⌖ Ø0.2 A B"])
    assert missing_glyphs(["Ø20 H7 ±0.05"]) == []
