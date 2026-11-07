"""Annotation layout and view placement (SPEC §5).

Deterministic semantic placement + local push-out + conflict report; no global solver.
Every element ends up with ``_prims`` (sheet coordinates) and ``_resolved`` (incl. ``bbox``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .errors import InvalidArgument
from .text import text_size

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


@dataclass(frozen=True)
class Solid:
    pts: tuple
    layer: str


@dataclass(frozen=True)
class Hatch:
    loops: tuple  # each: tuple of points, or ("circle", c, r)
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
        return replace(pr, at=_mv(pr.at, dx, dy), box=(b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy))
    if isinstance(pr, Solid):
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
        (c[0] + r * math.cos(math.radians(a0 + sweep * k / n)), c[1] + r * math.sin(math.radians(a0 + sweep * k / n)))
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
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


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


def make_text(s, at, h, std, rot=0, layer="dim"):
    w, hh = text_size(s, h, std)
    if rot % 180 == 90:
        box = (at[0] - hh / 2, at[1] - w / 2, at[0] + hh / 2, at[1] + w / 2)
    else:
        box = (at[0] - w / 2, at[1] - hh / 2, at[0] + w / 2, at[1] + hh / 2)
    return Text(s, tuple(at), h, rot, layer, box)


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
DIA_ANGLES = (45, 135, 315, 225, 30, 150, 60, 120)
NOTE_ANGLES = (45, 135, 315, 225, 60, 120, 300, 240)
LEADS = (3.0, 8.0, 13.0, 18.0, 25.0, 35.0)  # extra leader lengths tried, shortest first
ORDER = ("front", "top", "bottom", "left", "right", "rear")


class _Obstacles:
    def __init__(self):
        self.segs = []  # (owner, p, q)
        self.boxes = []  # (owner, box)
        self.dimlines = []  # (owner, p, q)

    def add(self, owner, segs=(), boxes=(), dimlines=()):
        self.segs += [(owner, p, q) for p, q in segs]
        self.boxes += [(owner, b) for b in boxes]
        self.dimlines += [(owner, p, q) for p, q in dimlines]

    def add_prims(self, owner, prims):
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


class _ViewLayout:
    def __init__(self, L, view):
        self.L, self.d, self.std, self.s = L, L.d, L.std, L.d.scale
        self.view = view
        self.name = view.name
        self.parts: dict[str, list] = {}
        self.obst = _Obstacles()
        self.G = None

    def P(self, p):
        return (p[0] * self.s, p[1] * self.s)

    def els(self, kind):
        return [e for e in self.d._els.values() if e.kind == kind and e._intent.get("view") == self.name]

    def put(self, el, prims, obstacle=True):
        self.parts.setdefault(el._id, []).extend(prims)
        if obstacle:
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
                prims = [center_piece(a, b, self.std)]
            elif i["type"] == "mark":
                c, h = self.P(i["c"]), i["r"] * self.s + ext
                # four pieces from the centre outwards: the crossing falls on long dashes
                prims = [center_piece(c, (c[0] + dx * h, c[1] + dy * h), self.std)
                         for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
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
            for lp in e._intent["loops"]:
                if "points" in lp:
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
            self.put(e, [Hatch(tuple(loops), "hatch")], obstacle=False)

    # -- section symbols (in the cut view) ----------------------------------------------------
    def section_symbols(self):
        sec = self.std["section"]
        for e in self.d._els.values():
            if e.kind != "section" or e._intent["cut_in"] != self.name:
                continue
            i = e._intent
            a, b = self.P(i["through"][0]), self.P(i["through"][1])
            L = math.dist(a, b)
            u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            t0, t1 = _clip_line(a, u, self.G)
            if t0 is None:
                t0, t1 = 0.0, L
            look = {"left": (-1, 0), "right": (1, 0), "up": (0, 1), "down": (0, -1)}[i["look"]]
            n = (-u[1], u[0])
            if n[0] * look[0] + n[1] * look[1] < 0:
                n = (-n[0], -n[1])
            prims = []
            gap, sl, al = sec["stroke_gap"], sec["stroke_length"], sec["arrow_length"]
            lh = sec["letter_height"]
            for t_in, sgn in ((t0, -1), (t1, 1)):
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
                at = (p1[0] + n[0] * al / 2 + u[0] * sgn * off, p1[1] + n[1] * al / 2 + u[1] * sgn * off)
                prims.append(make_text(i["letter"], at, lh, self.std, layer="text"))
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
        rows = [None] if side == "inside" else ([lay["row"]] if lay.get("row") else range(1, int(dm["max_rows"]) + 1))
        h = dm["text_height"]
        w, hh = text_size(i["text"], h, std)
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
                level = {"top": G[3] + dist, "bottom": G[1] - dist, "right": G[2] + dist, "left": G[0] - dist}[side]
                ext_pts = [a, b]
            span = hi - lo
            fits = span >= w + 2 * al + 2 * gap
            positions = []
            if fits:
                for f in (0.5, 0.75, 0.25):
                    c = lo + span * f
                    if c - w / 2 >= lo + al + gap - 1e-9 and c + w / 2 <= hi - al - gap + 1e-9:
                        positions.append(("in", c))
            positions += [("out_hi", hi + al + 2 + w / 2), ("out_lo", lo - al - 2 - w / 2)]
            for pos, c in positions:
                out.append(self._linear_geom(el, dir, side, row, off, level, lo, hi, ext_pts, pos, c, w, hh))
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
            prims += [Line(*line, "dim"), arrow(pt(lo, level), d_lo, self.std), arrow(pt(hi, level), d_hi, self.std)]
        else:
            x0, x1 = lo - al - 2, hi + al + 2
            if pos == "out_hi":
                x1 = c + w / 2
            else:
                x0 = c - w / 2
            line = (pt(x0, level), pt(x1, level))
            prims += [Line(*line, "dim"), arrow(pt(lo, level), d_hi, self.std), arrow(pt(hi, level), d_lo, self.std)]
        segs.append(line)
        tg = dm["text_gap"]
        if dir == "h":
            t = make_text(el._intent["text"], (c, level + tg + hh / 2), dm["text_height"], self.std)
        else:
            t = make_text(el._intent["text"], (level - tg - hh / 2, c), dm["text_height"], self.std, rot=90)
        prims.append(t)
        fields = {"side": side, "row": row, "offset": off}
        why = {"in": "", "out_hi": "文字放不下，移到界线外", "out_lo": "文字放不下，移到界线外"}[pos]
        if pos == "in" and abs(c - (lo + hi) / 2) > 1e-6:
            why = "文字避让，沿尺寸线移位"
        return {"prims": prims, "boxes": [t.box], "segs": segs, "dimline": line, "fields": fields, "why": why}

    def circle_cands(self, el):
        i, lay = el._intent, el._layout
        std, dm = self.std, self.std["dim"]
        c, r = self.P(i["c"]), i["r"] * self.s
        h = dm["text_height"]
        w, hh = text_size(i["text"], h, std)
        al = dm["arrow_length"]
        angles = [lay["at"]] if lay.get("at") is not None else list(DIA_ANGLES)
        circ = self.d._els.get(i["circle"])
        if lay.get("at") is None and circ is not None and circ._intent.get("shape") == "arc":
            a0, a1 = circ._intent["start"], circ._intent["end"]
            sweep = (a1 - a0) % 360 or 360
            inside = [a for a in angles if (a - a0) % 360 <= sweep]
            angles = inside or [a0 + sweep / 2]
        out = []
        for lead, ang in [(lead, a) for lead in LEADS for a in angles]:
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
            t = make_text(i["text"], (e[0] + sg * (1 + w / 2), e[1] + dm["text_gap"] + hh / 2), h, std)
            prims.append(t)
            why = "引线加长以避开轮廓" if lead > al + LEADS[0] else ""
            out.append({"prims": prims, "boxes": [t.box], "segs": segs, "fields": {"at": ang}, "why": why})
        return out

    def note_cands(self, el):
        i, lay = el._intent, el._layout
        std, nt = self.std, self.std["note"]
        A = self.P(i["anchor"])
        base_len = nt["leader_length"]
        lengths = [lay["length"]] if lay.get("length") else [base_len + k for k in LEADS]
        sx, sy = lay.get("shift") or (0.0, 0.0)
        h = nt["text_height"]
        w, hh = text_size(i["text"], h, std)
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
            t = make_text(i["text"], (e[0] + sg * (g + w / 2), e[1] + std["dim"]["text_gap"] + hh / 2), h, std, layer="text")
            prims = [Line(e, A, "thin"), arrow(A, (d[0] / L, d[1] / L), std, "thin"), Line(e, sh, "thin"), t]
            out.append({"prims": prims, "boxes": [t.box], "segs": [(e, A), (e, sh)],
                        "fields": {"dir": ang, "length": length}, "why": ""})
        return out

    def choose(self, el, cands, auto_fields):
        clearance = self.std["dim"]["clearance"]
        best = None
        for k, cand in enumerate(cands):
            conf = self.obst.conflicts(el._id, cand, clearance)
            if not conf:
                best = (0, k, cand, conf)
                break
            if best is None or len(conf) < best[0]:
                best = (len(conf), k, cand, conf)
        _, k, cand, conf = best
        el._resolved.update(cand["fields"])
        el._auto = [f for f in auto_fields if f in cand["fields"]]
        reasons = []
        if "row" in el._auto and cand["fields"].get("row", 1) and cand["fields"]["row"] > 1 and not conf:
            reasons.append(f"前面的排有冲突，外推到第 {cand['fields']['row']} 排")
        if cand["why"]:
            reasons.append(cand["why"])
        if conf:
            reasons.append("所有候选都有冲突，取冲突最少的：与 " + "、".join(o for o, _ in conf) + " 冲突")
        el._reason = "；".join(reasons)
        self.put(el, cand["prims"], obstacle=False)
        self.obst.add(el._id, segs=cand["segs"], boxes=cand["boxes"],
                      dimlines=[cand["dimline"]] if cand.get("dimline") else ())

    def annotations(self):
        dims = self.els("dim")
        decl = {e._id: k for k, e in enumerate(dims)}
        linear = [e for e in dims if not e._intent.get("circle")]
        circular = [e for e in dims if e._intent.get("circle")]

        def is_fixed(e):
            lay = e._layout
            return lay.get("side") == "inside" or (lay.get("side") and lay.get("row"))

        def key(e):
            i = e._intent
            a, b = self.P(i["p1"]), self.P(i["p2"])
            side = e._layout.get("side") or self._side_for(a, b, i["dir"])
            return (SIDE_ORDER.index(side), i["measured"], decl[e._id])

        for e in [x for x in linear if is_fixed(x)] + sorted([x for x in linear if not is_fixed(x)], key=key):
            auto = [f for f in ("side", "row") if e._layout.get(f) is None]
            self.choose(e, self.linear_cands(e), auto)
        for e in [x for x in circular if x._layout.get("at") is not None] + [
            x for x in circular if x._layout.get("at") is None
        ]:
            self.choose(e, self.circle_cands(e), [] if e._layout.get("at") is not None else ["at"])
        notes = [e for e in self.els("note")]
        fixed = [n for n in notes if n._layout.get("dir") is not None]
        for e in fixed + [n for n in notes if n._layout.get("dir") is None]:
            auto = [f for f in ("dir", "length") if e._layout.get(f) is None]
            self.choose(e, self.note_cands(e), auto)

    def section_labels(self):
        sec = self.std["section"]
        for e in self.d._els.values():
            if e.kind != "section" or e._intent["view"] != self.name:
                continue
            top = union([prims_bbox(p) for p in self.parts.values()] + [self.G])[3]
            cx = (self.G[0] + self.G[2]) / 2
            text = f"{e._intent['letter']}-{e._intent['letter']}"
            h = sec["label_height"]
            _, hh = text_size(text, h, self.std)
            t = make_text(text, (cx, top + sec["label_gap"] + hh / 2), h, self.std, layer="text")
            self.put(e, [t])

    def run(self):
        self.geometry()
        self.section_symbols()
        self.annotations()
        self.section_labels()
        self.full = union([prims_bbox(p) for p in self.parts.values()] + [self.G])


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
        views = sorted(d.views(), key=lambda v: ORDER.index(v.name))
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
            v._resolved.update(origin=[ox, oy], scale=d.scale,
                               bbox=[full[0] + ox, full[1] + oy, full[2] + ox, full[3] + oy])
        for e in d._els.values():
            if e._prims:
                e._resolved["bbox"] = list(prims_bbox(e._prims))
        for e in d._els.values():  # features: union of their edges
            if e.kind == "feature":
                b = union([d._els[i]._resolved.get("bbox") for i in e._intent["edges"] if i in d._els])
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
        for ln in tb["lines"]:
            prims.append(Line((ox + ln["p1"][0], oy + ln["p1"][1]), (ox + ln["p2"][0], oy + ln["p2"][1]), ln.get("role", "thin")))
        for lb in tb.get("labels", []):
            prims.append(make_text(lb["text"], (ox + lb["at"][0], oy + lb["at"][1]), lb["height"], std, layer="text"))
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
            h = spec["height"]
            w, _ = text_size(text, h, std)
            if w > (x1 - x0) - 1:
                h = max(2.5, h * ((x1 - x0) - 1) / w)
            e._prims = [make_text(text, (ox + (x0 + x1) / 2, oy + (y0 + y1) / 2), h, std, layer="text")]
        tn = std["tech_notes"]
        notes = [e for e in d._els.values() if e.kind == "note" and e._intent.get("tech")]
        TN = None
        if notes:
            lh = tn["height"] * tn["line_spacing"]
            total = tn["title_height"] * 1.6 + len(notes) * lh
            x0 = TB[0] + 2
            top = TB[3] + tn["gap"] + total
            boxes = []
            for k, e in enumerate(notes, 1):
                s = f"{k}. {e._intent['text']}"
                w, _ = text_size(s, tn["height"], std)
                t = make_text(s, (x0 + w / 2, top - tn["title_height"] * 1.6 - (k - 0.5) * lh), tn["height"], std, layer="text")
                e._prims = [t]
                boxes.append(t.box)
            title = tn["title"]
            w, _ = text_size(title, tn["title_height"], std)
            t = make_text(title, (x0 + w / 2, top - tn["title_height"] * 0.8), tn["title_height"], std, layer="text")
            notes[0]._prims.insert(0, t)
            boxes.append(t.box)
            TN = union(boxes)
        return {"F": F, "TB": TB, "TN": TN}

    # -- view placement ----------------------------------------------------------------------------
    def arrange(self, vls, sheet):
        d, std = self.d, self.std
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

        rest = sorted([n for n in names if n != base], key=lambda n: (abs(pos[n][0]), ORDER.index(n)))
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
                others = [b for b in others if b[1] < yhi + gap and b[3] > ylo - gap] or [placed_box(base)]
                if col > 0:
                    x = max(b[2] for b in others) + gap - f[0]
                else:
                    x = min(b[0] for b in others) - gap - f[2]
            origins[n] = (x, y)
        for n in names:  # offsets from move(); the base view's offset moves the whole group
            if n != base:
                ox, oy = vls[n].view._layout.get("offset", [0.0, 0.0])
                origins[n] = (origins[n][0] + ox, origins[n][1] + oy)
        group = union([placed_box(n) for n in names])
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
        return {n: (o[0] + dx, o[1] + dy) for n, o in origins.items()}


def _rect(b):
    x0, y0, x1, y1 = b
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return list(zip(pts, pts[1:] + pts[:1]))


def layout(d):
    """Resolve every element's placement and prims (sheet coordinates)."""
    _Layout(d).run()
