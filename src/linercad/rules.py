"""Checks v1 rule packs (SPEC M1 §7): drafting, dimensioning, tolerancing, surface. The layout
pack stays in ``checks.py``. Each rule returns findings ``{rule, id, message, severity, ...}``;
``checks.run`` adds the pack and the standard number from the profile."""

from __future__ import annotations

import math

from .layout import Text

LINE_SERIES = (0.13, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0)  # GB/T 4457.4 / ISO 128-2


def _f(rule, id, message, severity="warn", **kw):
    return {
        "rule": rule,
        "id": id,
        "message": message,
        "severity": severity,
        "violations": [],
        "corridors": {},
        **kw,
    }


def _els(d, kind):
    return [e for e in d._els.values() if e.kind == kind]


# ---- drafting -------------------------------------------------------------------------------------


def line_width(d):
    out = []
    ln = d.std["lines"]
    for role, spec in ln.items():
        if isinstance(spec, dict) and not any(abs(spec["width"] - w) < 1e-6 for w in LINE_SERIES):
            out.append(
                _f("line_width", "T.frame", f"{role} 线宽 {spec['width']} 不在线宽系列内", "error")
            )
    t, n = ln["thick"]["width"], ln["thin"]["width"]
    if abs(t / n - 2) > 0.05:
        out.append(_f("line_width", "T.frame", f"粗线 {t} 与细线 {n} 应为 2:1", "error"))
    return out


def text_height(d):
    out = []
    series = d.std["text"]["heights"]
    dim_h = d.std["dim"]["text_height"]
    for e in d._els.values():
        hs = {round(p.height, 3) for p in e._prims if isinstance(p, Text)}
        bad = [h for h in hs if not any(abs(h - s) < 1e-3 for s in series)]
        if bad:
            out.append(
                _f("text_height", e.id, f"{e.id} 的字高 {bad} 不在字高系列 {series} 内", "error")
            )
        elif e.kind == "dim" and e._prims:
            main = [p for p in e._prims if isinstance(p, Text)][0].height
            if abs(main - dim_h) > 1e-3:
                out.append(
                    _f("text_height", e.id, f"{e.id} 的尺寸数字字高 {main} 与标准档 {dim_h} 不同")
                )
    return out


def scale(d):
    sc = d.std["scales"]
    out = []
    for txt, id in [(d.scale_text, "T.title.scale")] + [
        (v._intent["scale_text"], v.id) for v in d.views() if v._intent.get("scale_text")
    ]:
        if txt not in sc["preferred"] and txt not in sc["allowed"]:
            out.append(_f("scale", id, f"比例 {txt} 不在比例系列内", "warn"))
    return out


def sheet(d):
    sheets = d.std["sheets"]
    size = sorted(d.template["size"])
    if not any(sorted(v) == size for k, v in sheets.items() if isinstance(v, list)):
        return [_f("sheet", "T.frame", f"图幅 {d.template['size']} 不是基本幅面", "error")]
    return []


CONV_NEED = {"thread": 1, "spline": 1, "groove": 1, "keyway": 2}


def conv_dim(d):
    out = []
    dims = _els(d, "dim")
    for f in _els(d, "feature"):
        t = f._intent.get("type")
        need = CONV_NEED.get(t)
        if not need:
            continue
        ids = {f.id}
        if t == "keyway":  # its removed section carries the width and depth
            ids |= {g.id for g in _els(d, "feature") if g._intent.get("keyway") == f.id}
        n = sum(1 for x in dims if ids & set(x._refs))
        if n < need:
            out.append(
                _f(
                    "conv_dim",
                    f.id,
                    f"{f.id}（{t}）缺代号或必需尺寸（需要 {need} 个，有 {n} 个）",
                    "error",
                )
            )
    return out


def section_ref(d):
    out = []
    marks = {e._intent.get("letter") for e in d._els.values() if e.kind in ("section", "mark")}
    for v in d.views():
        if v._intent.get("aux") and v._intent["name"] not in marks:
            out.append(_f("section_ref", v.id, f"{v.id} 在父视图里没有对应的标记", "error"))
    for e in d._els.values():
        if e.kind == "section" and f"V.{e._intent['view']}" not in d._els:
            out.append(_f("section_ref", e.id, f"{e.id} 的目标视图不存在", "error"))
    return out


def _on_center(c, centers):
    for ce in centers:
        i = ce._intent
        if i["type"] in ("mark", "circle") and math.dist(i["c"], c) < 0.01:
            return True
        if i["type"] == "line":
            a, b = i["p1"], i["p2"]
            L = math.dist(a, b)
            if L < 1e-9:
                continue
            t = ((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / (L * L)
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            if -0.05 <= t <= 1.05 and math.dist(p, c) < 0.01:
                return True
    return False


def center_mark(d):
    out = []
    for v in d.views():
        centers = [e for e in _els(d, "center") if e.view == v.name]
        for e in _els(d, "edge"):
            if e.view == v.name and e.shape == "circle" and e.role in ("thick", "hidden"):
                if not _on_center(e._intent["c"], centers):
                    fid = e._intent.get("feature")
                    out.append(_f("center_mark", fid or e.id, f"{e.id} 的圆心没有中心线"))
    seen, uniq = set(), []
    for x in out:
        if x["id"] not in seen:
            seen.add(x["id"])
            uniq.append(x)
    return uniq


# ---- dimensioning ------------------------------------------------------------------------------------


def _key(x):
    return round(x, 6)


def duplicate(d):
    out, seen = [], {}
    for e in _els(d, "dim"):
        i = e._intent
        if i.get("reference"):
            continue
        if i.get("circle"):
            k = (i["view"], "circle", i["circle"], i["type"])
        elif "p1" in i and i["type"] in ("linear", "aligned"):
            pts = sorted([tuple(map(_key, i["p1"])), tuple(map(_key, i["p2"]))])
            if i["dir"] == "h":
                pts = sorted(_key(p[0]) for p in pts)
            elif i["dir"] == "v":
                pts = sorted(_key(p[1]) for p in pts)
            k = (i["view"], i["type"], i["dir"], tuple(pts))
        else:
            continue
        if k in seen:
            out.append(
                _f(
                    "duplicate",
                    e.id,
                    f"{e.id} 与 {seen[k]} 重复标注同一尺寸",
                    violations=[{"with": seen[k], "overlap": 0}],
                )
            )
        else:
            seen[k] = e.id
    return out


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.p[ra] = rb
        return True


def _links(d, view, axis):
    """(dim id, a, b) along one axis of a view: linear dims, chamfer and groove notes."""
    out = []
    k = 0 if axis == "h" else 1
    for e in _els(d, "dim"):
        i = e._intent
        if i["view"] != view or i.get("reference"):
            continue
        if i["type"] == "linear" and i["dir"] == axis:
            out.append((e.id, _key(i["p1"][k]), _key(i["p2"][k])))
        elif axis == "h" and i["type"] == "chamfer":
            out.append((e.id, _key(i["p1"][0]), _key(i["p2"][0])))
        elif axis == "h" and i["type"] == "groove":
            out.append((e.id, _key(i["x0"]), _key(i["x1"])))
    return out


def closed_loop(d):
    out = []
    for v in d.views():
        for axis in ("h", "v"):
            uf = _UF()
            for did, a, b in _links(d, v.name, axis):
                if a != b and not uf.union(a, b):
                    out.append(
                        _f(
                            "closed_loop",
                            did,
                            f"{did} 使 {v.id} 的尺寸链封闭（{axis} 向），改成参考尺寸或删去一个",
                        )
                    )
    return out


def missing(d):
    from .revolve import _corners

    out = []
    for f in _els(d, "feature"):
        i = f._intent
        if i.get("type") != "turned":
            continue
        uf = _UF()
        for _did, a, b in _links(d, i["view"], "h"):
            uf.union(a, b)
        xs = {_key(x) for x, *_ in _corners([tuple(p) for p in i["profile"]])}
        for k in _els(d, "feature"):
            if k._intent.get("type") == "keyway" and k.view == f.view and "x0" in k._intent:
                xs |= {_key(k._intent["x0"]), _key(k._intent["x0"] + k._intent["length"])}
        groups = {}
        for x in sorted(xs):
            groups.setdefault(uf.find(x), []).append(x)
        if len(groups) > 1:
            parts = sorted(groups.values(), key=lambda g: g[0])
            gaps = "；".join(f"{g[-1]:g} ↔ {h[0]:g}" for g, h in zip(parts, parts[1:]))
            out.append(
                _f(
                    "missing",
                    f.id,
                    f"{f.id} 的轴向台阶没有全部定位：{gaps}",
                    candidates=[f"x={g[0]:g}" for g in parts],
                )
            )
    return out


def param_cover(d):
    covered = set()
    for e in d._els.values():
        covered |= set(e._covers)
    out = []
    for name in d.P._params:
        if name not in covered:
            out.append(
                _f(
                    "param_cover",
                    f"P.{name}",
                    f"参数 {name} 没有被任何尺寸覆盖（写进尺寸、技术要求，或 accept）",
                )
            )
    return out


# ---- tolerancing --------------------------------------------------------------------------------


def dev_order(d):
    out = []
    for e in _els(d, "dim"):
        t = e._intent.get("tolerance")
        if t and t["upper"] < t["lower"] - 1e-12:
            out.append(_f("dev_order", e.id, f"{e.id} 上偏差小于下偏差", "error"))
    return out


def gtol_syntax(d):
    out = []
    for e in _els(d, "gtol"):
        missing_ = [r for r in e._intent.get("datum_refs", []) if r not in d._els]
        if missing_:
            out.append(
                _f(
                    "gtol_syntax",
                    e.id,
                    f"{e.id} 引用的基准 {missing_} 没有定义（v.datum）",
                    "error",
                    candidates=missing_,
                )
            )
    return out


def datum_letter(d):
    from . import res

    fn = getattr(res, "datum_excluded", None)
    if fn is None:
        return []
    try:
        bad = set(fn(d.std_name if d.std_name in ("GB", "ISO") else "GB"))
    except Exception:  # noqa: BLE001 - the profile may not list one
        return []
    return [
        _f("datum_letter", e.id, f"基准字母 {e._intent['letter']} 不宜使用", "error")
        for e in _els(d, "datum")
        if e._intent["letter"] in bad
    ]


def general_tol(d):
    from .pmi import general_class

    if general_class(d):
        return []
    for e in _els(d, "dim"):
        i = e._intent
        if (
            i["type"] in ("linear", "dia", "rad", "aligned")
            and not i.get("tolerance")
            and not i.get("reference")
        ):
            return [
                _f(
                    "general_tol",
                    e.id,
                    "有未注公差的尺寸，但没有未注公差说明（d.general_tol('m')）",
                )
            ]
    return []


def chain_limit(d):
    out = []
    for e in _els(d, "chain"):
        r = e._resolved.get("result")
        if r and not r["ok"]:
            req = e._intent["require"]
            out.append(_f("chain_limit", e.id, f"{e.id} 封闭环 {r['wc']} 超出要求 {req}", "error"))
    return out


# ---- surface ----------------------------------------------------------------------------------------


def rough_syntax(d):
    from . import res

    out = []
    for e in _els(d, "rough"):
        i = e._intent
        try:
            ser = res.rough_series(i["param"])
        except Exception:  # noqa: BLE001
            continue
        first, extra = (
            (ser.get("first", []), ser.get("supplementary", []))
            if isinstance(ser, dict)
            else (ser, [])
        )
        v = i["value"]
        if any(abs(v - x) < 1e-9 for x in first):
            continue
        if any(abs(v - x) < 1e-9 for x in extra):
            out.append(_f("rough_syntax", e.id, f"{e.id} 的 {i['param']} {v:g} 属于补充系列"))
        else:
            out.append(
                _f(
                    "rough_syntax",
                    e.id,
                    f"{e.id} 的 {i['param']} {v:g} 不在 GB/T 1031 系列内",
                    "error",
                    candidates=[str(x) for x in first],
                )
            )
    return out


def rough_default(d):
    rs = _els(d, "rough")
    if rs and not any(e._intent.get("default") for e in rs):
        return [_f("rough_default", rs[0].id, "标了粗糙度但没有“其余”通用符号（d.rough_default）")]
    return []


def rough_fit(d):
    out = []
    rs = _els(d, "rough")
    for e in _els(d, "dim"):
        t = e._intent.get("tolerance")
        if not t or t["kind"] != "fit":
            continue
        from . import res

        try:
            it = res.fit(t["code"], e._intent["value"])["it"]
        except Exception:  # noqa: BLE001
            continue
        if it > 7:
            continue
        i = e._intent
        ys = {round(abs(i["p1"][1]), 6), round(abs(i["p2"][1]), 6)} if "p1" in i else set()
        ok = False
        for r in rs:
            ref = d._els.get(r._intent.get("ref") or "")
            if ref is None:
                continue
            if ref.id == e.id:
                ok = True
            elif ref.kind == "edge" and ref.shape == "line" and ref.view == i["view"]:
                a, b = ref._intent["p1"], ref._intent["p2"]
                if abs(a[1] - b[1]) < 1e-9 and round(abs(a[1]), 6) in ys:
                    ok = True
        if not ok:
            out.append(_f("rough_fit", e.id, f"{e.id} 是 IT{it} 配合面，没有标粗糙度"))
    return out


PACKS = {
    "drafting": (line_width, text_height, scale, sheet, conv_dim, section_ref, center_mark),
    "dimensioning": (duplicate, closed_loop, missing, param_cover),
    "tolerancing": (dev_order, gtol_syntax, datum_letter, general_tol, chain_limit),
    "surface": (rough_syntax, rough_default, rough_fit),
}
