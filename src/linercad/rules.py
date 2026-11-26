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


CONV_NEED = {"thread": 1, "thread_mesh": 1, "spline": 1, "groove": 1, "keyway": 2}


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


# ---- geometric tolerances (E4): T.syntax / T.target / T.hier read res/gtol.toml ------


def _gtol_data(char):
    from . import res

    try:
        return res.gtol(char)
    except Exception:  # noqa: BLE001 - an unknown characteristic is a syntax finding, not a crash
        return None


def _gtol_clause(data, row=None) -> str:
    if row is not None and row.get("clause"):
        return f"GB/T 1182-2018 {row['clause']}；表1"
    refs = "、".join(str(c) for c in data.get("clauses", ())) or "表1"
    return f"GB/T 1182-2018 表1；{refs}"


_FORM_TARGETS = {
    "circularity": ("circle", "integral"),
    "cylindricity": ("cylindrical_surface", "integral"),
    "flatness": ("surface", "integral"),
    "straightness": ("line", "integral"),
    "profile_line": ("line", "integral"),
    "profile_surface": ("surface", "integral"),
}


def _target_row(data, target_kind, ref_shape, has_datums=False, direction_only=False):
    """(row, target, nature): the table-1 row and measured-element signature for this callout."""
    char = data["char"]
    rows = list(data["rows"])
    if char.startswith("profile_"):
        if has_datums:
            # rows are ordered form, orientation, location: >< marks the direction-only case,
            # otherwise a datum-constrained profile is a location specification
            rows = [r for r in rows if r["datum"] != "no"] or rows
            rows = [rows[0] if direction_only else rows[-1]]
        else:
            rows = [r for r in rows if r["datum"] == "no"] or rows
    if char == "circular_runout":
        wanted = [("circle", "integral")]
    elif char == "total_runout":
        wanted = [("surface", "integral")]
    elif char in _FORM_TARGETS:
        wanted = [_FORM_TARGETS[char]]
    elif target_kind == "axis":
        wanted = [
            ("derived_line", "derived"),
            ("line", "derived"),
            ("plane", "derived"),
            ("point", "derived"),
            ("derived_point", "derived"),
        ]
    else:
        wanted = [
            ("surface", "integral"),
            ("circle", "integral"),
            ("line", "integral"),
            ("cylindrical_surface", "integral"),
        ]
    for target, nature in wanted:  # prefer the most specific declared target
        for row in rows:
            if target in row["targets"] and nature in row["target_natures"]:
                return row, target, nature
    return None, None, None


def _condition_holds(when, target_kind, ref_shape) -> bool:
    """Can the declared intent establish the modifier_conditions 'when' clause?"""
    if when == "integral":
        return target_kind == "surface"
    if when == "integral_plane":
        return target_kind == "surface" and ref_shape == "line"
    if when == "derived_line":
        return target_kind == "axis" or ref_shape == "line"
    if when == "nominal_line_point_set":
        return target_kind in ("axis", "point") or ref_shape == "line"
    return False  # profile / profile_angle / direction_only need TEF/angle state not in the intent


def _runout_ref_ok(d, e, data, ref):
    if ref is None:
        return True
    if ref.kind == "dim":
        # only a diameter / radius dimension resolves to circular elements or an axis;
        # a linear dimension measures two parallel planes and is not a runout target
        return ref._intent.get("type") in ("dia", "rad")
    if ref.kind == "feature":
        return ref._intent.get("type") in ("turned", "cylinder", "revolved", "shaft")
    if ref._intent.get("shape") in ("circle", "arc"):
        return True
    feat = d._els.get(ref._intent.get("feature"))
    return feat is not None and feat._intent.get("type") in (
        "turned",
        "cylinder",
        "revolved",
        "shaft",
    )


def gtol_syntax(d):
    """T.syntax: table-1 semantics read from res/gtol.toml (datum rule, zone shape, modifiers,
    the Phi rule for a cylindrical zone on an axis, datum references defined)."""
    out = []
    defined = {e.id for e in _els(d, "datum")}
    n = 0
    for e in _els(d, "gtol"):
        i = e._intent
        data = _gtol_data(i.get("char"))
        n += 1
        if data is None:
            out.append(
                _f(
                    "gtol_syntax",
                    e.id,
                    f"{e.id}：特征项目 {i.get('char')!r} 不在 GB/T 1182-2018 表1 的数据中",
                    "error",
                    measured={"char": i.get("char")},
                    expected={"char": "GB/T 1182-2018 表1 的 14 个特征符号之一"},
                    std="GB/T 1182-2018",
                    clause="GB/T 1182-2018 表1",
                )
            )
            continue
        ref = d._els.get(i.get("ref"))
        shape = ref._intent.get("shape") if ref is not None else None
        refs = list(i.get("datum_refs") or ())
        row, _target, _nature = _target_row(
            data, i.get("target"), shape, bool(refs), "><" in (i.get("modifiers") or ())
        )
        row = row or data["rows"][0]
        std = data.get("std", "GB/T 1182-2018")
        clause = _gtol_clause(data, row)
        # 1. datum rule of the selected table-1 row
        if row["datum"] == "no" and refs:
            out.append(
                _f(
                    "gtol_syntax",
                    e.id,
                    f"{e.id}：{row['id']} 是形状公差行，不能带基准（{clause}）",
                    "error",
                    measured={"datums": [x.get("letter") for x in i.get("datums", ())]},
                    expected={"datum": "无"},
                    candidates=["去掉基准"],
                    std=std,
                    clause=clause,
                )
            )
        elif row["datum"] == "yes" and not refs:
            out.append(
                _f(
                    "gtol_syntax",
                    e.id,
                    f"{e.id}：{row['id']} 必须有基准（{clause}）",
                    "error",
                    measured={"datums": []},
                    expected={"datum": "至少一个已定义基准"},
                    candidates=["datums=['A']"],
                    std=std,
                    clause=clause,
                )
            )
        # 2. explicit tolerance-zone shape must be a shape of the selected row
        zone = i.get("zone")
        if zone is not None:
            n += 1
            shape_name = {"dia": "cylinder", "sphere": "sphere"}.get(zone, zone)
            if shape_name not in row["zone_shapes"]:
                out.append(
                    _f(
                        "gtol_syntax",
                        e.id,
                        f"{e.id}：{row['id']} 的公差带不能是 {zone!r}（行数据允许 {row['zone_shapes']}）",
                        measured={"zone": zone, "shape": shape_name},
                        expected={"zone_shapes": row["zone_shapes"]},
                        candidates=list(row["zone_shapes"]),
                        std=std,
                        clause=clause,
                    )
                )
        # 3. modifiers: unconditional row symbols, or conditional symbols whose 'when' holds
        mods = list(i.get("modifiers") or ())
        if mods:
            n += len(mods)
            allowed = set(row["modifiers"])
            cond_allowed = {}
            for c in row.get("modifier_conditions", ()):
                cond_allowed[c["symbol"]] = c
            unverified = set(data.get("modifiers_unverified", ()))
            for m in mods:
                if m in allowed:
                    continue
                cond = cond_allowed.get(m)
                if cond is not None and _condition_holds(cond["when"], i.get("target"), shape):
                    continue
                if cond is not None:
                    why = f"仅在 {cond['when']} 条件下可用（{cond['clause']}），当前意图无法建立该条件"
                elif m in unverified:
                    why = f"{m} 属于未读的 GB/T 16671-2018 / ISO 10579 数据"
                else:
                    why = f"不在 {row['id']} 的允许修饰符中"
                out.append(
                    _f(
                        "gtol_syntax",
                        e.id,
                        f"{e.id}：修饰符 {m} 不被 {row['id']} 接受（{why}）",
                        measured={"modifier": m, "allowed": sorted(allowed), "when": cond},
                        expected={"modifier": f"来自 {row['id']} 的修饰符数据"},
                        candidates=sorted(allowed | set(cond_allowed)),
                        std=std,
                        clause=cond["clause"] if cond else clause,
                    )
                )
        # 4. 7.4: a cylindrical zone on an axis is written with Phi.  Only require it when the
        # selected row's possible zones are all cylindrical (concentricity/coaxiality); an
        # omitted zone on straightness/position may legitimately mean parallel planes/lines.
        if i.get("target") == "axis":
            zones = set(row["zone_shapes"])
            cylindrical_only = zones and zones <= {
                "circle",
                "cylinder",
                "two_concentric_circles",
                "two_coaxial_cylinders",
            }
            measurable_axis = bool(set(row["targets"]) & {"line", "derived_line"})
            if zone == "dia":
                pass
            elif zone is None and cylindrical_only and measurable_axis:
                n += 1
                out.append(
                    _f(
                        "gtol_syntax",
                        e.id,
                        f"{e.id}：{row['id']} 的被测要素是轴线、公差带为圆柱，公差值前应加 Φ（zone='dia'）",
                        measured={"target": "axis", "zone": None},
                        expected={"zone": "dia"},
                        candidates=["zone='dia'"],
                        std=std,
                        clause=clause,
                    )
                )
        # 5. every referenced datum must be defined
        missing = [r for r in refs if r not in defined]
        n += len(refs)
        for r in missing:
            out.append(
                _f(
                    "gtol_syntax",
                    e.id,
                    f"{e.id} 引用的基准 {r} 没有定义（v.datum）",
                    "error",
                    measured={"referenced": refs, "defined": sorted(defined)},
                    expected={"referenced": "全部已定义"},
                    candidates=[r],
                    std=std,
                    clause=clause,
                )
            )
    return out, n


def gtol_target(d):
    """T.target: the measured element the callout points at must be a target of that
    characteristic in table 1, and datum callouts must carry a matching datum nature."""
    out = []
    n = 0
    for e in _els(d, "gtol"):
        i = e._intent
        data = _gtol_data(i.get("char"))
        if data is None:
            continue
        n += 1
        ref = d._els.get(i.get("ref"))
        shape = ref._intent.get("shape") if ref is not None else None
        refs = list(i.get("datum_refs") or ())
        row, target, nature = _target_row(
            data, i.get("target"), shape, bool(refs), "><" in (i.get("modifiers") or ())
        )
        if row is not None and data["char"] in _FORM_TARGETS:
            want = _FORM_TARGETS[data["char"]][0]
            if want in ("surface", "circle", "cylindrical_surface") and i.get("target") == "axis":
                row = None
            elif want in ("circle", "cylindrical_surface"):
                if shape not in ("circle", "arc"):
                    row = None
            elif want == "line":
                if ref is not None and ref.kind == "edge" and shape != "line":
                    row = None
            elif want == "surface":
                if ref is not None and ref.kind == "edge" and shape not in ("line",):
                    row = None
        if row is not None and data["char"] in ("circular_runout", "total_runout"):
            if not _runout_ref_ok(d, e, data, ref):
                row = None
        std = data.get("std", "GB/T 1182-2018")
        clause = _gtol_clause(data, row)
        if row is None:
            out.append(
                _f(
                    "gtol_target",
                    e.id,
                    f"{e.id}：{data['char']} 的被测要素（{i.get('target')}，引用 {i.get('ref')}）"
                    "不是该特征在表1 允许的要素种类/性质",
                    "error",
                    measured={"char": data["char"], "target": i.get("target"), "ref": i.get("ref")},
                    expected={"targets": data["targets"], "target_natures": data["target_natures"]},
                    candidates=list(data["targets"]),
                    std=std,
                    clause=clause,
                )
            )
        for r in refs:
            dt = d._els.get(r)
            if dt is None:
                continue
            n += 1
            dt_target = dt._intent.get("target")
            dref = d._els.get(dt._intent.get("ref"))
            bad = None
            if dt_target == "axis" and (dref is None or dref.kind != "dim"):
                bad = "axis datum must reference a feature of size (dimension)"
            elif dt_target == "surface" and (dref is None or dref.kind not in ("edge", "feature")):
                bad = "surface datum must reference an edge / face"
            if bad:
                out.append(
                    _f(
                        "gtol_target",
                        dt.id,
                        f"{dt.id}：基准 {dt._intent.get('letter')} 的 target={dt_target!r} 与引用几何不符（{bad}）",
                        "error",
                        measured={"target": dt_target, "ref": dt._intent.get("ref")},
                        expected={"target": "axis → 尺寸；surface → 边/面"},
                        std="GB/T 1182-2018 表1",
                        clause="GB/T 1182-2018 表1",
                    )
                )
    return out, n


_RANK = {"form": 0, "orientation": 1, "location": 2}


def _gtol_feature_key(d, ref):
    el = d._els.get(ref)
    if el is None:
        return ("ref", ref)
    if el.kind == "feature":
        return ("feature", ref)
    if el.kind == "edge":
        return ("feature", el._intent.get("feature") or ref)
    if el.kind == "dim":
        keys = set()
        for rid in getattr(el, "_refs", ()):
            o = d._els.get(rid)
            if o is None:
                continue
            if o.kind == "edge":
                keys.add(("feature", o._intent.get("feature") or rid))
            elif o.kind == "feature":
                keys.add(("feature", rid))
        if len(keys) == 1:
            return keys.pop()
    return ("ref", ref)


def _gtol_category(d, e, data):
    i = e._intent
    refs = bool(i.get("datum_refs"))
    char = data["char"]
    if char.startswith("profile_"):
        # TEF constrained by datums = orientation/location; '><' marks the direction-only case
        if refs:
            return "orientation" if "><" in (i.get("modifiers") or ()) else "location"
        return "form"
    row, _t, _n = _target_row(data, i.get("target"), None, refs, "><" in (i.get("modifiers") or ()))
    return row["category"] if row is not None else data["categories"][0]


def gtol_hier(d):
    """T.hier: same feature form <= orientation <= location; runout must not be tighter than
    the corresponding form/location tolerance.  Size-tolerance comparisons are not judged:
    the evidence (gtol-clauses.md §5) records that GB/T 4249 was not read for that relation."""
    out = []
    n = 0
    groups = {}
    for e in _els(d, "gtol"):
        i = e._intent
        data = _gtol_data(i.get("char"))
        if data is None:
            continue
        key = _gtol_feature_key(d, i.get("ref"))
        groups.setdefault(key, []).append((e, data, _gtol_category(d, e, data)))
    for entries in groups.values():
        for k, (a, _da, ca) in enumerate(entries):
            for b, _db, cb in entries[k + 1 :]:
                # runout vs form/location: t_runout must be >= the covered form/location value
                if ca == "run-out" or cb == "run-out":
                    ro, other = ((a, ca), (b, cb)) if ca == "run-out" else ((b, cb), (a, ca))
                    allowed_other = (
                        {"circularity"}
                        if ro[0]._intent["char"] == "circular_runout"
                        else {"concentricity", "coaxiality"}
                    )
                    if other[0]._intent["char"] in allowed_other:
                        n += 1
                        if ro[0]._intent["value"] < other[0]._intent["value"] - 1e-9:
                            out.append(
                                _f(
                                    "gtol_hier",
                                    ro[0].id,
                                    f"{ro[0].id}（{ro[0]._intent['char']} {ro[0]._intent['value']:g}）"
                                    f" 小于 {other[0].id}（{other[0]._intent['char']} "
                                    f"{other[0]._intent['value']:g}）：跳动应不小于对应的形状/位置公差",
                                    measured={"value": ro[0]._intent["value"], "with": other[0].id},
                                    expected={"value": f">= {other[0]._intent['value']:g}"},
                                    std="GB/T 4249-2018",
                                )
                            )
                    continue
                ra, rb = _RANK.get(ca), _RANK.get(cb)
                if ra is None or rb is None or ra == rb:
                    continue
                n += 1
                lo, hi = (a, b) if ra < rb else (b, a)
                if lo._intent["value"] > hi._intent["value"]:
                    out.append(
                        _f(
                            "gtol_hier",
                            lo.id,
                            f"{lo.id}（{lo._intent['char']} {lo._intent['value']:g}）"
                            f" 大于 {hi.id}（{hi._intent['char']} {hi._intent['value']:g}）："
                            "形状/方向/位置的公差值应逐级不减",
                            measured={"value": lo._intent["value"], "with": hi.id},
                            expected={"value": f"<= {hi._intent['value']:g}"},
                            std="GB/T 4249-2018",
                        )
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
    if not dims:
        return [], 0  # no untoleranced dimension: nothing for the drawing-level check to look at
    if general_class(d):
        return [], 1  # the drawing-level check ran against the declared class and passed
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


def _check_gb_text_range(rule: str, eid: str, h: float, series, scope: str):
    allowed = [s for s in series if 2.5 - 1e-6 <= s <= 5.0 + 1e-6]
    if 2.5 - 1e-6 <= h <= 5.0 + 1e-6 and any(abs(h - s) < 1e-3 for s in series):
        return None
    return _f(
        rule,
        eid,
        f"{eid} 的字高 {h:g} mm 超出{scope}推荐范围 [2.5, 5.0] 或不在字高系列 {allowed} 内",
        measured={"text_height": h},
        expected={"range": [2.5, 5.0], "heights": allowed},
        candidates=[f'd["{eid}"].set(text_height={s:g})' for s in allowed],
    )


def title_style_gb(d):
    out = []
    series = d.std["text"]["heights"]
    n = 0
    for e in d._els.values():
        if e.kind != "table.cell" or e._intent.get("table") != "title" or "field" not in e._intent:
            continue
        if e._intent.get("text_height") is None:
            continue
        n += 1
        f = _check_gb_text_range(
            "title_style_gb", e.id, float(e._intent["text_height"]), series, "标题栏"
        )
        if f is not None:
            out.append(f)
    return out, n


def table_style_gb(d):
    out = []
    series = d.std["text"]["heights"]
    n = 0
    for e in d._els.values():
        if e.kind == "table":
            if e._intent.get("text_height") is not None:
                n += 1
                f = _check_gb_text_range(
                    "table_style_gb", e.id, float(e._intent["text_height"]), series, "表格"
                )
                if f is not None:
                    out.append(f)
            if e._intent.get("border_width") is not None:
                n += 1
                bw = float(e._intent["border_width"])
                if not any(abs(bw - w) < 1e-6 for w in LINE_SERIES):
                    out.append(
                        _f(
                            "table_style_gb",
                            e.id,
                            f"{e.id} 边框线宽 {bw:g} mm 不在线宽系列内",
                            measured={"border_width": bw},
                            expected={"widths": list(LINE_SERIES)},
                            candidates=[
                                f'd["{e.id}"].set(border_width={w:g})' for w in LINE_SERIES
                            ],
                        )
                    )
        elif (
            e.kind == "table.cell"
            and e._intent.get("table") != "title"
            and e._intent.get("text_height") is not None
        ):
            n += 1
            f = _check_gb_text_range(
                "table_style_gb", e.id, float(e._intent["text_height"]), series, "表格"
            )
            if f is not None:
                out.append(f)
    return out, n


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
    "gtol_syntax": "按 GB/T 1182-2018 表1 判基准有无、公差带形状、修饰符与轴线圆柱带的 Φ；引用基准应已定义",
    "gtol_target": "被测要素的种类/性质应与 GB/T 1182-2018 表1 的特征项目匹配",
    "gtol_hier": "同一要素形状 ≤ 方向 ≤ 位置；跳动 ≥ 对应的圆度/同轴度；尺寸公差关系未判（GB/T 4249-2018 原文未读）",
    "datum_letter": "基准字母不应选用标准建议不用的字母",
    "general_tol": "有未注公差的尺寸时应注明未注公差等级",
    "chain_limit": "封闭环的极限尺寸应在设计要求范围内",
    "rough_syntax": "表面粗糙度参数值应取优先系列（资源库只录了优选系列）",
    "rough_default": "有表面粗糙度要求时应给出“其余”统一注法",
    "rough_fit": "IT≤7 的配合表面应标注表面粗糙度",
    "title_style_gb": "标题栏字体高度应符合推荐范围 [2.5, 5.0] mm 及标准字高系列",
    "table_style_gb": "表格字体高度应符合 [2.5, 5.0] mm 且边框线宽应在线宽系列内",
}


PACKS = {
    "drafting": (
        line_width,
        text_height,
        scale,
        sheet,
        conv_dim,
        section_ref,
        center_mark,
        title_style_gb,
        table_style_gb,
    ),
    "dimensioning": (duplicate, closed_loop, missing, param_cover),
    "tolerancing": (
        dev_order,
        gtol_syntax,
        gtol_target,
        gtol_hier,
        datum_letter,
        general_tol,
        chain_limit,
    ),
    "surface": (rough_syntax, rough_default, rough_fit),
}
