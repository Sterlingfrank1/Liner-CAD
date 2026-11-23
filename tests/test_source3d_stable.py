"""D4: projected edges are named by 3D topology, not by projection order.

G2 (first commit of the D4 PR): the projection-order test and the old-ID candidate test fail on
the M3 state, where edge IDs are sequential children of the feature scope.
"""

from __future__ import annotations

import json
import shutil
import textwrap

import pytest

pytest.importorskip("build123d")

from linercad import runtime  # noqa: E402
from linercad.errors import NotFound  # noqa: E402

MODEL = """
from build123d import Box, Cylinder, Pos

def model(L=120, W=80, T=12, D=50, H=40, d=30):
    body = Pos(0, 0, T / 2) * Box(L, W, T) + Pos(0, 0, H / 2) * Cylinder(D / 2, H)
    body = body - Pos(0, 0, H / 2) * Cylinder(d / 2, H + 2)
    for x in (-L / 2 + 12, L / 2 - 12):
        for y in (-W / 2 + 12, W / 2 - 12):
            body = body - Pos(x, y, T / 2) * Cylinder(5, T + 2)
    return body
"""

DRAWING = """
from linercad import Drawing, Param
d = Drawing(sheet="A3")
P = d.params(L=Param(120, min=80, max=200), d=Param(30, min=10, max=40, rule="d < 50"))
d.model("model.py")
d.view("front").project()
"""


def make(tmp_path, body=DRAWING):
    (tmp_path / "model.py").write_text(textwrap.dedent(MODEL), encoding="utf-8")
    (tmp_path / "drawing.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return runtime.build(tmp_path)


def _geom(e):
    keep = ("shape", "p1", "p2", "c", "r", "start", "end")
    intent = e._intent
    data = {k: intent[k] for k in keep if k in intent}
    return json.dumps(data, sort_keys=True)


def _edges(d, view="front"):
    return [e for e in d._els.values() if e.kind == "edge" and e.view == view]


def _clear_cache(tmp_path):
    shutil.rmtree(tmp_path / ".linercad" / "cache", ignore_errors=True)


def test_ids_do_not_depend_on_projection_order(tmp_path, monkeypatch):
    d1 = make(tmp_path).d
    first = {_geom(e): e.id for e in _edges(d1)}
    assert first

    import linercad.hlr as hlr

    real = hlr.project_classes

    def reversed_order(*args, **kwargs):
        return list(reversed(real(*args, **kwargs)))

    monkeypatch.setattr(hlr, "project_classes", reversed_order)
    _clear_cache(tmp_path)
    d2 = make(tmp_path).d
    second = {_geom(e): e.id for e in _edges(d2)}
    assert second == first


def test_repeated_projection_keeps_the_same_ids(tmp_path):
    d1 = make(tmp_path).d
    first = {_geom(e): e.id for e in _edges(d1)}
    _clear_cache(tmp_path)
    d2 = make(tmp_path).d
    second = {_geom(e): e.id for e in _edges(d2)}
    assert second == first


def test_projected_edges_have_topological_names_and_candidates_for_old_ids(tmp_path):
    d = make(tmp_path).d
    ids = {e.id for e in _edges(d)}
    assert any("f" in i for i in ids), ids  # new names encode the source face/edge ordinal
    with pytest.raises(NotFound) as ei:
        d["E.front.model.1"]  # M3 sequential child id is gone
    assert ei.value.candidates
    assert any(c.startswith("E.front.model.") for c in ei.value.candidates)
