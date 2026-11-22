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
    "place_ext_line": "尺寸界线应超出尺寸线约 2 mm，并应从轮廓线、轴线或中心线引出（间隙不超过档值）",
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


#: numeric conventions of the placement metrics; the placement profile may override them
DEFAULTS = {
    "balloon_clearance": 1.0,  # mm between two balloon circles
    "balloon_align_tol": 0.5,  # mm a balloon centre may deviate from its column / row
    "ext_gap_max": 1.5,  # mm the extension line may start away from the contour / axis
    "row_tol": 0.05,  # mm slack on the row pitch (the layout emits exact multiples)
}


def _cfg(d):
    return {**DEFAULTS, **(d.std.get("placement") or {})}


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


def _line_angle(p):
    return math.degrees(math.atan2(p.q[1] - p.p[1], p.q[0] - p.p[0])) % 180.0


def _parallel(a, b, tol_deg=1.0):
    d = abs(_line_angle(a) - _line_angle(b)) % 180.0
    return min(d, 180.0 - d) < tol_deg


def _unit(a, b):
    L = math.dist(a, b)
    return ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-12 else (1.0, 0.0)


def _dot(p, u):
    return p[0] * u[0] + p[1] * u[1]


def _frame_dim(e):
    """A dimension drawn as the frame / bar family: two parallel extension lines plus one
    dimension line (axis-aligned bar or diagonal aligned dimension), or the inside variant with a
    single dimension line between the arrows (DESIGN §4.6 side="inside")."""
    if e.kind != "dim":
        return None
    lines = [p for p in e._prims if isinstance(p, Line)]
    arrows = [p for p in e._prims if isinstance(p, Solid)]
    texts = [p for p in e._prims if isinstance(p, Text)]
    if len(arrows) < 2:
        return None
    if len(lines) == 1:
        dim = lines[0]
        ang = _line_angle(dim)
        direction = "h" if (ang < 1.0 or ang > 179.0) else ("v" if abs(ang - 90.0) < 1.0 else "d")
        return {
            "dir": direction,
            "dim": dim,
            "ext": [],
            "arrows": arrows,
            "texts": texts,
            "lines": [dim],
        }
    if len(lines) < 3:
        return None
    groups = []
    for p in lines:
        for g in groups:
            if _parallel(p, g[0]):
                g.append(p)
                break
        else:
            groups.append([p])
    if len(groups) != 2 or sorted(len(g) for g in groups) != [1, 2]:
        return None
    dim = next(g[0] for g in groups if len(g) == 1)
    ext = next(g for g in groups if len(g) == 2)
    ang = _line_angle(dim)
    if ang < 1.0 or ang > 179.0:
        direction = "h"
    elif abs(ang - 90.0) < 1.0:
        direction = "v"
    else:
        direction = "d"  # aligned dimension: the dimension line is diagonal
    return {
        "dir": direction,
        "dim": dim,
        "ext": ext,
        "arrows": arrows,
        "texts": texts,
        "lines": [dim],
    }


def _box_dim(e):
    """Axis-aligned (bar) dimension of any kind (outside frame or inside single line)."""
    info = _frame_dim(e)
    return info if info is not None and info["dir"] in ("h", "v") else None


def _leader_dim(e):
    """Leader-type dimension (circle diameter/radius, chamfer, groove, hole, spline): its dimension
    geometry is the two leader segments (the shoulder may be collinear for at=0 / 180)."""
    if e.kind != "dim":
        return None
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
        "lines": lines,
    }


def _dim_info(e):
    """(kind, {dir, dim, ext, arrows, texts, lines}) for a dimension element, or None.

    Angle dimensions (their dimension line is an arc) are deliberately not judged: their placement
    follows the angle candidate rules, not the linear ones."""
    if e.kind != "dim":
        return None
    frame = _frame_dim(e)
    if frame is not None:
        return "frame", frame
    leader = _leader_dim(e)
    if leader is not None:
        return "leader", leader
    return None


def _dim_segments(info):
    """The dimension-line segments of a classified dimension (one for a frame, both leader parts)."""
    return info.get("lines") or [info["dim"]]


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


def _frame_axis(info):
    """Canonical (u, n): u is the dimension-line direction with a stable sign, n its normal."""
    u = _unit(info["dim"].p, info["dim"].q)
    if u[0] < -1e-9 or (abs(u[0]) <= 1e-9 and u[1] < 0):
        u = (-u[0], -u[1])
    return u, (-u[1], u[0])


def _frame_rows(info):
    """(u, n, outward, position, interval) of a frame dimension placed outside the outline.

    outward says which side of the measured geometry the dimension line sits on (taken from the
    short "beyond" end of the extension lines), position is the dimension line's normal coordinate
    with the outward sign applied, so two parallel dimension lines' spacing is simply the
    difference of their positions (whatever each dimension measures)."""
    if not info["ext"]:
        return None
    u, n = _frame_axis(info)
    level = _dot(info["dim"].p, n)
    signs = []
    for ext in info["ext"]:
        s = [_dot(pt, n) - level for pt in (ext.p, ext.q)]
        k = 0 if abs(s[0]) < abs(s[1]) else 1
        signs.append(1 if s[k] >= 0 else -1)
    if len(set(signs)) != 1:
        return None  # the extension lines disagree on the side: not a clean row
    outward = signs[0]
    return u, n, outward, outward * level, _frame_interval(info)


def _frame_interval(info):
    """The dimension's extent along its own axis (sheet coordinates)."""
    u = _unit(info["dim"].p, info["dim"].q)
    segs = []
    for line in info["ext"] or [info["dim"]]:
        segs += [line.p, line.q]
    vals = [_dot(pt, u) for pt in segs]
    return min(vals), max(vals)


def _frame_span(info):
    a, b = _frame_interval(info)
    return b - a


def _overlap_1d(a, b):
    return min(a[1], b[1]) - max(a[0], b[0]) > 0.01


def _center_segments(d, view):
    out = []
    for e in d._els.values():
        if e.kind == "center" and e.view == view:
            for p in e._prims:
                out += prim_segments(p)
    return out


def _straight_edge_segments(d, view):
    """Only the straight contour segments of a view (used for leader-type dimensions: a diameter
    leader necessarily crosses the arc it points at, so arcs are not counted there)."""
    out = []
    for e in d._els.values():
        if e.kind != "edge" or e.view != view or e.role not in ("thick", "hidden"):
            continue
        out += [(p.p, p.q) for p in e._prims if isinstance(p, Line)]
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


def _all_edge_segments(d):
    """Every visible / hidden contour segment of the drawing, whatever view it belongs to."""
    out = []
    for e in d._els.values():
        if e.kind != "edge" or e.role not in ("thick", "hidden"):
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


def _hatch_polys(d):
    """Point-in-polygon test helpers for the rendered section lining: [(view, polygon)]."""
    out = []
    for e in d._els.values():
        if e.kind != "hatch":
            continue
        for pr in e._prims:
            if not isinstance(pr, Hatch):
                continue
            for loop in pr.loops:
                if not loop:
                    continue
                if loop[0] == "circle":
                    c, rad = loop[1], loop[2]
                    pts = [
                        (
                            c[0] + rad * math.cos(2 * math.pi * k / 32),
                            c[1] + rad * math.sin(2 * math.pi * k / 32),
                        )
                        for k in range(32)
                    ]
                else:
                    pts = list(loop)
                out.append((pts, e.view))
    return out


def _point_in_poly(pt, poly):
    x, y = pt
    inside = False
    for i in range(len(poly)):
        x0, y0 = poly[i - 1]
        x1, y1 = poly[i]
        if (y0 > y) != (y1 > y):
            xin = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xin:
                inside = not inside
    return inside


def place_dim_cross(d):
    """尺寸线互相交叉 (GB/T 4458.4 / ISO 129-1); bars, aligned dimensions, inside dimensions and
    leaders are judged (an angle dimension's dimension line is an arc and is not judged)."""
    items = [(e, info) for e in d._els.values() if (info := _dim_info(e)) is not None]
    items = [(e, info[1]) for e, info in items]
    findings = []
    for i, (e, info) in enumerate(items):
        for other, oinfo in items[i + 1 :]:
            hit = None
            for a in _dim_segments(info):
                for b in _dim_segments(oinfo):
                    if _crosses(a.p, a.q, b.p, b.q):
                        hit = (a, b)
                        break
                if hit:
                    break
            if hit is None:
                continue
            (a, b) = hit
            pt = _intersection(a.p, a.q, b.p, b.q)
            for me, them in ((e, other), (other, e)):
                findings.append(
                    _f(
                        "place_dim_cross",
                        d,
                        me.id,
                        f"{me.id} 的尺寸线与 {them.id} 的尺寸线相交",
                        measured={"with": them.id, "at": [round(pt[0], 2), round(pt[1], 2)]},
                        expected={"crossings": 0},
                        candidates=[f"移动 {me.id} 的排 / 侧向，避开 {them.id}"],
                    )
                )
    seen, uniq = set(), []
    for f in findings:
        if f["id"] not in seen:
            seen.add(f["id"])
            uniq.append(f)
    return uniq, len(items)


def place_dim_outline(d):
    """尺寸线不应与轮廓线相交 (GB/T 4458.4 / ISO 129-1). Judged on frame dimensions (bar, aligned,
    inside): a leader (引出线) is meant to leave the feature through the contour, so it is governed
    by the leader rules, not by this clause."""
    items = [(e, info[1]) for e in d._els.values() if (info := _dim_info(e)) is not None]
    items = [(e, info) for e, info in items if info["dir"] != "leader"]
    edges = _all_edge_segments(d)
    findings = []
    for e, info in items:
        hit = any(_crosses(seg.p, seg.q, a, b) for seg in _dim_segments(info) for a, b in edges)
        if hit:
            findings.append(
                _f(
                    "place_dim_outline",
                    d,
                    e.id,
                    f"{e.id} 的尺寸线与轮廓线交叉",
                    measured={
                        "line": [
                            [round(seg.p[0], 2), round(seg.p[1], 2)] for seg in _dim_segments(info)
                        ]
                    },
                    expected={"outline_crossings": 0},
                    candidates=[f"移动 {e.id} 到轮廓外，或加大排距"],
                )
            )
    return findings, len(items)


def _side_groups(d):
    """{(view, direction, outward): [(element, info, position)]} for frame dimensions outside the
    outline; parallel dimension lines (axis-aligned or aligned) share one group and are ordered by
    their normal position, so their spacing is the real row spacing."""
    groups = {}
    for e in d._els.values():
        info = _frame_dim(e)
        if info is None:
            continue
        rows = _frame_rows(info)
        if rows is None:
            continue
        u, _n, outward, position, _interval = rows
        key = (e.view, round(math.degrees(math.atan2(u[1], u[0])) % 180.0, 1), outward)
        groups.setdefault(key, []).append((e, info, position))
    for items in groups.values():
        items.sort(key=lambda item: item[2])
    return groups


def place_row_spacing(d):
    """平行尺寸线的间距不小于标准档排距 (all overlapping pairs, not just neighbours)."""
    groups = _side_groups(d)
    pitch = d.std["dim"]["row_pitch"]
    tol = _cfg(d)["row_tol"]
    by_outer = {}
    checks = 0
    for items in groups.values():
        for i, (e0, i0, d0) in enumerate(items):
            for e1, i1, d1 in items[i + 1 :]:
                if not _overlap_1d(_frame_interval(i0), _frame_interval(i1)):
                    continue  # side by side, not stacked: no row pitch requirement
                checks += 1
                gap = d1 - d0
                if gap < pitch - tol:
                    prev = by_outer.get(e1.id)
                    if prev is None or gap < prev[0]:
                        by_outer[e1.id] = (gap, e0.id)
    findings = [
        _f(
            "place_row_spacing",
            d,
            eid,
            f"{eid} 与 {other} 的尺寸线间距 {gap:.2f} 小于排距 {pitch:g}",
            measured={"gap": round(gap, 3), "with": other},
            expected={"gap": f">= {pitch:g}"},
            candidates=[f"外推到下一排：place(row=...)，或移动 {eid}"],
        )
        for eid, (gap, other) in by_outer.items()
    ]
    return findings, checks


def place_nesting(d):
    """小尺寸在内、大尺寸在外 (all overlapping pairs)."""
    groups = _side_groups(d)
    checks = 0
    worst = {}
    for items in groups.values():
        for i, (e0, i0, _d0) in enumerate(items):
            for e1, i1, _d1 in items[i + 1 :]:
                if not _overlap_1d(_frame_interval(i0), _frame_interval(i1)):
                    continue  # side by side, not nested: order does not matter
                checks += 1
                span0, span1 = _frame_span(i0), _frame_span(i1)
                if span0 > span1 + 0.01:  # the inner dimension is the longer one
                    prev = worst.get(e0.id)
                    if prev is None or span0 - span1 > prev[0]:
                        worst[e0.id] = (span0 - span1, e1.id, span0, span1)
    findings = [
        _f(
            "place_nesting",
            d,
            eid,
            f"{eid}（{s0:.1f}）比外侧的 {other}（{s1:.1f}）大，小尺寸应在内",
            measured={
                "inner": eid,
                "inner_span": round(s0, 3),
                "outer": other,
                "outer_span": round(s1, 3),
            },
            expected={"inner_span": "<= outer_span"},
            candidates=[f"交换 {eid} 与 {other} 的排"],
        )
        for eid, (_delta, other, s0, s1) in worst.items()
    ]
    return findings, checks


def place_ext_line(d):
    """尺寸界线超出约 2 mm，且从轮廓线 / 轴线 / 中心线引出（起点离几何不超过档值）。"""
    dm = d.std["dim"]
    cfg = _cfg(d)
    beyond = dm["ext_beyond"]
    lo, hi = beyond - 0.5, beyond + 1.0
    max_gap = cfg["ext_gap_max"]
    findings = []
    checks = 0
    for e in d._els.values():
        info = _frame_dim(e)
        if info is None or not info["ext"]:
            continue
        rows = _frame_rows(info)
        if rows is None:
            continue
        _u, n, outward, position, _interval = rows
        level = outward * position
        edges = _edge_segments(d, e.view) + _center_segments(d, e.view)
        checks += 1  # one check per dimension, however many extension lines it has
        bad = []
        for ext in info["ext"]:
            vals = [(pt, (_dot(pt, n) - level) * outward) for pt in (ext.p, ext.q)]
            far_pt, far = max(vals, key=lambda item: item[1])
            near_pt, near = min(vals, key=lambda item: item[1])
            if far <= 0:  # the extension line does not reach / pass the dimension line
                bad.append({"reaches": False, "beyond": round(far, 3)})
                continue
            gap = min((_seg_dist(near_pt, a, b) for a, b in edges), default=float("inf"))
            item = {"beyond": round(far, 3)}
            failed = not lo <= far <= hi
            if gap == float("inf"):
                failed = True  # the line does not start at / near the geometry at all
                item["gap"] = None
            else:
                item["gap"] = round(gap, 3)
                failed = failed or gap > max_gap
            if failed:
                bad.append(item)
        if bad:
            findings.append(
                _f(
                    "place_ext_line",
                    d,
                    e.id,
                    f"{e.id} 的尺寸界线不合规（超出应约 {beyond:g} mm，"
                    f"起点应落在轮廓 / 轴线 / 中心线上）",
                    measured={"lines": bad},
                    expected={"beyond": f"{lo:g}..{hi:g}", "gap": f"<= {max_gap:g}"},
                    candidates=[f"调整 {e.id} 的排距，使尺寸界线从轮廓外引出"],
                )
            )
    return findings, checks


def place_text_direction(d):
    """文字方向 (GB/T 4458.4 / ISO 129-1)."""
    findings = []
    checks = 0
    for e in d._els.values():
        info = _frame_dim(e)
        if info is None or info["dir"] not in ("h", "v"):
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
    """尺寸数字与其他图元重叠 (GB/T 4458.4 / ISO 129-1); the dimension's own lines, the other
    elements and the rendered section lining are all judged."""
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
    hatches = [
        (polys, eid)
        for eid, polys in (
            (e._id, [poly for poly, _view in _hatch_polys(d)])
            for e in d._els.values()
            if e.kind == "hatch"
        )
    ]
    hatches = []
    for e in d._els.values():
        if e.kind != "hatch":
            continue
        loops = [poly for poly, view in _hatch_polys(d) if view == e.view]
        if loops:
            hatches.append((e._id, loops))  # even-odd over all loops of the hatch
    findings = []
    checks = 0
    for e in d._els.values():
        info = _dim_info(e)
        if info is None or not info[1]["texts"]:
            continue
        checks += 1
        viol = {}
        for t in info[1]["texts"]:
            box = t.box
            center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            for o, (osegs, oboxes) in prims.items():
                if o == e._id:  # own primitives are judged; only the very same box is skipped
                    oboxes = [b for b in oboxes if b != box]
                for a, b in osegs:
                    ov = _seg_in_box(a, b, box)
                    if ov > 0.05:
                        viol[o] = max(viol.get(o, 0.0), ov)
                for ob in oboxes:
                    ov = _box_overlap(box, ob)
                    if ov > 0.05:
                        viol[o] = max(viol.get(o, 0.0), ov)
            for hid, loops in hatches:
                if sum(1 for poly in loops if _point_in_poly(center, poly)) % 2 == 1:
                    viol[hid] = max(viol.get(hid, 1.0), 1.0)
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
    """箭头大小一致 (GB/T 4458.4: 箭头长 >= 6d, 全图一致). One check per dimension element."""
    dm = d.std["dim"]
    aw, al = dm["arrow_width"], dm["arrow_length"]
    want_long = math.hypot(al, aw / 2)
    tol = 0.25
    findings = []
    checks = 0
    for e in d._els.values():
        if e.kind != "dim":
            continue
        arrows = [p for p in e._prims if isinstance(p, Solid)]
        if not arrows:
            continue
        checks += 1
        bad = 0
        for p in arrows:
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
    """同一侧（同一视图）的序号成列 / 成行 (GB/T 4458.2). One check per side group: a group whose
    centres spread out is reported once (two balloons alone cannot tell which one moved)."""
    cfg = _cfg(d)
    tol = cfg["balloon_align_tol"]
    groups = {}
    for e in d._els.values():
        parts = _balloon_parts(e)
        if parts is None:
            continue
        side = _balloon_side(d, e, parts[1])
        if side is None:
            continue
        groups.setdefault((e.view, side), []).append((e, parts[1]))
    findings, checks = [], 0
    for (view, side), items in groups.items():
        checks += 1
        if len(items) < 2:
            continue
        k = 0 if side in ("left", "right") else 1
        coords = [p.c[k] for _, p in items]
        spread = max(coords) - min(coords)
        if spread > tol:
            first = sorted(items, key=lambda t: (t[1].c[k], t[0].id))[0][0]
            findings.append(
                _f(
                    "place_balloon_align",
                    d,
                    first.id,
                    f"{view} {side} 侧的 {len(items)} 个序号没有排成{'一列' if k == 0 else '一行'}"
                    f"（散布 {spread:.2f}）",
                    measured={
                        "view": view,
                        "side": side,
                        "spread": round(spread, 3),
                        "balloons": [e.id for e, _ in items],
                    },
                    expected={"spread": f"<= {tol:g}"},
                    candidates=[f"把 {e.id} 对齐到同侧序号轴线" for e, _ in items],
                )
            )
    return findings, checks


def place_balloon_spacing(d):
    """序号圆圈之间留间隙、不重叠 (GB/T 4458.2); every pair of balloons on the sheet is checked."""
    cfg = _cfg(d)
    clearance = cfg["balloon_clearance"]
    items = []
    for e in d._els.values():
        parts = _balloon_parts(e)
        if parts is not None:
            items.append((e, parts[1]))
    items.sort(key=lambda item: item[0].id)
    findings = []
    checks = 0
    for i, (e0, c0) in enumerate(items):
        for e1, c1 in items[i + 1 :]:
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
