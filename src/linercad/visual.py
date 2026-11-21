"""The visual verification contract (`docs/VISUAL-VERIFICATION.md`): pixels, ink and glyphs.

A PNG is what an agent *looks at*; ids, numbers and rules are what it *checks*. This module turns
the perceptual half into numbers a test can hold: pixels per millimetre, the pixel height a number
needs before the digits can be trusted, how much ink a sheet must carry before "blank" and "clean"
are different words, and which characters the raster font cannot draw at all — a missing glyph is
an empty box, never an error, so it has to be checked instead of suffered.
"""

from __future__ import annotations

from pathlib import Path

MM_PER_INCH = 25.4

# A dimension number must be at least this tall before the digits are trustworthy. Measured on
# rendered probes (2026-11-21): from 14 px up, "Ø20 H7" / "120 ±0.05" / "Ra 3.2" are read
# correctly every time; at 8-10 px they are readable only because the string is half expected.
MIN_TEXT_PX = 14.0
# Below this, text is a grey smudge: usable as "something is written here", never as a value.
MARGINAL_TEXT_PX = 8.0
# A sheet with a frame and at least one view carries more ink than this. Under it the export is
# blank (wrong colour policy, empty layout, text-only modelspace), not "clean".
MIN_INK_RATIO = 0.002


def px_per_mm(dpi: float) -> float:
    """Pixels per millimetre of a page rendered at `dpi` with the page keeping its sheet size."""
    return dpi / MM_PER_INCH


def text_px(height_mm: float, dpi: float) -> float:
    """Pixel height of text drawn `height_mm` tall on a page rendered at `dpi`."""
    return height_mm * px_per_mm(dpi)


def ink_ratio(png, *, dark: int = 200) -> float:
    """Fraction of pixels darker than `dark` (0-255). Blank is ~0.0, a real sheet > 0.02."""
    from PIL import Image

    image = Image.open(png).convert("L")
    total = image.size[0] * image.size[1]
    return sum(image.histogram()[:dark]) / float(total)


def rasterize_pdf(pdf, out, *, page: int = 1, dpi: int = 150) -> Path:
    """Rasterise one PDF page to a PNG so it can be looked at: a PDF is not an image.

    PyMuPDF is optional: `uv add "linercad[visual]"`.
    """
    try:
        import pymupdf
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on the environment
        raise ModuleNotFoundError(
            'rasterising a PDF needs PyMuPDF: uv add "linercad[visual]"'
        ) from exc
    out = Path(out)
    with pymupdf.open(Path(pdf)) as doc:
        pix = doc[page - 1].get_pixmap(dpi=dpi)
        out.parent.mkdir(parents=True, exist_ok=True)
        pix.save(out)
    return out


def _cmap(font: str | None = None) -> dict:
    from ezdxf.fonts import fonts

    manager = fonts.font_manager
    return manager.get_ttf_font(font or manager.fallback_font_name()).getBestCmap()


def missing_glyphs(texts, font: str | None = None) -> list[str]:
    """Characters in `texts` that `font` (default: the raster fallback) cannot draw.

    Reads the font's cmap, so it stays true if the font is swapped. A missing glyph renders as an
    empty box, never as an error.
    """
    cmap = _cmap(font)
    chars = {c for text in texts for c in text if c.strip()}
    return sorted(c for c in chars if ord(c) not in cmap)


def missing_text_glyphs(doc) -> list[str]:
    """Characters the render would draw as empty boxes anywhere in `doc`, per text style.

    Each TEXT/MTEXT entity is checked against its own style's font (LC → simfang carries CJK,
    Standard → the fallback does not), because that is the font the rasteriser resolves it with.
    """
    from ezdxf.fonts import fonts

    fallback = fonts.font_manager.fallback_font_name()
    cmaps: dict[str, dict] = {}
    missing = set()
    layouts = [doc.modelspace(), *doc.blocks]
    for layout in layouts:
        for e in layout:
            kind = e.dxftype()
            if kind == "TEXT":
                text, style = e.dxf.text, e.dxf.style
            elif kind == "MTEXT":
                text, style = e.plain_text(), e.dxf.style
            else:
                continue
            if style not in cmaps:
                font = doc.styles.get(style).dxf.font or fallback
                cmaps[style] = _cmap(font)
            cmap = cmaps[style]
            missing.update(c for c in text if c.strip() and ord(c) not in cmap)
    return sorted(missing)
