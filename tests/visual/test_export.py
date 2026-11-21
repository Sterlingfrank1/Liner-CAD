"""What a sheet export must be before an agent may look at it (VISUAL-VERIFICATION §2).

These tests pin the *file*: page-sized pixels, black on white, ink on the page. They say nothing
about whether the drawing is right — that is lcad check and the element ids.
"""

from __future__ import annotations

import ezdxf
import pytest
from PIL import Image

from linercad.render import FULL_DPI, render_pdf, render_png
from linercad.visual import MIN_INK_RATIO, ink_ratio, px_per_mm

from .conftest import EXAMPLES


def test_full_sheet_png_keeps_the_sheet_size(built, tmp_path):
    """A3 at 150 dpi is 2480x1754 px. The page must not be rescaled to matplotlib's default
    figure: if it is, the whole sheet lands at ~2.4 px/mm and 2.5 mm text is 6 px of smudge."""
    for name in EXAMPLES:
        res = built[name][1]
        W, H = res.d.template["size"]
        png = render_png(res.doc, (W, H), tmp_path / f"{name}.png", dpi=FULL_DPI)
        w, h = Image.open(png).size
        assert abs(w - W * px_per_mm(FULL_DPI)) <= 1.5, (name, w, W)
        assert abs(h - H * px_per_mm(FULL_DPI)) <= 1.5, (name, h, H)


def test_full_sheet_png_is_black_on_white_with_ink(built, tmp_path):
    """Everything is drawn in black on white and the page carries ink: a white-on-white export
    looks clean, which is the most expensive way to be wrong."""
    for name in EXAMPLES:
        res = built[name][1]
        W, H = res.d.template["size"]
        png = render_png(res.doc, (W, H), tmp_path / f"{name}.png", dpi=FULL_DPI)
        assert ink_ratio(png) > MIN_INK_RATIO, name


def test_text_only_sheet_is_not_blank(tmp_path):
    """A modelspace holding only notes still renders. Before the page was kept at sheet size this
    came out as an empty white page (ink 0.0), and a blank page passes every "no visible defect"
    review: there is nothing to see, so nothing is wrong."""
    doc = ezdxf.new("R2018", setup=True)
    y = 10.0
    for i in range(12):
        doc.modelspace().add_text(f"{i:02d} NOTE {i * 7} mm", height=2.5).set_placement((5, y))
        y += 6
    png = render_png(doc, (120, 90), tmp_path / "text.png", dpi=FULL_DPI)
    assert ink_ratio(png) > MIN_INK_RATIO


def test_pdf_page_is_the_sheet_size(built, tmp_path):
    """The PDF page is the sheet: one sheet = one page, A3 = 1190.55 x 841.89 pt."""
    pymupdf = pytest.importorskip("pymupdf")
    res = built["shaft"][1]
    W, H = res.d.template["size"]
    pdf = render_pdf(res.doc, (W, H), tmp_path / "sheet.pdf")
    with pymupdf.open(pdf) as doc:
        rect = doc[0].rect
    assert abs(rect.width - W * 72 / 25.4) < 1.0
    assert abs(rect.height - H * 72 / 25.4) < 1.0


def test_pdf_rasterizes_to_a_readable_page(built, tmp_path):
    """A PDF is not an image: it needs a rasteriser before an agent can look at it, and the
    rasterised page must still be legible (>= 5.9 px/mm at 150 dpi)."""
    pytest.importorskip("pymupdf")
    from linercad.visual import rasterize_pdf

    res = built["flange"][1]
    W, H = res.d.template["size"]
    pdf = render_pdf(res.doc, (W, H), tmp_path / "sheet.pdf")
    png = rasterize_pdf(pdf, tmp_path / "page.png", dpi=FULL_DPI)
    assert ink_ratio(png) > MIN_INK_RATIO
    w, h = Image.open(png).size
    assert abs(w - W * px_per_mm(FULL_DPI)) <= 2
    assert abs(h - H * px_per_mm(FULL_DPI)) <= 2
