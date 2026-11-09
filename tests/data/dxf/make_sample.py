"""Writes ``sample_part.dxf``: a small plate drawn the way a CAD program would, with native DIMENSION
entities (linear, aligned, diameter, radius, angular 2L / 3P), HIDDEN / CENTER layers, a TEXT, an
MTEXT, a SPLINE, an ELLIPSE and a few entities the importer skips (HATCH, INSERT, POINT).

    uv run python tests/data/dxf/make_sample.py [out.dxf]

The file is generated, not hand drawn: ezdxf 1.4 only, no other source, so the license is ours.
"""

from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
from ezdxf import units

OUT = Path(__file__).with_name("sample_part.dxf")


def build() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    doc.header["$MEASUREMENT"] = 1
    for name, lt, lw in (
        ("OUTLINE", "Continuous", 50),
        ("HIDDEN", "HIDDEN", 25),
        ("CENTER", "CENTER", 25),
        ("THIN", "Continuous", 25),
        ("DIM", "Continuous", 25),
        ("TEXT", "Continuous", 25),
    ):  # (ezdxf's setup already has the Defpoints layer)
        doc.layers.add(name, linetype=lt, lineweight=lw)
    msp = doc.modelspace()
    dim = {"layer": "DIM", "dimstyle": "EZDXF"}
    OVR = {
        "dimtxt": 3.5,
        "dimasz": 3.0,
        "dimexe": 1.5,
        "dimexo": 1.0,
        "dimgap": 1.0,
        "dimlfac": 1.0,
    }  # mm-sized

    # outline: a plate 100 x 60 with two chamfered corners
    outline = [
        ((0, 0), (90, 0)),
        ((90, 0), (100, 10)),
        ((100, 10), (100, 60)),
        ((100, 60), (15, 60)),
        ((15, 60), (0, 45)),
        ((0, 45), (0, 0)),
    ]
    for a, b in outline:
        msp.add_line(a, b, dxfattribs={"layer": "OUTLINE"})
    # a through hole and a slot (a closed polyline with two semicircular bulges)
    msp.add_circle((30, 30), 10, dxfattribs={"layer": "OUTLINE"})
    msp.add_lwpolyline(
        [(60, 20, 0, 0, 0), (80, 20, 0, 0, 1), (80, 40, 0, 0, 0), (60, 40, 0, 0, 1)],
        format="xyseb",
        close=True,
        dxfattribs={"layer": "OUTLINE"},
    )
    # centre lines and a pitch circle on CENTER, hidden lines on HIDDEN, a thin line on THIN
    msp.add_line((15, 30), (45, 30), dxfattribs={"layer": "CENTER"})
    msp.add_line((30, 15), (30, 45), dxfattribs={"layer": "CENTER"})
    msp.add_circle((30, 30), 15, dxfattribs={"layer": "CENTER"})
    msp.add_line((20, 52), (45, 52), dxfattribs={"layer": "HIDDEN"})
    msp.add_line((20, 56), (45, 56), dxfattribs={"layer": "HIDDEN"})
    msp.add_circle((75, 50), 4, dxfattribs={"layer": "HIDDEN"})
    msp.add_line((70, 50), (80, 50), dxfattribs={"layer": "CENTER"})
    msp.add_line((75, 45), (75, 55), dxfattribs={"layer": "CENTER"})
    msp.add_line((20, 5), (70, 5), dxfattribs={"layer": "OUTLINE", "linetype": "DASHED"})
    msp.add_line((62, 12), (88, 12), dxfattribs={"layer": "THIN"})

    # native dimensions
    msp.add_linear_dim(
        base=(0, -15), p1=(0, 0), p2=(100, 10), dxfattribs=dim, override=OVR
    ).render()
    msp.add_linear_dim(
        base=(-15, 30), p1=(0, 0), p2=(15, 60), angle=90, dxfattribs=dim, override=OVR
    ).render()
    msp.add_aligned_dim(
        p1=(90, 0), p2=(100, 10), distance=-6, dxfattribs=dim, override=OVR
    ).render()
    msp.add_diameter_dim(
        center=(30, 30), radius=10, angle=135, dxfattribs=dim, override=OVR
    ).render()
    msp.add_diameter_dim(
        center=(75, 50), radius=4, angle=45, text="%%c8 THRU", dxfattribs=dim, override=OVR
    ).render()
    msp.add_radius_dim(
        center=(80, 30), radius=10, angle=20, text="2x<>", dxfattribs=dim, override=OVR
    ).render()
    msp.add_angular_dim_2l(
        base=(70, 8),
        line1=((0, 0), (90, 0)),
        line2=((90, 0), (100, 10)),
        dxfattribs=dim,
        override=OVR,
    ).render()
    msp.add_angular_dim_3p(
        base=(88.9, 14.6), center=(100, 10), p1=(100, 60), p2=(90, 0), dxfattribs=dim, override=OVR
    ).render()

    # text
    msp.add_text("SAMPLE PART", height=5, dxfattribs={"layer": "TEXT"}).set_placement((0, -40))
    mt = msp.add_mtext(
        "Technical requirements\\P1. Deburr all edges",
        dxfattribs={"layer": "TEXT", "char_height": 3.5},
    )
    mt.set_location((0, -55))

    # curves the importer keeps as raw X
    msp.add_spline(
        fit_points=[(45, 44), (52, 47), (58, 44), (65, 47)], dxfattribs={"layer": "THIN"}
    )
    msp.add_ellipse((50, 12), major_axis=(8, 0), ratio=0.5, dxfattribs={"layer": "OUTLINE"})

    # entities it skips: a hatch, a block reference and a point on Defpoints
    h = msp.add_hatch(color=7, dxfattribs={"layer": "THIN"})
    h.paths.add_polyline_path([(92, 40), (98, 40), (98, 55), (92, 55)], is_closed=True)
    blk = doc.blocks.new("MARK")
    blk.add_line((-2, 0), (2, 0))
    blk.add_line((0, -2), (0, 2))
    msp.add_blockref("MARK", (5, 5), dxfattribs={"layer": "THIN"})
    msp.add_point((0, 0), dxfattribs={"layer": "Defpoints"})
    return doc


def main(out: Path = OUT) -> Path:
    doc = build()
    doc.saveas(out)
    return out


if __name__ == "__main__":
    print(main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT))
