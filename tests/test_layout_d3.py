"""D3: assembly balloon sequences — alignment, minimum spacing, order, crossing-free leaders.

G2 (first commit of the D3 PR): the order test fails on the D2 state; the layout change makes it
pass.  Acceptance of issue #85 on the three L3 assemblies: same-side balloons form one row /
column, the numbers ascend along the same clockwise (or counter-clockwise) walk on every side,
spacing follows the standard gap δ, leaders do not cross, and the three E5 A.place rules stay 0.
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import pytest

from linercad import place
from linercad.layout import Circle, Line, _seg_cross, layout
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


def _sequence(d, counter=False):
    """Numbers per side, walked clockwise (top left->right, right top->bottom, bottom
    right->left, left bottom->top) or the reverse for counter-clockwise."""
    items = _balloons(d)
    out = []
    for side in CW_SIDES:
        group = [b for b in items if b["side"] == side]
        if side == "top":
            reverse = counter
        elif side == "bottom":
            reverse = not counter
        elif side == "right":
            reverse = not counter
        else:  # left
            reverse = counter
        if side in ("top", "bottom"):
            group.sort(key=lambda b: b["c"][0], reverse=reverse)
        else:
            group.sort(key=lambda b: b["c"][1], reverse=reverse)
        out.append((side, [b["number"] for b in group]))
    return out


@pytest.mark.parametrize("name", CASES)
def test_balloon_numbers_ascend_along_each_side(tmp_path, name):
    d = _build(tmp_path, name)
    ok = False
    seen = []
    for counter in (False, True):
        seq = _sequence(d, counter)
        seen.append(seq)
        if all(nums == sorted(nums) for _side, nums in seq):
            ok = True
    assert ok, seen


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
    cfg = d.std["assembly"]
    gap = float(cfg["balloon_gap"])
    r = float(cfg["balloon_radius"])
    tol = float(cfg["balloon_align_tol"])
    items = _balloons(d)
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


@pytest.mark.parametrize("name", CASES)
def test_no_balloon_overlap_warning_on_l3(tmp_path, name):
    """Balloon leaders / numbers must not run through other annotations' text boxes (the G
    overlap pack would warn); the one pre-existing L3 warning is T.bom vs C.top.axis."""
    _build(tmp_path, name)
    for f in build(tmp_path / name, dxf=False).findings:
        if f["rule"] != "overlap":
            continue
        involved = {f["id"], *((f.get("measured") or {}).get("with") or [])}
        assert not any(str(x).startswith("B.") for x in involved), f


def test_written_balloon_side_is_kept(tmp_path):
    d = _build(tmp_path, "jack")
    target = sorted((e for e in d._els.values() if e.kind == "balloon"), key=lambda e: e.number)[0]
    target.place(side="right")
    layout(d)
    assert target._layout["side"] == "right"
    assert target._resolved["side"] == "right"


def test_balloon_layout_is_deterministic(tmp_path):
    d = _build(tmp_path, "vise")
    snap = [(b["id"], repr(b["leader"]), b["c"]) for b in _balloons(d)]
    layout(d)
    snap2 = [(b["id"], repr(b["leader"]), b["c"]) for b in _balloons(d)]
    assert snap == snap2
