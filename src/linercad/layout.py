"""Annotation layout and view placement (SPEC §5).

Deterministic semantic placement + local push-out + conflict report; no global solver.
Every element ends up with ``_prims`` (sheet coordinates) and ``_resolved`` (incl. ``bbox``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .errors import InvalidArgument
from .text import text_size
from .views import wavy_points

LEADER_TYPES = ("chamfer", "groove", "hole", "spline")

# ---- prims ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    p: tuple
    q: tuple
    layer: str
    ltscale: float = 1.0


@dataclass(frozen=True)
class Circle:
    c: tuple
    r: float
    layer: str
    ltscale: float = 1.0


@dataclass(frozen=True)
class Arc:
    c: tuple
    r: float
    a0: float
    a1: float
    layer: str


@dataclass(frozen=True)
class Text:
    text: str
    at: tuple  # centre of the text box
    height: float  # GB character height
    rot: float  # 0 or 90
    layer: str
    box: tuple  # (x0, y0, x1, y1)
    cjk: bool | None = None  # metric override for mixed-language blocks (technical notes)
    exact_height: bool = False  # imported text keeps the DXF height verbatim
    style: str | None = None
    layer_name: str | None = None
    align: tuple | None = None  # (halign, valign) of the source TEXT / MTEXT
    anchor: tuple | None = None  # sheet-coordinate insertion point of the source entity
    anchor2: tuple | None = None  # second alignment point (ALIGNED / FIT)


@dataclass(frozen=True)
class Solid:
    pts: tuple
    layer: str


@dataclass(frozen=True)
class Hatch:
    loops: tuple  # each: tuple of points, or ("circle", c, r)
    layer: str
    angle: float | None = None  # per-part override (assemblies), else the profile's
    spacing: float | None = None
    solid: bool = False  # imported SOLID fill (no pattern lines)
    pattern: str | None = None  # imported predefined pattern (exact round-trip)
    scale: float | None = None  # imported pattern_scale
    hatch_style: int = 0  # imported DXF hatch_style
    loop_flags: tuple = ()  # imported boundary path flags per loop
    pattern_angle: float | None = None  # source pattern_angle (exact round-trip)


@dataclass(frozen=True)
class Poly:
    pts: tuple  # open polyline (wavy lines)
    layer: str


def _mv(p, dx, dy):
    return (p[0] + dx, p[1] + dy)


def move_prim(pr, dx, dy):

    if isinstance(pr, Line):
        return replace(pr, p=_mv(pr.p, dx, dy), q=_mv(pr.q, dx, dy))
    if isinstance(pr, (Circle, Arc)):
        return replace(pr, c=_mv(pr.c, dx, dy))
    if isinstance(pr, Text):
        b = pr.box
        anchor = _mv(pr.anchor, dx, dy) if pr.anchor is not None else None
        anchor2 = _mv(pr.anchor2, dx, dy) if pr.anchor2 is not None else None
        return replace(
            pr,
            at=_mv(pr.at, dx, dy),
            box=(b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy),
            anchor=anchor,
            anchor2=anchor2,
        )
    if isinstance(pr, (Solid, Poly)):
        return replace(pr, pts=tuple(_mv(p, dx, dy) for p in pr.pts))
    if isinstance(pr, Hatch):
        loops = []
        for lp in pr.loops:
            if lp and lp[0] == "circle":
                loops.append(("circle", _mv(lp[1], dx, dy), lp[2]))
            else:
                loops.append(tuple(_mv(p, dx, dy) for p in lp))
        return replace(pr, loops=tuple(loops))
    raise TypeError(pr)


def _arc_pts(c, r, a0, a1, n=None):
    sweep = (a1 - a0) % 360 or 360
    n = n or max(4, int(math.ceil(sweep / 7.5)))
    return [
        (
            c[0] + r * math.cos(math.radians(a0 + sweep * k / n)),
            c[1] + r * math.sin(math.radians(a0 + sweep * k / n)),
        )
        for k in range(n + 1)
    ]


def prim_segments(pr):
    """Line segments approximating a prim (for collision tests)."""
    if isinstance(pr, Line):
        return [(pr.p, pr.q)]
    if isinstance(pr, Circle):
        pts = _arc_pts(pr.c, pr.r, 0, 360, 48)
        return list(zip(pts, pts[1:]))
    if isinstance(pr, Arc):
        pts = _arc_pts(pr.c, pr.r, pr.a0, pr.a1)
        return list(zip(pts, pts[1:]))
    if isinstance(pr, Solid):
        pts = list(pr.pts) + [pr.pts[0]]
        return list(zip(pts, pts[1:]))
    if isinstance(pr, Poly):
        return list(zip(pr.pts, pr.pts[1:]))
    return []


def prim_bbox(pr):
    if isinstance(pr, Text):
        return pr.box
    if isinstance(pr, Circle):
        return (pr.c[0] - pr.r, pr.c[1] - pr.r, pr.c[0] + pr.r, pr.c[1] + pr.r)
    if isinstance(pr, Hatch):
        pts = []
        for lp in pr.loops:
            if lp and lp[0] == "circle":
                c, r = lp[1], lp[2]
                pts += [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
            else:
                pts += list(lp)
        return _bbox_pts(pts)
    pts = [p for s in prim_segments(pr) for p in s]
    return _bbox_pts(pts)


def _bbox_pts(pts):
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def prims_bbox(prims):
    return union(prim_bbox(p) for p in prims)


# ---- geometry tests --------------------------------------------------------------------------


def inflate(b, d):
    return (b[0] - d, b[1] - d, b[2] + d, b[3] + d)


def box_overlap(a, b):
    """Overlap amount (>0) of two boxes, or 0."""
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return min(dx, dy) if dx > 1e-9 and dy > 1e-9 else 0.0


def seg_in_box(p, q, b):
    """Length of segment pq inside box b (Liang-Barsky)."""
    x0, y0 = p
    dx, dy = q[0] - x0, q[1] - y0
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, x0 - b[0]), (dx, b[2] - x0), (-dy, y0 - b[1]), (dy, b[3] - y0)):
        if abs(pp) < 1e-12:
            if qq < 0:
                return 0.0
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return 0.0
    return (t1 - t0) * math.hypot(dx, dy)


def _crosses(p, q, r, s):
    """Proper intersection of segments pq and rs (touching at an end does not count)."""

    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return o(r, s, p) * o(r, s, q) < -1e-9 and o(p, q, r) * o(p, q, s) < -1e-9


def _cross_point(p, q, r, s):
    """Intersection point of two properly crossing segments, else None."""
    if not _crosses(p, q, r, s):
        return None
    den = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])
    if abs(den) < 1e-12:
        return None
    t = ((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0])) / den
    return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))


def _near_any(pt, spots):
    """Is pt within the radius of one of the (point, radius) spots?"""
    return any(math.dist(pt, c) <= r + 1e-9 for c, r in spots)


def _crosses_circle(p, q, c, r):
    """Proper crossing of segment pq with a circle (tangency / touching an end excluded)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - c[0], p[1] - c[1]
    a = dx * dx + dy * dy
    if a < 1e-18:
        return False
    disc = (fx * dx + fy * dy) ** 2 - a * (fx * fx + fy * fy - r * r)
    if disc <= 1e-9:  # miss or tangency: a tangent line touches, it does not cut
        return False
    root = math.sqrt(disc)
    for t in ((-(fx * dx + fy * dy) - root) / a, (-(fx * dx + fy * dy) + root) / a):
        if 1e-9 < t < 1 - 1e-9:
            return True
    return False


def _on_arc(pt, arc):
    """Is the point strictly inside the arc sweep (touching an end does not count)?"""
    sweep = (arc.a1 - arc.a0) % 360 or 360
    if sweep >= 360 - 1e-9:  # a full circle has no end points
        return True
    ang = math.degrees(math.atan2(pt[1] - arc.c[1], pt[0] - arc.c[0])) % 360
    rel = (ang - arc.a0) % 360
    return 1e-9 < rel < sweep - 1e-9


def _crosses_arc(p, q, arc):
    """Proper crossing of segment pq with an arc (same rule as a circle, plus the sweep)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - arc.c[0], p[1] - arc.c[1]
    a = dx * dx + dy * dy
    if a < 1e-18:
        return False
    disc = (fx * dx + fy * dy) ** 2 - a * (fx * fx + fy * fy - arc.r * arc.r)
    if disc <= 1e-9:
        return False
    root = math.sqrt(disc)
    for t in ((-(fx * dx + fy * dy) - root) / a, (-(fx * dx + fy * dy) + root) / a):
        if 1e-9 < t < 1 - 1e-9:
            pt = (p[0] + t * dx, p[1] + t * dy)
            if _on_arc(pt, arc):
                return True
    return False


def collinear_overlap(a, b):
    """Open-interval overlap length of two collinear segments (0 if not collinear)."""
    (p, q), (r, s) = a, b
    ux, uy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(ux, uy)
    if L < 1e-9:
        return 0.0
    ux, uy = ux / L, uy / L
    for pt in (r, s):
        if abs((pt[0] - p[0]) * uy - (pt[1] - p[1]) * ux) > 0.01:
            return 0.0
    t = sorted(((r[0] - p[0]) * ux + (r[1] - p[1]) * uy, (s[0] - p[0]) * ux + (s[1] - p[1]) * uy))
    ov = min(L, t[1]) - max(0.0, t[0])
    return ov if ov > 1e-6 else 0.0


def arrow(tip, d, std, layer="dim"):
    """Filled arrowhead: tip point, unit direction d (pointing to the tip)."""
    al, aw = std["dim"]["arrow_length"], std["dim"]["arrow_width"]
    bx, by = tip[0] - d[0] * al, tip[1] - d[1] * al
    nx, ny = -d[1] * aw / 2, d[0] * aw / 2
    return Solid((tuple(tip), (bx + nx, by + ny), (bx - nx, by - ny)), layer)


def make_text(
    s,
    at,
    h,
    std,
    rot=0,
    layer="dim",
    cjk=None,
    exact_height=False,
    style=None,
    layer_name=None,
    align=None,
    anchor=None,
    anchor2=None,
):
    w, hh = text_size(s, h, std, cjk)
    if abs(rot % 180 - 90) < 1e-9:
        box = (at[0] - hh / 2, at[1] - w / 2, at[0] + hh / 2, at[1] + w / 2)
    elif abs(rot % 180) < 1e-9:
        box = (at[0] - w / 2, at[1] - hh / 2, at[0] + w / 2, at[1] + hh / 2)
    else:  # axis-aligned box of the rotated text rectangle
        c, s_ = abs(math.cos(math.radians(rot))), abs(math.sin(math.radians(rot)))
        bw, bh = (w * c + hh * s_) / 2, (w * s_ + hh * c) / 2
        box = (at[0] - bw, at[1] - bh, at[0] + bw, at[1] + bh)
    return Text(
        s,
        tuple(at),
        h,
        rot,
        layer,
        box,
        cjk,
        exact_height,
        style,
        layer_name,
        align,
        anchor,
        anchor2,
    )


def center_piece(a, b, std):
    """A centre-line piece from a to b whose linetype scale makes it start and end on a long dash
    (k whole periods + one long dash; a piece shorter than a dash is one dash)."""
    pat = std["linetypes"]["LC_CENTER"]["pattern"]
    period = sum(abs(x) for x in pat)
    dash = pat[0]
    L = math.dist(a, b)
    if L < 1e-9:
        return None
    if L <= dash:
        lts = L / dash
    else:
        k = max(0, round((L - dash) / period))
        lts = L / (k * period + dash)
    return Line(tuple(a), tuple(b), "center", lts)


# ---- the engine --------------------------------------------------------------------------------

SIDE_ORDER = ("top", "bottom", "left", "right", "inside")
# Candidate directions for a diameter / radius leader, preferred drafting directions first.  The
# extra directions are only picked when they avoid a crossing the preferred ones cannot (§4.6:
# try candidate angles in order, keep the first clean one).
DIA_ANGLES = (45, 135, 315, 225, 30, 150, 60, 120)
DIA_ANGLES_MORE = (0, 90, 180, 270, 15, 75, 105, 165, 195, 210, 240, 255, 285, 300, 330, 345)
NOTE_ANGLES = (45, 135, 315, 225, 60, 120, 300, 240)
LEADS = (3.0, 8.0, 13.0, 18.0, 25.0, 35.0)  # extra leader lengths tried, shortest first
ORDER = ("front", "top", "bottom", "left", "right", "rear")


class _Obstacles:
    def __init__(self):
        self.segs = []  # (owner, p, q)
        self.boxes = []  # (owner, box)
        self.dimlines = []  # (owner, p, q)
        self.ann = set()  # owners that are annotations (their lines must not be crossed by leaders)
        self.prims = {}  # owner id -> prims (concentric circles, contour tests)
        self.kinds = {}  # owner id -> element kind
        self.centres = {}  # circular dimension id -> centre of its circle
        self.radial = set()  # ids of circular diameter / radius dimensions

    def add(self, owner, segs=(), boxes=(), dimlines=()):
        self.segs += [(owner, p, q) for p, q in segs]
        self.boxes += [(owner, b) for b in boxes]
        self.dimlines += [(owner, p, q) for p, q in dimlines]

    def add_prims(self, owner, prims):
        self.prims.setdefault(owner, []).extend(prims)
        for pr in prims:
            if isinstance(pr, Text):
                self.boxes.append((owner, pr.box))
            elif not isinstance(pr, Hatch):
                self.segs += [(owner, p, q) for p, q in prim_segments(pr)]

    def conflicts(self, owner, cand, clearance):
        """[(other_id, amount)] for a candidate {boxes, segs, dimline}."""
        out = {}
        for b in cand.get("boxes", ()):
            bb = inflate(b, clearance)
            for o, p, q in self.segs:
                if o != owner:
                    v = seg_in_box(p, q, bb)
                    if v > 1e-6:
                        out[o] = max(out.get(o, 0), v)
            for o, ob in self.boxes:
                if o != owner:
                    v = box_overlap(bb, ob)
                    if v > 0:
                        out[o] = max(out.get(o, 0), v)
        for p, q in cand.get("segs", ()):
            for o, ob in self.boxes:
                if o != owner:
                    v = seg_in_box(p, q, ob)
                    if v > 1e-6:
                        out[o] = max(out.get(o, 0), v)
        dl = cand.get("dimline")
        if dl:
            for o, p, q in self.dimlines:
                if o != owner:
                    v = collinear_overlap(dl, (p, q))
                    if v > 0:
                        out[o] = max(out.get(o, 0), v)
        return sorted(out.items())

    def crossings(self, owner, cand):
        """Annotation owners a candidate's leader cuts through (a soft cost after overlaps).

        A crossing at a spot listed in ``cross_ignore`` is inherent only when the other
        annotation is itself a dimension about the same centre (concentric diameters all run
        through it); any other line crossing there is still avoidable.
        """
        allow = set(cand.get("allow_cross", ()))
        ignore = cand.get("cross_ignore", ())
        hit = set()
        for p, q in cand.get("cross", ()):
            for o, a, b in self.segs:
                if o == owner or o not in self.ann or o in allow:
                    continue
                pt = _cross_point(p, q, a, b)
                if pt is None:
                    continue
                if _near_any(pt, ignore) and self._same_centre(o, ignore):
                    continue
                hit.add(o)
        return sorted(hit)

    def overlaps(self, owner, cand):
        """Owners a candidate's line runs along / on top of (GB/T 4458.4: 尺寸线不与其他图线重合)."""
        allow = set(cand.get("allow_cross", ()))
        hit = set()
        for p, q in cand.get("cross", ()):
            for o, a, b in self.segs:
                if o == owner or o in allow:
                    continue
                if collinear_overlap((p, q), (a, b)) > 0.5:
                    hit.add(o)
        return sorted(hit)

    def contour_crossings(self, owner, cand):
        """Outline a candidate's leader cuts.

        A circle concentric with the dimensioned one is crossed by the diametral line itself
        whatever its direction, so cutting it is inherent and never counts as avoidable.
        """
        allow = set(cand.get("allow_cross", ()))
        centre = cand.get("cross_centre")
        hit = set()
        for o, prims in self.prims.items():
            if o == owner or o in allow or self.kinds.get(o) != "edge":
                continue
            if centre is not None and self._concentric_with(o, centre):
                continue
            for p, q in cand.get("cross", ()):
                if self._cuts(o, prims, p, q):
                    hit.add(o)
                    break
        return sorted(hit)

    @staticmethod
    def _cuts(owner, prims, p, q):
        """Does segment pq properly cut any of the owner's lines / circles / arcs?"""
        for pr in prims:
            if isinstance(pr, Line):
                if _cross_point(p, q, pr.p, pr.q) is not None:
                    return True
            elif isinstance(pr, Circle):
                if _crosses_circle(p, q, pr.c, pr.r):
                    return True
            elif isinstance(pr, Arc):
                if _crosses_arc(p, q, pr):
                    return True
            else:
                for a, b in prim_segments(pr):
                    if _cross_point(p, q, a, b) is not None:
                        return True
        return False

    def _same_centre(self, owner, ignore):
        """Is ``owner`` a circular dimension about the same centre (concentric diameters)?"""
        if owner not in self.radial:
            return False
        c = self.centres.get(owner)
        return c is not None and any(math.dist(c, p) <= r + 1e-9 for p, r in ignore)

    def _concentric_with(self, owner, centre):
        prims = self.prims.get(owner, ())
        return bool(prims) and all(
            isinstance(pr, (Circle, Arc)) and math.dist(pr.c, centre) < 1e-6 for pr in prims
        )


class _ViewLayout:
    def __init__(self, L, view):
        self.L, self.d, self.std, self.s = L, L.d, L.std, view.scale
        self.view = view
        self.name = view.name
        self.parts: dict[str, list] = {}
        self.obst = _Obstacles()
        self.G = None

    def P(self, p):
        return (p[0] * self.s, p[1] * self.s)

    def els(self, kind):
        return [
            e for e in self.d._els.values() if e.kind == kind and e._intent.get("view") == self.name
        ]

    def put(self, el, prims, obstacle=True):
        self.parts.setdefault(el._id, []).extend(prims)
        if obstacle:
            self.obst.kinds[el._id] = el.kind
            self.obst.add_prims(el._id, prims)

    # -- geometry ------------------------------------------------------------------------------
    def geometry(self):
        boxes = []
        for e in self.els("edge"):
            i = e._intent
            if i["shape"] == "line":
                pr = Line(self.P(i["p1"]), self.P(i["p2"]), i["role"])
            elif i["shape"] == "circle":
                pr = Circle(self.P(i["c"]), i["r"] * self.s, i["role"])
            else:
                pr = Arc(self.P(i["c"]), i["r"] * self.s, i["start"], i["end"], i["role"])
            self.put(e, [pr])
            boxes.append(prim_bbox(pr))
        self._raw_curves(boxes)
        self.G = union(boxes) or (0.0, 0.0, 0.0, 0.0)
        ext = self.std["center"]["extend"]
        for e in self.els("center"):
            i = e._intent
            prims = []
            if i["type"] == "line":
                a, b = self.P(i["p1"]), self.P(i["p2"])
                L = math.dist(a, b)
                if L < 1e-9:
                    continue
                u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
                a = (a[0] - u[0] * ext, a[1] - u[1] * ext)
                b = (b[0] + u[0] * ext, b[1] + u[1] * ext)
                if i.get(
                    "split"
                ):  # crosses another centre line at its middle: two pieces from there
                    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                    prims = [center_piece(m, a, self.std), center_piece(m, b, self.std)]
                else:
                    prims = [center_piece(a, b, self.std)]
            elif i["type"] == "mark":
                c, h = self.P(i["c"]), i["r"] * self.s + ext
                # four pieces from the centre outwards: the crossing falls on long dashes
                prims = [
                    center_piece(c, (c[0] + dx * h, c[1] + dy * h), self.std)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                ]
            else:
                c, r = self.P(i["c"]), i["r"] * self.s
                pat = self.std["linetypes"]["LC_CENTER"]["pattern"]
                period = sum(abs(x) for x in pat)
                C = 2 * math.pi * r
                k = max(1, round(C / period))
                prims = [Circle(c, r, "center", C / (k * period))]
            self.put(e, [p for p in prims if p is not None])
        for e in self.els("hatch"):
            loops = []
            loop_flags = []
            for lp in e._intent["loops"]:
                if isinstance(lp, dict) and "points" in lp:
                    loop_flags.append(int(lp.get("flags", 1)))
                    loops.append(tuple(self.P(p) for p in lp["points"]))
                    continue
                ref = self.d._els.get(lp["ref"])
                if ref is None:
                    raise InvalidArgument(f"{e.id} 的边界 {lp['ref']} 不存在", id=e.id)
                if ref.kind == "edge":
                    loops.append(("circle", self.P(ref._intent["c"]), ref._intent["r"] * self.s))
                else:
                    lpts = ref.loop()
                    if lpts[0] == "circle":
                        loops.append(("circle", self.P(lpts[1]), lpts[2] * self.s))
                    else:
                        loops.append(tuple(self.P(p) for p in lpts))
            it = e._intent
            hs = self.std["hatch"]
            imported = it.get("pattern") is not None
            spacing = it.get("spacing")
            if imported and spacing is None:
                spacing = hs["spacing"] * float(it.get("scale") or 1.0)
            render_angle = it.get("angle")
            if imported and render_angle is not None:
                render_angle = float(render_angle) + float(hs["angle"])  # ANSI31 base 45°
            hp = Hatch(
                tuple(loops),
                "hatch",
                render_angle,
                spacing,
                solid=bool(it.get("solid")),
                pattern=it.get("pattern"),
                scale=it.get("scale"),
                hatch_style=int(it.get("hatch_style", 0) or 0),
                loop_flags=tuple(loop_flags),
                pattern_angle=it.get("pattern_angle"),
            )
            self.put(e, [hp], obstacle=False)
            if e._intent.get("outline"):
                ol = []
                for lp in loops:
                    if lp and lp[0] == "circle":
                        ol.append(Circle(lp[1], lp[2], e._intent["outline"]))
                    else:
                        ol += [
                            Line(a, b, e._intent["outline"]) for a, b in zip(lp, lp[1:] + lp[:1])
                        ]
                self.put(e, ol)
        wv = self.std["wavy"]
        for e in self.els("wavy"):
            pts = wavy_points(
                [self.P(p) for p in e._intent["points"]], wv["amplitude"], wv["wavelength"]
            )
            self.put(e, [Poly(tuple(pts), "thin")])
        if self.view.aux == "detail":
            self.detail_geometry()

    def _raw_curves(self, boxes):
        """Imported SPLINE / ELLIPSE: the DXF writer places the real entity; the flattened curve is
        what the Viewer draws and what dimensions keep clear of."""
        from .importdxf import raw_polylines

        for e in self.els("raw"):
            if "data" not in e._intent:
                continue
            role = e._intent.get("role", "thick")
            prims = [
                Poly(tuple(self.P(p) for p in pl), role)
                for pl in raw_polylines(e._intent)
                if len(pl) > 1
            ]
            if prims:
                self.put(e, prims)
                boxes.extend(prim_bbox(p) for p in prims)

    # -- detail views: parent geometry clipped to the circle, at this view's scale ---------------
    def detail_geometry(self):
        from .views import clip_arc, clip_segment, hatch_lines, point_in_poly

        i = self.view._intent
        par = i["parent"]
        c, r = tuple(i["center"]), i["r"]
        S = self.s
        prims = []
        ext = self.std["center"]["extend"] / S

        def P(p):
            return (p[0] * S, p[1] * S)

        src = [e for e in self.d._els.values() if e._intent.get("view") == par]
        for e in src:
            it = e._intent
            if e.kind == "edge":
                if it["shape"] == "line":
                    seg = clip_segment(it["p1"], it["p2"], c, r)
                    if seg:
                        prims.append(Line(P(seg[0]), P(seg[1]), it["role"]))
                else:
                    a0, a1 = (0, 360) if it["shape"] == "circle" else (it["start"], it["end"])
                    for b0, b1 in clip_arc(it["c"], it["r"], a0, a1, c, r):
                        if b1 - b0 >= 360 - 1e-6:
                            prims.append(Circle(P(it["c"]), it["r"] * S, it["role"]))
                        else:
                            prims.append(
                                Arc(P(it["c"]), it["r"] * S, b0 % 360, b1 % 360, it["role"])
                            )
            elif e.kind == "center" and it["type"] == "line":
                a, b = it["p1"], it["p2"]
                L = math.dist(a, b)
                if L > 1e-9:
                    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
                    a = (a[0] - u[0] * ext, a[1] - u[1] * ext)
                    b = (b[0] + u[0] * ext, b[1] + u[1] * ext)
                    seg = clip_segment(a, b, c, r)
                    if seg:
                        pc = center_piece(P(seg[0]), P(seg[1]), self.std)
                        if pc:
                            prims.append(pc)
            elif e.kind == "hatch":
                loops = []
                for lp in it["loops"]:
                    if "points" in lp:
                        loops.append([P(p) for p in lp["points"]])
                    else:
                        ref = self.d._els.get(lp["ref"])
                        lpts = ref.loop() if ref is not None and ref.kind == "feature" else None
                        if ref is not None and ref.kind == "edge":
                            lpts = ("circle", ref._intent["c"], ref._intent["r"])
                        if lpts and lpts[0] == "circle":
                            loops.append(("circle", P(lpts[1]), lpts[2] * S))
                        elif lpts:
                            loops.append([P(p) for p in lpts])
                hs = self.std["hatch"]
                for a, b in hatch_lines(loops, P(c), r * S, hs["spacing"], hs["angle"]):
                    prims.append(Line(a, b, "hatch"))
        # wavy boundary where the circle runs through material (GB/T 4458.1)
        regions = self._material(src)
        n = 96
        inside = [
            any(
                fn(
                    (
                        c[0] + r * math.cos(2 * math.pi * k / n),
                        c[1] + r * math.sin(2 * math.pi * k / n),
                    )
                )
                for fn in regions
            )
            for k in range(n)
        ]
        if any(inside):
            start = next((k for k in range(n) if not inside[k]), None)
            runs, cur = [], []
            order = range(n + 1) if start is None else [start + k for k in range(n + 1)]
            for k in order:  # unwrapped indices, so a run crossing angle 0 stays increasing
                if inside[k % n]:
                    cur.append(k)
                elif cur:
                    runs.append(cur)
                    cur = []
            if cur:
                runs.append(cur)
            wv = self.std["wavy"]
            for run in runs:
                k0, k1 = run[0] - 0.5, run[-1] + 0.5
                m = max(2, int((k1 - k0) * 4))
                base = [
                    P(
                        (
                            c[0] + r * math.cos(2 * math.pi * (k0 + (k1 - k0) * j / m) / n),
                            c[1] + r * math.sin(2 * math.pi * (k0 + (k1 - k0) * j / m) / n),
                        )
                    )
                    for j in range(m + 1)
                ]
                prims.append(
                    Poly(tuple(wavy_points(base, wv["amplitude"], wv["wavelength"])), "thin")
                )
        self.put(self.view, prims)
        box = prims_bbox(prims) if prims else None
        self.G = box or (c[0] * S - r * S, c[1] * S - r * S, c[0] * S + r * S, c[1] * S + r * S)
        _ = point_in_poly  # material tests use it below

    def _material(self, src):
        """Point-in-material tests (model coords) from the parent's hatches, closed features and
        turned outlines."""
        from .views import point_in_poly

        tests = []
        for e in src:
            it = e._intent
            if e.kind == "hatch":
                polys = [[tuple(p) for p in lp["points"]] for lp in it["loops"] if "points" in lp]
                if polys:
                    tests.append(
                        lambda q, polys=polys: sum(point_in_poly(q, pl) for pl in polys) % 2 == 1
                    )
            elif e.kind == "feature" and it.get("type") == "turned":
                prof, ax = [tuple(p) for p in it["profile"]], it["axis"]
                outline = [(x, ax + r) for x, r in prof] + [(x, ax - r) for x, r in reversed(prof)]
                bore = it.get("bore")
                cut = it.get("cut")
                if bore and cut:
                    continue  # section regions come from the hatch
                tests.append(lambda q, outline=outline: point_in_poly(q, outline))
            elif e.kind == "feature" and it.get("closed") and it.get("points"):
                pl = [tuple(p) for p in it["points"]]
                tests.append(lambda q, pl=pl: point_in_poly(q, pl))
        return tests

    # -- section symbols (in the cut view) ----------------------------------------------------
    def section_symbols(self):
        sec = self.std["section"]
        lh = sec["letter_height"]
        gap, sl, al = sec["stroke_gap"], sec["stroke_length"], sec["arrow_length"]
        for e in self.d._els.values():
            if e.kind == "mark" and e._intent["view"] == self.name:
                self.marker(e)
                continue
            if e.kind != "section" or e._intent["cut_in"] != self.name:
                continue
            i = e._intent
            pts = [self.P(p) for p in i["through"]]
            look = {"left": (-1, 0), "right": (1, 0), "up": (0, 1), "down": (0, -1)}[i["look"]]
            prims = []

            def unit(a, b):
                L = math.dist(a, b)
                return ((b[0] - a[0]) / L, (b[1] - a[1]) / L)

            def letter_at(at, prims=prims, i=i):
                prims.append(make_text(i["letter"], at, lh, self.std, layer="text"))

            ends = []
            a, b = pts[0], pts[1]
            u = unit(a, b)
            t0, _ = _clip_line(a, u, self.G)
            ends.append((a, u, (t0 if t0 is not None else 0.0), -1))
            a, b = pts[-2], pts[-1]
            u = unit(a, b)
            _, t1 = _clip_line(a, u, self.G)
            ends.append((a, u, (t1 if t1 is not None else math.dist(a, b)), 1))
            for a, u, t_in, sgn in ends:
                n = (-u[1], u[0])
                if n[0] * look[0] + n[1] * look[1] < 0:
                    n = (-n[0], -n[1])
                s0 = t_in + sgn * gap
                s1 = s0 + sgn * sl
                p0 = (a[0] + u[0] * s0, a[1] + u[1] * s0)
                p1 = (a[0] + u[0] * s1, a[1] + u[1] * s1)
                prims.append(Line(p0, p1, "section"))
                tip = (p1[0] + n[0] * al, p1[1] + n[1] * al)
                prims.append(Line(p1, tip, "thin"))
                prims.append(arrow(tip, n, self.std, "thin"))
                w, hh = text_size(i["letter"], lh, self.std)
                off = max(w, hh) / 2 + 1.5
                letter_at(
                    (
                        p1[0] + n[0] * al / 2 + u[0] * sgn * off,
                        p1[1] + n[1] * al / 2 + u[1] * sgn * off,
                    )
                )
            arm = sl / 2
            for k in range(1, len(pts) - 1):  # bends: an L of two short strokes + the letter
                v = pts[k]
                w1, w2 = unit(v, pts[k - 1]), unit(v, pts[k + 1])
                prims.append(Line(v, (v[0] + w1[0] * arm, v[1] + w1[1] * arm), "section"))
                prims.append(Line(v, (v[0] + w2[0] * arm, v[1] + w2[1] * arm), "section"))
                bx, by = -(w1[0] + w2[0]), -(w1[1] + w2[1])
                bl = math.hypot(bx, by) or 1.0
                w, hh = text_size(i["letter"], lh, self.std)
                off = max(w, hh) / 2 + 1.5
                letter_at((v[0] + bx / bl * off, v[1] + by / bl * off))
            self.put(e, prims)

    def marker(self, e):
        """Detail circle + letter, or oblique-view arrow + letter, in the parent view."""
        i = e._intent
        sec = self.std["section"]
        lh = sec["letter_height"]
        prims = []
        if i["type"] == "detail":
            c, r = self.P(i["c"]), i["r"] * self.s
            prims.append(Circle(c, r, "thin"))
            u = (math.cos(math.radians(45)), math.sin(math.radians(45)))
            p = (c[0] + u[0] * r, c[1] + u[1] * r)
            q = (p[0] + u[0] * 6, p[1] + u[1] * 6)
            prims.append(Line(p, q, "thin"))
            w, hh = text_size(i["letter"], lh, self.std)
            prims.append(
                make_text(
                    i["letter"], (q[0] + w / 2 + 1, q[1] + hh / 2), lh, self.std, layer="text"
                )
            )
        else:
            tip = self.P(i["at"])
            u = (math.cos(math.radians(i["look"])), math.sin(math.radians(i["look"])))
            tail = (
                tip[0] - u[0] * (sec["arrow_length"] + 6),
                tip[1] - u[1] * (sec["arrow_length"] + 6),
            )
            prims += [Line(tail, tip, "thin"), arrow(tip, u, self.std, "thin")]
            w, hh = text_size(i["letter"], lh, self.std)
            n = (-u[1], u[0])
            off = max(w, hh) / 2 + 1.5
            prims.append(
                make_text(
                    i["letter"],
                    (tail[0] + n[0] * off, tail[1] + n[1] * off),
                    lh,
                    self.std,
                    layer="text",
                )
            )
        self.put(e, prims)

    # -- dimensions -------------------------------------------------------------------------------
    def _side_for(self, a, b, dir):
        G = self.G
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        cx, cy = (G[0] + G[2]) / 2, (G[1] + G[3]) / 2
        if dir == "h":
            return "top" if my > cy + 1e-9 else "bottom"
        return "right" if mx > cx + 1e-9 else "left"

    def linear_cands(self, el):
        i, lay = el._intent, el._layout
        std, dm = self.std, self.std["dim"]
        a, b = self.P(i["p1"]), self.P(i["p2"])
        dir = i["dir"]
        side = lay.get("side") or self._side_for(a, b, dir)
        off = lay.get("offset") or 0.0
        rows = (
            [None]
            if side == "inside"
            else ([lay["row"]] if lay.get("row") else range(1, int(dm["max_rows"]) + 1))
        )
        w, hh = label_size(i, std)
        al, gap = dm["arrow_length"], 1.0
        out = []
        for row in rows:
            # work in a frame where the dimension line is horizontal: along = x (h) or y (v)
            if dir == "h":
                lo, hi = sorted((a[0], b[0]))
            else:
                lo, hi = sorted((a[1], b[1]))
            if side == "inside":
                level = (a[1] if dir == "h" else a[0]) + off
                ext_pts = []
            else:
                dist = dm["first_row"] + (row - 1) * dm["row_pitch"] + off
                G = self.G
                level = {
                    "top": G[3] + dist,
                    "bottom": G[1] - dist,
                    "right": G[2] + dist,
                    "left": G[0] - dist,
                }[side]
                ext_pts = [a, b]
            span = hi - lo
            fits = span >= w + 2 * al + 2 * gap
            positions = []
            if fits:
                # inside an outline the axis centre line runs through the middle: start above it,
                # then as close to the upper arrow as fits
                cs = [lo + span * f for f in (0.75, 0.25, 0.5)] if side == "inside" else []
                cs[1:1] = [hi - al - gap - w / 2, lo + al + gap + w / 2] if cs else []
                if not cs:
                    cs = [lo + span * f for f in (0.5, 0.75, 0.25)]
                for c in cs:
                    if c - w / 2 >= lo + al + gap - 1e-9 and c + w / 2 <= hi - al - gap + 1e-9:
                        positions.append(("in", c))
            positions += [("out_hi", hi + al + 2 + w / 2), ("out_lo", lo - al - 2 - w / 2)]
            for pos, c in positions:
                out.append(
                    self._linear_geom(
                        el, dir, side, row, off, level, lo, hi, ext_pts, pos, c, w, hh
                    )
                )
        return out

    def _linear_geom(self, el, dir, side, row, off, level, lo, hi, ext_pts, pos, c, w, hh):
        dm = self.std["dim"]
        al = dm["arrow_length"]

        def pt(along, across):
            return (along, across) if dir == "h" else (across, along)

        prims, segs = [], []
        sgn = {"top": 1, "right": 1, "bottom": -1, "left": -1}.get(side, 0)
        for p in ext_pts:
            along, across = (p[0], p[1]) if dir == "h" else (p[1], p[0])
            start = across + sgn * dm["ext_gap"]
            end = level + sgn * dm["ext_beyond"]
            if abs(end - start) > 1e-6:
                ln = Line(pt(along, start), pt(along, end), "dim")
                prims.append(ln)
                segs.append((ln.p, ln.q))
        d_hi = (1, 0) if dir == "h" else (0, 1)
        d_lo = (-d_hi[0], -d_hi[1])
        if pos == "in":
            line = (pt(lo, level), pt(hi, level))
            prims += [
                Line(*line, "dim"),
                arrow(pt(lo, level), d_lo, self.std),
                arrow(pt(hi, level), d_hi, self.std),
            ]
        else:
            x0, x1 = lo - al - 2, hi + al + 2
            if pos == "out_hi":
                x1 = c + w / 2
            else:
                x0 = c - w / 2
            line = (pt(x0, level), pt(x1, level))
            prims += [
                Line(*line, "dim"),
                arrow(pt(lo, level), d_hi, self.std),
                arrow(pt(hi, level), d_lo, self.std),
            ]
        segs.append(line)
        tg = dm["text_gap"]
        if dir == "h":
            tp, tbox = dim_label(el._intent, (c, level + tg + hh / 2), self.std)
        else:
            tp, tbox = dim_label(el._intent, (level - tg - hh / 2, c), self.std, 90)
        prims += tp
        fields = {"side": side, "row": row, "offset": off}
        why = {"in": "", "out_hi": "文字放不下，移到界线外", "out_lo": "文字放不下，移到界线外"}[
            pos
        ]
        if pos == "in" and abs(c - (lo + hi) / 2) > 1e-6:
            why = "文字避让，沿尺寸线移位"
        return {
            "prims": prims,
            "boxes": [tbox],
            "segs": segs,
            "dimline": line,
            "ends": [pt(lo, level), pt(hi, level)],
            "fields": fields,
            "why": why,
        }

    def circle_cands(self, el):
        i, lay = el._intent, el._layout
        std, dm = self.std, self.std["dim"]
        circ = self.d._els.get(i["circle"])
        src = circ._intent if circ is not None else i  # follow the circle if it moved
        c, r = self.P(src["c"]), src["r"] * self.s
        w, hh = label_size(i, std)
        al = dm["arrow_length"]
        if lay.get("at") is not None:  # written angle: only the leader length may adapt
            primary, extra = [lay["at"]], []
        else:
            primary = list(DIA_ANGLES)
            extra = [a for a in DIA_ANGLES_MORE if a not in DIA_ANGLES]
        circ = self.d._els.get(i["circle"])
        if lay.get("at") is None and circ is not None and circ._intent.get("shape") == "arc":
            a0, a1 = circ._intent["start"], circ._intent["end"]
            sweep = (a1 - a0) % 360 or 360
            inside = [a for a in primary if (a - a0) % 360 <= sweep]
            primary = inside or [a0 + sweep / 2]
            extra = [a for a in extra if (a - a0) % 360 <= sweep]
        # customary directions first: the extra angles are only reached when none of them can be
        # placed cleanly (they exist to dodge a crossing, not to restyle an already clean drawing)
        combos = [(lead, a) for lead in LEADS for a in primary]
        combos += [(lead, a) for lead in LEADS for a in extra]
        out = []
        for lead, ang in combos:
            lead = al + lead
            u = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
            p1 = (c[0] + u[0] * r, c[1] + u[1] * r)
            p2 = (c[0] - u[0] * r, c[1] - u[1] * r)
            e = (p1[0] + u[0] * lead, p1[1] + u[1] * lead)
            sg = 1 if u[0] >= -1e-9 else -1
            sh = (e[0] + sg * (w + 2), e[1])
            prims, segs = [], []
            if i["type"] == "dia":
                if 2 * r >= 2 * al + 1:
                    prims += [Line(p2, e, "dim"), arrow(p1, u, std), arrow(p2, (-u[0], -u[1]), std)]
                    segs.append((p2, e))
                else:
                    prims += [Line(p1, e, "dim"), arrow(p1, (-u[0], -u[1]), std)]
                    segs.append((p1, e))
            else:
                if r >= al + 1:
                    prims += [Line(c, e, "dim"), arrow(p1, u, std)]
                    segs.append((c, e))
                else:
                    prims += [Line(p1, e, "dim"), arrow(p1, (-u[0], -u[1]), std)]
                    segs.append((p1, e))
            prims.append(Line(e, sh, "dim"))
            segs.append((e, sh))
            tp, tbox = dim_label(i, (e[0] + sg * (1 + w / 2), e[1] + dm["text_gap"] + hh / 2), std)
            prims += tp
            why = "引线加长以避开轮廓" if lead > al + LEADS[0] else ""
            out.append(
                {
                    "prims": prims,
                    "boxes": [tbox],
                    "segs": segs,
                    # a circumference dimension may cut prints of its own circle and, where
                    # concentric diameters meet, the shared centre; nothing else is inherent
                    "cross": segs,
                    "allow_cross": (i["circle"],),
                    "cross_ignore": ((c, 0.5),),
                    "cross_centre": c,
                    "contour": True,
                    "overlap_cost": True,
                    "fields": {"at": ang},
                    "ends": [p2, p1],
                    "why": why,
                }
            )
        return out

    def note_cands(self, el):
        i, lay = el._intent, el._layout
        std, nt = self.std, self.std["note"]
        A = self.P(i["anchor"])
        base_len = nt["leader_length"]
        lengths = (
            [lay["length"]] if lay.get("length") else [base_len] + [base_len + k for k in LEADS]
        )
        sx, sy = lay.get("shift") or (0.0, 0.0)
        h = nt["text_height"]
        w, hh = rich_size(i["text"], h, std)
        g = nt["shoulder_gap"]
        angles = [lay["dir"]] if lay.get("dir") is not None else list(NOTE_ANGLES)
        out = []
        for length, ang in [(n, a) for n in lengths for a in angles]:
            u = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
            e = (A[0] + u[0] * length + sx, A[1] + u[1] * length + sy)
            sg = 1 if u[0] >= -1e-9 else -1
            sh = (e[0] + sg * (w + 2 * g), e[1])
            d = (A[0] - e[0], A[1] - e[1])
            L = math.hypot(*d) or 1.0
            tp, tbox = rich_text(
                i["text"], (e[0] + sg * (g + w / 2), e[1] + std["dim"]["text_gap"] + hh / 2), h, std
            )
            prims = [
                Line(e, A, "thin"),
                arrow(A, (d[0] / L, d[1] / L), std, "thin"),
                Line(e, sh, "thin"),
                *tp,
            ]
            out.append(
                {
                    "prims": prims,
                    "boxes": [tbox],
                    "segs": [(e, A), (e, sh)],
                    "fields": {"dir": ang, "length": length},
                    "why": "",
                }
            )
        return out

    def _corridors(self, box):
        """Free distance from a text box to the nearest obstacle in each direction."""
        x0, y0, x1, y1 = box
        boxes = [b for _o, b in self.obst.boxes]
        boxes += [
            (min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1]))
            for _o, p, q in self.obst.segs
        ]
        tests = {
            "right": lambda b: b[1] < y1 and b[3] > y0 and b[0] >= x1 - 1e-9 and b[0] - x1,
            "left": lambda b: b[1] < y1 and b[3] > y0 and b[2] <= x0 + 1e-9 and x0 - b[2],
            "up": lambda b: b[0] < x1 and b[2] > x0 and b[1] >= y1 - 1e-9 and b[1] - y1,
            "down": lambda b: b[0] < x1 and b[2] > x0 and b[3] <= y0 + 1e-9 and y0 - b[3],
        }
        out = {}
        for name, test in tests.items():
            ds = []
            for b in boxes:
                v = test(b)
                if v is not None and v is not False:
                    ds.append(max(0.0, float(v)))
            out[name] = round(min(ds + [50.0]), 3)
        return out

    def choose(self, el, cands, auto_fields):
        clearance = self.std["dim"]["clearance"]
        best = None
        for k, cand in enumerate(cands):
            conf = self.obst.conflicts(el._id, cand, clearance)
            if best is not None and len(conf) > best[0][0]:
                continue  # cannot win on the first key; skip the more expensive scans
            cut = self.obst.crossings(el._id, cand) if cand.get("cross") else []
            if best is not None and (len(conf), len(cut)) > best[0][:2]:
                continue
            overlap = self.obst.overlaps(el._id, cand) if cand.get("overlap_cost") else []
            outline = self.obst.contour_crossings(el._id, cand) if cand.get("contour") else []
            # text overlap first, then cutting other annotations, then running along other
            # lines, and only then crossing the part outline
            key = (len(conf), len(cut), len(overlap), len(outline))
            if key == (0, 0, 0, 0):
                best = (key, k, cand, conf, cut, overlap, outline)
                break
            if best is None or key < best[0]:
                best = (key, k, cand, conf, cut, overlap, outline)
        _, k, cand, conf, cut, overlap, outline = best
        el._resolved.update(cand["fields"])
        if cand.get("ends"):
            el._resolved["ends"] = [list(p) for p in cand["ends"]]
        if cand.get("mode"):
            el._resolved["mode"] = cand["mode"]
        el._auto = [f for f in auto_fields if f in cand["fields"]]
        reasons = []
        if (
            "row" in el._auto
            and cand["fields"].get("row", 1)
            and cand["fields"]["row"] > 1
            and not conf
        ):
            reasons.append(f"前面的排有冲突，外推到第 {cand['fields']['row']} 排")
        if cand["why"]:
            reasons.append(cand["why"])
        if conf:
            reasons.append(
                "所有候选都有冲突，取冲突最少的：与 " + "、".join(o for o, _ in conf) + " 冲突"
            )
        elif cut or overlap or outline:
            hits = sorted(set(cut) | set(overlap) | set(outline))
            reasons.append(
                "所有候选都与其他图元相交，取交叉最少的：与 " + "、".join(hits) + " 相交"
            )
        elif k and "at" in el._auto and cand["fields"].get("at") != cands[0]["fields"].get("at"):
            reasons.append("换角度避开交叉")
        if cand.get("overlap_cost") and (conf or cut or overlap or outline):
            # radial leader: an avoidable conflict always wins above, so what is left is
            # unavoidable — draw it and report it for the agent (DESIGN §4.6.3).  Text/space
            # conflicts are reported too, not just crossings.
            violations = [{"with": o, "kind": "overlap", "amount": round(v, 3)} for o, v in conf]
            violations += [{"with": o, "kind": "cross"} for o in cut]
            violations += [{"with": o, "kind": "coincide"} for o in overlap]
            violations += [{"with": o, "kind": "outline"} for o in outline]
            el._resolved["violations"] = violations
            if cut or overlap or outline:
                hit = sorted(set(cut) | set(overlap) | set(outline))
                reasons.append("不可避免的交叉：与 " + "、".join(hit) + " 相交")
                el._resolved["crossings"] = hit
            boxes = cand.get("boxes") or []
            if boxes:
                el._resolved["corridors"] = self._corridors(boxes[0])
        el._reason = "；".join(reasons)
        if cand.get("contour") and cand.get("ends"):  # circular dimension: remember its centre
            a, b = cand["ends"]
            self.obst.centres[el._id] = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            self.obst.radial.add(el._id)
        self.put(el, cand["prims"], obstacle=False)
        self.obst.ann.add(el._id)
        self.obst.kinds[el._id] = el.kind
        self.obst.add(
            el._id,
            segs=cand["segs"],
            boxes=cand["boxes"],
            dimlines=[cand["dimline"]] if cand.get("dimline") else (),
        )

    def annotations(self):
        dims = self.els("dim")
        decl = {e._id: k for k, e in enumerate(dims)}
        lin_t = ("linear", "dia", "rad", "aligned")
        linear = [e for e in dims if not e._intent.get("circle") and e._intent["type"] in lin_t]
        circular = [e for e in dims if e._intent.get("circle")]
        others = [e for e in dims if e._intent["type"] in ("angle",) + LEADER_TYPES]

        def is_fixed(e):
            lay = e._layout
            return lay.get("side") == "inside" or (lay.get("side") and lay.get("row"))

        def key(e):
            i = e._intent
            a, b = self.P(i["p1"]), self.P(i["p2"])
            side = e._layout.get("side") or (
                "top" if i["dir"] == "a" else self._side_for(a, b, i["dir"])
            )
            return (SIDE_ORDER.index(side), i["measured"], decl[e._id])

        notes = self.els("note")

        def fixed(e):
            if e.kind == "note" or e._intent.get("type") in LEADER_TYPES:
                return e._layout.get("dir") is not None
            if e._intent.get("type") == "angle":
                return e._layout.get("r") is not None
            if e._intent.get("circle"):
                return e._layout.get("at") is not None
            return bool(is_fixed(e))

        def place(e):
            if e.kind == "note" or e._intent.get("type") in LEADER_TYPES:
                auto = [f for f in ("dir", "length") if e._layout.get(f) is None]
                self.choose(e, self.note_cands(e), auto)
            elif e._intent.get("type") == "angle":
                auto = [] if e._layout.get("r") is not None else ["r"]
                self.choose(e, angle_cands(self, e), auto)
            elif e._intent.get("type") == "aligned":
                auto = [f for f in ("side", "row") if e._layout.get(f) is None]
                self.choose(e, aligned_cands(self, e), auto)
            elif e._intent.get("circle"):
                self.choose(
                    e, self.circle_cands(e), [] if e._layout.get("at") is not None else ["at"]
                )
            else:
                auto = [f for f in ("side", "row") if e._layout.get(f) is None]
                self.choose(e, self.linear_cands(e), auto)

        # PMI leaders hang on geometry or on already placed dimensions: place them before the
        # automatic circular leaders, so those dodge them instead of crowding them afterwards.
        pmi = (("datum", datum_cands), ("gtol", gtol_cands), ("rough", rough_cands))

        def ref_pending(e):
            r = self.d._els.get(e._intent.get("ref"))
            return r is not None and r.kind == "dim" and "ends" not in r._resolved

        def place_pmi(item):
            _kind, fn, e = item
            cands = fn(self, e)
            if cands:
                auto = [f for f in ("at", "length") if e._layout.get(f) is None]
                self.choose(e, cands, auto)

        for e in [x for x in dims + notes if fixed(x)]:  # all fixed elements first (SPEC 5.1)
            place(e)
        # a PMI leader with both layout fields written is fixed too: put it in before the
        # automatic dimensions (DESIGN §4.6.2: fixed elements are placed first, as obstacles)
        fixed_pmi = [
            (kind, fn, e)
            for kind, fn in pmi
            for e in self.els(kind)
            if all(e._layout.get(f) is not None for f in e.LAYOUT) and not ref_pending(e)
        ]
        placed_pmi = set()
        deferred = set()
        clearance = self.std["dim"]["clearance"]
        for item in fixed_pmi:
            cands = item[1](self, item[2])
            if any(not self.obst.conflicts(item[2]._id, c, clearance) for c in cands):
                place_pmi(item)
                placed_pmi.add(item[2]._id)
            else:  # cannot be placed cleanly now: defer rather than block the automatic ones
                deferred.add(item[2]._id)
        for e in sorted([x for x in linear if not fixed(x)], key=key):
            place(e)
        # split the rest only after the dimensions are placed: a leader on a placed dimension
        # can go first, one on an automatic circular dimension has to wait for it
        # an unclean fixed PMI is placed with the early leaders (after the automatic dimensions,
        # where it can still see them) instead of claiming a spot it cannot hold cleanly
        early = [
            (kind, fn, e)
            for kind, fn in pmi
            for e in self.els(kind)
            if e._id not in placed_pmi and not ref_pending(e)
        ]
        late = [
            (kind, fn, e)
            for kind, fn in pmi
            for e in self.els(kind)
            if e._id not in placed_pmi and ref_pending(e)
        ]
        for item in early:
            place_pmi(item)
        for e in [x for x in circular + others + notes if not fixed(x)]:
            place(e)
        for e in self.els("feature"):
            if e._intent.get("type") == "center_hole":
                self.choose(e, center_hole_cands(self, e), [])
        for item in late:  # leaders whose target dimension was placed above
            place_pmi(item)

    def plain_texts(self):
        """Imported plain text elements (DXF TEXT / MTEXT): no leader, fixed position / height /
        rotation / alignment / style from the source; MTEXT line breaks stacked per line with the
        source line-spacing factor (DXF base 5/3)."""
        from .text import has_cjk

        for e in self.els("text"):
            i = e._intent
            h = i["height"] * self.s
            rot = i.get("rotation", 0.0)
            halign = i.get("halign", 0)
            valign = i.get("valign", 0)
            lines = str(i["text"]).split("\n")
            factor = i.get("line_spacing") or 1.0
            step = h * (5.0 / 3.0) * factor
            c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            x0, y0 = self.P(i["at"])
            insert = self.P(i.get("insert", i["at"]))
            cjk = has_cjk(i["text"]) or None
            sizes = [text_size(line, h, self.std, cjk) for line in lines]
            n = len(lines)
            if valign == 3:  # MTEXT top: first line's top edge at the insertion point
                dy0 = -sizes[0][1] / 2.0
            elif valign == 2:  # MTEXT middle: block centred at the insertion point
                dy0 = (n - 1) * step / 2.0
            elif valign == 1:  # MTEXT bottom: last line's bottom edge at the insertion point
                dy0 = (n - 1) * step + sizes[-1][1] / 2.0
            else:  # TEXT baseline
                dy0 = sizes[0][1] / 2.0
            prims = []
            for k, (line, (w, _hh)) in enumerate(zip(lines, sizes)):
                if halign == 0:
                    dx = w / 2.0
                elif halign in (3, 5):  # ALIGNED / FIT: anchor is the second alignment point
                    dx = -w / 2.0
                elif halign == 2:
                    dx = -w / 2.0
                else:  # center / middle
                    dx = 0.0
                ly = dy0 - k * step
                px = x0 + dx * c - ly * s_
                py = y0 + dx * s_ + ly * c
                if valign == 3:
                    up = -k
                elif valign == 2:
                    up = (n - 1) / 2.0 - k
                elif valign == 1:
                    up = (n - 1) - k
                else:
                    up = 0.0
                line_anchor = (
                    insert[0] - up * step * s_,
                    insert[1] + up * step * c,
                )
                second = i.get("align_point")
                line_anchor2 = self.P(second) if second is not None else None
                prims.append(
                    make_text(
                        line,
                        (px, py),
                        h,
                        self.std,
                        rot,
                        layer="text",
                        cjk=cjk,
                        exact_height=True,
                        style=i.get("style"),
                        layer_name=i.get("layer"),
                        align=(halign, valign),
                        anchor=line_anchor,
                        anchor2=line_anchor2,
                    )
                )
            self.put(e, prims)

    def section_labels(self):
        sec = self.std["section"]
        h = sec["label_height"]

        def top_center():
            top = union([prims_bbox(p) for p in self.parts.values()] + [self.G])[3]
            return (self.G[0] + self.G[2]) / 2, top

        for e in self.d._els.values():
            if e.kind != "section" or e._intent["view"] != self.name:
                continue
            cx, top = top_center()
            text = f"{e._intent['letter']}-{e._intent['letter']}"
            _, hh = text_size(text, h, self.std)
            t = make_text(text, (cx, top + sec["label_gap"] + hh / 2), h, self.std, layer="text")
            self.put(e, [t])
        aux = self.view.aux
        if aux in ("detail", "oblique"):
            i = self.view._intent
            cx, top = top_center()
            letter = i["name"]
            w, hh = text_size(letter, h, self.std)
            prims = []
            if aux == "detail":  # letter over a short line over the scale (GB/T 4458.1)
                st = i["scale_text"]
                ws, hs = text_size(st, h, self.std)
                y0 = top + sec["label_gap"]
                prims.append(make_text(st, (cx, y0 + hs / 2), h, self.std, layer="text"))
                y1 = y0 + hs + 0.8
                L = max(w, ws) + 2
                prims.append(Line((cx - L / 2, y1), (cx + L / 2, y1), "thin"))
                prims.append(make_text(letter, (cx, y1 + 0.8 + hh / 2), h, self.std, layer="text"))
            else:
                y = top + sec["label_gap"] + hh / 2
                prims.append(make_text(letter, (cx, y), h, self.std, layer="text"))
                if i.get("rotate"):  # rotation symbol: half circle arrow before the letter
                    rc = (cx - w / 2 - h, y)
                    prims.append(Arc(rc, h / 2, 0, 180, "thin"))
                    prims.append(arrow((rc[0] - h / 2, y), (0, -1), self.std, "thin"))
            self.put(self.view, prims)

    def run(self):
        self.geometry()
        self.section_symbols()
        self.plain_texts()
        self.annotations()
        self.section_labels()
        self.balloons()
        self.full = union([prims_bbox(p) for p in self.parts.values()] + [self.G])

    def balloons(self):
        """Assembly balloons (GB/T 4458.2): a dot on the part, a thin leader, the number in a
        circle; circles in a column left of / a row above the view, leaders not crossing."""
        bs = sorted(self.els("balloon"), key=lambda e: e.number or 0)
        if not bs:
            return
        h = 5.0
        r = 0.9 * h
        B = union([prims_bbox(p) for p in self.parts.values() if p] + [self.G])
        gap = 8.0
        sides = {"left": [], "top": [], "right": [], "bottom": []}
        for e in bs:
            A = self.P(e._intent["anchor"])
            side = e._layout.get("side")
            if side not in sides:
                dl, dt = A[0] - B[0], B[3] - A[1]
                side = "left" if dl <= dt else "top"
            e._auto.append("side")
            e._resolved["side"] = side
            sides[side].append((e, A))
        step = 2 * r + 2
        for side, items in sides.items():
            if not items:
                continue
            vert = side in ("left", "right")
            k = 1 if vert else 0
            items.sort(key=lambda t: t[1][k])
            pos = [t[1][k] for t in items]
            for i in range(1, len(pos)):
                pos[i] = max(pos[i], pos[i - 1] + step)
            shift = (sum(t[1][k] for t in items) - sum(pos)) / len(pos)
            pos = [p + shift for p in pos]

            def centre(p, side=side):
                return {
                    "left": (B[0] - gap - r, p),
                    "right": (B[2] + gap + r, p),
                    "top": (p, B[3] + gap + r),
                }.get(side, (p, B[1] - gap - r))

            for _ in range(len(items) ** 2):  # swap slots until no two leaders cross
                done = True
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        if _seg_cross(items[i][1], centre(pos[i]), items[j][1], centre(pos[j])):
                            pos[i], pos[j] = pos[j], pos[i]
                            done = False
                if done:
                    break
            for (e, A), p in zip(items, pos):
                if side == "left":
                    c = (B[0] - gap - r, p)
                elif side == "right":
                    c = (B[2] + gap + r, p)
                elif side == "top":
                    c = (p, B[3] + gap + r)
                else:
                    c = (p, B[1] - gap - r)
                L_ = math.dist(A, c)
                q = (c[0] + (A[0] - c[0]) * r / L_, c[1] + (A[1] - c[1]) * r / L_) if L_ > r else c
                w = 0.7
                n_, s_, e_, w_ = (
                    (A[0], A[1] + w),
                    (A[0], A[1] - w),
                    (A[0] + w, A[1]),
                    (A[0] - w, A[1]),
                )
                prims = [
                    Circle(c, r, "thin"),
                    Line(A, q, "thin"),
                    Solid((w_, n_, e_), "thin"),  # the dot: two triangles (DXF SOLID)
                    Solid((w_, s_, e_), "thin"),
                    make_text(str(e.number), c, h, self.std, layer="text"),
                ]
                self.put(e, prims)


def _clip_line(a, u, G):
    """Parameter range where the infinite line a + t·u crosses box G, or (None, None)."""
    t0, t1 = -math.inf, math.inf
    for k in (0, 1):
        lo, hi = G[k], G[k + 2]
        if abs(u[k]) < 1e-12:
            if a[k] < lo - 1e-9 or a[k] > hi + 1e-9:
                return None, None
            continue
        ta, tb = (lo - a[k]) / u[k], (hi - a[k]) / u[k]
        t0, t1 = max(t0, min(ta, tb)), min(t1, max(ta, tb))
    if t0 > t1:
        return None, None
    return t0, t1


class _Layout:
    def __init__(self, d):
        self.d, self.std = d, d.std

    def run(self):
        d = self.d
        for e in d._els.values():
            e._prims = []
            e._resolved = {}
            e._auto = []
            e._reason = ""
        allv = d.views()
        views = sorted([v for v in allv if v.aux is None], key=lambda v: ORDER.index(v.name))
        views += [v for v in allv if v.aux is not None]
        vls = {v.name: _ViewLayout(self, v) for v in views}
        for vl in vls.values():
            vl.run()
        sheet = self.sheet_frame()
        origins = self.arrange(vls, sheet)
        for name, vl in vls.items():
            ox, oy = origins[name]
            for eid, prims in vl.parts.items():
                d._els[eid]._prims += [move_prim(p, ox, oy) for p in prims]
            v = vl.view
            full = vl.full
            v._resolved.update(
                origin=[ox, oy],
                scale=d.scale,
                bbox=[full[0] + ox, full[1] + oy, full[2] + ox, full[3] + oy],
            )
        for e in d._els.values():
            if e._prims and e.kind != "view":
                e._resolved["bbox"] = list(prims_bbox(e._prims))
        from .pmi import chain_result

        for e in d._els.values():
            if e.kind == "chain":
                e._resolved["result"] = chain_result(d, e)
        for e in d._els.values():  # features: union of their edges
            if e.kind == "feature":
                b = union(
                    [d._els[i]._resolved.get("bbox") for i in e._intent["edges"] if i in d._els]
                )
                if b:
                    e._resolved["bbox"] = list(b)

    # -- frame, title block, technical requirements -------------------------------------------
    def sheet_frame(self):
        d, std, tpl = self.d, self.std, self.d.template
        W, H = tpl["size"]
        F = tpl["frame"]
        tb = tpl["title_block"]
        ox, oy = tb["origin"]
        prims = [Line(a, b, "thin") for a, b in _rect((0, 0, W, H))]
        prims += [Line(a, b, "thick") for a, b in _rect(F)]
        sym = tb.get("projection", {}).get(std["views"]["projection"], {})  # ISO 5456-2 symbol
        for ln in [*tb["lines"], *sym.get("lines", [])]:
            prims.append(
                Line(
                    (ox + ln["p1"][0], oy + ln["p1"][1]),
                    (ox + ln["p2"][0], oy + ln["p2"][1]),
                    ln.get("role", "thin"),
                )
            )
        for c in [*tb.get("circles", []), *sym.get("circles", [])]:
            prims.append(Circle((ox + c["c"][0], oy + c["c"][1]), c["r"], c.get("role", "thick")))
        for lb in tb.get("labels", []):
            prims.append(
                make_text(
                    lb["text"],
                    (ox + lb["at"][0], oy + lb["at"][1]),
                    lb["height"],
                    std,
                    layer="text",
                )
            )
        d._els["T.frame"]._prims = prims
        TB = (ox, oy, ox + tb["size"][0], oy + tb["size"][1])
        for e in d._els.values():
            if e.kind != "table.cell":
                continue
            spec = tb["fields"][e._intent["field"]]
            x0, y0, x1, y1 = spec["box"]
            text = e._intent["text"]
            if not text:
                continue
            # the largest height of the GB/T 14691 series (up to the slot's) that fits the slot
            fit = [
                s
                for s in std["text"]["heights"]
                if s <= spec["height"] + 1e-9
                and text_size(text, s, std)[0] <= (x1 - x0) - 1
                and text_size(text, s, std)[1] <= y1 - y0
            ]
            h = max(fit) if fit else std["text"]["heights"][0]
            e._prims = [
                make_text(text, (ox + (x0 + x1) / 2, oy + (y0 + y1) / 2), h, std, layer="text")
            ]
        bom = d._els.get("T.bom")
        if bom is not None:
            from .assembly import bom_rows

            bom._prims = bom_prims(bom_rows(d), TB, std)
            TB = (TB[0], TB[1], TB[2], prims_bbox(bom._prims)[3])
        tn = std["tech_notes"]
        notes = [e for e in d._els.values() if e.kind == "note" and e._intent.get("tech")]
        TN = None
        if notes:
            lh = tn["height"] * tn["line_spacing"]
            total = tn["title_height"] * 1.6 + len(notes) * lh
            x0 = TB[0] + 2
            top = TB[3] + tn["gap"] + total
            boxes = []
            from .text import has_cjk

            cjk = any(has_cjk(e._intent["text"]) for e in notes) or None  # one metric per block
            for k, e in enumerate(notes, 1):
                s = f"{k}. {e._intent['text']}"
                w, _ = text_size(s, tn["height"], std, cjk)
                t = make_text(
                    s,
                    (x0 + w / 2, top - tn["title_height"] * 1.6 - (k - 0.5) * lh),
                    tn["height"],
                    std,
                    layer="text",
                    cjk=cjk,
                )
                e._prims = [t]
                boxes.append(t.box)
            title = tn["title"]
            w, _ = text_size(title, tn["title_height"], std)
            t = make_text(
                title,
                (x0 + w / 2, top - tn["title_height"] * 0.8),
                tn["title_height"],
                std,
                layer="text",
            )
            notes[0]._prims.insert(0, t)
            boxes.append(t.box)
            TN = union(boxes)
        rd = d._els.get("R.default")
        if rd is not None:
            rd._prims = rough_default_prims(rd, std, TB[2] - 2, TB[3] + tn["gap"])
            rd._resolved["bbox"] = list(prims_bbox(rd._prims))
            TN = union([TN, prims_bbox(rd._prims)])
        return {"F": F, "TB": TB, "TN": TN}

    # -- view placement ----------------------------------------------------------------------------
    def arrange(self, vls, sheet):
        _d, std = self.d, self.std
        if not vls:
            return {}
        gap = std["views"]["gap"]
        pos = {"front": [0, 0], **std["views"]["positions"][std["views"]["projection"]]}
        names = list(vls)
        if len(names) > 1 and "front" not in vls:
            raise InvalidArgument("多个视图时必须有 front（主视图）", candidates=names)
        base = "front" if "front" in vls else names[0]
        origins = {base: (0.0, 0.0)}

        def placed_box(n):
            f = vls[n].full
            o = origins[n]
            return (f[0] + o[0], f[1] + o[1], f[2] + o[0], f[3] + o[1])

        auxs = [n for n in names if vls[n].view.aux is not None]
        names_b = [n for n in names if n not in auxs]
        rest = sorted(
            [n for n in names_b if n != base], key=lambda n: (abs(pos[n][0]), ORDER.index(n))
        )
        for n in rest:
            col, row = pos[n]
            f = vls[n].full
            fb = placed_box(base)
            if col == 0:
                x = origins[base][0]
                y = fb[1] - gap - f[3] if row < 0 else fb[3] + gap - f[1]
            else:
                y = origins[base][1]
                ylo, yhi = f[1] + y, f[3] + y
                others = [placed_box(m) for m in origins]
                others = [b for b in others if b[1] < yhi + gap and b[3] > ylo - gap] or [
                    placed_box(base)
                ]
                if col > 0:
                    x = max(b[2] for b in others) + gap - f[0]
                else:
                    x = min(b[0] for b in others) - gap - f[2]
            origins[n] = (x, y)
        for n in names_b:  # offsets from move(); the base view's offset moves the whole group
            if n != base:
                ox, oy = vls[n].view._layout.get("offset", [0.0, 0.0])
                origins[n] = (origins[n][0] + ox, origins[n][1] + oy)
        self.place_aux(vls, auxs, origins, placed_box, gap)
        group = union(
            [placed_box(n) for n in names if vls[n].view._layout.get("at") is None or n == base]
        )
        fv = vls[base].view
        bx, by = fv._layout.get("offset", [0.0, 0.0])
        if fv._layout.get("at") is not None:
            ax, ay = fv._layout["at"]
            dx, dy = ax - origins[base][0], ay - origins[base][1]
        else:
            F = sheet["F"]
            dx = (F[0] + F[2]) / 2 - (group[0] + group[2]) / 2
            dy = (F[1] + F[3]) / 2 - (group[1] + group[3]) / 2
            zone = union([sheet["TB"], sheet["TN"]])
            g = (group[0] + dx, group[1] + dy, group[2] + dx, group[3] + dy)
            if box_overlap(inflate(zone, gap / 2), g) > 0:
                up = zone[3] + gap - g[1]
                left = g[2] - (zone[0] - gap)
                if g[3] + up <= F[3] + 1e-9:
                    dy += up
                elif g[0] - left >= F[0] - 1e-9:
                    dx -= left
                else:
                    dy += max(0.0, F[3] - g[3])
                    dx -= max(0.0, g[0] - F[0])
        dx, dy = dx + bx, dy + by
        out = {n: (o[0] + dx, o[1] + dy) for n, o in origins.items()}
        for n in auxs:  # place(at=...) on an auxiliary view is an absolute sheet position
            at = vls[n].view._layout.get("at")
            if at is not None:
                ox, oy = vls[n].view._layout.get("offset", [0.0, 0.0])
                out[n] = (at[0] + ox, at[1] + oy)
        return out

    def place_aux(self, vls, auxs, origins, placed_box, gap):
        """Auxiliary views go next to the basic group: removed sections on the extension of the
        cutting line below (then above) the group, others right / below / above; first free spot."""
        occupied = [placed_box(n) for n in origins]
        for n in auxs:
            v = vls[n].view
            f = vls[n].full
            i = v._intent
            G = union(occupied)
            cands = []
            if i["aux"] == "section":
                pv = vls[i["parent"]]
                po = origins[i["parent"]]
                a, b = i["trace"]
                mx = po[0] + (a[0] + b[0]) / 2 * pv.s
                my = po[1] + (a[1] + b[1]) / 2 * pv.s
                vert = abs(b[0] - a[0]) <= abs(b[1] - a[1])
                if vert:
                    cands += [(mx, G[1] - gap - f[3]), (mx, G[3] + gap - f[1])]
                else:
                    cands += [(G[2] + gap - f[0], my), (G[0] - gap - f[2], my)]
            cands += [
                (G[2] + gap - f[0], G[3] - f[3]),
                (G[2] + gap - f[0], G[1] - f[1]),
                (G[0] - f[0], G[1] - gap - f[3]),
                (G[0] - f[0], G[3] + gap - f[1]),
            ]

            def box(o, f=f):
                return (f[0] + o[0], f[1] + o[1], f[2] + o[0], f[3] + o[1])

            pick = None
            for o in cands:
                if all(box_overlap(inflate(box(o), gap / 2 - 1e-6), b) <= 0 for b in occupied):
                    pick = o
                    break
            if pick is None:  # stack further out below the group
                low = min(b[1] for b in occupied)
                pick = (cands[0][0], low - gap - f[3])
            ox, oy = v._layout.get("offset", [0.0, 0.0])
            origins[n] = (pick[0] + ox, pick[1] + oy)
            occupied.append(placed_box(n))


def _rect(b):
    x0, y0, x1, y1 = b
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return list(zip(pts, pts[1:] + pts[:1]))


BOM_COLS = (("序号", 8), ("代号", 40), ("名称", 44), ("数量", 8), ("材料", 38))  # GB/T 10609.2
BOM_ROW = 7.0


def _seg_cross(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2 = orient(c, d, a), orient(c, d, b)
    d3, d4 = orient(a, b, c), orient(a, b, d)
    return d1 * d2 < 0 and d3 * d4 < 0


def bom_prims(rows, TB, std):
    """Parts list on top of the title block: header row at the bottom, item 1 just above it."""
    x0, x1, y0 = TB[0], TB[2], TB[3]
    cols = list(BOM_COLS) + [("备注", (x1 - x0) - sum(w for _, w in BOM_COLS))]
    xs = [x0]
    for _, w in cols:
        xs.append(xs[-1] + w)
    n = len(rows)
    top = y0 + BOM_ROW * (n + 1)
    # GB/T 10609.2: vertical lines thick, horizontal lines thin (the top one too)
    prims = [Line((x, y0), (x, top), "thick") for x in xs]
    prims += [Line((x0, y0 + BOM_ROW * k), (x1, y0 + BOM_ROW * k), "thin") for k in range(1, n + 2)]

    def cell(text, k, j):
        if text in ("", None):
            return
        w = xs[j + 1] - xs[j]
        hs = [h for h in std["text"]["heights"] if h <= 3.5 + 1e-9]
        h = max([s for s in hs if text_size(str(text), s, std)[0] <= w - 1] or [hs[0]])
        prims.append(
            make_text(
                str(text), ((xs[j] + xs[j + 1]) / 2, y0 + BOM_ROW * (k + 0.5)), h, std, layer="text"
            )
        )

    for j, (label, _) in enumerate(cols):
        cell(label, 0, j)
    for r in rows:
        for j, key in enumerate(("no", "code", "name", "qty", "material", "remark")):
            cell(r[key], r["no"], j)
    return prims


def layout(d):
    """Resolve every element's placement and prims (sheet coordinates)."""
    _Layout(d).run()


# PMI layout uses the prims above (import last: circular)
from .pmi_layout import (  # noqa: E402
    aligned_cands,
    angle_cands,
    center_hole_cands,
    datum_cands,
    dim_label,
    gtol_cands,
    label_size,
    rich_size,
    rich_text,
    rough_cands,
    rough_default_prims,
)
