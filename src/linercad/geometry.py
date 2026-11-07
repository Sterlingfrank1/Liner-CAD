"""Views and 2D native geometry (SPEC §4.2). Coordinates are view-local model mm."""

from __future__ import annotations

import math

from .errors import InvalidArgument
from .model import ROLES, Element, check_name, num
from .record import mutator

EPS = 1e-9


def _role(role):
    if role not in ROLES:
        raise InvalidArgument(f"线型角色 {role!r} 不存在", candidates=list(ROLES), values={"role": role})
    return role


def resolve_point(d, p, view=None, what="点"):
    """``(x, y)`` (numbers or expressions) or an anchor ``"<ID>:<anchor>"`` → (x, y)."""
    if isinstance(p, str):
        if ":" not in p:
            raise InvalidArgument(
                f"{what} {p!r} 不是锚点；锚点写成 '<元素ID>:<start|end|mid|center>'",
                values={what: p},
            )
        eid, anchor = p.rsplit(":", 1)
        el = d[eid]
        if view is not None and el.view is not None and el.view != view:
            raise InvalidArgument(
                f"锚点 {p} 在视图 {el.view}，不在 {view}", id=eid, values={"view": el.view}
            )
        pts = el._anchors() if hasattr(type(el), "_anchors") else {}
        if anchor not in pts or pts[anchor] is None:
            raise InvalidArgument(
                f"{eid} 没有锚点 {anchor!r}",
                id=eid,
                candidates=[k for k, v in pts.items() if v is not None],
            )
        return pts[anchor]
    try:
        x, y = p
    except (TypeError, ValueError):
        raise InvalidArgument(f"{what} 应为 (x, y) 或锚点串，收到 {p!r}", values={what: repr(p)})
    return (num(x, f"{what}.x"), num(y, f"{what}.y"))


def _pt(p):
    return [p[0], p[1]]


class Edge(Element):
    """A single geometric primitive: line, circle or arc."""

    kind = "edge"
    SETTABLE = ("role",)
    READ = ("shape", "role", "length", "dir", "start", "end", "mid", "center", "r", "feature")

    shape = property(lambda s: s._intent["shape"])
    role = property(lambda s: s._intent["role"])
    feature = property(lambda s: s._intent.get("feature"))

    @property
    def r(self):
        return self._intent.get("r")

    @property
    def center(self):
        c = self._intent.get("c")
        return tuple(c) if c else None

    def _arc_pt(self, a):
        cx, cy = self._intent["c"]
        r = self._intent["r"]
        return (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))

    def _sweep(self):
        a0, a1 = self._intent["start"], self._intent["end"]
        return (a1 - a0) % 360 or 360

    @property
    def start(self):
        s = self.shape
        if s == "line":
            return tuple(self._intent["p1"])
        if s == "arc":
            return self._arc_pt(self._intent["start"])
        return None

    @property
    def end(self):
        s = self.shape
        if s == "line":
            return tuple(self._intent["p2"])
        if s == "arc":
            return self._arc_pt(self._intent["end"])
        return None

    @property
    def mid(self):
        s = self.shape
        if s == "line":
            (x1, y1), (x2, y2) = self._intent["p1"], self._intent["p2"]
            return ((x1 + x2) / 2, (y1 + y2) / 2)
        if s == "arc":
            return self._arc_pt(self._intent["start"] + self._sweep() / 2)
        return tuple(self._intent["c"])

    @property
    def length(self):
        s = self.shape
        if s == "line":
            (x1, y1), (x2, y2) = self._intent["p1"], self._intent["p2"]
            return math.hypot(x2 - x1, y2 - y1)
        if s == "circle":
            return 2 * math.pi * self._intent["r"]
        return math.radians(self._sweep()) * self._intent["r"]

    @property
    def dir(self):
        if self.shape != "line":
            return None
        (x1, y1), (x2, y2) = self._intent["p1"], self._intent["p2"]
        if abs(y2 - y1) < EPS:
            return "h"
        if abs(x2 - x1) < EPS:
            return "v"
        return None

    def _anchors(self):
        return {"start": self.start, "end": self.end, "mid": self.mid, "center": self.center}

    def _apply_set(self, fields):
        if "role" in fields:
            _role(fields["role"])
        self._intent.update(fields)

    def _apply_move(self, dx, dy):
        i = self._intent
        for k in ("p1", "p2", "c"):
            if k in i:
                i[k] = [i[k][0] + dx, i[k][1] + dy]


class Feature(Element):
    """A named group of edges (and its centre lines)."""

    kind = "feature"
    READ = ("type", "edges", "closed")

    type = property(lambda s: s._intent["type"])
    closed = property(lambda s: bool(s._intent.get("closed")))

    @property
    def edges(self):
        return [self._d._els[i] for i in self._intent["edges"] if i in self._d._els]

    def _children(self):
        return list(self._intent["edges"]) + list(self._intent.get("centers", []))

    def loop(self):
        """Closed boundary as a point list (polygon/rect) or ('circle', c, r)."""
        i = self._intent
        if not i.get("closed"):
            return None
        if i["type"] == "circle":
            return ("circle", tuple(i["c"]), i["r"])
        return [tuple(p) for p in i["points"]]

    def _apply_move(self, dx, dy):
        i = self._intent
        if "points" in i:
            i["points"] = [[p[0] + dx, p[1] + dy] for p in i["points"]]
        if "profile" in i:  # turned: (x, r) pairs about the axis
            i["profile"] = [[p[0] + dx, p[1]] for p in i["profile"]]
            i["axis"] = i["axis"] + dy
        if "c" in i:
            i["c"] = [i["c"][0] + dx, i["c"][1] + dy]
        for cid in self._children():
            el = self._d._els.get(cid)
            if el is not None:
                el._apply_move(dx, dy)


class CenterLine(Element):
    """Centre line (thin chain line). Extension beyond the outline is added at layout from the std."""

    kind = "center"
    READ = ("type",)

    type = property(lambda s: s._intent["type"])

    def _anchors(self):
        i = self._intent
        if i["type"] == "line":
            (x1, y1), (x2, y2) = i["p1"], i["p2"]
            return {"start": tuple(i["p1"]), "end": tuple(i["p2"]), "mid": ((x1 + x2) / 2, (y1 + y2) / 2)}
        return {"center": tuple(i["c"])}

    def _apply_move(self, dx, dy):
        i = self._intent
        for k in ("p1", "p2", "c"):
            if k in i:
                i[k] = [i[k][0] + dx, i[k][1] + dy]


class View(Element):
    """A basic view. Geometry methods take view-local model coordinates."""

    kind = "view"
    LAYOUT = ("at",)
    READ = ("name", "dim")

    name = property(lambda s: s._intent["name"])

    def _apply_place(self, fields):
        at = fields.get("at")
        if at is not None:
            fields = dict(fields, at=list(resolve_point(self._d, at, what="at")))
        super()._apply_place(fields)

    def _apply_move(self, dx, dy):
        n = self.name
        if (n in ("top", "bottom") and abs(dx) > 1e-9) or (n in ("left", "right", "rear") and abs(dy) > 1e-9):
            free = "dy" if n in ("top", "bottom") else "dx"
            raise InvalidArgument(
                f"{self._id} 只能沿 {free} 方向移动，否则破坏投影对齐",
                id=self._id,
                values={"dx": dx, "dy": dy},
                hint="移动整组视图用 V.front.move(...)",
            )
        ox, oy = self._layout.get("offset", [0.0, 0.0])
        self._layout["offset"] = [ox + dx, oy + dy]

    def _children(self):
        return [e._id for e in self._d._els.values() if e is not self and e.view == self.name]

    # ---- internal helpers -------------------------------------------------------------
    def _p(self, p, what="点"):
        return resolve_point(self._d, p, view=self.name, what=what)

    def _edge(self, scope_name, intent, feature=None):
        v = self.name
        if feature is None:
            eid = self._d._alloc("E", (v,))
        else:
            eid = self._d._alloc("E", (v, scope_name))
        intent = {"view": v, **intent}
        refs = [self._id]
        if feature is not None:
            intent["feature"] = feature
            refs.append(feature)
        return self._d._add(Edge(self._d, eid, intent, refs=refs))

    def _feature(self, name, intent):
        fid = f"F.{self.name}.{check_name(name)}"
        if fid in self._d._els:
            self._d._add(Feature(self._d, fid, {}))  # raises DuplicateId with a suggestion
        f = Feature(self._d, fid, {"view": self.name, **intent, "edges": []}, refs=[self._id])
        return self._d._add(f)

    def _feature_edges(self, f, edge_intents):
        for ei in edge_intents:
            e = self._edge(f.id.split(".")[-1], ei, feature=f.id)
            f._intent["edges"].append(e.id)
        return f

    def _center(self, name, intent, refs=()):
        cid = self._d._alloc("C", (self.name,), name)
        c = CenterLine(self._d, cid, {"view": self.name, **intent}, refs=[self._id, *refs])
        return self._d._add(c)

    def _single(self, name, ftype, edge_intent, extra=None):
        if name is None:
            return self._edge(None, edge_intent)
        f = self._feature(name, {"type": ftype, **(extra or {})})
        self._feature_edges(f, [edge_intent])
        return f.edges[0]

    def _poly(self, name, ftype, pts, role, closed):
        segs = list(zip(pts, pts[1:] + pts[:1] if closed else pts[1:]))
        intents = [{"shape": "line", "p1": _pt(a), "p2": _pt(b), "role": role} for a, b in segs]
        if name is None:  # multi-edge shapes always get a feature, auto-named <type>_<n>
            name = self._d._auto_name("F", (self.name,), ftype)
        f = self._feature(name, {"type": ftype, "closed": closed, "points": [_pt(p) for p in pts]})
        return self._feature_edges(f, intents)

    # ---- public geometry API ------------------------------------------------------------
    @mutator("line")
    def line(self, p1, p2, role="thick", name=None):
        a, b = self._p(p1, "p1"), self._p(p2, "p2")
        return self._single(name, "line", {"shape": "line", "p1": _pt(a), "p2": _pt(b), "role": _role(role)})

    @mutator("polyline")
    def polyline(self, points, role="thick", name=None):
        pts = [self._p(p) for p in points]
        if len(pts) < 2:
            raise InvalidArgument("polyline 至少要 2 个点", values={"n": len(pts)})
        return self._poly(name, "polyline", pts, _role(role), closed=False)

    @mutator("polygon")
    def polygon(self, points, role="thick", name=None):
        pts = [self._p(p) for p in points]
        if len(pts) < 3:
            raise InvalidArgument("polygon 至少要 3 个点", values={"n": len(pts)})
        return self._poly(name, "polygon", pts, _role(role), closed=True)

    @mutator("rect")
    def rect(self, corner, w, h, role="thick", name=None):
        x, y = self._p(corner, "corner")
        w, h = num(w, "w"), num(h, "h")
        if w <= 0 or h <= 0:
            raise InvalidArgument("rect 的宽高必须为正", values={"w": w, "h": h})
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        return self._poly(name, "rect", pts, _role(role), closed=True)

    @mutator("circle")
    def circle(self, center, r, role="thick", name=None):
        c, r = self._p(center, "center"), num(r, "r")
        if r <= 0:
            raise InvalidArgument("圆的半径必须为正", values={"r": r})
        ei = {"shape": "circle", "c": _pt(c), "r": r, "role": _role(role)}
        return self._single(name, "circle", ei, {"closed": True, "c": _pt(c), "r": r})

    @mutator("arc")
    def arc(self, center, r, start, end, role="thick", name=None):
        c, r = self._p(center, "center"), num(r, "r")
        if r <= 0:
            raise InvalidArgument("圆弧的半径必须为正", values={"r": r})
        ei = {"shape": "arc", "c": _pt(c), "r": r, "start": num(start, "start"), "end": num(end, "end"), "role": _role(role)}
        return self._single(name, "arc", ei)

    @mutator("turned")
    def turned(self, name, profile, axis=0, role="thick"):
        """Turned (revolved) part outline from the upper half profile [(x, r), ...]."""
        pts = [(num(x, "profile.x"), num(r, "profile.r")) for x, r in profile]
        if len(pts) < 2:
            raise InvalidArgument("turned 的 profile 至少要 2 个点", values={"n": len(pts)})
        for (x0, _), (x1, _) in zip(pts, pts[1:]):
            if x1 < x0 - EPS:
                raise InvalidArgument("turned 的 profile 中 x 必须单调不减", values={"x0": x0, "x1": x1})
        if any(r <= 0 for _, r in pts):
            raise InvalidArgument("turned 的 profile 中 r 必须为正", values={"r": [r for _, r in pts]})
        ax = num(axis, "axis")
        role = _role(role)
        top, bottom = [], []
        for (x0, r0), (x1, r1) in zip(pts, pts[1:]):
            if abs(x1 - x0) > EPS:
                top.append({"shape": "line", "p1": [x0, ax + r0], "p2": [x1, ax + r1], "role": role})
                bottom.append({"shape": "line", "p1": [x0, ax - r0], "p2": [x1, ax - r1], "role": role})
        verticals = []
        xs = sorted({x for x, _ in pts})
        for x in xs:
            idx = [i for i, (px, _) in enumerate(pts) if abs(px - x) <= EPS]
            rmax = max(pts[i][1] for i in idx)
            first, last = idx[0] == 0, idx[-1] == len(pts) - 1
            corner = first or last or len(idx) > 1
            if not corner:
                i = idx[0]
                (xa, ra), (xb, rb), (xc, rc) = pts[i - 1], pts[i], pts[i + 1]
                cross = (xb - xa) * (rc - rb) - (rb - ra) * (xc - xb)
                corner = abs(cross) > 1e-9
            if corner:
                verticals.append({"shape": "line", "p1": [x, ax - rmax], "p2": [x, ax + rmax], "role": role})
        f = self._feature(name, {"type": "turned", "profile": [list(p) for p in pts], "axis": ax})
        self._feature_edges(f, top + bottom + verticals)
        c = self._center(name, {"type": "line", "p1": [pts[0][0], ax], "p2": [pts[-1][0], ax]}, refs=[f.id])
        f._intent["centers"] = [c.id]
        return f

    @mutator("centerline")
    def centerline(self, p1, p2, name=None):
        a, b = self._p(p1, "p1"), self._p(p2, "p2")
        return self._center(name, {"type": "line", "p1": _pt(a), "p2": _pt(b)})

    @mutator("center_mark")
    def center_mark(self, center, r, name=None):
        c, r = self._p(center, "center"), num(r, "r")
        if r <= 0:
            raise InvalidArgument("center_mark 的半径必须为正", values={"r": r})
        return self._center(name, {"type": "mark", "c": _pt(c), "r": r})

    @mutator("holes_on_circle")
    def holes_on_circle(self, name, center, pcd, n, d, start=90, role="thick"):
        c = self._p(center, "center")
        pcd, dd, start = num(pcd, "pcd"), num(d, "d"), num(start, "start")
        n = int(num(n, "n"))
        if n < 1 or pcd <= 0 or dd <= 0:
            raise InvalidArgument("holes_on_circle 需要 n≥1、pcd>0、d>0", values={"n": n, "pcd": pcd, "d": dd})
        R = pcd / 2
        centers = []
        for k in range(n):
            a = math.radians(start + 360.0 * k / n)
            centers.append((c[0] + R * math.cos(a), c[1] + R * math.sin(a), a))
        f = self._feature(
            name, {"type": "holes", "c": _pt(c), "pcd": pcd, "n": n, "d": dd, "start": start}
        )
        self._feature_edges(f, [{"shape": "circle", "c": [x, y], "r": dd / 2, "role": _role(role)} for x, y, _ in centers])
        cids = [self._center(name, {"type": "circle", "c": _pt(c), "r": R}, refs=[f.id]).id]
        for k, (x, y, a) in enumerate(centers, 1):
            ux, uy = math.cos(a), math.sin(a)
            h = dd / 2
            cl = CenterLine(
                self._d,
                f"C.{self.name}.{name}.{k}",
                {"view": self.name, "type": "line", "p1": [x - h * ux, y - h * uy], "p2": [x + h * ux, y + h * uy]},
                refs=[self._id, f.id],
            )
            cids.append(self._d._add(cl).id)
        f._intent["centers"] = cids
        return f
