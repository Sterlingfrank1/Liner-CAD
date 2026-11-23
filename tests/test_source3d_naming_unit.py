"""D4: deterministic projection-edge naming helpers (no build123d needed).

These keep the naming contract covered in the ordinary CI jobs; the full HLR integration test lives
in test_source3d_stable.py and needs the optional 3d extra.
"""

from __future__ import annotations

import copy
import itertools

from linercad.source3d import (
    _edge_geometry_key,
    _name_projection_edges,
    _projection_edge_base,
)


def _line(topo, p1, p2, role="thick", component=None):
    s3 = {"model": "M.main", "topo": topo, "edge": 1, "faces": [0, 1], "hash": "h"}
    if component:
        s3["component"] = component
    return {"shape": "line", "p1": list(p1), "p2": list(p2), "role": role, "src3d": s3}


def test_line_geometry_key_ignores_direction_but_not_position():
    a = _line("f0_1_e0", (10, 0), (0, 0))
    b = _line("f0_1_e0", (0, 0), (10, 0))
    c = _line("f0_1_e0", (0, 1), (10, 1))
    assert _edge_geometry_key(a) == _edge_geometry_key(b)
    assert _edge_geometry_key(a) != _edge_geometry_key(c)


def test_same_topology_gets_stable_suffixes_independent_of_input_order():
    a = _line("f0_1_e0", (0, 0), (10, 0))
    b = _line("f0_1_e0", (20, 0), (30, 0), role="hidden")
    expected = None
    for order in itertools.permutations([a, b]):
        edges = [copy.deepcopy(e) for e in order]
        _name_projection_edges(edges)
        got = {e["name"]: (e["role"], tuple(e["p1"]), tuple(e["p2"])) for e in edges}
        if expected is None:
            expected = got
        else:
            assert got == expected


def test_names_are_canonical_lines_and_component_qualified():
    a = _line("f0_1_e0", (10, 0), (0, 0))
    b = _line("f0_1_e0", (0, 0), (10, 0), role="hidden")
    edges = [a, b]
    _name_projection_edges(edges)
    for e in edges:
        assert e["p1"] <= e["p2"], e
    assert _projection_edge_base(a) == "f0_1_e0"
    assert _projection_edge_base(_line("f0_1_e0", (0, 0), (1, 0), component="A.base")) == (
        "A_base_f0_1_e0"
    )
