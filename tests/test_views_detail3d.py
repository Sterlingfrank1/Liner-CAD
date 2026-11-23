"""D7: a detail of a 3D projected view keeps the source topology references (needs 3d)."""

from __future__ import annotations

import textwrap

import pytest

pytest.importorskip("build123d")

from linercad import Drawing, runtime  # noqa: E402

MODEL = """
from build123d import Box, Cylinder, Pos

def model(L=60, W=40, T=10, D=16):
    body = Pos(0, 0, T / 2) * Box(L, W, T) + Pos(0, 0, 22) * Cylinder(D / 2, 24)
    body = body - Pos(0, 0, 22) * Cylinder(5, 30)
    return body
"""

DRAWING = """
from linercad import Drawing
d = Drawing(sheet="A3")
d.model("model.py")
v = d.view("front")
v.project()
d.detail("I", parent="front", center=(0, 22), r=12, scale="3:1")
d.title(name="投影局部放大", drawing_no="LC-DT-01")
"""


def test_projected_detail_links_back_to_source_edges_and_features(tmp_path):
    (tmp_path / "model.py").write_text(textwrap.dedent(MODEL), encoding="utf-8")
    (tmp_path / "drawing.py").write_text(textwrap.dedent(DRAWING), encoding="utf-8")
    r = runtime.build(tmp_path)
    d = r.d
    src = d.q.detail_sources("I")
    ids = src.ids()
    assert ids, "the detail view must remember its parent elements"
    assert any(i.startswith("E.front.") for i in ids)
    edges = [e for e in src if e.kind == "edge"]
    assert edges and all(e._intent.get("src3d") for e in edges)
    assert d["V.I"]._intent["detail_sources"]
    # every source id still exists and belongs to the parent view
    assert all(i in d for i in ids)
    assert all(d[i]._intent.get("view") == "front" for i in ids)
