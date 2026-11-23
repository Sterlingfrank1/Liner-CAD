"""D5 (G2 first commit): long parts-list text wraps inside its cell and the row grows.

Against the D2 state these fail: `bom_prims` keeps every cell on one line, picks a smaller text
height when the string is long, and uses the fixed 7 mm row height, so a long name either shrinks
to an illegible height or overflows its cell; no row ever grows.
"""

from __future__ import annotations

import pytest

from linercad.layout import BOM_COLS, BOM_ROW, Line, Text, bom_prims
from linercad.std import load_std


def _table(rows, width=260.0):
    std = load_std("GB")
    TB = (0.0, 0.0, width, 20.0)
    prims = bom_prims(rows, TB, std)
    xs = [TB[0]]
    for _label, w in BOM_COLS:
        xs.append(xs[-1] + w)
    xs.append(TB[2])  # remark takes the rest
    horizontal = sorted(
        {
            round(TB[1], 6),
            *(round(p.p[1], 6) for p in prims if isinstance(p, Line) and p.p[1] == p.q[1]),
        }
    )
    vertical = sorted({round(p.p[0], 6) for p in prims if isinstance(p, Line) and p.p[0] == p.q[0]})
    texts = [p for p in prims if isinstance(p, Text)]
    return xs, horizontal, vertical, texts


def _cell_of(xs, box):
    cx = (box[0] + box[2]) / 2
    for j in range(len(xs) - 1):
        if xs[j] <= cx <= xs[j + 1]:
            return j
    return None


def _row_of(lines, box):
    cy = (box[1] + box[3]) / 2
    for k in range(len(lines) - 1):
        if lines[k] <= cy <= lines[k + 1]:
            return k
    return None


@pytest.mark.parametrize("text", ["超长零件名称" * 8, "A" * 90])
def test_long_cell_text_wraps_inside_its_cell(text):
    rows = [
        {
            "no": 1,
            "id": "A.long",
            "code": "GB/T 5782-2016",
            "name": text,
            "qty": 1,
            "material": "材料" * 12,
            "remark": "",
        }
    ]
    xs, horizontal, _vertical, texts = _table(rows)
    # the row must be taller than the standard 7 mm because of the wrapped cells
    assert horizontal[-1] - horizontal[0] > 2 * BOM_ROW

    # every text box stays inside the cell it belongs to (cell padding is part of the contract)
    for prim in texts:
        j = _cell_of(xs, prim.box)
        assert j is not None, prim
        assert prim.box[0] >= xs[j] - 1e-6, (prim.text, prim.box, xs[j])
        assert prim.box[2] <= xs[j + 1] + 1e-6, (prim.text, prim.box, xs[j + 1])
        k = _row_of(horizontal, prim.box)
        assert k is not None, (prim.text, prim.box, horizontal)
        assert prim.box[1] >= horizontal[k] - 1e-6
        assert prim.box[3] <= horizontal[k + 1] + 1e-6

    # a cell carried several actual lines, not one shrunk string
    by_cell = {}
    for prim in texts:
        j = _cell_of(xs, prim.box)
        k = _row_of(horizontal, prim.box)
        by_cell.setdefault((k, j), []).append(prim)
    assert any(len(v) >= 2 for v in by_cell.values())
    # no two lines in one cell may overlap vertically
    for lines in by_cell.values():
        boxes = sorted((p.box for p in lines), key=lambda b: (b[1], b[0]))
        for a, b in zip(boxes, boxes[1:]):
            assert b[1] >= a[3] - 1e-6, (a, b)
