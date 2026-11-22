"""The examples build with zero warnings from `lcad init --from` (SPEC §11, §12 item 1).

E5 (D.place) reports the current placement debt of the reference drawings as a warn-level metric; it
is recorded in evals/baseline.json and docs/milestones/v0.1.1/evidence/placement-scores.md and is
driven down by D1/D2. Everything outside the placement pack must stay clean here.
"""

import pytest

from linercad import txn
from linercad.runtime import build

#: E5 placement debt of each example (frozen here on purpose: D1/D2 shrink this list, and any
#: new placement warning must show up as a deliberate update of this table in the same PR).
PLACEMENT_DEBT = {
    "bearing_support": {
        ("place_dim_cross", "D.D"),
        ("place_dim_cross", "D.d"),
        ("place_nesting", "D.W"),
    },
    "bracket": set(),
    "end_cover": {
        ("place_nesting", "D.Ls"),
        ("place_row_spacing", "D.dc"),
        ("place_row_spacing", "D.lb"),
    },
    "flange": set(),
    "gear_cover": {("place_nesting", "D.D"), ("place_nesting", "D.W")},
    "pulley": {
        ("place_dim_outline", "D.tw"),
        ("place_nesting", "D.B"),
        ("place_nesting", "D.da"),
        ("place_row_spacing", "D.di"),
        ("place_row_spacing", "D.f"),
    },
    "pump_body": {
        ("place_dim_cross", "D.Db"),
        ("place_dim_cross", "D.dp"),
        ("place_ext_line", "D.Hc"),
        ("place_nesting", "D.Hc"),
        ("place_nesting", "D.W"),
        ("place_nesting", "D.py"),
        ("place_nesting", "D.tw"),
        ("place_row_spacing", "D.Rc2"),
        ("place_row_spacing", "D.t"),
    },
    "shaft": {
        ("place_dim_outline", "D.d1"),
        ("place_dim_outline", "D.d2"),
        ("place_dim_outline", "D.d3"),
        ("place_dim_outline", "D.d5"),
        ("place_ext_line", "D.gh"),
        ("place_ext_line", "D.gw"),
        ("place_nesting", "D.L"),
        ("place_row_spacing", "D.l2"),
        ("place_row_spacing", "D.l4"),
    },
    "shift_fork": {("place_dim_cross", "D.D"), ("place_dim_cross", "D.d")},
    "sleeve": set(),
    "spline_shaft": {
        ("place_dim_outline", "D.d2"),
        ("place_dim_outline", "D.d3"),
        ("place_dim_outline", "D.d5"),
        ("place_nesting", "D.L"),
        ("place_row_spacing", "D.l2"),
    },
}


@pytest.mark.parametrize("name", txn.EXAMPLES)
def test_example_builds_clean(tmp_path, name):
    if txn.needs_3d(name):
        pytest.importorskip("build123d")
    out = txn.init(tmp_path / name, from_=name)
    assert out["ok"]
    other = [f for f in out["warnings"] if f.get("pack") != "placement"]
    assert other == [], other
    debt = {(f["rule"], f["id"]) for f in out["warnings"] if f.get("pack") == "placement"}
    assert debt == PLACEMENT_DEBT[name], debt
    assert (tmp_path / name / ".linercad/build/drawing.dxf").exists()


def test_flange_full_section(tmp_path):
    txn.init(tmp_path / "f", from_="flange")
    d = build(tmp_path / "f").d
    assert [e.id for e in d.q.hatches()] == ["H.front.body"]
    s = d["S.A"]
    texts = sorted(p.text for p in s._prims if hasattr(p, "text"))
    assert texts == ["A", "A", "A-A"]
    assert sum(1 for p in s._prims if getattr(p, "layer", "") == "section") == 2


def test_bracket_views_aligned(tmp_path):
    txn.init(tmp_path / "b", from_="bracket")
    d = build(tmp_path / "b").d
    o = {n: d.view(n)._resolved["origin"] for n in ("front", "top", "left")}
    assert o["top"][0] == o["front"][0] and o["left"][1] == o["front"][1]


def _hatched(h, p):
    """Is the sheet point ``p`` inside the hatch region (even-odd over its loops)?"""
    from linercad.views import point_in_poly

    loops = [list(lp) for lp in h._prims[0].loops]
    return sum(point_in_poly(p, lp) for lp in loops) % 2 == 1


def test_bearing_support_rib_is_not_hatched(tmp_path):
    """GB/T 4458.6: a rib cut lengthwise is drawn without section lines; walls and base are."""
    txn.init(tmp_path / "b", from_="bearing_support")
    d = build(tmp_path / "b").d
    left, hatches = d.view("left"), [d["H.left.lo"], d["H.left.up"]]

    def hatched(u, z):
        return any(_hatched(h, left.to_sheet(u, z)) for h in hatches)

    assert not hatched(4, 21)  # inside the rib polygon (-18, 12) (32, 12) (20, 29) (-18, 29)
    assert not hatched(0, 55)  # the bore
    assert hatched(0, 5) and hatched(0, 34) and hatched(-24, 20)  # base, boss wall, riser
    rib = d["F.left.rib"]
    assert rib.type == "polygon" and all(e._intent["role"] == "thick" for e in rib.edges)


def test_shift_fork_sections(tmp_path):
    txn.init(tmp_path / "f", from_="shift_fork")
    d = build(tmp_path / "f").d
    assert {"H.top.b", "H.C.c"} <= {e.id for e in d.q.hatches()}
    assert d["S.B"]._intent["kind"] == "full" and d["S.C"]._intent["kind"] == "removed"
    assert len(d["H.top.b"]._intent["loops"]) == 2  # hub wall (left) and wall + arm + jaw (right)
