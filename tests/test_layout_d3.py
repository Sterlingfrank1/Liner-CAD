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

pytest.importorskip("build123d")  # L3 assemblies are 3D-sourced; CI non-3d job skips this file

from linercad import place
from linercad.layout import Circle, Line, _seg_cross, layout
from linercad.runtime import build

L3 = Path(__file__).resolve().parents[1] / "evals" / "L3"
CASES = ("jack", "vise", "bearing")
CW_SIDES = ("top", "right", "bottom", "left")


def _build_res(tmp_path, name):
    work = tmp_path / name
    shutil.copytree(
        L3 / name, work, ignore=shutil.ignore_patterns(".linercad", "__pycache__", "*.jsonl")
    )
    return build(work)


def _build(tmp_path, name):
    return _build_res(tmp_path, name).d


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
    gap = float(d.std["placement"]["balloon_clearance"])
    r = float(cfg["balloon_radius"])
    tol = float(d.std["placement"]["balloon_align_tol"])
    items = _balloons(d)
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            assert math.dist(a["c"], b["c"]) >= 2 * r + gap - 1e-9
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
    for f in _build_res(tmp_path, name).findings:
        if f["rule"] != "overlap":
            continue
        involved = {f["id"], *((f.get("measured") or {}).get("with") or [])}
        assert not any(str(x).startswith("B.") for x in involved), f


@pytest.mark.parametrize("name", CASES)
def test_l3_uses_the_order_plan(tmp_path, name):
    d = _build(tmp_path, name)
    for e in d._els.values():
        if e.kind == "balloon":
            assert e._resolved.get("order") == "side-monotonic", e.id


def test_fallback_reports_its_order_state(tmp_path, monkeypatch):
    import linercad.layout as L

    monkeypatch.setattr(L, "_balloon_plan", lambda *a, **k: None)
    d = _build(tmp_path, "jack")
    states = {e._resolved.get("order") for e in d._els.values() if e.kind == "balloon"}
    assert states == {"fallback"}
    for fn in (place.place_balloon_cross, place.place_balloon_align, place.place_balloon_spacing):
        found, _ = fn(d)
        assert found == [], (fn.__name__, found)


def test_balloons_from_two_views_do_not_collide(tmp_path):
    from linercad.layout import union

    d = _build(tmp_path, "vise")  # vise drawing has a real front + top pair
    names = [v.name for v in d.views()]
    assert "top" in names and "front" in names, names
    top = "top"
    boxes = [
        e._resolved.get("bbox")
        for e in d._els.values()
        if e._intent.get("view") == top and e._resolved.get("bbox")
    ]
    gb = union(boxes)
    view = d["V.top"]._resolved
    ox, oy = view["origin"]
    scale = view["scale"]
    anchor = [((gb[0] + gb[2]) / 2 - ox) / scale, ((gb[1] + gb[3]) / 2 - oy) / scale]
    balloons = sorted((e for e in d._els.values() if e.kind == "balloon"), key=lambda e: e.number)
    moved = balloons[0]
    moved._intent["view"] = top
    moved._intent["anchor"] = anchor
    layout(d)
    assert moved.view == top and moved._resolved.get("bbox")
    for fn in (place.place_balloon_cross, place.place_balloon_align, place.place_balloon_spacing):
        found, _ = fn(d)
        assert found == [], (fn.__name__, found)
    leaders = [b["leader"] for b in _balloons(d)]
    for i, a in enumerate(leaders):
        for b in leaders[i + 1 :]:
            assert not _seg_cross(a.p, a.q, b.p, b.q)


def test_balloon_plan_is_capped_and_falls_back_explicitly():
    from linercad.layout import _can_plan_balloons

    assert _can_plan_balloons(2) and _can_plan_balloons(12)
    assert not _can_plan_balloons(1) and not _can_plan_balloons(13)


def test_written_balloon_side_is_kept(tmp_path):
    d = _build(tmp_path, "jack")
    target = sorted((e for e in d._els.values() if e.kind == "balloon"), key=lambda e: e.number)[0]
    target.place(side="right")
    layout(d)
    assert target._layout["side"] == "right"
    assert target._resolved["side"] == "right"


def test_duplicate_numbers_keep_written_side_independent(tmp_path):
    # D5: merged BOM rows give several balloons one number; a hand-written side on one instance
    # must not move the other instance to the same slot (the plan is index-keyed).
    d = _build(tmp_path, "vise")
    bs = {e.id: e for e in d._els.values() if e.kind == "balloon"}
    fixed, other = bs["B.plate_fixed"], bs["B.plate_mov"]
    assert fixed.number == other.number
    fixed.place(side="right")
    layout(d)
    assert fixed._layout["side"] == "right" and fixed._resolved["side"] == "right"
    assert fixed.number == other.number
    circles = [b["c"] for b in _balloons(d)]
    assert len(set(circles)) == len(circles), "same-number balloons must keep distinct slots"


def test_balloon_layout_is_deterministic(tmp_path):
    from linercad.layout import _BALLOON_PLAN_CACHE

    d = _build(tmp_path, "vise")
    snap = [(b["id"], repr(b["leader"]), b["c"]) for b in _balloons(d)]
    _BALLOON_PLAN_CACHE.clear()  # prove the plan itself is deterministic, not just the cache
    layout(d)
    snap2 = [(b["id"], repr(b["leader"]), b["c"]) for b in _balloons(d)]
    assert snap == snap2
