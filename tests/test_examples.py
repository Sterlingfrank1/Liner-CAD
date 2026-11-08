"""The three examples build with zero warnings from `lcad init --from` (SPEC §11, §12 item 1)."""

import pytest

from linercad import txn
from linercad.runtime import build


@pytest.mark.parametrize("name", txn.EXAMPLES)
def test_example_builds_clean(tmp_path, name):
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
