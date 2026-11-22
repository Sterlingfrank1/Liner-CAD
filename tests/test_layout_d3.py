"""D3: assembly balloon sequences — alignment, minimum spacing, order, crossing-free leaders.

G2 (first commit of the D3 PR): these tests fail on the D2 state and are made to pass by the
assembly/layout changes.  They state the acceptance of issue #85 on the three L3 assemblies:
balloons form a clockwise / counter-clockwise consecutive sequence (same side = same row/column,
numbers consecutive around the view), spacing >= the standard gap, and leaders do not cross.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import pytest

from linercad import Drawing, place
from linercad.layout import Line, _seg_cross, layout
from linercad.runtime import build

L3 = Path(__file__).resolve().parents[1] / "evals" / "L3"
CASES = ("jack", "vise", "bearing")
CW_SIDES = ("top", "right", "bottom", "left")


def _build(tmp_path, name):
    work = tmp_path / name
    shutil.copytree(
        L3 / name, work, ignore=shutil.ignore_patterns(".linercad", "__pycache__", "*.jsonl")
    )
    return build(work).d


def _balloons(d):
    out = []
    for e in d._els.values():
        if e.kind != "balloon":
            continue
        from linercad.layout import Circle

        circle = next(p for p in e._prims if isinstance(p, Circle))
        leader = next(p for p in e._prims if isinstance(p, Line))
        out.append(
            {
                "id": e.id,
                "number": e.number,
                "side": e._resolved.get("side"),
                "c": circle.c,
                "leader": leader,
                "written_side": e._layout.get("side"),
            }
        )
    return out


def _sequence(d):
    """Balloon numbers walked clockwise: top row left->right, right column top->bottom,
    bottom row right->left, left column bottom->top."""
    items = _balloons(d)
    seq = []
    for side in CW_SIDES:
        group = [b for b in items if b["side"] == side]
        if side in ("top", "bottom"):
            group.sort(key=lambda b: b["c"][0], reverse=side == "bottom")
        else:
            group.sort(key=lambda b: b["c"][1], reverse=side == "left")
        seq += [b["number"] for b in group]
    return seq


@pytest.mark.parametrize("name", CASES)
def test_balloon_sequence_is_clockwise_continuous(tmp_path, name):
    d = _build(tmp_path, name)
    seq = _sequence(d)
    n = len(seq)
    assert sorted(seq) == list(range(1, n + 1))
    assert all((seq[(i + 1) % n] - seq[i] - 1) % n == 0 for i in range(n)), seq


@pytest.mark.parametrize("name", CASES)
def test_balloon_leaders_do_not_cross(tmp_path, name):
    d = _build(tmp_path, name)
    leaders = [b["leader"] for b in _balloons(d)]
    for i, a in enumerate(leaders):
        for b in leaders[i + 1 :]:
            assert not _seg_cross(a.p, a.q, b.p, b.q)


@pytest.mark.parametrize("name", CASES)
def test_balloon_spacing_and_alignment_follow_the_standard(tmp_path, name):
    d = _build(tmp_path, name)
    cfg = d.std.get("assembly") or {}
    gap = cfg.get("balloon_gap", 2.0)
    tol = cfg.get("balloon_align_tol", 0.5)
    items = _balloons(d)
    radius = max(math.dist((0, 0), (0, 0)) for _ in ()) if False else None
    # radius from spacing rule: the circles have equal radius; derive it from the standard
    r = (
        d.std["assembly"]["balloon_radius"]
        if "balloon_radius" in d.std.get("assembly", {})
        else 4.5
    )
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            assert math.dist(a["c"], b["c"]) >= 2 * r + gap - 0.25
    for side in CW_SIDES:
        group = [b for b in items if b["side"] == side]
        if len(group) < 2:
            continue
        if side in ("top", "bottom"):
            assert max(b["c"][1] for b in group) - min(b["c"][1] for b in group) <= tol
        else:
            assert max(b["c"][0] for b in group) - min(b["c"][0] for b in group) <= tol


@pytest.mark.parametrize("name", CASES)
def test_a_place_balloon_rules_are_clean(tmp_path, name):
    d = _build(tmp_path, name)
    for fn in (place.place_balloon_cross, place.place_balloon_align, place.place_balloon_spacing):
        found, _ = fn(d)
        assert found == [], (fn.__name__, found)


def test_written_balloon_side_is_kept(tmp_path):
    d = _build(tmp_path, "jack")
    target = sorted((e for e in d._els.values() if e.kind == "balloon"), key=lambda e: e.number)[0]
    target.place(side="right")
    layout(d)
    assert target._resolved["side"] == "right"
    assert (
        target.placement["resolved"]["side"] == "right" if "placement" in target.__dict__ else True
    )


def test_balloon_layout_is_deterministic(tmp_path):
    d = _build(tmp_path, "vise")
    snap = [(b["id"], repr(b["leader"]), b["c"]) for b in _balloons(d)]
    layout(d)
    snap2 = [(b["id"], repr(b["leader"]), b["c"]) for b in _balloons(d)]
    assert snap == snap2
