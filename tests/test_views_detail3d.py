"""D7: a detail of a 3D projected view keeps the source topology references (needs 3d)."""

from __future__ import annotations

import math
import textwrap

import pytest

pytest.importorskip("build123d")

from linercad import runtime  # noqa: E402

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


def test_gear_cover_and_an_assembly_have_working_detail_views(tmp_path):
    import shutil
    from pathlib import Path

    from linercad import txn

    # gear_cover (3D box-family example): a detail of its sectioned front view
    g = tmp_path / "gc"
    txn.init(g, from_="gear_cover")
    drawing = g / "drawing.py"
    drawing.write_text(
        drawing.read_text(encoding="utf-8")
        + '\nd.detail("I", parent="front", center=(-55, 10), r=15, scale="3:1")\n',
        encoding="utf-8",
    )
    r = runtime.build(g)
    assert not [f for f in r.findings if f["severity"] == "error"]
    src = r.d.q.detail_sources("I")
    assert any(e.id.startswith("E.front.") and e._intent.get("src3d") for e in src)
    assert any(e.kind == "hatch" for e in src)
    assert len(src) == 12
    assert len(r.d["V.I"]._prims) == 48

    # an L3 assembly view: clipped edges keep their component attribution
    l3 = Path(__file__).resolve().parents[1] / "evals" / "L3" / "bearing"
    work = tmp_path / "bearing"
    shutil.copytree(l3, work, ignore=shutil.ignore_patterns(".linercad", "__pycache__", "*.jsonl"))
    drawing = work / "drawing.py"
    drawing.write_text(
        drawing.read_text(encoding="utf-8")
        + '\nd.detail("I", parent="front", center=(42, 15), r=18, scale="3:1")\nd["V.I"].place(at=(170, 150))\n',
        encoding="utf-8",
    )
    r = runtime.build(work)
    assert not [f for f in r.findings if f["severity"] == "error"]
    src = r.d.q.detail_sources("I")
    assert any(e._intent.get("component") for e in src if e.kind == "edge")
    assert any(e.kind == "hatch" and e._intent.get("component") for e in src)
    assert r.d["V.I"]._intent["detail_sources"]
    assert len(r.d["V.I"]._prims) == 82
    assert len(src) == 17
    from collections import Counter

    from linercad.layout import Line

    angles = Counter()
    for prim in r.d["V.I"]._prims:
        if isinstance(prim, Line) and prim.layer == "hatch":
            angles[
                round(
                    math.degrees(math.atan2(prim.q[1] - prim.p[1], prim.q[0] - prim.p[0])) % 180,
                    1,
                )
            ] += 1
    assert angles == {45.0: 8, 135.0: 53}, angles
