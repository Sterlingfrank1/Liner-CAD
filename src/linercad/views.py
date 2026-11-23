"""Auxiliary views (SPEC M1 §5): removed sections, detail views, oblique views, and wavy lines.

An auxiliary view is a ``View`` named by its letter (``V.B``, ``V.I``) with ``intent.aux`` set;
it is placed freely after the basic views. Its marker in the parent view is ``S.<letter>``.
"""

from __future__ import annotations

import math
import re

from .annotate import LOOK_VEC, SECTION_LOOK, Section, _check_look
from .errors import InvalidArgument, NotFound
from .geometry import View, resolve_point
from .model import Element, check_name, num, parse_scale

ROMAN = re.compile(r"^(?=[IVXL])L?X{0,3}(IX|IV|V?I{0,3})$")


class Mark(Element):
    """Marker of a detail or oblique view drawn in the parent view."""

    kind = "mark"
    READ = ("letter", "type")

    letter = property(lambda s: s._intent["letter"])
    type = property(lambda s: s._intent["type"])


class Wavy(Element):
    """Thin wavy line (local section boundary, break line)."""

    kind = "wavy"
    READ = ("points",)

    points = property(lambda s: [tuple(p) for p in s._intent["points"]])


def _letter(d, letter, roman=False):
    ok = isinstance(letter, str) and (
        re.fullmatch(r"[A-Z]", letter) or (roman and ROMAN.match(letter))
    )
    if not ok:
        raise InvalidArgument(
            "视图字母应为一个大写拉丁字母" + ("或罗马数字（I、II…）" if roman else ""),
            values={"letter": letter},
        )
    for p in ("V", "S"):
        if f"{p}.{letter}" in d._els:
            raise InvalidArgument(f"字母 {letter} 已被 {p}.{letter} 使用", id=f"{p}.{letter}")
    return letter


def _parent(d, parent):
    vid = f"V.{parent}"
    if vid not in d._els:
        raise NotFound(f"视图 {parent} 不存在", id=vid, candidates=[v.id for v in d.views()])
    return d._els[vid]


def removed_section(d, letter, parent, through, look=None):
    letter = _letter(d, letter)
    _parent(d, parent)
    try:
        p1, p2 = through
    except (TypeError, ValueError):
        raise InvalidArgument("移出断面的 through 应为两点 [p1, p2]")
    a = resolve_point(d, p1, view=parent, what="through[0]")
    b = resolve_point(d, p2, view=parent, what="through[1]")
    L = math.dist(a, b)
    if L < 1e-9:
        raise InvalidArgument("through 的两点重合", values={"p": list(a)})
    t = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    if t[1] < -1e-9 or (abs(t[1]) <= 1e-9 and t[0] < 0):
        t = (-t[0], -t[1])
    if look is None:
        look = "left" if abs(t[1]) >= abs(t[0]) else "down"
    elif look not in SECTION_LOOK:
        raise InvalidArgument(f"look 只能是 {SECTION_LOOK}", candidates=list(SECTION_LOOK))
    _check_look(look, a, b)
    lx, ly = LOOK_VEC[look]
    depth = 1 if lx * t[1] - ly * t[0] > 0 else -1
    v = View(
        d,
        f"V.{letter}",
        {
            "name": letter,
            "aux": "section",
            "parent": parent,
            "trace": [list(a), list(b)],
            "axes": {"v": [round(t[0], 12), round(t[1], 12)], "depth": depth},
        },
        refs=[f"V.{parent}"],
    )
    d._add(v)
    intent = {
        "letter": letter,
        "view": letter,
        "cut_in": parent,
        "through": [list(a), list(b)],
        "look": look,
        "kind": "removed",
    }
    d._add(Section(d, f"S.{letter}", intent, refs=[f"V.{letter}", f"V.{parent}"]))
    return v


def detail(d, letter, parent, center, r, scale):
    letter = _letter(d, letter, roman=True)
    _parent(d, parent)
    c = resolve_point(d, center, view=parent, what="center")
    r = num(r, "r")
    if r <= 0:
        raise InvalidArgument("局部放大的半径必须为正", values={"r": r})
    text, k = parse_scale(scale)
    v = View(
        d,
        f"V.{letter}",
        {
            "name": letter,
            "aux": "detail",
            "parent": parent,
            "center": list(c),
            "r": r,
            "scale": k,
            "scale_text": text,
        },
        refs=[f"V.{parent}"],
    )
    d._add(v)
    mark = {
        "letter": letter,
        "type": "detail",
        "view": parent,
        "target": letter,
        "c": list(c),
        "r": r,
    }
    d._add(Mark(d, f"S.{letter}", mark, refs=[f"V.{parent}"]))
    return v


def detail_sources(d, letter):
    """Parent elements that the detail view V.<letter> clipped (semantic back-reference).

    The detail view owns its primitives (SPEC M1 §5), but each clipped primitive remembers the
    parent edge / center line / hatch element it came from, so a selection in the detail view can
    be followed back to the source feature.  Requires the drawing to be laid out."""
    v = d.get(f"V.{letter}")
    if v is None:
        raise NotFound(
            f"视图 V.{letter} 不存在",
            id=f"V.{letter}",
            candidates=[x.id for x in d.views()],
        )
    if v._intent.get("aux") != "detail":
        raise InvalidArgument(
            f"V.{letter} 不是局部放大图",
            id=v.id,
            candidates=[x.id for x in d.views() if x._intent.get("aux") == "detail"],
        )
    if "detail_sources" not in v._intent:
        raise InvalidArgument(
            f"V.{letter} 还没有裁剪结果：query 应在 build/layout 之后使用",
            id=v.id,
            hint="局部放大的源映射在 layout 阶段生成；先在 drawing.py 里 build，再查询",
        )
    out = []
    for rec in v._intent.get("detail_sources", ()):
        el = d._els.get(rec.get("id"))
        if el is not None and el not in out:
            out.append(el)
    return out


def oblique(d, letter, parent, at, look, rotate=False):
    letter = _letter(d, letter)
    _parent(d, parent)
    p = resolve_point(d, at, view=parent, what="at")
    look = num(look, "look")
    v = View(
        d,
        f"V.{letter}",
        {"name": letter, "aux": "oblique", "parent": parent, "look": look, "rotate": bool(rotate)},
        refs=[f"V.{parent}"],
    )
    d._add(v)
    mark = {
        "letter": letter,
        "type": "oblique",
        "view": parent,
        "target": letter,
        "at": list(p),
        "look": look,
    }
    d._add(Mark(d, f"S.{letter}", mark, refs=[f"V.{parent}"]))
    return v


def view_wavy(self, name, points):
    d = self._d
    pts = [resolve_point(d, p, view=self.name) for p in points]
    if len(pts) < 2:
        raise InvalidArgument("波浪线至少两个点", values={"n": len(pts)})
    if name is None:
        name = d._auto_name("W", (self.name,), "wavy")
    wid = f"W.{self.name}.{check_name(name)}"
    return d._add(
        Wavy(d, wid, {"view": self.name, "points": [list(p) for p in pts]}, refs=[self.id])
    )


# ---- geometry helpers used by the layout ---------------------------------------------------------


def wavy_points(base, amp, wavelength):
    """Deterministic wave along a base polyline (sheet mm): offset ± amp along the normal."""
    out = []
    s_tot = 0.0
    step = wavelength / 12
    for (x0, y0), (x1, y1) in zip(base, base[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-9:
            continue
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        n = max(1, int(math.ceil(L / step)))
        for k in range(0 if not out else 1, n + 1):
            t = L * k / n
            w = amp * math.sin(2 * math.pi * (s_tot + t) / wavelength)
            out.append((x0 + ux * t - uy * w, y0 + uy * t + ux * w))
        s_tot += L
    return out


def clip_segment(p, q, c, r):
    """Part of segment pq inside the circle (c, r), or None."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - c[0], p[1] - c[1]
    A = dx * dx + dy * dy
    if A < 1e-18:
        return None
    B = 2 * (fx * dx + fy * dy)
    C = fx * fx + fy * fy - r * r
    disc = B * B - 4 * A * C
    if disc <= 0:
        return None
    sq = math.sqrt(disc)
    t0, t1 = max(0.0, (-B - sq) / (2 * A)), min(1.0, (-B + sq) / (2 * A))
    if t1 - t0 < 1e-9:
        return None
    return (p[0] + dx * t0, p[1] + dy * t0), (p[0] + dx * t1, p[1] + dy * t1)


def clip_arc(cc, rr, a0, a1, c, r):
    """Angle ranges (deg) of the arc (cc, rr, a0→a1 ccw) inside the circle (c, r)."""
    d = math.dist(cc, c)
    sweep = (a1 - a0) % 360 or 360
    if d + rr <= r + 1e-9:
        return [(a0, a0 + sweep)]
    if d >= rr + r or d + r <= rr or d < 1e-12:
        return []
    # angle (about cc) of the direction to c, and half-width of the inside range
    base = math.degrees(math.atan2(c[1] - cc[1], c[0] - cc[0]))
    cosv = (rr * rr + d * d - r * r) / (2 * rr * d)
    half = math.degrees(math.acos(max(-1.0, min(1.0, cosv))))
    lo = base - half
    out = []
    for k in (-1, 0, 1):  # intersect [lo, lo + 2·half] with [a0, a0 + sweep] on the circle
        s0, s1 = lo + 360 * k, lo + 2 * half + 360 * k
        x0, x1 = max(s0, a0), min(s1, a0 + sweep)
        if x1 - x0 > 1e-6:
            out.append((x0, x1))
    return out


def hatch_lines(loops, clip_c, clip_r, spacing, angle):
    """Hatch segments (sheet mm) inside the even-odd region of ``loops`` and the clip circle."""
    polys = []
    for lp in loops:
        if lp and lp[0] == "circle":
            c, r = lp[1], lp[2]
            polys.append(
                [
                    (
                        c[0] + r * math.cos(2 * math.pi * k / 72),
                        c[1] + r * math.sin(2 * math.pi * k / 72),
                    )
                    for k in range(72)
                ]
            )
        else:
            polys.append(list(lp))
    a = math.radians(angle)
    u = (math.cos(a), math.sin(a))
    n = (-u[1], u[0])
    out = []
    k = -int(clip_r / spacing) - 1
    while k * spacing <= clip_r + spacing:
        off = k * spacing
        o = (clip_c[0] + n[0] * off, clip_c[1] + n[1] * off)
        ts = []
        for poly in polys:
            for p, q in zip(poly, poly[1:] + poly[:1]):
                den = u[0] * (q[1] - p[1]) - u[1] * (q[0] - p[0])
                if abs(den) < 1e-12:
                    continue
                w = ((p[0] - o[0]) * (q[1] - p[1]) - (p[1] - o[1]) * (q[0] - p[0])) / den
                s = ((p[0] - o[0]) * u[1] - (p[1] - o[1]) * u[0]) / den
                if 0 <= s < 1:
                    ts.append(w)
        ts.sort()
        for t0, t1 in zip(ts[0::2], ts[1::2]):
            seg = clip_segment(
                (o[0] + u[0] * t0, o[1] + u[1] * t0),
                (o[0] + u[0] * t1, o[1] + u[1] * t1),
                clip_c,
                clip_r,
            )
            if seg:
                out.append(seg)
        k += 1
    return out


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for k in range(n):
        (x1, y1), (x2, y2) = poly[k], poly[(k + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside
