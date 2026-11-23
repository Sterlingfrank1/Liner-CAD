"""D5: parts-list merge identity without 3D (runs in every CI job, build123d not needed).

The L3 assembly tests live in test_assembly.py and are skipped when the optional build123d
dependency is absent; these unit tests keep the merge/qty/ids semantics covered everywhere.
"""

from __future__ import annotations

from linercad import Drawing
from linercad.assembly import Component, bom_rows, number


def _component(d, name, *, path="parts/p", std=None, spec=None, qty=1, title=None, params=None):
    intent = {
        "name": name,
        "path": path,
        "at": [[0, 0, 0]] * qty,
        "rot": [0, 0, 0],
        "params": params or {},
        "solid": False,
        "qty": qty,
        "title": title or {},
        "hash": "h1",
    }
    if std:
        intent["std"] = std
        intent["spec"] = spec
        intent["info"] = {"std": std, "kind": "bolt"}
    return d._add(Component(d, f"A.{name}", intent))


def test_identical_parts_merge_and_sum_qty():
    d = Drawing(kind="assembly")
    _component(d, "plate", title={"drawing_no": "P-1", "name": "板", "material": "45"})
    _component(d, "plate2", title={"drawing_no": "P-1", "name": "板", "material": "45"})
    rows = bom_rows(d)
    assert len(rows) == 1 and rows[0]["qty"] == 2
    assert rows[0]["ids"] == ["A.plate", "A.plate2"]


def test_same_drawing_different_instance_params_still_merge():
    d = Drawing(kind="assembly")
    _component(
        d, "left", title={"drawing_no": "P-1", "name": "板", "material": "45"}, params={"side": 1}
    )
    _component(
        d, "right", title={"drawing_no": "P-1", "name": "板", "material": "45"}, params={"side": -1}
    )
    rows = bom_rows(d)
    assert len(rows) == 1 and rows[0]["qty"] == 2
    assert number(d, "A.left") == number(d, "A.right") == 1


def test_standard_parts_merge_on_std_spec_and_material():
    d = Drawing(kind="assembly")
    _component(
        d,
        "bolt1",
        std="GB/T 5782-2016",
        spec="M10×75",
        qty=2,
        title={"name": "螺栓", "material": "Q235"},
    )
    _component(
        d,
        "bolt2",
        std="GB/T 5782-2016",
        spec="M10×75",
        qty=3,
        title={"name": "螺栓", "material": "Q235"},
    )
    _component(
        d,
        "bolt3",
        std="GB/T 5782-2016",
        spec="M10×75",
        qty=1,
        title={"name": "螺栓", "material": "8.8"},
    )
    rows = bom_rows(d)
    assert len(rows) == 2  # different material stays separate
    assert rows[0]["qty"] == 5 and rows[0]["ids"] == ["A.bolt1", "A.bolt2"]
    assert rows[1]["qty"] == 1 and rows[1]["ids"] == ["A.bolt3"]
    assert rows[0]["no"] == 1 and rows[1]["no"] == 2
