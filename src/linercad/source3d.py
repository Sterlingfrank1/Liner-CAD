"""3D geometry source: ``d.model`` + ``V.project`` (SPEC M3 §1.1).

The model (``model.py`` with ``model(**P)``, or a STEP file) is projected with OCC hidden-line
removal. Projected edges keep their curve type (line / circle / arc; other curves become short
lines tagged ``approx``) and record where they came from in ``intent.src3d``.
"""

from __future__ import annotations

import hashlib
import json
import math
import runpy
from pathlib import Path

from .errors import InvalidArgument, LinerError, NotFound
from .hlr import _t
from .model import DRAW_DIR, Element, check_name

CACHE_VERSION = 1
TOL = 0.01  # curve fitting, mm
MATCH = 0.05  # projected edge ↔ model edge, mm


class MissingExtra(LinerError):
    code = "missing_extra"


def need_3d():
    try:
        import build123d  # noqa: F401
    except ImportError:
        raise MissingExtra(
            "3D 来源需要可选依赖 build123d（linercad[3d]）",
            hint='uv add "linercad[3d]"（pip: pip install "linercad[3d]"）',
        )


class Model(Element):
    kind = "model"
    READ = ("path", "hash")

    path = property(lambda s: s._intent["path"])
    hash = property(lambda s: s._intent["hash"])


def _dir() -> Path:
    return Path(DRAW_DIR.get() or ".")


def drawing_model(d, path, name="main"):
    need_3d()
    name = check_name(name)
    p = _dir() / str(path)
    if not p.is_file():
        raise NotFound(f"模型文件 {path} 不存在（相对图纸目录）", values={"path": str(path)})
    if p.suffix.lower() not in (".py", ".step", ".stp"):
        raise InvalidArgument(
            "模型只能是 model.py（定义 model(**P)）或 .step/.stp",
            values={"path": str(path)},
            candidates=[".py", ".step", ".stp"],
        )
    h = hashlib.sha1(p.read_bytes()).hexdigest()[:12]
    return d._add(Model(d, f"M.{name}", {"path": str(path), "hash": h}))


_SHAPES: dict = {}


def load_shape(d, mid):
    """The build123d shape of model ``mid`` at the drawing's current parameter values."""
    m = d._els.get(mid)
    if m is None or m.kind != "model":
        raise NotFound(
            f"模型 {mid} 不存在，先 d.model('model.py')",
            id=mid,
            candidates=[e.id for e in d._els.values() if e.kind == "model"],
        )
    p = _dir() / m.path
    P = d.P.values()
    key = (str(p.resolve()), m.hash, tuple(sorted(P.items())))
    if key in _SHAPES:
        return _SHAPES[key]
    if p.suffix.lower() == ".py":
        ns = runpy.run_path(str(p), run_name="linercad_model")
        fn = ns.get("model")
        if not callable(fn):
            raise InvalidArgument(f"{m.path} 里没有 model(**P) 函数", id=mid)
        import inspect

        sig = inspect.signature(fn)
        if any(x.kind == x.VAR_KEYWORD for x in sig.parameters.values()):
            kw = P
        else:
            kw = {k: v for k, v in P.items() if k in sig.parameters}
        shape = fn(**kw)
    else:
        from build123d import import_step

        shape = import_step(str(p))
    if not hasattr(shape, "wrapped"):
        raise InvalidArgument(f"{m.path} 的 model() 应返回 build123d 形体", id=mid)
    if len(_SHAPES) > 32:
        _SHAPES.clear()
    _SHAPES[key] = shape
    return shape


# ---- 2D curve fitting ----------------------------------------------------------------------------


def _samples(edge, n=None):
    L = edge.length
    n = n or max(16, min(400, int(L / 0.5)))
    return [(q.X, q.Y) for q in (edge @ (k / n) for k in range(n + 1))]


def _circ3(a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    dd = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(dd) < 1e-12:
        return None
    ux = (
        (ax * ax + ay * ay) * (by - cy)
        + (bx * bx + by * by) * (cy - ay)
        + (cx * cx + cy * cy) * (ay - by)
    ) / dd
    uy = (
        (ax * ax + ay * ay) * (cx - bx)
        + (bx * bx + by * by) * (ax - cx)
        + (cx * cx + cy * cy) * (bx - ax)
    ) / dd
    return (ux, uy), math.dist((ux, uy), a)


def _seg_dist(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def _dp(pts, tol):
    """Douglas–Peucker simplification."""
    if len(pts) < 3:
        return list(pts)
    a, b = pts[0], pts[-1]
    k, dm = 0, -1.0
    for i in range(1, len(pts) - 1):
        dd = _seg_dist(pts[i], a, b)
        if dd > dm:
            k, dm = i, dd
    if dm <= tol:
        return [a, b]
    return _dp(pts[: k + 1], tol)[:-1] + _dp(pts[k:], tol)


def _r(v):
    return round(v, 4)


def fit(pts):
    """Sampled 2D points → list of edge shapes: one line / circle / arc, or short lines (approx)."""
    a, b = pts[0], pts[-1]
    closed = math.dist(a, b) < 1e-6
    if not closed and max(_seg_dist(p, a, b) for p in pts) <= TOL:
        return [{"shape": "line", "p1": [_r(a[0]), _r(a[1])], "p2": [_r(b[0]), _r(b[1])]}]
    n = len(pts) - 1
    trio = (pts[0], pts[n // 3], pts[2 * n // 3]) if closed else (a, pts[n // 2], b)
    cr = _circ3(*trio)
    if cr is not None:
        (cx, cy), r = cr
        if r < 1e5 and max(abs(math.dist(p, (cx, cy)) - r) for p in pts) <= TOL:
            c = [_r(cx), _r(cy)]
            if closed:
                return [{"shape": "circle", "c": c, "r": _r(r)}]

            def ang(p):
                return math.degrees(math.atan2(p[1] - cy, p[0] - cx)) % 360

            a0, am, a1 = ang(a), ang(pts[n // 2]), ang(b)
            if (am - a0) % 360 > (a1 - a0) % 360:  # clockwise as sampled
                a0, a1 = a1, a0
            return [
                {"shape": "arc", "c": c, "r": _r(r), "start": _r(a0) % 360, "end": _r(a1) % 360}
            ]
    q = _dp(pts, TOL * 2)
    return [
        {"shape": "line", "p1": [_r(p[0]), _r(p[1])], "p2": [_r(s[0]), _r(s[1])], "approx": True}
        for p, s in zip(q, q[1:])
        if math.dist(p, s) > 1e-6
    ]


# ---- provenance ----------------------------------------------------------------------------------


def _edge_hash(e):
    g = e.geom_type.name
    p0, p1 = e.position_at(0), e.position_at(1)
    parts = [g, *(round(c, 3) for c in (*_t(p0), *_t(p1)))]
    if g == "CIRCLE":
        parts += [round(c, 3) for c in _t(e.arc_center)] + [round(e.radius, 3)]
    else:
        parts += [round(c, 3) for c in _t(e.position_at(0.5))]
    return hashlib.sha1(json.dumps(parts).encode()).hexdigest()[:10]


def _model_index(shape, view):
    """Projected polylines of the model's own edges + their adjacent face indices."""
    from .hlr import to_view

    faces = list(shape.faces())
    fmap: dict = {}
    for j, f in enumerate(faces):
        for e in f.edges():
            fmap.setdefault(e, []).append(j)
    idx = []
    for i, e in enumerate(shape.edges()):
        L = e.length
        n = max(8, min(200, int(L / 0.5)))
        pl = [to_view(view, _t(e @ (k / n))) for k in range(n + 1)]
        xs, ys = [p[0] for p in pl], [p[1] for p in pl]
        bb = (min(xs) - MATCH, min(ys) - MATCH, max(xs) + MATCH, max(ys) + MATCH)
        idx.append((i, pl, bb, sorted(set(fmap.get(e, []))), e))
    return idx


def _match(pts, idx):
    probe = [pts[len(pts) * k // 4] for k in (1, 2, 3)] + [pts[0], pts[-1]]
    for i, pl, bb, faces, e in idx:
        if not all(bb[0] <= p[0] <= bb[2] and bb[1] <= p[1] <= bb[3] for p in probe):
            continue
        if all(min(_seg_dist(p, a, b) for a, b in zip(pl, pl[1:])) <= MATCH for p in probe):
            return i, faces, e
    return None


# ---- projection ----------------------------------------------------------------------------------


def _on_poly(p, poly, tol=MATCH):
    return any(_seg_dist(p, a, b) <= tol for a, b in zip(poly, poly[1:] + poly[:1]))


def _wire_pts(w, view):
    from .hlr import to_view

    pts = []
    for e in w.order_edges() if hasattr(w, "order_edges") else w.edges():
        L = e.length
        n = max(1, min(200, int(L / 0.5)))
        seg = [to_view(view, _t(e @ (k / n))) for k in range(n + 1)]
        if pts and math.dist(pts[-1], seg[0]) > math.dist(pts[-1], seg[-1]):
            seg.reverse()
        pts.extend(seg if not pts else seg[1:])
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts.pop()
    return [[_r(x), _r(y)] for x, y in _dp(pts + [pts[0]], TOL)[:-1]]


def compute(d, view, model, cut, depth, region, ribs, hidden, half="top"):
    """The projection as plain data: {"edges": [intent], "hatch": [loop], "wavy": [points]}."""
    from . import hlr

    shape = load_shape(d, model)
    m = d._els[model]
    key = json.dumps(
        [CACHE_VERSION, m.path, m.hash, d.P.values(), view, cut, depth, region, ribs, hidden, half],
        sort_keys=True,
    )
    cdir = _dir() / ".linercad" / "cache"
    cfile = cdir / f"proj-{hashlib.sha1(key.encode()).hexdigest()[:16]}.json"
    if cfile.is_file():
        try:
            return json.loads(cfile.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    src = shape
    loops = []
    if cut:
        src = hlr.section(shape, view, cut, half=half, at=depth, region=region)
        for f in hlr.cut_faces(src, view, depth):
            loops.append(_wire_pts(f.outer_wire(), view))
            loops.extend(_wire_pts(w, view) for w in f.inner_wires())
    idx = _model_index(shape, view)
    edges, wavy, seen = [], [], set()
    for cls, vis, e in hlr.project_classes(src, view, hidden=hidden):
        if not vis and cls == "smooth":
            continue
        pts = _samples(e)
        if region and all(_on_poly(p, region) for p in pts[:: max(1, len(pts) // 6)]):
            if vis:
                wavy.append([[_r(x), _r(y)] for x, y in _dp(pts, TOL)])
            continue
        hit = _match(pts, idx) if cls != "outline" else None
        if hit:
            i, faces, me = hit
            s3 = {"model": model, "edge": i, "faces": faces, "hash": _edge_hash(me)}
        elif cls == "outline":
            s3 = {"model": model, "outline": True}
        else:
            s3 = {"model": model, "cut": True}
        role = "hidden" if not vis else ("thin" if cls == "smooth" else "thick")
        for sh in fit(pts):
            k = json.dumps({x: sh[x] for x in sh if x != "approx"}, sort_keys=True)
            if k in seen:  # visible first: a hidden edge under a visible one is not drawn
                continue
            seen.add(k)
            tags = (["approx"] if sh.pop("approx", False) else []) + (
                ["conv"] if cls == "smooth" else []
            )
            edges.append({**sh, "role": role, "src3d": s3, "tags": tags})
    for rb in ribs or ():
        rp = [[_r(float(x)), _r(float(y))] for x, y in rb]
        loops.append(rp)
        for p, q in zip(rp, rp[1:] + rp[:1]):
            edges.append({"shape": "line", "p1": p, "p2": q, "role": "thick", "tags": ["rib"]})
    out = {"edges": edges, "hatch": loops, "wavy": wavy}
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        cfile.write_text(json.dumps(out), encoding="utf-8", newline="\n")
    except OSError:
        pass
    return out


def _pts(v, what, ps):
    try:
        out = [(float(x), float(y)) for x, y in ps]
    except (TypeError, ValueError):
        raise InvalidArgument(f"{what} 应为点列 [(u, v), ...]（视图坐标）", values={what: repr(ps)})
    if len(out) < 3:
        raise InvalidArgument(f"{what} 至少 3 个点", values={"n": len(out)})
    return out


def view_project(
    v,
    name="model",
    cut=None,
    depth=0.0,
    region=None,
    ribs=(),
    hidden=True,
    model="main",
    half="top",
):
    from .annotate import Hatch
    from .views import Wavy

    need_3d()
    d = v._d
    name = check_name(name)
    if cut not in (None, "full", "half"):
        raise InvalidArgument(
            "cut 只能是 None、'full'、'half'", values={"cut": cut}, candidates=["full", "half"]
        )
    if half not in ("top", "bottom"):
        raise InvalidArgument("half 只能是 'top' 或 'bottom'", candidates=["top", "bottom"])
    if region is not None and not cut:
        cut = "full"
    reg = _pts(v, "region", region) if region is not None else None
    rbs = [_pts(v, "ribs[k]", r) for r in ribs or ()]
    mid = model if str(model).startswith("M.") else f"M.{model}"
    data = compute(d, v.name, mid, cut, float(depth), reg, rbs, bool(hidden), half)
    f = v._feature(name, {"type": "projection", "model": mid, "cut": cut, "closed": False})
    for ei in data["edges"]:
        e = v._edge(name, ei, feature=f.id)
        f._intent["edges"].append(e.id)
    if data["hatch"]:
        hid = f"H.{v.name}.{name}"
        d._add(
            Hatch(
                d,
                hid,
                {"view": v.name, "loops": [{"points": lp} for lp in data["hatch"]]},
                refs=[v.id, f.id],
            )
        )
    for k, pts in enumerate(data["wavy"], 1):
        wid = f"W.{v.name}.{name}_{k}"
        d._add(Wavy(d, wid, {"view": v.name, "points": pts}, refs=[v.id, f.id]))
    return f
