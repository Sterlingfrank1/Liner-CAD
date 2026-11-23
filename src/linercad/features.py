"""Conventional representations, first batch (SPEC M1 §4): threads, tapped holes, center holes,
keyways, splines. Each tool draws per the GB/T 4459.x rules with values from ``linercad.res`` and
yields a semantic feature ``F.<view>.<name>``. Lines that do not exist on the real part carry the
``conv`` tag; real 3D edges a convention leaves out are covered by ``intent.mask``."""

from __future__ import annotations

import functools
import math

from . import res
from .errors import InvalidArgument
from .geometry import Feature, View
from .model import check_name, num

GAP = 0.7  # mm on paper between parallel lines (GB/T 4457.4)


def _feat(view, name, ftype, intent, edges):
    f = view._feature(check_name(name), {"type": ftype, **intent})
    view._feature_edges(f, edges)
    return f


def _line(p, q, role, conv=False):
    e = {"shape": "line", "p1": [p[0], p[1]], "p2": [q[0], q[1]], "role": role}
    if conv:
        e["tags"] = ["conv"]
    return e


def _rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def thread(view, name, spec, x0, x1, axis=0, kind="ext", cls=None, cut=True):
    t = res.thread(spec, cls=cls) if cls else res.thread(spec)
    cls = cls or ("6g" if kind == "ext" else "6H")
    if kind not in ("ext", "int"):
        raise InvalidArgument(
            "kind 只能是 'ext'（外螺纹）或 'int'（内螺纹）", candidates=["ext", "int"]
        )
    x0, x1, ax = num(x0, "x0"), num(x1, "x1"), num(axis, "axis")
    d, d1 = t["d"], t["d1"]
    rmaj = d / 2
    edges = []
    if kind == "ext":
        rmin = min(d1 / 2, rmaj - GAP / view.scale)
        for sg in (1, -1):
            edges.append(_line((x0, ax + sg * rmin), (x1, ax + sg * rmin), "thin", True))
        edges.append(_line((x1, ax - rmaj), (x1, ax + rmaj), "thick", True))
        mask = None
    else:  # the bore at the minor diameter is the agent's; add the major lines and the end line
        rmaj = max(rmaj, d1 / 2 + GAP / view.scale)
        maj, term = ("thin", "thick") if cut else ("hidden", "hidden")
        for sg in (1, -1):
            edges.append(_line((x0, ax + sg * rmaj), (x1, ax + sg * rmaj), maj, True))
        edges.append(_line((x1, ax - rmaj), (x1, ax + rmaj), term, True))
        mask = None
    intent = {
        "spec": spec,
        "kind": kind,
        "d": d,
        "P": t["P"],
        "d1": d1,
        "d2": t["d2"],
        "coarse": t.get("coarse", True),
        "cls": cls,
        "x0": x0,
        "x1": x1,
        "axis": ax,
        "std": t.get("std"),
        "mask": mask,
    }
    return _feat(view, name, "thread", intent, edges)


def thread_end(view, name, c, spec, kind="ext"):
    t = res.thread(spec)
    c = view._p(c, "c")
    d, d1 = t["d"], t["d1"]
    rmaj, rmin = d / 2, min(d1 / 2, d / 2 - GAP / view.scale)
    if kind == "ext":
        full, part = (rmaj, "thick"), (rmin, "thin")
    else:
        full, part = (d1 / 2, "thick"), (max(rmaj, d1 / 2 + GAP / view.scale), "thin")
    edges = [
        {"shape": "circle", "c": list(c), "r": full[0], "role": full[1]},
        {
            "shape": "arc",
            "c": list(c),
            "r": part[0],
            "start": 90.0,
            "end": 0.0,
            "role": part[1],
            "tags": ["conv"],
        },
    ]
    # the 3D chamfer circle (between the two diameters) is not drawn by convention
    r_lo, r_hi = min(full[0], part[0]), max(full[0], part[0])
    mask = _ring(c, r_lo - 1.0, r_hi - 0.01) if kind == "ext" else _ring(c, r_lo + 0.01, r_hi + 1.0)
    intent = {
        "spec": spec,
        "kind": kind,
        "d": d,
        "P": t["P"],
        "d1": d1,
        "d2": t["d2"],
        "coarse": t.get("coarse", True),
        "cls": "6g" if kind == "ext" else "6H",
        "c": list(c),
        "std": t.get("std"),
        "mask": mask,
        "end_view": True,
    }
    return _feat(view, name, "thread", intent, edges)


def _ring(c, r0, r1, n=48):
    """Annulus as one polygon (outer ccw, then inner cw) — geocmp drops model edges inside."""
    out = [
        [c[0] + r1 * math.cos(2 * math.pi * k / n), c[1] + r1 * math.sin(2 * math.pi * k / n)]
        for k in range(n + 1)
    ]
    inn = [
        [c[0] + r0 * math.cos(-2 * math.pi * k / n), c[1] + r0 * math.sin(-2 * math.pi * k / n)]
        for k in range(n + 1)
    ]
    return out + inn


def tapped_hole(view, name, at, dir, spec, depth, drill_depth=None, cut=True):
    """Tapped hole from the entry point ``at`` along dir (+x/-x/+y/-y) in a non-revolved view."""
    t = res.thread(spec)
    dirs = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}
    if dir not in dirs:
        raise InvalidArgument("dir 只能是 +x / -x / +y / -y", candidates=list(dirs))
    u = dirs[dir]
    n = (-u[1], u[0])
    p = view._p(at, "at")
    depth = num(depth, "depth")
    dd = num(drill_depth, "drill_depth") if drill_depth is not None else depth + 0.5 * t["d"]
    r1, R = t["d1"] / 2, max(t["d"] / 2, t["d1"] / 2 + GAP / view.scale)
    tip = r1 / math.tan(math.radians(60))

    def P(a, b):  # along, across → view coordinates
        return (p[0] + u[0] * a + n[0] * b, p[1] + u[1] * a + n[1] * b)

    wall, maj, term = ("thick", "thin", "thick") if cut else ("hidden", "hidden", "hidden")
    edges = []
    for sg in (1, -1):
        edges.append(_line(P(0, sg * r1), P(dd, sg * r1), wall))
        edges.append(_line(P(dd, sg * r1), P(dd + tip, 0), wall))
        edges.append(_line(P(0, sg * R), P(depth, sg * R), maj, True))
    edges.append(_line(P(dd, -r1), P(dd, r1), wall))
    edges.append(_line(P(depth, -R), P(depth, R), term, True))
    pts = [list(P(0, r1)), list(P(dd, r1)), list(P(dd + tip, 0)), list(P(dd, -r1)), list(P(0, -r1))]
    intent = {
        "spec": spec,
        "kind": "int",
        "d": t["d"],
        "P": t["P"],
        "d1": t["d1"],
        "d2": t["d2"],
        "coarse": t.get("coarse", True),
        "cls": "6H",
        "depth": depth,
        "drill_depth": dd,
        "closed": True,
        "points": pts,
        "std": t.get("std"),
        "mask": None,
    }
    return _feat(view, name, "tapped_hole", intent, edges)


def center_hole(view, name, on, end="left", type="A", d=2.5, keep=True, length=None):
    """Simplified representation of a standard centre hole (GB/T 4459.5): a leader from the axis
    end, the keep symbol and the designation ``GB/T 4459.5-<type><d>/<D>``; the real cone / arc /
    thread edges are not drawn and ``intent.mask`` covers them. ``type`` = "A" / "B" / "R" / "C";
    type C needs the thread length ``length`` for its designation ("CM6L10/10.5"). The sizes come
    from ``res.center_hole`` (GB/T 145-2001)."""
    from .geometry import Feature as F

    body = view._d[on] if isinstance(on, str) else on
    if not isinstance(body, F) or body.type != "turned":
        raise InvalidArgument(
            "center_hole 的 on 应为回转体特征（turned）", id=getattr(body, "id", None)
        )
    if end not in ("left", "right"):
        raise InvalidArgument("end 只能是 left / right", candidates=["left", "right"])
    if type == "C" and length is None:
        raise InvalidArgument(
            "C 型中心孔的代号需要螺纹长度 L（GB/T 4459.5-1999 4.2，如 CM6L10/10.5）",
            values={"type": type, "d": d},
            hint="给 length=10（mm）",
        )
    # bool is a subclass of int: reject it before num() turns True into 1.0
    if isinstance(d, bool):
        raise InvalidArgument(f"中心孔 d 应为数或参数表达式，得到 {d!r}", values={"d": d})
    if isinstance(length, bool):
        raise InvalidArgument(
            f"中心孔 length 应为数或参数表达式，得到 {length!r}", values={"length": length}
        )
    if length is not None:
        length = num(length, "length")  # a parameter expression is resolved; NaN / inf rejected
    if not (type == "C" and isinstance(d, str)):
        d = num(d, "d")  # a parameter expression is resolved (type C also takes "M6")
    ch = res.center_hole(type, d, length=length)
    prof, ax = body._intent["profile"], body._intent["axis"]
    x = prof[0][0] if end == "left" else prof[-1][0]
    sg = 1 if end == "left" else -1
    D = ch["D"]
    depth = (
        D / 2 / math.tan(math.radians(30)) + ch["d"] * 1.5
    )  # cone plus pilot, generous for the mask
    if length is not None:  # type C: the mask also covers the whole threaded length L
        depth = max(depth, ch["l"] + length + GAP)
    mask = _rect(x, ax - D / 2 - 0.5, x + sg * depth, ax + D / 2 + 0.5)
    intent = {
        "designation": ch["designation"],
        "form": ch["type"],
        "d": ch["d"],
        "D": D,
        "keep": keep,
        "on": body.id,
        "end": end,
        "x": x,
        "axis": ax,
        "std": ch.get("std"),
        "mark_std": "GB/T 4459.5",
        "mask": [list(p) for p in mask],
    }
    # the sizes the resource library returned are part of the feature's semantics, not just the text
    for key in ("D1", "D2", "D3", "l2", "l_min", "d2", "r_max", "r_min", "l", "t"):
        if key in ch:
            intent[key] = ch[key]
    if "thread" in ch:
        intent["thread"] = ch["thread"]
    if length is not None:
        intent["length"] = length
    f = view._feature(check_name(name), {"type": "center_hole", **intent})
    f._refs.append(body.id)
    return f


def keyway(view, name, x0, length, d, axis=0, facing="viewer", kind="shaft"):
    if kind != "shaft":
        raise InvalidArgument(
            "轴向视图里的 keyway 只画轴上键槽；轮毂键槽用 turned(hub_keyway=...) 和 keyway_end",
            candidates=["shaft"],
        )
    if facing != "viewer":
        raise InvalidArgument("M1 只支持 facing='viewer'（键槽朝观察者）", candidates=["viewer"])
    k = res.key(num(d, "d"))
    x0, L, ax = num(x0, "x0"), num(length, "length"), num(axis, "axis")
    b = k["b"]
    if L <= b:
        raise InvalidArgument(f"键槽长度 {L:g} 应大于槽宽 {b:g}", values={"length": L, "b": b})
    r = b / 2
    edges = [
        _line((x0 + r, ax + r), (x0 + L - r, ax + r), "thick"),
        _line((x0 + r, ax - r), (x0 + L - r, ax - r), "thick"),
        {"shape": "arc", "c": [x0 + r, ax], "r": r, "start": 90.0, "end": 270.0, "role": "thick"},
        {
            "shape": "arc",
            "c": [x0 + L - r, ax],
            "r": r,
            "start": 270.0,
            "end": 90.0,
            "role": "thick",
        },
    ]
    intent = {
        "kind": "shaft",
        "facing": facing,
        "d": num(d, "d"),
        "b": b,
        "h": k["h"],
        "t1": k["t1"],
        "t2": k["t2"],
        "x0": x0,
        "length": L,
        "axis": ax,
        "std": k.get("std"),
        "tol_b": k.get("width_fit", {}).get("normal", {}).get("shaft", "N9"),
        "t1_dev": k.get("t1_dev"),
        "t2_dev": k.get("t2_dev"),
    }
    return _feat(view, name, "keyway", intent, edges)


def _notched_circle(c, r, b, depth, ang):
    """Closed outline of a circle with a rectangular notch (width b, radial depth) centred at
    angle ``ang`` (deg). Positive depth cuts inward (shaft keyway), negative outward (hub)."""
    u = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
    t = (-u[1], u[0])
    half = math.degrees(math.asin(min(1.0, b / 2 / r)))
    a0, a1 = ang + half, ang - half + 360
    pts = []
    n = 72
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * k / n)
        pts.append([c[0] + r * math.cos(a), c[1] + r * math.sin(a)])
    inner = r - depth  # GB/T 1095: t1 / t2 measured from the surface on the key centre line
    pts.append([c[0] + u[0] * inner - t[0] * b / 2, c[1] + u[1] * inner - t[1] * b / 2])
    pts.append([c[0] + u[0] * inner + t[0] * b / 2, c[1] + u[1] * inner + t[1] * b / 2])
    seg = {
        "arc": {
            "shape": "arc",
            "c": list(c),
            "r": r,
            "start": a0 % 360,
            "end": a1 % 360,
            "role": "thick",
        },
        "lines": [
            _line(pts[n], pts[n + 1], "thick"),
            _line(pts[n + 1], pts[n + 2], "thick"),
            _line(pts[n + 2], pts[0], "thick"),
        ],
    }
    return pts, seg


def shaft_cut(view, name, d, keyway=None, axis=None):
    """Shaft cross-section in a removed-section view: circle, keyway notch, hatch, centre mark."""
    if view._intent.get("aux") != "section":
        raise InvalidArgument(
            "shaft_cut 只用在移出断面视图里（d.removed_section 返回的视图）", id=view.id
        )
    D = num(d, "d")
    r = D / 2
    kw = None
    if keyway is not None:
        kw = view._d[keyway] if isinstance(keyway, str) else keyway
        if not isinstance(kw, Feature) or kw.type != "keyway":
            raise InvalidArgument(
                "keyway 应为键槽特征（v.keyway 返回的）", id=getattr(kw, "id", None)
            )
    if axis is None:
        axis = kw._intent["axis"] if kw is not None else 0.0
    t = view._intent["axes"]["v"]
    a = view._intent["trace"][0]
    c = (0.0, a[0] * t[0] + num(axis, "axis") * t[1])  # the shaft axis in local (u, v), SPEC §5
    if kw is None:
        f = view._feature(
            check_name(name), {"type": "shaft_cut", "d": D, "closed": True, "c": list(c), "r": r}
        )
        view._feature_edges(f, [{"shape": "circle", "c": list(c), "r": r, "role": "thick"}])
        loops = [{"ref": f.id}]
    else:
        # keyway faces the parent's viewer: local u = depth × axes.depth (SPEC §5)
        ang = 0.0 if view._intent["axes"]["depth"] > 0 else 180.0
        pts, seg = _notched_circle(c, r, kw._intent["b"], kw._intent["t1"], ang)
        f = view._feature(
            check_name(name),
            {
                "type": "shaft_cut",
                "d": D,
                "closed": True,
                "points": pts,
                "keyway": kw.id,
                "b": kw._intent["b"],
                "t1": kw._intent["t1"],
                "notch_angle": ang,
                "c": list(c),
            },
        )
        view._feature_edges(f, [seg["arc"], *seg["lines"]])
        f._refs.append(kw.id)
        loops = [{"points": pts}]
    from .annotate import Hatch

    hid = f"H.{view.name}.{name}"
    view._d._add(Hatch(view._d, hid, {"view": view.name, "loops": loops}, refs=[view.id, f.id]))
    f._intent["hatch"] = hid
    cm = view._center(f"{name}_c", {"type": "mark", "c": list(c), "r": r}, refs=[f.id])
    f._intent["centers"] = [cm.id]
    return f


def keyway_end(view, name, c, d, kind="hub", angle=90):
    """Hub keyway in the end view: the bore circle with its rectangular notch."""
    if kind != "hub":
        raise InvalidArgument("keyway_end 画轮毂键槽（kind='hub'）", candidates=["hub"])
    D = num(d, "d")
    k = res.key(D)
    c = view._p(c, "c")
    pts, seg = _notched_circle(c, D / 2, k["b"], -k["t2"], num(angle, "angle"))
    intent = {
        "kind": "hub",
        "d": D,
        "b": k["b"],
        "h": k["h"],
        "t1": k["t1"],
        "t2": k["t2"],
        "c": list(c),
        "closed": True,
        "points": pts,
        "std": k.get("std"),
        "tol_b": k.get("width_fit", {}).get("normal", {}).get("hub", "JS9"),
        "t2_dev": k.get("t2_dev"),
    }
    return _feat(view, name, "keyway", intent, [seg["arc"], *seg["lines"]])


def spline(view, name, spec, x0, x1, axis=0):
    s = res.spline(spec)
    x0, x1, ax = num(x0, "x0"), num(x1, "x1"), num(axis, "axis")
    rD, rd = s["D"] / 2, s["d"] / 2
    rmin = min(rd, rD - GAP / view.scale)
    edges = [_line((x0, ax + sg * rmin), (x1, ax + sg * rmin), "thin", True) for sg in (1, -1)]
    edges.append(_line((x1, ax - rD), (x1, ax + rD), "thin", True))  # GB/T 4459.3: thin end line
    lo, hi = sorted((x0, x1))
    mask = _rect(lo - 0.01, ax - rD + 0.01, hi + 0.01, ax + rD - 0.01)
    intent = {
        **{k: s[k] for k in ("N", "d", "D", "B")},
        "series": s.get("series"),
        "spec": spec,
        "x0": x0,
        "x1": x1,
        "axis": ax,
        "std": s.get("std"),
        "mask": mask,
        "fits": [
            s.get("tol", {}).get("shaft", {}).get("sliding", {}).get(k, f)
            for k, f in (("d", "f7"), ("D", "a11"), ("B", "d10"))
        ],
    }
    return _feat(view, name, "spline", intent, edges)


def spline_end(view, name, c, spec):
    s = res.spline(spec)
    c = view._p(c, "c")
    N, rD, rd, B = s["N"], s["D"] / 2, s["d"] / 2, s["B"]
    pD, pd = math.degrees(math.asin(B / 2 / rD)), math.degrees(math.asin(B / 2 / rd))

    def P(r, a):
        return [c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a))]

    edges, pts = [], []
    for k in range(N):
        th = 90 + 360 * k / N
        nxt = 90 + 360 * (k + 1) / N
        edges.append(_line(P(rd, th - pd), P(rD, th - pD), "thick"))
        edges.append(
            {
                "shape": "arc",
                "c": list(c),
                "r": rD,
                "start": (th - pD) % 360,
                "end": (th + pD) % 360,
                "role": "thick",
            }
        )
        edges.append(_line(P(rD, th + pD), P(rd, th + pd), "thick"))
        edges.append(
            {
                "shape": "arc",
                "c": list(c),
                "r": rd,
                "start": (th + pd) % 360,
                "end": (nxt - pd) % 360,
                "role": "thick",
            }
        )
        for j in range(5):
            pts.append(P(rD, th - pD + 2 * pD * j / 4))
        for j in range(9):
            pts.append(P(rd, th + pd + (nxt - pd - th - pd) * j / 8))
    intent = {
        **{k: s[k] for k in ("N", "d", "D", "B")},
        "spec": spec,
        "c": list(c),
        "closed": True,
        "points": pts,
        "std": s.get("std"),
        "end_view": True,
    }
    return _feat(view, name, "spline", intent, edges)


def thread_mesh(
    view, name, spec, screw, hole, axis=0, outer=None, cls_ext=None, cls_int=None, cut=True
):
    """GB/T 4459.1 screwed connection in an assembly section (a screw threaded into a tapped
    hole).  screw=(x0, x1) is the external-thread extent, hole=(x0, x1) the tapped-hole extent;
    the engaged length is their axial overlap (also exposed by assembly.thread_engagement).

    Engaged portion: drawn as the external thread (major diameter thick, minor thin); the
    internal thread lines are not repeated there.  Unengaged portions keep their own drawing
    (internal: minor thick, major thin).  The hole end face line stops at the thread minor
    diameter (outer is the connected part's outer radius).  All conventional lines carry the
    conv tag; assembly.thread_hatch_loops() gives the matching section hatch boundary at the
    external thread crest."""
    from .assembly import thread_engagement

    t = res.thread(spec)
    cls_ext = cls_ext or "6g"
    cls_int = cls_int or "6H"
    res.thread(spec, cls=cls_ext)  # validates the class with candidates
    res.thread(spec, cls=cls_int)

    def pair(v, what):
        try:
            vals = [num(c, what) for c in v]
        except TypeError:
            raise InvalidArgument(f"{what} 应为 (x0, x1) 两元组", values={what: repr(v)})
        if len(vals) != 2:
            raise InvalidArgument(f"{what} 应为 (x0, x1) 两元组", values={what: repr(v)})
        return sorted(vals)

    a, b = pair(screw, "screw")
    c, e = pair(hole, "hole")
    ax = num(axis, "axis")
    eng0, eng1 = thread_engagement((a, b), (c, e))
    angle = view.scale
    d, d1 = t["d"], t["d1"]
    rmaj = d / 2
    rmin = min(d1 / 2, rmaj - GAP / angle)
    rcrest = d1 / 2  # internal thread crest (minor), thick in the unengaged internal part
    rroot = max(rmaj, rcrest + GAP / angle)  # internal thread root (major), thin
    outer = num(outer, "outer") if outer is not None else None
    if outer is not None and outer <= rcrest + 1e-9:
        raise InvalidArgument("outer 必须大于螺纹小径半径", values={"outer": outer, "d1/2": rcrest})

    edges = []

    def bands(x0, x1, r, role):
        for sg in (1, -1):
            edges.append(_line((x0, ax + sg * r), (x1, ax + sg * r), role, True))

    # the external thread runs over its whole extent; in the engaged interval it is also the
    # representation of the connection (no internal crest/root lines are added there)
    bands(a, b, rmaj, "thick")
    bands(a, b, rmin, "thin")
    edges.append(_line((b, ax - rmaj), (b, ax + rmaj), "thick", True))  # thread termination

    # unengaged internal thread keeps its own representation
    for u, v in ((c, eng0), (eng1, e)):
        if v - u > 1e-9:
            bands(u, v, rcrest, "thick")
            bands(u, v, rroot, "thin")
    edges.append(_line((e, ax - rroot), (e, ax + rroot), "thick", True))

    # the connected part's end face line at the tapped-hole mouth: only down to the minor dia.
    if outer is not None:
        for sg in (1, -1):
            edges.append(_line((c, ax + sg * rcrest), (c, ax + sg * outer), "thick", True))

    intent = {
        "spec": spec,
        "kind": "thread_mesh",
        "d": d,
        "P": t["P"],
        "d1": d1,
        "d2": t["d2"],
        "coarse": t.get("coarse", True),
        "std": t.get("std"),
        "x0": a,
        "x1": b,
        "axis": ax,
        "screw": [a, b],
        "hole": [c, e],
        "engaged": [eng0, eng1],
        "outer": outer,
        "cls": cls_ext,
        "cls_ext": cls_ext,
        "cls_int": cls_int,
        "cut": bool(cut),
        "mask": None,
    }
    return _feat(view, name, "thread_mesh", intent, edges)


def install():
    """Attach the tools to View (kept here so geometry.py stays about plain geometry)."""
    from .record import mutator

    def wrap(op, fn):
        @functools.wraps(fn)  # keeps fn's signature for the recorder
        def method(self, *a, **k):
            return fn(self, *a, **k)

        return mutator(op)(method)

    for op, fn in (
        ("thread_mesh", thread_mesh),
        ("thread", thread),
        ("thread_end", thread_end),
        ("tapped_hole", tapped_hole),
        ("center_hole", center_hole),
        ("keyway", keyway),
        ("keyway_end", keyway_end),
        ("shaft_cut", shaft_cut),
        ("spline", spline),
        ("spline_end", spline_end),
    ):
        setattr(View, op, wrap(op, fn))


install()
