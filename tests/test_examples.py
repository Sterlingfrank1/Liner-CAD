"""The three examples build with zero warnings from `lcad init --from` (SPEC §11, §12 item 1)."""

import pytest

from linercad import txn
from linercad.runtime import build


@pytest.mark.parametrize("name", txn.EXAMPLES)
def test_example_builds_clean(tmp_path, name):
    if txn.needs_3d(name):
        pytest.importorskip("build123d")
    out = txn.init(tmp_path / name, from_=name)
    assert out["ok"] and out["warnings"] == []
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
