"""Assembly drawings: components, standard parts, balloons and the parts list (SPEC M3 §1.2–1.3).

A component is a part directory (``model.py`` + optional ``drawing.py``); its parameter defaults and
title fields are read from ``drawing.py`` with ``ast`` (literals only, the file is not executed).
Views of an assembly come from ``V.project()`` over all components (``source3d``).
"""

from __future__ import annotations

import ast
import hashlib
import math
import runpy
from pathlib import Path

from .errors import InvalidArgument, NotFound
from .model import DRAW_DIR, Element, check_name, num

# GB/T 4458.6 (ISO 128-50): adjacent parts differ in hatch direction or spacing
PALETTE = [(45, None), (135, None), (45, 1.5), (135, 1.5), (60, None), (120, None)]
NEAR = 0.5  # parts closer than this count as adjacent for hatching (clearances, thread gaps)
SOLID_KINDS = ("bolt", "nut", "washer", "pin", "csk_screw", "set_screw")  # GB/T 4458.6: not cut


class Component(Element):
    kind = "component"
    READ = ("name", "path", "std", "spec", "qty", "solid", "title")

    name = property(lambda s: s._intent["name"])
    path = property(lambda s: s._intent.get("path"))
    std = property(lambda s: s._intent.get("std"))
    spec = property(lambda s: s._intent.get("spec"))
    qty = property(lambda s: s._intent["qty"])
    solid = property(lambda s: s._intent["solid"])
    title = property(lambda s: dict(s._intent.get("title", {})))


class Balloon(Element):
    kind = "balloon"
    LAYOUT = ("side",)
    READ = ("number", "component")

    number = property(lambda s: number(s._d, s._intent["component"]))
    component = property(lambda s: s._intent["component"])


class Bom(Element):
    kind = "bom"
    READ = ("rows",)

    @property
    def rows(self):
        return bom_rows(self._d)


def _dir(d=None) -> Path:
    return Path((getattr(d, "_dir", None) if d is not None else None) or DRAW_DIR.get() or ".")


def _need_assembly(d):
    if getattr(d, "kind", "part") != "assembly":
        raise InvalidArgument(
            "组件只能加在装配图里", hint='Drawing(kind="assembly")', values={"kind": d.kind}
        )


def _before_projection(d):
    done = [
        e.id
        for e in d._els.values()
        if e.kind == "feature" and e._intent.get("type") == "projection"
    ]
    if done:
        raise InvalidArgument(
            "组件要在视图投影（V.project）之前加，否则不会出现在视图里",
            id=done[0],
            hint="加组件属于结构改动：改 drawing.py，把 d.component / d.std_part 放在 project() 前面，再 lcad build -m",
        )


def _lit(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def read_part(path: Path) -> dict:
    """Parameter defaults and title fields of a part's ``drawing.py`` (literals only)."""
    out = {"params": {}, "title": {}}
    src = path / "drawing.py"
    if not src.is_file():
        return out
    tree = ast.parse(src.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr == "params":
            for kw in node.keywords:
                v = kw.value
                if isinstance(v, ast.Call) and v.args:  # Param(default, ...)
                    v = v.args[0]
                val = _lit(v)
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    out["params"][kw.arg] = float(val)
        elif node.func.attr == "title":
            for kw in node.keywords:
                val = _lit(kw.value)
                if isinstance(val, str):
                    out["title"][kw.arg] = val
    return out


def _places(at):
    try:
        if at and isinstance(at[0], (list, tuple)):
            pts = [[num(c, "at") for c in p] for p in at]
        else:
            pts = [[num(c, "at") for c in at]]
    except TypeError:
        raise InvalidArgument("at 应为 (x, y, z) 或其列表", values={"at": repr(at)})
    if any(len(p) != 3 for p in pts):
        raise InvalidArgument("at 的每个点要 3 个坐标 (x, y, z)", values={"at": repr(at)})
    return pts


def _rot(rot):
    r = [num(c, "rot") for c in rot]
    if len(r) != 3:
        raise InvalidArgument("rot 应为 (rx, ry, rz)，单位度", values={"rot": repr(rot)})
    return r


def drawing_component(d, path, name=None, at=(0, 0, 0), rot=(0, 0, 0), params=None, solid=False):
    _need_assembly(d)
    _before_projection(d)
    p = _dir(d) / str(path)
    if not (p / "model.py").is_file():
        raise NotFound(
            f"组件目录 {path} 里没有 model.py（相对图纸目录）",
            values={"path": str(path)},
            hint="组件目录要有 model.py（定义 model(**P)），可选 drawing.py 提供参数缺省值和标题栏",
        )
    name = check_name(name or p.resolve().name)
    part = read_part(p)
    over = {}
    for k, v in (params or {}).items():
        over[str(k)] = num(v, f"params.{k}")
    unknown = [k for k in over if part["params"] and k not in part["params"]]
    if unknown:
        raise InvalidArgument(
            f"组件 {name} 没有参数 {unknown[0]}",
            values={"params": over},
            candidates=list(part["params"]),
        )
    hh = hashlib.sha1()
    for f in sorted(p.glob("*.py")):
        hh.update(f.name.encode() + f.read_bytes())
    h = hh.hexdigest()[:12]
    pl = _places(at)
    intent = {
        "name": name,
        "path": str(path),
        "at": pl,
        "rot": _rot(rot),
        "params": {**part["params"], **over},
        "solid": bool(solid),
        "qty": len(pl),
        "title": part["title"],
        "hash": h,
    }
    return _with_balloon(d, d._add(Component(d, f"A.{name}", intent)))


def _with_balloon(d, c):
    bom = d._els.get("T.bom")
    if bom is not None:
        balloon_for(d, c, bom._intent["balloons"])
    return c


def drawing_std_part(d, std, spec, qty=None, name=None, at=(0, 0, 0), rot=(0, 0, 0), material=None):
    from . import res

    _need_assembly(d)
    _before_projection(d)
    info = res.std_part(std, spec)
    pl = _places(at)
    if qty is not None and int(qty) < len(pl):
        raise InvalidArgument("qty 小于放置位置数", values={"qty": qty, "at": len(pl)})
    stem = f"{info['kind']}_{info['d']:g}" + (f"x{info['l']:g}" if "l" in info else "")
    name = check_name(name or stem.replace(".", "_"))
    intent = {
        "name": name,
        "std": info["std"],
        "spec": str(spec),
        "info": info,
        "at": pl,
        "rot": _rot(rot),
        "solid": info["kind"] in SOLID_KINDS,
        "qty": int(qty) if qty is not None else len(pl),
        "title": {"name": info["name"], **({"material": str(material)} if material else {})},
    }
    return _with_balloon(d, d._add(Component(d, f"A.{name}", intent)))


def components(d):
    return [e for e in d._els.values() if e.kind == "component"]


# ---- shapes ----------------------------------------------------------------------------------------

_SHAPES: dict = {}


def std_shape(info):
    """Simplified standard-part solid in its own frame: axis +Z, bearing face at z = 0."""
    from build123d import Cone, Cylinder, Pos, RegularPolygon, extrude

    k = info["kind"]
    d = info["d"]
    if k == "bolt":
        head = extrude(RegularPolygon(info["s"] / math.sqrt(3), 6), info["k"])
        return head + Pos(0, 0, -info["l"] / 2) * Cylinder(d / 2, info["l"])
    if k == "nut":
        return extrude(RegularPolygon(info["s"] / math.sqrt(3), 6), info["m"]) - Pos(
            0, 0, info["m"] / 2
        ) * Cylinder(d / 2, info["m"] + 2)
    if k == "washer":
        h = info["h"]
        return Pos(0, 0, h / 2) * (Cylinder(info["d2"] / 2, h) - Cylinder(info["d1"] / 2, h + 2))
    if k == "pin":
        return Pos(0, 0, info["l"] / 2) * Cylinder(d / 2, info["l"])
    if k == "csk_screw":
        kk, L = info["k"], info["l"]
        head = Pos(0, 0, -kk / 2) * Cone(d / 2, info["dk"] / 2, kk)
        return head + Pos(0, 0, -(L + kk) / 2) * Cylinder(d / 2, L - kk)
    if k == "set_screw":
        L = info["l"]
        tip = min(L / 3, (d - info["dt"]) / 2)
        return Pos(0, 0, -(L - tip) / 2) * Cylinder(d / 2, L - tip) + Pos(
            0, 0, -L + tip / 2
        ) * Cone(info["dt"] / 2, d / 2, tip)
    raise InvalidArgument(f"标准件种类 {k} 没有形体")


def comp_shape(d, c):
    from build123d import Compound, Pos, Rot

    it = c._intent
    key = (
        c.id,
        it.get("hash"),
        repr(it.get("params")),
        repr(it["at"]),
        repr(it["rot"]),
        repr(it.get("info")),
    )
    if key in _SHAPES:
        return _SHAPES[key]
    if it.get("std"):
        base = std_shape(it["info"])
    else:
        p = _dir(d) / it["path"] / "model.py"
        ns = runpy.run_path(str(p), run_name="linercad_model")
        fn = ns.get("model")
        if not callable(fn):
            raise InvalidArgument(f"{it['path']}/model.py 里没有 model(**P)", id=c.id)
        import inspect

        sig = inspect.signature(fn)
        kw = dict(it["params"])
        if not any(x.kind == x.VAR_KEYWORD for x in sig.parameters.values()):
            kw = {k: v for k, v in kw.items() if k in sig.parameters}
        base = fn(**kw)
    rx, ry, rz = it["rot"]
    placed = [Pos(*at) * Rot(rx, ry, rz) * base for at in it["at"]]
    shape = placed[0] if len(placed) == 1 else Compound(placed)  # no re-parenting (cached)
    if len(_SHAPES) > 64:
        _SHAPES.clear()
    _SHAPES[key] = shape
    return shape


def parts(d):
    """[(component id, placed shape, solid)] in component order."""
    cs = components(d)
    if not cs:
        raise InvalidArgument(
            "装配图还没有组件", hint="d.component('../零件目录') / d.std_part(...)"
        )
    return [(c.id, comp_shape(d, c), c.solid) for c in cs]


def parts_key(d):
    return [
        [
            c.id,
            c._intent.get("hash"),
            c._intent.get("params"),
            c._intent["at"],
            c._intent["rot"],
            c._intent.get("spec"),
            c._intent.get("info"),
            c.solid,
        ]
        for c in components(d)
    ]


def hatch_styles(shapes):
    """Greedy colouring over touching components → {cid: (angle, spacing|None)}."""
    ids = list(shapes)
    adj = {i: set() for i in ids}
    boxes = {}
    for i in ids:
        bb = shapes[i].bounding_box()
        boxes[i] = ((bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z))
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            (amin, amax), (bmin, bmax) = boxes[ids[a]], boxes[ids[b]]
            if any(amin[k] > bmax[k] + NEAR or bmin[k] > amax[k] + NEAR for k in range(3)):
                continue
            if shapes[ids[a]].distance_to(shapes[ids[b]]) <= NEAR:
                adj[ids[a]].add(ids[b])
                adj[ids[b]].add(ids[a])
    out = {}
    for i in ids:
        used = {out[j] for j in adj[i] if j in out}
        out[i] = next((p for p in PALETTE if p not in used), PALETTE[len(out) % len(PALETTE)])
    return out


# ---- balloons and parts list ---------------------------------------------------------------------


def bom_rows(d):
    rows = []
    for k, c in enumerate(components(d), 1):
        t = c._intent.get("title", {})
        if c.std:
            code = c.std
            name = f"{t.get('name', '')} {c.spec}"
        else:
            code = t.get("drawing_no", "")
            name = t.get("name", c.name)
        rows.append(
            {
                "no": k,
                "id": c.id,
                "code": code,
                "name": name,
                "qty": c.qty,
                "material": t.get("material", ""),
                "remark": "",
            }
        )
    return rows


def number(d, cid):
    """Balloon number = the component's row in the parts list."""
    ids = [c.id for c in components(d)]
    return ids.index(cid) + 1 if cid in ids else None


def balloon_for(d, c, view):
    """Balloon ``B.<component name>`` for component ``c`` in ``view`` (else another projected
    view); None when the component shows in no view."""
    views = [view] + [v.name for v in d.views() if v.name != view]
    for vn in views:
        a = anchor(d, vn, c.id)
        if a is None:
            continue
        intent = {"view": vn, "component": c.id, "anchor": [round(a[0], 3), round(a[1], 3)]}
        return d._add(Balloon(d, f"B.{c.name}", intent, refs=[f"V.{vn}", c.id]))
    return None


def drawing_balloons(d, view="front"):
    _need_assembly(d)
    if f"V.{view}" not in d._els:
        raise NotFound(f"视图 {view} 不存在", id=f"V.{view}", candidates=[e.id for e in d.views()])
    return [b for c in components(d) if (b := balloon_for(d, c, view)) is not None]


def anchor(d, view, cid):
    """A point inside the component in the view: in its section area, else the middle of its
    visible outline (on the axis for bolts, pins and shafts; GB/T 4458.2)."""
    from .views import point_in_poly

    for e in d._els.values():
        if e.kind == "hatch" and e.view == view and e._intent.get("component") == cid:
            loops = [lp["points"] for lp in e._intent["loops"] if "points" in lp]
            if not loops:
                continue
            big = max(loops, key=lambda lp: abs(_area(lp)))
            p = _inside(big, loops, point_in_poly)
            if p:
                return p
    if not any(
        e.kind == "edge"
        and e.view == view
        and e._intent.get("component") == cid
        and e._intent["role"] != "hidden"
        for e in d._els.values()
    ):
        return None
    from .hlr import CAMERA, to_view

    if view not in CAMERA:
        return None
    shape = comp_shape(d, d._els[cid])
    sols = list(shape.solids())
    first = sols[0] if len(sols) > 1 else shape  # one instance
    c = first.bounding_box().center()
    return to_view(view, (c.X, c.Y, c.Z))


def _area(lp):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(lp, lp[1:] + lp[:1])) / 2


def _inside(big, loops, pip):
    xs, ys = [p[0] for p in big], [p[1] for p in big]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cands = [((x0 + x1) / 2, (y0 + y1) / 2)]
    for i in range(1, 8):
        for j in range(1, 8):
            cands.append((x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * j / 8))
    for p in cands:
        if sum(1 for lp in loops if pip(p, lp)) % 2 == 1:
            return p
    return None


def drawing_bom(d, view="front"):
    _need_assembly(d)
    b = d._add(Bom(d, "T.bom", {"view": None, "balloons": view}))
    drawing_balloons(d, view)
    return b
