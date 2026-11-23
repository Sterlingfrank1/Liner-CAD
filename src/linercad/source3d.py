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

CACHE_VERSION = 6  # 6: edges are named by 3D topology, not projection order
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


def _dir(d=None) -> Path:
    return Path((getattr(d, "_dir", None) if d is not None else None) or DRAW_DIR.get() or ".")


def drawing_model(d, path, name="main"):
    need_3d()
    name = check_name(name)
    p = _dir(d) / str(path)
    if not p.is_file():
        raise NotFound(f"模型文件 {path} 不存在（相对图纸目录）", values={"path": str(path)})
    if p.suffix.lower() not in (".py", ".step", ".stp"):
        raise InvalidArgument(
            "模型只能是 model.py（定义 model(**P)）或 .step/.stp",
            values={"path": str(path)},
            candidates=[".py", ".step", ".stp"],
        )
    return d._add(Model(d, f"M.{name}", {"path": str(path), "hash": model_hash(p)}))


def model_hash(p: Path) -> str:
    """Content hash of a model file plus its sibling modules (helpers ``model.py`` may import;
    ``drawing.py`` excluded) and the build123d version."""
    import build123d

    h = hashlib.sha1(p.read_bytes())
    if p.suffix.lower() == ".py":
        for f in sorted(p.parent.glob("*.py")):
            if f.name not in (p.name, "drawing.py"):
                h.update(f.name.encode() + f.read_bytes())
    h.update(str(getattr(build123d, "__version__", "")).encode())
    return h.hexdigest()[:12]


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
    p = _dir(d) / m.path
    P = d.P.values()
    key = (str(p.resolve()), m.hash, tuple(sorted(P.items())))
    if key in _SHAPES:
        return _SHAPES[key]
    if p.suffix.lower() == ".py":
        import sys

        sys.path.insert(0, str(p.parent))
        try:
            ns = runpy.run_path(str(p), run_name="linercad_model")
        finally:
            sys.path.remove(str(p.parent))
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
    if not hasattr(shape, "wrapped") and hasattr(shape, "part"):
        shape = shape.part  # a BuildPart context
    if not hasattr(shape, "wrapped"):
        raise InvalidArgument(
            f"{m.path} 的 model() 应返回 build123d 形体，收到 {type(shape).__name__}",
            id=mid,
            hint="Builder 模式返回 part.part；参数是 float，range() 前先 int()",
        )
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
    ends = sorted(tuple(round(c, 3) + 0.0 for c in _t(e.position_at(t))) for t in (0, 1))
    parts = [g, *ends[0], *ends[1]]
    if g == "CIRCLE":
        parts += [round(c, 3) + 0.0 for c in _t(e.arc_center)] + [round(e.radius, 3) + 0.0]
    else:
        parts += [round(c, 3) + 0.0 for c in _t(e.position_at(0.5))]
    return hashlib.sha1(json.dumps(parts).encode()).hexdigest()[:10]


def _model_index(shape, view):
    """Projected polylines of the model's own edges + their adjacent faces and a topology key.

    The topology key (adjacent face index + the edge's ordinal in that face) survives parameter
    changes that only move geometry, so it can name the projected edge independently of the
    hidden-line output order."""
    from .hlr import to_view

    faces = list(shape.faces())
    fmap: dict = {}
    for j, f in enumerate(faces):
        for e in f.edges():
            fmap.setdefault(e, []).append(j)
    face_edges = [list(f.edges()) for f in faces]
    idx = []
    for i, e in enumerate(shape.edges()):
        L = e.length
        n = max(8, min(200, int(L / 0.5)))
        pl = [to_view(view, _t(e @ (k / n))) for k in range(n + 1)]
        xs, ys = [p[0] for p in pl], [p[1] for p in pl]
        bb = (min(xs) - MATCH, min(ys) - MATCH, max(xs) + MATCH, max(ys) + MATCH)
        fs = sorted(set(fmap.get(e, [])))
        if fs:
            ordinal = face_edges[fs[0]].index(e)
            topo = "f" + "_".join(str(j) for j in fs) + f"_e{ordinal}"
        else:
            topo = f"e{i}"  # a free edge: no adjacent face, keep the topological edge index
        idx.append((i, pl, bb, fs, e, topo))
    return idx


def _match(pts, idx):
    probe = [pts[len(pts) * k // 4] for k in (1, 2, 3)] + [pts[0], pts[-1]]
    best = None
    for cid, i, pl, bb, faces, e, topo in idx:
        if not all(bb[0] <= p[0] <= bb[2] and bb[1] <= p[1] <= bb[3] for p in probe):
            continue
        dd = max(min(_seg_dist(p, a, b) for a, b in zip(pl, pl[1:])) for p in probe)
        if dd <= MATCH and (best is None or dd < best[0]):
            best = (dd, (cid, i, faces, e, topo))
    return best[1] if best else None


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


CACHE_KEEP = 200


def _cache(d, key):
    cdir = _dir(d) / ".linercad" / "cache"
    return cdir, cdir / f"proj-{hashlib.sha1(key.encode()).hexdigest()[:16]}.json"


def _save(cdir, cfile, out):
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        cfile.write_text(json.dumps(out), encoding="utf-8", newline="\n")
        files = sorted(cdir.glob("proj-*.json"), key=lambda f: f.stat().st_mtime)
        for f in files[:-CACHE_KEEP]:
            f.unlink(missing_ok=True)
    except OSError:
        pass


def _key(sh):
    """Dedup key: lines without direction (a reversed hidden line under a visible one)."""
    g = {x: sh[x] for x in sh if x != "approx"}
    if g["shape"] == "line":
        g["p1"], g["p2"] = sorted([g["p1"], g["p2"]])
    return json.dumps(g, sort_keys=True)


def _ident(d, model):
    """Cache identity of the 3D source: a model's path + hash, or an assembly's components."""
    if getattr(d, "kind", "part") == "assembly" and model not in d._els:
        from .assembly import parts_key

        return parts_key(d)
    m = d._els.get(model)
    if m is None or m.kind != "model":
        load_shape(d, model)  # raises NotFound with candidates
    return [m.path, m.hash]


def _sources(d, model):
    """[(component id or None, shape, solid)]."""
    if getattr(d, "kind", "part") == "assembly" and model not in d._els:
        from .assembly import parts

        return parts(d)
    return [(None, load_shape(d, model), False)]


def _edge_geometry_key(ei):
    """Canonical projected geometry of one edge intent (for deterministic sibling ordering and
    for the visible-over-hidden coincident-edge tie-break; direction does not matter)."""
    keys = ("shape", "p1", "p2", "c", "r", "start", "end")
    d = {k: ei.get(k) for k in keys}
    if d.get("shape") == "line":
        d["p1"], d["p2"] = sorted([d.get("p1"), d.get("p2")])
    return json.dumps(d, sort_keys=True)


def _projection_edge_base(ei):
    """Stable ID stem from the 3D topology; projection order never enters it."""
    s3 = ei.get("src3d") or {}
    comp = str(s3.get("component") or "").replace(".", "_")
    if s3.get("topo"):
        return f"{comp}_{s3['topo']}" if comp else s3["topo"]
    if s3.get("outline"):
        return f"{comp}_outline" if comp else "outline"
    if s3.get("unmatched"):
        return f"{comp}_unmatched" if comp else "unmatched"
    if "rib" in (ei.get("tags") or ()):
        return "rib"
    return "edge"


def _name_projection_edges(edges):
    """Give every projected edge an explicit name derived from its source topology.

    Siblings that share one source edge (an arc split by HLR, an outline class with several
    curves) get a deterministic suffix after sorting by projected geometry, so the result does
    not depend on the order the hidden-line algorithm returns its edges in."""
    ordered = sorted(edges, key=lambda ei: (_projection_edge_base(ei), _edge_geometry_key(ei)))
    counts = {}
    for ei in ordered:
        base = _projection_edge_base(ei)
        counts[base] = counts.get(base, 0) + 1
        ei["name"] = base if counts[base] == 1 else f"{base}_{counts[base]}"


def compute(d, view, model, cut, depth, region, ribs, hidden, half="right"):
    """The projection as plain data: {"edges": [intent], "hatch": [{loops, component, angle,
    spacing}], "wavy": [points]}. ``depth``: the cutting plane's distance from the model origin
    toward the viewer. An assembly projects all components together (occlusion) and attributes
    each edge to its component; solid components are not cut (SPEC M3 §1.2)."""
    from . import hlr

    key = json.dumps(
        [
            CACHE_VERSION,
            _ident(d, model),
            d.P.values(),
            view,
            cut,
            depth,
            region,
            ribs,
            hidden,
            half,
        ],
        sort_keys=True,
    )
    cdir, cfile = _cache(d, key)
    if cfile.is_file():
        try:
            return json.loads(cfile.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    srcs = _sources(d, model)
    multi = srcs[0][0] is not None
    look, _ = hlr.CAMERA[view]
    k = next(i for i in range(3) if look[i])
    at = -look[k] * depth
    styles = {}
    if multi and cut:
        from .assembly import hatch_styles

        styles = hatch_styles({cid: shp for cid, shp, _ in srcs})
    hatch, pieces, idx = [], [], []
    for cid, shp, solid in srcs:
        piece = shp
        if cut and solid and region is None and len(shp.solids()) > 1:
            from build123d import Compound

            kept = [ch for ch in shp.solids() if _near(ch, look, k) <= depth + 1e-6]
            if not kept:
                continue
            shp = kept[0] if len(kept) == 1 else Compound(kept)
        if cut and solid and region is None:
            bb = shp.bounding_box()
            near = min(
                -look[k] * (bb.min.X, bb.min.Y, bb.min.Z)[k],
                -look[k] * (bb.max.X, bb.max.Y, bb.max.Z)[k],
            )
            if near > depth + 1e-6:
                continue  # wholly on the viewer's side of the plane: removed with the cut material
        if cut and not solid:
            piece = hlr.section(shp, view, cut, half=half, at=at, region=region)
            loops = []
            for f in hlr.cut_faces(piece, view, at, original=shp):
                loops.append(_wire_pts(f.outer_wire(), view))
                loops.extend(_wire_pts(w, view) for w in f.inner_wires() if w.edges())
            if loops:
                ang, sp = styles.get(cid, (None, None))
                hatch.append({"loops": loops, "component": cid, "angle": ang, "spacing": sp})
        pieces.append((cid, piece))
        idx += [(cid, *x) for x in _model_index(shp, view)]
    if cut and not hatch and any(not solid for _, _, solid in srcs):
        vals = []
        for _, shp, _ in srcs:
            bb = shp.bounding_box()
            vals += [
                -look[k] * (bb.min.X, bb.min.Y, bb.min.Z)[k],
                -look[k] * (bb.max.X, bb.max.Y, bb.max.Z)[k],
            ]
        raise InvalidArgument(
            f"剖切面 depth={depth:g} 没有切到实体（视图 {view}）",
            values={"depth": depth, "range": [round(min(vals), 3), round(max(vals), 3)]},
            hint="depth 是剖切面离模型原点、朝观察者方向的距离，应落在 range 之内",
        )
    if len(pieces) == 1:
        src = pieces[0][1]
    else:
        from build123d import Compound

        src = Compound([pc for _, pc in pieces])  # never Compound(children=): it re-parents
    owners = _owner_index(pieces, view, hidden) if len(pieces) > 1 else None
    model_id = "assembly" if multi else model
    edges, wavy = [], []
    for cls, vis, e in hlr.project_classes(src, view, hidden=hidden):
        if not vis and cls == "smooth":
            continue
        pts = _samples(e)
        if region and all(_on_poly(p, region, 0.01) for p in pts[:: max(1, len(pts) // 24)]):
            if vis:
                wavy.append([[_r(x), _r(y)] for x, y in _dp(pts, TOL)])
            continue
        hit = _match(pts, idx) if cls != "outline" else None
        if hit:
            cid, i, faces, me, topo = hit
            s3 = {
                "model": model_id,
                "edge": i,
                "faces": faces,
                "topo": topo,
                "hash": _edge_hash(me),
            }
        else:
            cid = _owner(pts, owners) if owners else srcs[0][0]
            if cls == "outline":
                s3 = {"model": model_id, "outline": True}
            else:  # a section boundary, or a curve the fit could not match back
                s3 = {"model": model_id, "unmatched": True}
        if cid is not None:
            s3["component"] = cid
        role = "hidden" if not vis else ("thin" if cls == "smooth" else "thick")
        for sh in fit(pts):
            tags = (["approx"] if sh.pop("approx", False) else []) + (
                ["conv"] if cls == "smooth" else []
            )
            ei = {**sh, "role": role, "src3d": s3, "tags": tags}
            if cid is not None:
                ei["component"] = cid
            edges.append(ei)
    # Coincident candidates: visible beats hidden; among equals the 3D topology (then projected
    # geometry) decides, so the retained edge does not depend on the hidden-line output order.
    chosen = {}
    for ei in edges:
        rank = (
            ei.get("role") == "hidden",
            _projection_edge_base(ei),
            _edge_geometry_key(ei),
            ei.get("component") or "",
        )
        kk = _edge_geometry_key(ei)
        if kk not in chosen or rank < chosen[kk][0]:
            chosen[kk] = (rank, ei)
    edges = [ei for _rank, ei in chosen.values()]
    edges.sort(key=lambda ei: (_projection_edge_base(ei), _edge_geometry_key(ei)))
    seen = set(chosen)  # projected-geometry keys already drawn
    for rp in ribs or ():
        rp = [[_r(float(x)), _r(float(y))] for x, y in rp]
        if hatch:
            hatch[0]["loops"].append(rp)
        for p, q in zip(rp, rp[1:] + rp[:1]):
            sh = {"shape": "line", "p1": p, "p2": q}
            if _key(sh) not in seen:
                seen.add(_key(sh))
                edges.append({**sh, "role": "thick", "tags": ["rib"]})
    merged = _merge_arcs(edges)
    _name_projection_edges(merged)
    out = {"edges": merged, "hatch": hatch, "wavy": wavy}
    _save(cdir, cfile, out)
    return out


def _near(shape, look, k):
    """Nearest coordinate of ``shape`` toward the viewer along the view axis."""
    bb = shape.bounding_box()
    lo, hi = (bb.min.X, bb.min.Y, bb.min.Z)[k], (bb.max.X, bb.max.Y, bb.max.Z)[k]
    return min(-look[k] * lo, -look[k] * hi)


def _merge_arcs(edges):
    """Arcs split at a cylinder seam (or by HLR) on the same circle → one arc, or one circle when
    they close the full turn; so ``d.q.circles`` finds projected holes and bosses."""
    groups, rest = {}, []
    for e in edges:
        if e["shape"] == "arc":
            key = (
                round(e["c"][0], 3),
                round(e["c"][1], 3),
                round(e["r"], 3),
                e["role"],
                e.get("component"),
            )
            groups.setdefault(key, []).append(e)
        else:
            rest.append(e)
    out = list(rest)
    for arcs in groups.values():
        arcs.sort(key=lambda a: a["start"] % 360)
        merged = [dict(arcs[0])]
        for a in arcs[1:]:
            m = merged[-1]
            if (
                abs((a["start"] - m["end"]) % 360) < 1e-2
                or abs((a["start"] - m["end"]) % 360 - 360) < 1e-2
            ):
                m["end"] = a["end"]
            else:
                merged.append(dict(a))
        if len(merged) > 1:
            f, l_ = merged[0], merged[-1]
            if abs((f["start"] - l_["end"]) % 360) < 1e-2:  # wrap-around join
                l_["end"] = f["end"]
                merged = merged[1:]
        for m in merged:
            if abs((m["end"] - m["start"]) % 360) < 1e-2:
                m = {k: v for k, v in m.items() if k not in ("start", "end")}
                m["shape"] = "circle"
            out.append(m)
    return out


def _owner_index(pieces, view, hidden):
    from . import hlr

    return [
        (cid, [_samples(e, 24) for _, _, e in hlr.project_classes(pc, view, hidden=hidden)])
        for cid, pc in pieces
    ]


def _owner(pts, owners):
    probe = [pts[len(pts) // 2], pts[len(pts) // 4]]
    best = (math.inf, None)
    for cid, pls in owners:
        for pl in pls:
            dd = max(min(_seg_dist(p, a, b) for a, b in zip(pl, pl[1:])) for p in probe)
            if dd < best[0]:
                best = (dd, cid)
    return best[1]


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
    half="right",
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
    if half not in ("left", "right", "top", "bottom"):
        raise InvalidArgument(
            "half 只能是 'right' / 'left'（以竖直轴分）或 'top' / 'bottom'（以水平轴分）",
            candidates=["right", "left", "top", "bottom"],
        )
    if region is not None and not cut:
        cut = "full"
    reg = _pts(v, "region", region) if region is not None else None
    if ribs and not cut:
        raise InvalidArgument(
            "ribs 只用于剖视（肋板纵剖不画剖面线），先给 cut=", values={"cut": cut}
        )
    if ribs and ribs[0] and isinstance(ribs[0][0], (int, float)):
        ribs = [ribs]  # one polygon given as a point list
    rbs = [_pts(v, "ribs[k]", r) for r in ribs or ()]
    mid = model if str(model).startswith("M.") else f"M.{model}"
    if getattr(d, "kind", "part") == "assembly" and mid not in d._els:
        mid = "assembly"
    data = compute(d, v.name, mid, cut, float(depth), reg, rbs, bool(hidden), half)
    f = v._feature(name, {"type": "projection", "model": mid, "cut": cut, "closed": False})
    for ei in data["edges"]:
        e = v._edge(name, ei, feature=f.id)
        f._intent["edges"].append(e.id)
    for hd in data["hatch"]:
        cid = hd.get("component")
        hid = f"H.{v.name}.{name}" if cid is None else f"H.{v.name}.{cid.split('.', 1)[1]}"
        intent = {"view": v.name, "loops": [{"points": lp} for lp in hd["loops"]]}
        if cid is not None:
            intent.update(component=cid, angle=hd["angle"], spacing=hd["spacing"])
        d._add(Hatch(d, hid, intent, refs=[v.id, f.id] + ([cid] if cid else [])))
    for k, pts in enumerate(data["wavy"], 1):
        wid = f"W.{v.name}.{name}_{k}"
        d._add(Wavy(d, wid, {"view": v.name, "points": pts}, refs=[v.id, f.id]))
    return f
