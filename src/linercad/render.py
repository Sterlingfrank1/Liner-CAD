"""PNG rendering for agent self-check (SPEC §9.2): ezdxf drawing add-on + matplotlib."""

from __future__ import annotations

from pathlib import Path

from .dxfout import APPID

FULL_DPI = 150
FOCUS_DPI = 300
# PNG only: widen lines so the 2:1 thick/thin ratio survives rasterising (DXF widths unchanged)
LINEWEIGHT_SCALING = 1.8


def _xid(entity):
    try:
        return entity.get_xdata(APPID)[0].value
    except Exception:
        return None


def render_png(doc, sheet_size, out, *, focus_bbox=None, focus_id=None, dpi=None) -> Path:
    """Render ``doc`` (sheet coordinates) to ``out``. Everything black; ``focus_id`` red.

    One pixel is ``dpi / 25.4`` mm of sheet: a 2.5 mm note at 150 dpi is 15 px, so the numbers in
    a full sheet stay readable (docs/VISUAL-VERIFICATION.md §3).
    """
    return _render(
        doc,
        sheet_size,
        out,
        focus_bbox=focus_bbox,
        focus_id=focus_id,
        dpi=dpi,
        scaling=LINEWEIGHT_SCALING,
    )


def render_pdf(doc, sheet_size, out) -> Path:
    """Vector PDF of the whole sheet (page = sheet size). Line widths are DXF's, not widened."""
    return _render(doc, sheet_size, out, scaling=1.0)


def _render(doc, sheet_size, out, *, focus_bbox=None, focus_id=None, dpi=None, scaling) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration, LineweightPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    W, H = sheet_size
    x0, y0, x1, y1 = focus_bbox or (0.0, 0.0, W, H)
    dpi = dpi or (FOCUS_DPI if focus_bbox else FULL_DPI)
    cfg = Configuration(
        background_policy=BackgroundPolicy.WHITE,
        lineweight_policy=LineweightPolicy.ABSOLUTE,
        lineweight_scaling=scaling,
        min_lineweight=0.05,
    )
    fig = plt.figure(figsize=((x1 - x0) / 25.4, (y1 - y0) / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    # adjust_figure would fit the figure to matplotlib's default 6.4x4.8 in instead of the sheet:
    # A3 then lands at 2.4 px/mm (2.5 mm text = 6 px), and ``dpi`` stops meaning anything.
    frontend = Frontend(RenderContext(doc), MatplotlibBackend(ax, adjust_figure=False), config=cfg)

    def colour(entity, props):
        props.color = "#ff0000" if focus_id and _xid(entity) == focus_id else "#000000"

    frontend.push_property_override_function(colour)
    frontend.draw_layout(doc.modelspace(), finalize=True)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="white")
    plt.close(fig)
    return out
