"""D.place / A.place placement metrics (E5; docs/proposals/benchmark-metrics.md §3.2, §3.4).

The layout engine already places annotations; these checks judge the laid-out primitives
(sheet-coordinate lines, arrows, texts, balloon circles), never the intent, so they measure what a
reader would see and stay valid for imported drawings.

Every rule follows the E1 protocol: it returns (findings, opportunities) where opportunities is the
number of independent checks performed (at most one finding each). Findings carry the E1 fields
(clause / measured / expected / candidates) plus the standard number of the active profile.
checks.run adds these under the placement pack; the balloon rules feed the A family, the dimension
rules feed D (see checks.family).
"""

from __future__ import annotations

import math

from .layout import Circle, Hatch, Line, Solid, Text, prim_segments

EPS = 1e-6

#: standard number per profile and subject (the clause statements are in CLAUSES)
STANDARDS = {
    "GB": {"dim": "GB/T 4458.4-2003", "balloon": "GB/T 4458.2-2003"},
    "ISO": {"dim": "ISO 129-1:2018", "balloon": "ISO 6433:1981"},
}

#: what each rule checks, quoted as the clause statement it implements
CLAUSES = {
    "place_dim_cross": "尺寸线不应与其他尺寸线相交",
    "place_dim_outline": "尺寸线不应与轮廓线相交",
    "place_row_spacing": "平行的尺寸线之间应保持不小于排距的间距",
    "place_nesting": "尺寸较小的尺寸应靠近轮廓，尺寸较大的尺寸应在外侧",
    "place_ext_line": "尺寸界线应超出尺寸线约 2 mm，并应从轮廓线、轴线或中心线引出",
    "place_text_direction": "水平尺寸的数字字头朝上，垂直尺寸的数字字头朝左",
    "place_text_overlap": "尺寸数字不应与其他图元重叠",
    "place_arrow": "同一图纸的箭头大小应一致，并符合标准档的箭头尺寸",
    "place_balloon_cross": "零件序号的引线不应相交",
    "place_balloon_align": "同一侧的零件序号应排成一列或一行",
    "place_balloon_spacing": "零件序号的圆圈之间应保持间隙，不得重叠",
}

#: A.place rules feed the assembly family; the rest feed D
FAMILY_OVERRIDES = {
    "place_balloon_cross": "A",
    "place_balloon_align": "A",
    "place_balloon_spacing": "A",
}


def _std(d, rule):
    return STANDARDS.get(d.std_name, STANDARDS["GB"])[
        "balloon" if rule.startswith("place_balloon") else "dim"
    ]


def _f(rule, d, id, message, measured=None, expected=None, candidates=None):
    std = _std(d, rule)
    return {
        "rule": rule,
        "id": id,
        "message": message,
        "severity": "warn",
        "violations": [],
        "corridors": {},
        "measured": dict(measured or {}),
        "expected": dict(expected or {}),
        "candidates": list(candidates or []),
        "std": std,
        "clause": f"{std}：{CLAUSES[rule]}",
    }


# ---- geometry helpers ---------------------------------------------------------------------------


def _crosses(p1, p2, q1, q2):
    """True when the two segments cross at interior points (touching / collinear does not count)."""

    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)

    return (
        orient(p1, p2, q1) * orient(p1, p2, q2) < 0 and orient(q1, q2, p1) * orient(q1, q2, p2) < 0
    )


def _intersection(p1, p2, q1, q2):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = q1
    x4, y4 = q2
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _seg_dist(pt, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.dist(pt, a)
    t = max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / L2))
    return math.dist(pt, (ax + t * dx, ay + t * dy))


def _is_h(p):
    return abs(p.p[1] - p.q[1]) < EPS


def _is_v(p):
    return abs(p.p[0] - p.q[0]) < EPS


def _box_dim(e):
    """Axis-aligned box dimension: (direction, dim line, extension lines, arrows, texts)."""
    if e.kind != "dim":
        return None
    lines = [p for p in e._prims if isinstance(p, Line)]
    if len(lines) < 3:
        return None
    arrows = [p for p in e._prims if isinstance(p, Solid)]
    texts = [p for p in e._prims if isinstance(p, Text)]
    if len(arrows) < 2:
        return None
    h = [p for p in lines if _is_h(p)]
    v = [p for p in lines if _is_v(p)]
    if len(h) == 1 and len(v) == 2:
        return {"dir": "h", "dim": h[0], "ext": v, "arrows": arrows, "texts": texts}
    if len(v) == 1 and len(h) == 2:
        return {"dir": "v", "dim": v[0], "ext": h, "arrows": arrows, "texts": texts}
    return None


def _leader_dim(e):
    """Leader-type dimension (circle diameter/radius, chamfer, groove, hole, spline): its dim line
    is the longest line of the leader."""
    lines = [p for p in e._prims if isinstance(p, Line)]
    arrows = [p for p in e._prims if isinstance(p, Solid)]
    texts = [p for p in e._prims if isinstance(p, Text)]
    if len(lines) != 2 or len(arrows) < 1:
        return None
    return {
        "dir": "leader",
        "dim": max(lines, key=lambda p: math.dist(p.p, p.q)),
        "ext": [],
        "arrows": arrows,
        "texts": texts,
    }


def _dim_info(e):
    """(kind, {dir, dim, ext, arrows, texts}) for a dimension element, or None."""
    if e.kind != "dim":
        return None
    box = _box_dim(e)
    if box is not None:
        return "box", box
    leader = _leader_dim(e)
    if leader is not None:
        return "leader", leader
    return None


def _view_bbox(d, name):
    """Bounding box of the view's outline (edges only: the view element's bbox includes the
    annotations, which is exactly what must be excluded when deciding a side / a distance)."""
    boxes = [
        e._resolved["bbox"]
        for e in d._els.values()
        if e.kind == "edge"
        and e.view == name
        and e.role in ("thick", "hidden")
        and e._resolved.get("bbox")
    ]
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _side(bbox, info):
    """Which side of the view the dimension line sits on (None: inside / cannot tell)."""
    if not bbox:
        return None
    if info["dir"] == "h":
        y = info["dim"].p[1]
        if y > bbox[3] + 0.5:
            return "top"
        if y < bbox[1] - 0.5:
            return "bottom"
        return None
    if info["dir"] == "v":
        x = info["dim"].p[0]
        if x > bbox[2] + 0.5:
            return "right"
        if x < bbox[0] - 0.5:
            return "left"
        return None
    return None


def _outline_distance(bbox, info):
    if not bbox:
        return None
    if info["dir"] == "h":
        y = info["dim"].p[1]
        return y - bbox[3] if y > bbox[3] else bbox[1] - y
    x = info["dim"].p[0]
    return x - bbox[2] if x > bbox[2] else bbox[0] - x


def _box_span(info):
    """Distance between the two extension lines = the dimension's drawn length on the sheet."""
    if info["dir"] == "h":
        return abs(info["ext"][0].p[0] - info["ext"][1].p[0])
    return abs(info["ext"][0].p[1] - info["ext"][1].p[1])


def _box_interval(info):
    """The dimension's extent along its own axis (sheet coordinates), used to tell whether two
    parallel dimension lines sit above one another at all."""
    k = 0 if info["dir"] == "h" else 1
    a, b = sorted((info["ext"][0].p[k], info["ext"][1].p[k]))
    return a, b


def _overlap_1d(a, b):
    return min(a[1], b[1]) - max(a[0], b[0]) > 0.01


def _center_segments(d, view):
    out = []
    for e in d._els.values():
        if e.kind == "center" and e.view == view:
            for p in e._prims:
                out += prim_segments(p)
    return out


def _edge_segments(d, view):
    out = []
    for e in d._els.values():
        if e.kind != "edge" or e.view != view:
            continue
        if e.role not in ("thick", "hidden"):
            continue
        for p in e._prims:
            if isinstance(p, Hatch):
                continue
            out += prim_segments(p)
    return out


def _arrow_size(solid):
    """(short side, long side) of the arrow triangle: base width and tip-to-base height."""
    pts = solid.pts
    ds = sorted(math.dist(pts[i], pts[j]) for i in range(3) for j in range(i + 1, 3))
    return ds[0], ds[2]


# ---- D.place rules ------------------------------------------------------------------------------


def place_dim_cross(d):
    """尺寸线互相交叉 (GB/T 4458.4 / ISO 129-1); judged on box dimensions."""
    targets = []
    for e in d._els.values():
        info = _box_dim(e)
        if info is None:
            continue
        targets.append((e, info["dim"]))
    findings = []
    for i, (e, line) in enumerate(targets):
        for j, (other, other_line) in enumerate(targets):
            if i >= j:
                continue
            if _crosses(line.p, line.q, other_line.p, other_line.q):
                pt = _intersection(line.p, line.q, other_line.p, other_line.q)
                for me, them in ((e, other), (other, e)):
                    findings.append(
                        _f(
                            "place_dim_cross",
                            d,
                            me.id,
                            f"{me.id} 的尺寸线与 {them.id} 的尺寸线相交",
                            measured={
                                "with": them.id,
                                "at": [round(pt[0], 2), round(pt[1], 2)],
                            },
                            expected={"crossings": 0},
                            candidates=[f"移动 {me.id} 的排 / 侧向，避开 {them.id}"],
                        )
                    )
    seen, uniq = set(), []
    for f in findings:
        if f["id"] not in seen:
            seen.add(f["id"])
            uniq.append(f)
    return uniq, len(targets)


def place_dim_outline(d):
    """尺寸线与轮廓线交叉; judged on box dimensions (leaders point at their own outline)."""
    targets, findings = [], []
    for e in d._els.values():
        info = _box_dim(e)
        if info is None:
            continue
        line = info["dim"]
        edges = _edge_segments(d, e.view)
        hit = any(_crosses(line.p, line.q, a, b) for a, b in edges)
        targets.append(e)
        if hit:
            findings.append(
                _f(
                    "place_dim_outline",
                    d,
                    e.id,
                    f"{e.id} 的尺寸线与轮廓线交叉",
                    measured={
                        "line": [
                            [round(line.p[0], 2), round(line.p[1], 2)],
                            [round(line.q[0], 2), round(line.q[1], 2)],
                        ]
                    },
                    expected={"outline_crossings": 0},
                    candidates=[f"移动 {e.id} 到轮廓外，或加大排距"],
                )
            )
    return findings, len(targets)


def _side_groups(d):
    """{(view, dir, side): [(element, info, distance)]} for box dimensions outside the outline."""
    groups = {}
    for e in d._els.values():
        info = _box_dim(e)
        if info is None:
            continue
        bbox = _view_bbox(d, e.view)
        side = _side(bbox, info)
        if side is None:
            continue
        dist = _outline_distance(bbox, info)
        groups.setdefault((e.view, info["dir"], side), []).append((e, info, dist))
    for items in groups.values():
        items.sort(key=lambda t: t[2])
    return groups


def place_row_spacing(d):
    """平行尺寸线的间距不小于标准档排距."""
    groups = _side_groups(d)
    pitch = d.std["dim"]["row_pitch"]
    tol = 0.5
    findings, checks = [], 0
    for items in groups.values():
        for (e0, i0, d0), (e1, i1, d1) in zip(items, items[1:]):
            if not _overlap_1d(_box_interval(i0), _box_interval(i1)):
                continue  # side by side, not stacked: no row pitch requirement
            checks += 1
            gap = d1 - d0
            if gap < pitch - tol:
                findings.append(
                    _f(
                        "place_row_spacing",
                        d,
                        e1.id,
                        f"{e1.id} 与 {e0.id} 的尺寸线间距 {gap:.2f} 小于排距 {pitch:g}",
                        measured={"gap": round(gap, 3), "with": e0.id},
                        expected={"gap": f">= {pitch:g}"},
                        candidates=[f"外推到下一排：place(row=...)，或移动 {e1.id}"],
                    )
                )
    return findings, checks


def place_nesting(d):
    """小尺寸在内、大尺寸在外."""
    groups = _side_groups(d)
    findings, checks = [], 0
    for items in groups.values():
        for (e0, i0, _d0), (e1, i1, _d1) in zip(items, items[1:]):
            if not _overlap_1d(_box_interval(i0), _box_interval(i1)):
                continue  # side by side, not nested: order does not matter
            span0, span1 = _box_span(i0), _box_span(i1)
            checks += 1
            if span0 > span1 + 0.01:  # the inner dimension is the longer one
                findings.append(
                    _f(
                        "place_nesting",
                        d,
                        e0.id,
                        f"{e0.id}（{span0:.1f}）比外侧的 {e1.id}（{span1:.1f}）大，小尺寸应在内",
                        measured={
                            "inner": e0.id,
                            "inner_span": round(span0, 3),
                            "outer": e1.id,
                            "outer_span": round(span1, 3),
                        },
                        expected={"inner_span": "<= outer_span"},
                        candidates=[f"交换 {e0.id} 与 {e1.id} 的排"],
                    )
                )
    return findings, checks


def place_ext_line(d):
    """尺寸界线超出约 2 mm 并与轮廓线留隙."""
    dm = d.std["dim"]
    beyond = dm["ext_beyond"]
    lo, hi = beyond - 0.5, beyond + 1.0
    max_gap = 1.5  # the line must start on the contour / axis (small gaps are invisible)
    findings, checks = [], 0
    for e in d._els.values():
        info = _box_dim(e)
        if info is None:
            continue
        bbox = _view_bbox(d, e.view)
        side = _side(bbox, info)
        if side is None:
            continue
        edges = _edge_segments(d, e.view) + _center_segments(d, e.view)
        level = info["dim"].p[1] if info["dir"] == "h" else info["dim"].p[0]
        outward = 1.0 if side in ("top", "right") else -1.0
        for ext in info["ext"]:
            checks += 1
            k = 1 if info["dir"] == "h" else 0  # vertical ext line: y; horizontal: x
            signs = [(p[k] - level) * outward for p in (ext.p, ext.q)]
            outward_signs = [s for s in signs if s >= -1e-9]
            if not outward_signs:  # the extension line does not reach the dimension line
                findings.append(
                    _f(
                        "place_ext_line",
                        d,
                        e.id,
                        f"{e.id} 的尺寸界线没有越过尺寸线（超出 {min(signs):.2f}）",
                        measured={"beyond": round(max(signs), 3)},
                        expected={"beyond": f"{lo:g}..{hi:g}"},
                        candidates=[f"把 {e.id} 的尺寸界线延长到越过尺寸线约 {beyond:g}"],
                    )
                )
                continue
            over = min(outward_signs)
            inward = [p for p, s in zip((ext.p, ext.q), signs) if s < -1e-9]
            gap = (
                min((_seg_dist(inward[0], s, q) for s, q in edges), default=float("inf"))
                if inward
                else float("inf")
            )
            measured = {"beyond": round(over, 3)}
            bad = not lo <= over <= hi
            if gap != float("inf"):
                measured["gap"] = round(gap, 3)
                bad = bad or gap > max_gap
            if bad:
                findings.append(
                    _f(
                        "place_ext_line",
                        d,
                        e.id,
                        f"{e.id} 的尺寸界线超出 {over:.2f}（应约 {beyond:g}）"
                        + (f"，与轮廓间隙 {gap:.2f}" if gap != float("inf") else ""),
                        measured=measured,
                        expected={"beyond": f"{lo:g}..{hi:g}", "gap": f"<= {max_gap:g}"},
                        candidates=[f"调整 {e.id} 的排距，使尺寸界线超出约 {beyond:g}"],
                    )
                )
    seen, uniq = set(), []
    for f in findings:
        if f["id"] not in seen:
            seen.add(f["id"])
            uniq.append(f)
    return uniq, checks


def place_text_direction(d):
    """文字方向 (GB/T 4458.4 / ISO 129-1)."""
    findings, checks = [], 0
    for e in d._els.values():
        info = _box_dim(e)
        if info is None:
            continue
        checks += 1
        want = 0.0 if info["dir"] == "h" else 90.0
        bad = [p for p in info["texts"] if abs((p.rot - want + 180) % 360 - 180) > 1e-6]
        if bad:
            findings.append(
                _f(
                    "place_text_direction",
                    d,
                    e.id,
                    f"{e.id} 的数字方向 {bad[0].rot:g}° 与 "
                    f"{'水平' if want == 0 else '垂直'}尺寸不符",
                    measured={"rot": bad[0].rot, "texts": len(bad)},
                    expected={"rot": want},
                    candidates=[f"把 {e.id} 的文字旋转到 {want:g}°"],
                )
            )
    return findings, checks


def place_text_overlap(d):
    """尺寸数字与其他图元重叠 (GB/T 4458.4 / ISO 129-1)."""
    prims = {}
    for e in d._els.values():
        segs, boxes = [], []
        for p in e._prims:
            if isinstance(p, Hatch):
                continue
            if isinstance(p, Text):
                boxes.append(p.box)
            else:
                segs += prim_segments(p)
        prims[e._id] = (segs, boxes)
    findings, checks = [], 0
    for e in d._els.values():
        info = _dim_info(e)
        if info is None or not info[1]["texts"]:
            continue
        checks += 1
        viol = {}
        for t in info[1]["texts"]:
            box = t.box
            for o, (osegs, oboxes) in prims.items():
                if o == e._id:
                    continue
                for a, b in osegs:
                    ov = _seg_in_box(a, b, box)
                    if ov > 0.05:
                        viol[o] = max(viol.get(o, 0.0), ov)
                for ob in oboxes:
                    ov = _box_overlap(box, ob)
                    if ov > 0.05:
                        viol[o] = max(viol.get(o, 0.0), ov)
        if viol:
            findings.append(
                _f(
                    "place_text_overlap",
                    d,
                    e.id,
                    f"{e.id} 的尺寸数字与 {'、'.join(sorted(viol))} 重叠",
                    measured={"with": sorted(viol), "overlap": round(max(viol.values()), 3)},
                    expected={"overlap": 0.0},
                    candidates=[f"移动 {e.id} 的文字或加大排距"],
                )
            )
    return findings, checks


def place_arrow(d):
    """箭头大小一致 (GB/T 4458.4: 箭头长 >= 6d, 全图一致)."""
    dm = d.std["dim"]
    aw, al = dm["arrow_width"], dm["arrow_length"]
    want_long = math.hypot(al, aw / 2)
    tol = 0.25
    findings, checks = [], 0
    for e in d._els.values():
        if e.kind != "dim":
            continue
        bad = 0
        for p in e._prims:
            if not isinstance(p, Solid):
                continue
            checks += 1
            short, long_ = _arrow_size(p)
            if abs(short - aw) > tol or abs(long_ - want_long) > tol:
                bad += 1
        if bad:
            findings.append(
                _f(
                    "place_arrow",
                    d,
                    e.id,
                    f"{e.id} 有 {bad} 个箭头尺寸与标准档（{al:g}×{aw:g}）不一致",
                    measured={"arrows": bad},
                    expected={"size": f"{al:g}×{aw:g}"},
                    candidates=[f"用标准档箭头重画 {e.id}"],
                )
            )
    return findings, checks


# ---- A.place rules (balloons) -------------------------------------------------------------------


def _balloon_parts(e):
    """(leader, circle) of a balloon element, or None when it has no laid-out prims."""
    if e.kind != "balloon":
        return None
    lines = [p for p in e._prims if isinstance(p, Line)]
    circles = [p for p in e._prims if isinstance(p, Circle)]
    if not lines or not circles:
        return None
    return max(lines, key=lambda p: math.dist(p.p, p.q)), circles[0]


def _balloon_side(d, e, circle):
    bbox = _view_bbox(d, e.view)
    if not bbox:
        return None
    cx, cy = circle.c
    if cx < bbox[0]:
        return "left"
    if cx > bbox[2]:
        return "right"
    if cy > bbox[3]:
        return "top"
    if cy < bbox[1]:
        return "bottom"
    return None


def place_balloon_cross(d):
    """零件序号引线不应相交 (GB/T 4458.2 / ISO 6433)."""
    items = []
    for e in d._els.values():
        parts = _balloon_parts(e)
        if parts is not None:
            items.append((e, parts[0]))
    findings, seen = [], set()
    for i, (e, line) in enumerate(items):
        for j, (other, other_line) in enumerate(items):
            if i >= j:
                continue
            if _crosses(line.p, line.q, other_line.p, other_line.q):
                pt = _intersection(line.p, line.q, other_line.p, other_line.q)
                for me, them in ((e, other), (other, e)):
                    if me.id in seen:
                        continue
                    seen.add(me.id)
                    findings.append(
                        _f(
                            "place_balloon_cross",
                            d,
                            me.id,
                            f"{me.id} 的序号引线与 {them.id} 的引线相交",
                            measured={
                                "with": them.id,
                                "at": [round(pt[0], 2), round(pt[1], 2)],
                            },
                            expected={"crossings": 0},
                            candidates=[f"交换 {me.id} 与 {them.id} 的序号位置"],
                        )
                    )
    return findings, len(items)


def place_balloon_align(d):
    """同一侧序号成列 / 成行 (GB/T 4458.2)."""
    sides = {}
    for e in d._els.values():
        parts = _balloon_parts(e)
        if parts is None:
            continue
        side = _balloon_side(d, e, parts[1])
        if side is None:
            continue
        sides.setdefault(side, []).append((e, parts[1]))
    findings, checks = [], 0
    for side, items in sides.items():
        checks += len(items)
        if len(items) < 2:
            continue
        k = 0 if side in ("left", "right") else 1
        want = sum(p.c[k] for _, p in items) / len(items)
        for e, circle in items:
            if abs(circle.c[k] - want) > 0.5:
                findings.append(
                    _f(
                        "place_balloon_align",
                        d,
                        e.id,
                        f"{e.id} 的序号圆心没有排成{'一列' if k == 0 else '一行'}",
                        measured={"coord": round(circle.c[k], 3), "side": side},
                        expected={"coord": round(want, 3)},
                        candidates=[f"把 {e.id} 对齐到同侧序号轴线"],
                    )
                )
    return findings, checks


def place_balloon_spacing(d):
    """序号圆圈之间留间隙、不重叠 (GB/T 4458.2: 序号排列整齐、不重叠)."""
    sides = {}
    for e in d._els.values():
        parts = _balloon_parts(e)
        if parts is None:
            continue
        side = _balloon_side(d, e, parts[1])
        if side is None:
            continue
        sides.setdefault(side, []).append((e, parts[1]))
    clearance = 1.0
    findings, checks = [], 0
    for side, items in sides.items():
        k = 1 if side in ("left", "right") else 0
        items.sort(key=lambda t: t[1].c[k])
        for (e0, c0), (e1, c1) in zip(items, items[1:]):
            checks += 1
            gap = math.dist(c0.c, c1.c) - c0.r - c1.r
            if gap < clearance - 1e-9:
                findings.append(
                    _f(
                        "place_balloon_spacing",
                        d,
                        e1.id,
                        f"{e1.id} 与 {e0.id} 的序号间距 {gap:.2f} 小于 {clearance:g}",
                        measured={"gap": round(gap, 3), "with": e0.id},
                        expected={"gap": f">= {clearance:g}"},
                        candidates=[f"拉开 {e1.id} 与 {e0.id} 的序号"],
                    )
                )
    return findings, checks


#: every placement rule; checks.run runs them in this order
RULES = (
    place_dim_cross,
    place_dim_outline,
    place_row_spacing,
    place_nesting,
    place_ext_line,
    place_text_direction,
    place_text_overlap,
    place_arrow,
    place_balloon_cross,
    place_balloon_align,
    place_balloon_spacing,
)


def _seg_in_box(p, q, box):
    """Overlap length of the part of segment p-q that lies inside box (0 when outside)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return 0.0
    ux, uy = dx / L, dy / L
    hits = []
    for k in (0, 1):
        if abs((ux, uy)[k]) < 1e-12:
            continue
        for bound in (box[k], box[k + 2]):
            t = (bound - p[k]) / (ux, uy)[k]
            x, y = p[0] + ux * t, p[1] + uy * t
            if box[0] - 1e-9 <= x <= box[2] + 1e-9 and box[1] - 1e-9 <= y <= box[3] + 1e-9:
                hits.append(min(max(t, 0.0), L))
    inside = [
        t
        for t in (0.0, L)
        if box[0] - 1e-9 <= p[0] + ux * t <= box[2] + 1e-9
        and box[1] - 1e-9 <= p[1] + uy * t <= box[3] + 1e-9
    ]
    hits += inside
    return max(0.0, max(hits) - min(hits)) if len(hits) >= 2 else 0.0


def _box_overlap(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)
