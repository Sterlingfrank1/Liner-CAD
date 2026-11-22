"""Checks v1 rule packs (SPEC M1 §7): drafting, dimensioning, tolerancing, surface. The layout
pack stays in ``checks.py``; ``checks.run`` adds the pack, the standard number and the clause.

Rule protocol (v0.1.1 E1): a rule takes the drawing and returns ``(findings, opportunities)``.
*Opportunities* is the number of independent checks the rule performed — every check can produce
at most one finding, so a rule's pass rate is ``1 - violations / opportunities``
(docs/proposals/benchmark-metrics.md §2). "Check" and "object" coincide for the element rules;
the few drawing-level predicates (the thick:thin ratio, the general-tolerance note) count as one
check. Every finding carries ``rule, id, message, severity``, the measured values, the expectation
it broke, candidate fixes (an empty dict / list when the field has nothing to say) and the clause
statement being applied. ``checks.run`` prefixes the clause with the standard number from the
active profile's ``[checks]`` table, so a GB drawing cites GB and an ISO drawing cites ISO.
"""

from __future__ import annotations

import math

from .layout import Text

LINE_SERIES = (0.13, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0)  # GB/T 4457.4 / ISO 128-2


def _f(rule, id, message, severity="warn", measured=None, expected=None, candidates=None, **kw):
    return {
        "rule": rule,
        "id": id,
        "message": message,
        "severity": severity,
        "violations": [],
        "corridors": {},
        "measured": dict(measured or {}),
        "expected": dict(expected or {}),
        "candidates": list(candidates or []),
        **kw,
    }


def _els(d, kind):
    return [e for e in d._els.values() if e.kind == kind]


# ---- drafting -------------------------------------------------------------------------------------


def line_width(d):
    out = []
    ln = d.std["lines"]
    n = sum(1 for spec in ln.values() if isinstance(spec, dict))
    for role, spec in ln.items():
        if isinstance(spec, dict) and not any(abs(spec["width"] - w) < 1e-6 for w in LINE_SERIES):
            out.append(
                _f(
                    "line_width",
                    "T.frame",
                    f"{role} 线宽 {spec['width']} 不在线宽系列内",
                    "error",
                    measured={"role": role, "width": spec["width"]},
                    expected={"width": "线宽系列"},
                    candidates=[f"{w:g}" for w in LINE_SERIES],
                )
            )
    t, thin = ln["thick"]["width"], ln["thin"]["width"]
    n += 1  # the thick:thin ratio is one more object of the rule
    if abs(t / thin - 2) > 0.05:
        out.append(
            _f(
                "line_width",
                "T.frame",
                f"粗线 {t} 与细线 {thin} 应为 2:1",
                "error",
                measured={"thick": t, "thin": thin, "ratio": round(t / thin, 3)},
                expected={"ratio": 2.0},
                candidates=[f"{2 * thin:g}"],
            )
        )
    return out, n


def text_height(d):
    out = []
    series = d.std["text"]["heights"]
    dim_h = d.std["dim"]["text_height"]
    n = 0
    for e in d._els.values():
        hs = {round(p.height, 3) for p in e._prims if isinstance(p, Text)}
        if not hs:
            continue
        n += 1
        bad = [h for h in hs if not any(abs(h - s) < 1e-3 for s in series)]
        if bad:
            out.append(
                _f(
                    "text_height",
                    e.id,
                    f"{e.id} 的字高 {bad} 不在字高系列 {series} 内",
                    "error",
                    measured={"heights": bad},
                    expected={"heights": "字高系列"},
                    candidates=[f"{s:g}" for s in series],
                )
            )
        elif e.kind == "dim" and e._prims:
            main = [p for p in e._prims if isinstance(p, Text)][0].height
            if abs(main - dim_h) > 1e-3:
                out.append(
                    _f(
                        "text_height",
                        e.id,
                        f"{e.id} 的尺寸数字字高 {main} 与标准档 {dim_h} 不同",
                        measured={"height": main, "standard": dim_h},
                        expected={"height": dim_h},
                        candidates=[f"{dim_h:g}"],
                    )
                )
    return out, n


def scale(d):
    sc = d.std["scales"]
    items = [(d.scale_text, "T.title.scale")] + [
        (v._intent["scale_text"], v.id) for v in d.views() if v._intent.get("scale_text")
    ]
    out = []
    for txt, id in items:
        if txt not in sc["preferred"] and txt not in sc["allowed"]:
            out.append(
                _f(
                    "scale",
                    id,
                    f"比例 {txt} 不在比例系列内",
                    "warn",
                    measured={"scale": txt},
                    expected={"scale": "比例优先 / 允许系列"},
                    candidates=list(sc["preferred"]),
                )
            )
    return out, len(items)


def sheet(d):
    sheets = d.std["sheets"]
    size = sorted(d.template["size"])
    if not any(sorted(v) == size for k, v in sheets.items() if isinstance(v, list)):
        return [
            _f(
                "sheet",
                "T.frame",
                f"图幅 {d.template['size']} 不是基本幅面",
                "error",
                measured={"size": list(d.template["size"])},
                expected={"size": "基本幅面"},
                candidates=[k for k, v in sheets.items() if isinstance(v, list)],
            )
        ], 1
    return [], 1


CONV_NEED = {"thread": 1, "spline": 1, "groove": 1, "keyway": 2}


def conv_dim(d):
    out = []
    dims = _els(d, "dim")
    feats = [f for f in _els(d, "feature") if CONV_NEED.get(f._intent.get("type"))]
    for f in feats:
        t = f._intent.get("type")
        need = CONV_NEED[t]
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
                    measured={"type": t, "dimensions": n},
                    expected={"dimensions": f">= {need}"},
                )
            )
    return out, len(feats)


def section_ref(d):
    out = []
    marks = {e._intent.get("letter") for e in d._els.values() if e.kind in ("section", "mark")}
    views = [v for v in d.views() if v._intent.get("aux")]
    sections = [e for e in d._els.values() if e.kind == "section"]
    for v in views:
        if v._intent.get("name") not in marks:
            out.append(
                _f(
                    "section_ref",
                    v.id,
                    f"{v.id} 在父视图里没有对应的标记",
                    "error",
                    measured={"aux_view": v.name},
                    expected={"mark": v._intent.get("name")},
                )
            )
    view_ids = [v.id for v in d.views()]
    for e in sections:
        if f"V.{e._intent['view']}" not in d._els:
            out.append(
                _f(
                    "section_ref",
                    e.id,
                    f"{e.id} 的目标视图不存在",
                    "error",
                    measured={"target": f"V.{e._intent['view']}"},
                    expected={"target": "在图纸里"},
                    candidates=view_ids,
                )
            )
    return out, len(views) + len(sections)


def _on_center(c, centers):
    for ce in centers:
        i = ce._intent
        kind = i.get("type") or i.get(
            "shape"
        )  # CenterLine.type, or the shape of a centre-role edge
        if kind in ("mark", "circle") and math.dist(i["c"], c) < 0.01:
            return True
        if kind == "line":
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
    targets = {}  # target id -> its circles: the finding is reported once per target
    for v in d.views():
        centers = [e for e in _els(d, "center") if e.view == v.name]
        centers += [  # centre lines drawn as plain edges (a DXF import has no CenterLine elements)
            e
            for e in _els(d, "edge")
            if e.view == v.name and e.role == "center" and e.shape != "arc"
        ]
        for e in _els(d, "edge"):
            if e.view == v.name and e.shape == "circle" and e.role in ("thick", "hidden"):
                tid = e._intent.get("feature") or e.id
                targets.setdefault(tid, []).append((e, centers))
    for tid, circles in targets.items():
        bad = [e for e, centers in circles if not _on_center(e._intent["c"], centers)]
        if bad:
            e = bad[0]
            out.append(
                _f(
                    "center_mark",
                    tid,
                    f"{e.id} 的圆心没有中心线",
                    measured={
                        "circle": e.id,
                        "center": list(e._intent["c"]),
                        "missing": len(bad),
                    },
                    expected={"center_line": "过圆心"},
                )
            )
    return out, len(targets)


# ---- dimensioning ------------------------------------------------------------------------------------


def _key(x):
    return round(x, 6)


def duplicate(d):
    out, seen = [], {}
    n = 0
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
        n += 1
        if k in seen:
            out.append(
                _f(
                    "duplicate",
                    e.id,
                    f"{e.id} 与 {seen[k]} 重复标注同一尺寸",
                    violations=[{"with": seen[k], "overlap": 0}],
                    measured={"duplicate_of": seen[k], "annotations": 2},
                    expected={"annotations": 1},
                    candidates=[seen[k]],
                )
            )
        else:
            seen[k] = e.id
    return out, n


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
    n = 0
    for v in d.views():
        for axis in ("h", "v"):
            uf = _UF()
            for did, a, b in _links(d, v.name, axis):
                n += 1
                if a != b and not uf.union(a, b):
                    out.append(
                        _f(
                            "closed_loop",
                            did,
                            f"{did} 使 {v.id} 的尺寸链封闭（{axis} 向），改成参考尺寸或删去一个",
                            measured={"view": v.name, "axis": axis},
                            expected={"closed_loop": False},
                            candidates=["改为参考尺寸（reference=True）", "删去一个尺寸"],
                        )
                    )
    return out, n


def missing(d):
    from .revolve import _corners

    out = []
    feats = [f for f in _els(d, "feature") if f._intent.get("type") == "turned"]
    for f in feats:
        i = f._intent
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
            parts = sorted(groups.values(), key=len, reverse=True)
            loose = "；".join("x=" + "、".join(f"{x:g}" for x in g) for g in parts[1:])
            out.append(
                _f(
                    "missing",
                    f.id,
                    f"{f.id} 有轴向台阶没有尺寸连到其余台阶：{loose}（已连通：x={parts[0][0]:g}…{parts[0][-1]:g}）",
                    measured={"unconnected": [f"x={g[0]:g}" for g in parts[1:]]},
                    expected={"axis_steps": "全部连通"},
                    candidates=[f"x={g[0]:g}" for g in parts[1:]],
                )
            )
    return out, len(feats)


def param_cover(d):
    covered = set()
    for e in d._els.values():
        covered |= set(e._covers)
    out = []
    names = list(d.P._params)
    for name in names:
        if name not in covered:
            out.append(
                _f(
                    "param_cover",
                    f"P.{name}",
                    f"参数 {name} 没有被任何尺寸覆盖（写进尺寸、技术要求，或 accept）",
                    measured={"param": name, "covered": False},
                    expected={"covered": "被尺寸、技术要求或 accept 覆盖"},
                )
            )
    return out, len(names)


# ---- tolerancing --------------------------------------------------------------------------------


def dev_order(d):
    out = []
    dims = [e for e in _els(d, "dim") if e._intent.get("tolerance")]
    for e in dims:
        t = e._intent["tolerance"]
        if t["upper"] < t["lower"] - 1e-12:
            out.append(
                _f(
                    "dev_order",
                    e.id,
                    f"{e.id} 上偏差小于下偏差",
                    "error",
                    measured={"upper": t["upper"], "lower": t["lower"]},
                    expected={"upper": ">= lower"},
                )
            )
    return out, len(dims)


def gtol_syntax(d):
    out = []
    gtols = _els(d, "gtol")
    defined = sorted(e._intent["letter"] for e in _els(d, "datum"))
    for e in gtols:
        i = e._intent
        if (
            i["char"] in ("concentricity", "position")
            and i["target"] == "axis"
            and i["zone"] is None
        ):
            out.append(
                _f(
                    "gtol_syntax",
                    e.id,
                    f"{e.id}：被测要素是轴线时公差带为圆柱，公差值前应加 Φ（zone='dia'）",
                    measured={"target": i["target"], "zone": i["zone"]},
                    expected={"zone": "dia"},
                    candidates=["zone='dia'"],
                )
            )
        missing_ = [r for r in i.get("datum_refs", []) if r not in d._els]
        if missing_:
            out.append(
                _f(
                    "gtol_syntax",
                    e.id,
                    f"{e.id} 引用的基准 {missing_} 没有定义（v.datum）",
                    "error",
                    measured={"referenced": list(i.get("datum_refs", [])), "defined": defined},
                    expected={"referenced": "全部已定义"},
                    candidates=missing_,
                )
            )
    n = len(gtols)  # every gtol: are its datum references defined?
    n += sum(  # the additional zone assertion only applies to an axis with a cylindrical zone
        1
        for e in gtols
        if e._intent["char"] in ("concentricity", "position") and e._intent["target"] == "axis"
    )
    return out, n


def datum_letter(d):
    from . import res

    fn = getattr(res, "datum_excluded", None)
    if fn is None:
        return [], 0
    try:
        bad = set(fn(d.std_name if d.std_name in ("GB", "ISO") else "GB")["letters"])
    except Exception:  # noqa: BLE001 - the profile may not list one
        return [], 0
    # the standard only recommends against these letters (GB/T 17851-2010 6.2 note 2), so warn
    datums = _els(d, "datum")
    return [
        _f(
            "datum_letter",
            e.id,
            f"基准字母 {e._intent['letter']}：标准建议不用 {'、'.join(sorted(bad))}",
            "warn",
            measured={"letter": e._intent["letter"]},
            expected={"letter": f"不在建议不用的字母 {'、'.join(sorted(bad))} 内"},
        )
        for e in datums
        if e._intent["letter"] in bad
    ], len(datums)


def general_tol(d):
    from .pmi import general_class

    dims = []
    for e in _els(d, "dim"):
        i = e._intent
        if (
            i["type"] in ("linear", "dia", "rad", "aligned")
            and not i.get("tolerance")
            and not i.get("reference")
        ):
            dims.append(e)
    if general_class(d) or not dims:
        return [], 1  # the drawing-level check ran and passed
    e = dims[0]
    return [
        _f(
            "general_tol",
            e.id,
            "有未注公差的尺寸，但没有未注公差说明（d.general_tol('m')）",
            measured={"dimension": e.id, "tolerance": None},
            expected={"general_tolerance": "已声明"},
            candidates=["d.general_tol('m')"],
        )
    ], 1


def chain_limit(d):
    out = []
    chains = _els(d, "chain")
    for e in chains:
        r = e._resolved.get("result")
        if r and not r["ok"]:
            req = e._intent["require"]
            out.append(
                _f(
                    "chain_limit",
                    e.id,
                    f"{e.id} 封闭环 {r['wc']} 超出要求 {req}",
                    "error",
                    measured={"worst_case": r["wc"], "require": list(req)},
                    expected={"worst_case": f"在 {list(req)} 内"},
                )
            )
    return out, len(chains)


# ---- surface ----------------------------------------------------------------------------------------


def rough_syntax(d):
    from . import res

    out = []
    checked = []
    for e in _els(d, "rough"):
        try:
            checked.append((e, res.rough_series(e._intent["param"])))
        except Exception:  # noqa: BLE001 - the resource library has no series for this parameter
            continue
    for e, ser in checked:
        i = e._intent
        first, extra = (
            (ser.get("preferred") or ser.get("first", []), ser.get("supplementary", []))
            if isinstance(ser, dict)
            else (ser, [])
        )
        v = i["value"]
        if any(abs(v - x) < 1e-9 for x in first):
            continue
        if any(abs(v - x) < 1e-9 for x in extra):
            out.append(
                _f(
                    "rough_syntax",
                    e.id,
                    f"{e.id} 的 {i['param']} {v:g} 属于补充系列",
                    measured={"param": i["param"], "value": v, "series": "补充系列"},
                    expected={"value": "粗糙度优选系列"},
                    candidates=[f"{x:g}" for x in first],
                )
            )
        else:
            out.append(
                _f(
                    "rough_syntax",
                    e.id,
                    f"{e.id} 的 {i['param']} {v:g} 不在粗糙度的优选系列内（资源库只录了优选系列）",
                    "warn",
                    measured={"param": i["param"], "value": v},
                    expected={"value": "粗糙度优选系列（资源库只录了优选系列）"},
                    candidates=[f"{x:g}" for x in first],
                )
            )
    return out, len(checked)


def rough_default(d):
    rs = _els(d, "rough")
    if not rs:
        return [], 0
    if not any(e._intent.get("default") for e in rs):
        return [
            _f(
                "rough_default",
                rs[0].id,
                "标了粗糙度但没有“其余”通用符号（d.rough_default）",
                measured={"symbols": len(rs), "default": False},
                expected={"default": "标注“其余”通用符号"},
                candidates=["d.rough_default(6.3)"],
            )
        ], 1
    return [], 1


def rough_fit(d):
    from . import res

    out = []
    fits = []
    for e in _els(d, "dim"):
        t = e._intent.get("tolerance")
        if not t or t["kind"] != "fit":
            continue
        try:
            it = res.fit(t["code"], e._intent["value"])["it"]
        except Exception:  # noqa: BLE001
            continue
        if it > 7:
            continue
        fits.append((e, it))
    rs = _els(d, "rough")
    for e, it in fits:
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
            out.append(
                _f(
                    "rough_fit",
                    e.id,
                    f"{e.id} 是 IT{it} 配合面，没有标粗糙度",
                    measured={"dimension": e.id, "it": it, "roughness": None},
                    expected={"roughness": "IT≤7 的配合面标注 Ra"},
                    candidates=[f"标注粗糙度并指向 {e.id} 或其所在表面"],
                )
            )
    return out, len(fits)


#: What each rule checks, as the clause statement it implements (benchmark-metrics §2 clause).
#: The standard number is prefixed at run time from the active profile's [checks] table; the exact
#: clause / table numbers arrive with the rule catalog (E2, rules/catalog.toml).
CLAUSES = {
    "line_width": "图线宽度应按线宽系列选取，粗线与细线的宽度比为 2:1",
    "text_height": "字体高度应按字高系列选取，尺寸数字与尺寸线保持一致",
    "scale": "比例应优先选用优先系列，必要时用允许系列",
    "sheet": "图纸幅面应选用基本幅面",
    "conv_dim": "螺纹、花键、键槽、退刀槽等规定画法要素应注出代号或必需尺寸",
    "section_ref": "辅助视图应有对应的剖切标记，剖切标记指向的目标视图应存在",
    "center_mark": "整圆的圆心应画出中心线",
    "duplicate": "同一尺寸只应标注一次",
    "closed_loop": "尺寸链不应封闭；必须封闭时把其中一个注成参考尺寸",
    "missing": "回转体的每个轴向台阶都应有尺寸与其余台阶相连",
    "param_cover": "每个参数都应由尺寸、技术要求或明确的放行覆盖",
    "dev_order": "尺寸的上偏差不应小于下偏差",
    "gtol_syntax": "轴线为被测要素且公差带为圆柱时公差值前加 Φ；引用的基准应已定义",
    "datum_letter": "基准字母不应选用标准建议不用的字母",
    "general_tol": "有未注公差的尺寸时应注明未注公差等级",
    "chain_limit": "封闭环的极限尺寸应在设计要求范围内",
    "rough_syntax": "表面粗糙度参数值应取优先系列（资源库只录了优选系列）",
    "rough_default": "有表面粗糙度要求时应给出“其余”统一注法",
    "rough_fit": "IT≤7 的配合表面应标注表面粗糙度",
}


PACKS = {
    "drafting": (line_width, text_height, scale, sheet, conv_dim, section_ref, center_mark),
    "dimensioning": (duplicate, closed_loop, missing, param_cover),
    "tolerancing": (dev_order, gtol_syntax, datum_letter, general_tol, chain_limit),
    "surface": (rough_syntax, rough_default, rough_fit),
}
