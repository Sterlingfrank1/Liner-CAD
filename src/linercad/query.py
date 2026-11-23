"""References and queries (SPEC §4.4): d["ID"], d.q.<kind>(...), geometric selectors, d.near()."""

from __future__ import annotations

import math

from .errors import CountMismatch, InvalidArgument, UnknownAttribute
from .model import num

KINDS = {
    "views": ("view", None),
    "features": ("feature", None),
    "edges": ("edge", None),
    "lines": ("edge", "line"),
    "circles": ("edge", "circle"),
    "arcs": ("edge", "arc"),
    "centers": ("center", None),
    "dims": ("dim", None),
    "notes": ("note", None),
    "hatches": ("hatch", None),
    "sections": ("section", None),
    "cells": ("table.cell", None),
    "all": (None, None),
}


def facets(el) -> dict:
    """Flat attributes a query can filter on."""
    i = el._intent
    f = {"id": el.id, "kind": el.kind, "view": i.get("view")}
    for k in ("role", "type", "shape", "text", "field", "name", "value", "dir"):
        if k in i and not isinstance(i[k], (dict, list)):
            f[k] = i[k]
    if el.kind == "edge":
        f.update(shape=el.shape, role=el.role, length=el.length, dir=el.dir)
        f["x"], f["y"] = el.mid
        if el.r is not None:
            f["r"] = el.r
        if el.feature:
            f["feature"] = el.feature
    if el.kind == "feature":
        f["closed"] = el.closed
    for k in ("side", "row", "offset", "at"):
        v = el._layout.get(k, el._resolved.get(k))
        if v is not None:
            f[k] = v
    return f


def _match(el, conds, tol):
    f = facets(el)
    for k, want in conds.items():
        if k == "tag":
            if want not in el._tags:
                return False
            continue
        if k not in f:
            return False
        have = f[k]
        if isinstance(want, bool) or isinstance(have, bool):
            if have != want:
                return False
        elif (
            isinstance(want, (int, float))
            or hasattr(want, "__float__")
            and not isinstance(want, str)
        ):
            try:
                if abs(float(have) - float(want)) > tol:
                    return False
            except (TypeError, ValueError):
                return False
        elif have != want:
            return False
    return True


def _seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def model_dist(el, p) -> float:
    """Distance from a view-local point to an element's model geometry."""
    i = el._intent
    if el.kind in ("edge", "center"):
        shape = i.get("shape") or i.get("type")
        if shape == "line":
            return _seg_dist(p, i["p1"], i["p2"])
        if shape in ("circle", "mark"):
            dc = math.hypot(p[0] - i["c"][0], p[1] - i["c"][1])
            return abs(dc - i["r"]) if shape == "circle" else dc
        if shape == "arc":
            a = math.degrees(math.atan2(p[1] - i["c"][1], p[0] - i["c"][0]))
            if (a - i["start"]) % 360 <= ((i["end"] - i["start"]) % 360 or 360):
                return abs(math.hypot(p[0] - i["c"][0], p[1] - i["c"][1]) - i["r"])
            return min(math.dist(p, el.start), math.dist(p, el.end))
    if el.kind == "feature":
        ds = [model_dist(e, p) for e in el.edges]
        return min(ds) if ds else math.inf
    pts = [i[k] for k in ("p1", "p2", "anchor") if isinstance(i.get(k), list)]
    if pts:
        return min(math.dist(p, q) for q in pts)
    return math.inf


def describe(el) -> str:
    f = facets(el)
    parts = [el.id]
    for k in ("shape", "type", "role", "length", "r", "dir", "text"):
        if k in f and f[k] is not None:
            v = f[k]
            parts.append(f"{k}={round(v, 3) if isinstance(v, float) else v}")
    if "x" in f:
        parts.append(f"mid=({round(f['x'], 3)}, {round(f['y'], 3)})")
    return " ".join(parts)


class Query:
    """An ordered, filterable list of elements."""

    def __init__(self, d, els, label, view=None, near=None):
        self._d = d
        self._els = list(els)
        self._label = label
        self._view = view
        self._near = near  # (x, y, r, pool) when near() was used

    def where(self, pred=None, tol=0.01, **conds):
        tol = num(tol, "tol")
        if pred is not None and not callable(pred):
            raise InvalidArgument("where() 的位置参数必须是函数，条件用关键字给出")
        if conds:
            known = set()
            for e in self._els:
                known |= set(facets(e))
            known.add("tag")
            bad = [k for k in conds if k not in known] if self._els else []
            if bad:
                raise InvalidArgument(
                    f"where() 不认识条件 {', '.join(bad)}", candidates=sorted(known)
                )
        out = [e for e in self._els if (pred is None or pred(e)) and _match(e, conds, tol)]
        desc = ", ".join(f"{k}={v}" for k, v in conds.items()) or "fn"
        return Query(self._d, out, f"{self._label}.where({desc})", self._view, self._near)

    def near(self, x, y, r=2.0):
        p = (num(x, "x"), num(y, "y"))
        r = num(r, "r")
        views = {e.view for e in self._els}
        if self._view is None and len(views) > 1:
            raise InvalidArgument(
                "near() 用视图局部坐标，先用 view=... 限定到一个视图",
                candidates=sorted(v for v in views if v),
            )
        scored = sorted(
            ((model_dist(e, p), k, e) for k, e in enumerate(self._els)), key=lambda t: t[:2]
        )
        out = [e for dist, _, e in scored if dist <= r]
        return Query(
            self._d, out, f"{self._label}.near({p[0]}, {p[1]})", self._view, (p, r, scored)
        )

    def exactly(self, n):
        if len(self._els) != n:
            cands = [describe(e) for e in self._els[:10]]
            values = {"expected": n, "found": len(self._els)}
            if self._near is not None:
                p, r, scored = self._near
                cands += [
                    f"{describe(e)} dist={round(dist, 3)}" for dist, _, e in scored[:5] if dist > r
                ]
                values["near"] = list(p)
            raise CountMismatch(
                f"{self._label} 期望 {n} 个，实际 {len(self._els)} 个",
                candidates=cands,
                values=values,
                hint="调整 where/near 条件，或给几何起名后用 ID 引用",
            )
        return self

    def one(self):
        return self.exactly(1)._els[0]

    def first(self):
        if not self._els:
            self.exactly(1)
        return self._els[0]

    def ids(self):
        return [e.id for e in self._els]

    def __len__(self):
        return len(self._els)

    def __iter__(self):
        return iter(self._els)

    def __getitem__(self, k):
        return self._els[k]

    def __repr__(self):
        return f"<Query {self._label}: {self.ids()}>"


class QueryRoot:
    """``d.q``: one method per kind, e.g. ``d.q.dims(view="front", role="position")``."""

    def __init__(self, d):
        self._d = d

    def detail_sources(self, letter):
        """Parent elements behind a detail view (D7): d.q.detail_sources("I")."""
        from .views import detail_sources

        return Query(self._d, detail_sources(self._d, letter), f"q.detail_sources({letter})")

    def __getattr__(self, name):
        if name.startswith("_") or name not in KINDS:
            raise UnknownAttribute(f"d.q 没有种类 {name}", candidates=list(KINDS))
        kind, shape = KINDS[name]

        def run(**conds):
            els = [
                e
                for e in self._d._els.values()
                if (kind is None or e.kind == kind)
                and (shape is None or e._intent.get("shape") == shape)
            ]
            q = Query(self._d, els, f"q.{name}()", view=conds.get("view"))
            return q.where(**conds) if conds else q

        return run

    def __dir__(self):
        return [*KINDS, "detail_sources"]


def near_sheet(d, x, y, r):
    """Elements whose resolved sheet bbox lies within r of (x, y), nearest and smallest first."""
    out = []
    for k, e in enumerate(d._els.values()):
        b = e._resolved.get("bbox")
        if not b:
            continue
        dx = max(b[0] - x, 0, x - b[2])
        dy = max(b[1] - y, 0, y - b[3])
        dist = math.hypot(dx, dy)
        if dist <= r:
            out.append((dist, (b[2] - b[0]) * (b[3] - b[1]), k, e))
    return [e for *_, e in sorted(out, key=lambda t: t[:3])]
