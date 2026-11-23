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
    if data.get("shape") == "line":
        data["p1"], data["p2"] = sorted([data["p1"], data["p2"]])
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
    full1 = {e.id: json.dumps(e._intent, sort_keys=True) for e in _edges(d1)}
    full2 = {e.id: json.dumps(e._intent, sort_keys=True) for e in _edges(d2)}
    assert full2 == full1
    from linercad.versions import compare, snapshot

    cmp = compare(snapshot(d1), snapshot(d2))
    assert not [i for i in cmp["intent_changed"] + cmp["layout_changed"] if i.startswith("E.")]


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
    assert any(i.rsplit(".", 1)[-1].startswith("f") and "_e" in i for i in ids), ids
    with pytest.raises(NotFound) as ei:
        d["E.front.model.1"]  # M3 sequential child id is gone
    assert ei.value.candidates
    assert all(c in d and c.startswith("E.front.model.") for c in ei.value.candidates), (
        ei.value.candidates
    )


def test_gear_cover_parameter_change_only_touches_actually_changed_edges(tmp_path):
    from linercad import txn
    from linercad.versions import compare, snapshot

    g = tmp_path / "gc"
    txn.init(g, from_="gear_cover")
    r1 = runtime.build(g)
    drawing = g / "drawing.py"
    text = drawing.read_text(encoding="utf-8")
    assert "L=Param(150" in text
    drawing.write_text(text.replace("L=Param(150", "L=Param(160"), encoding="utf-8")
    r2 = runtime.build(g)

    def by_geom(res):
        return {(e.view, _geom(e)): e.id for e in res.d._els.values() if e.kind == "edge"}

    a, b = by_geom(r1), by_geom(r2)
    unchanged = {a[g] for g in set(a) & set(b) if a[g] == b[g]}
    # 72 edges keep their projected geometry under L: their IDs must stay and diff must not report them
    assert len(unchanged) == 72, len(unchanged)
    cmp = compare(snapshot(r1.d), snapshot(r2.d))
    reported = {i for i in cmp["intent_changed"] + cmp["layout_changed"] if i.startswith("E.")}
    assert len(reported) == 24, sorted(reported)
    assert not (reported & unchanged), sorted(reported & unchanged)
    added_removed = {i for i in cmp["added"] + cmp["removed"] if i.startswith("E.")}
    assert added_removed == set(), sorted(added_removed)
