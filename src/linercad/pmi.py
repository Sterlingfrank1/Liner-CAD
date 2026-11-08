"""Semantic PMI elements (SPEC M1 §3.2–3.3): datums, geometric tolerances, surface roughness,
dimension chains and the general-tolerance note. Every field is stored separately and ``refs``
point at the toleranced geometry, so v0.2 can map them to STEP AP242 semantic PMI."""

from __future__ import annotations

import difflib
import math
import re

from .errors import InvalidArgument
from .geometry import Edge, Feature
from .model import Element, check_name, num

# characteristic → (datum rule, symbol key); GB/T 1182-2018 ↔ ISO 1101:2017
CHARS = {
    "straightness": "none",
    "flatness": "none",
    "circularity": "none",
    "cylindricity": "none",
    "profile_line": "optional",
    "profile_surface": "optional",
    "parallelism": "required",
    "perpendicularity": "required",
    "angularity": "required",
    "position": "optional",
    "concentricity": "required",
    "symmetry": "required",
    "circular_runout": "required",
    "total_runout": "required",
}
MODIFIERS = ("M", "L", "P", "F", "CZ", "T", "U")  # Ⓜ Ⓛ Ⓟ Ⓕ, common zone, ...; Ⓔ belongs to sizes
ROUGH_PARAMS = ("Ra", "Rz")
REMOVAL = ("required", "forbidden", "any")


def _target(d, ref, view):
    """→ (target kind, element id). A dimension means its feature of size (axis / median)."""
    from .annotate import Dim

    el = ref if isinstance(ref, Element) else d[ref]
    if isinstance(el, Dim):
        if el.view != view:
            raise InvalidArgument(f"{el.id} 在视图 {el.view}，不在 {view}", id=el.id)
        return "axis", el.id
    if isinstance(el, (Edge, Feature)):
        if el.view != view:
            raise InvalidArgument(f"{el.id} 在视图 {el.view}，不在 {view}", id=el.id)
        return "surface", el.id
    raise InvalidArgument(
        f"ref 应为尺寸（轴线 / 中心面）或边、特征（表面），{el.id} 是 {el.kind}", id=el.id
    )


class _Leader(Element):
    LAYOUT = ("at", "length")

    def _apply_place(self, fields):
        for k in ("at", "length"):
            if fields.get(k) is not None:
                fields[k] = num(fields[k], k)
        super()._apply_place(fields)

    def _apply_move(self, dx, dy):
        sx, sy = self._layout.get("shift", [0.0, 0.0])
        self._layout["shift"] = [sx + dx, sy + dy]


class Datum(_Leader):
    kind = "datum"
    READ = ("letter", "target")
    letter = property(lambda s: s._intent["letter"])
    target = property(lambda s: s._intent["target"])


class GTol(_Leader):
    kind = "gtol"
    SETTABLE = ("value", "datums", "zone", "modifiers")
    READ = ("char", "value", "datums", "zone", "modifiers", "target")
    char = property(lambda s: s._intent["char"])
    value = property(lambda s: s._intent["value"])

    def _apply_set(self, fields):
        i = dict(self._intent)
        i.update(fields)
        self._intent.update(
            _gtol_intent(self._d, i["char"], i["value"], i["datums"], i["zone"], i["modifiers"])
        )
        old = set(self._intent.get("datum_refs", []))
        refs = [f"DT.{x}" for ds in self._intent["datums"] for x in ds["letters"]]
        self._intent["datum_refs"] = refs
        self._refs[:] = [r for r in self._refs if r not in old]


class Rough(_Leader):
    kind = "rough"
    SETTABLE = ("value", "param", "removal", "process")
    READ = ("param", "value", "removal", "process", "target")
    value = property(lambda s: s._intent["value"])

    def _apply_set(self, fields):
        i = dict(self._intent)
        i.update(fields)
        self._intent.update(
            _rough_intent(self._d, i["value"], i["param"], i["removal"], i["process"])
        )


class Chain(Element):
    kind = "chain"
    READ = ("closing", "increase", "decrease")


def _parse_datums(datums):
    out = []
    for item in datums or ():
        if isinstance(item, dict):
            letters, mods = list(item.get("letters", [])), list(item.get("modifiers", []))
        else:
            m = re.fullmatch(r"([A-Z](?:-[A-Z])*)((?:\((?:M|L)\))*)", str(item).replace(" ", ""))
            if not m:
                raise InvalidArgument(
                    f"基准 {item!r} 写法不对",
                    candidates=["A", "A-B", "B(M)"],
                    values={"datum": item},
                )
            letters = m.group(1).split("-")
            mods = re.findall(r"\((M|L)\)", m.group(2))
        out.append({"letters": letters, "common": len(letters) > 1, "modifiers": mods})
    return out


def _gtol_intent(d, char, value, datums, zone, modifiers):
    if char not in CHARS:
        raise InvalidArgument(
            f"没有形位公差特征项目 {char!r}",
            candidates=difflib.get_close_matches(str(char), CHARS, n=5, cutoff=0.3) or list(CHARS),
        )
    value = num(value, "value")
    if value <= 0:
        raise InvalidArgument("形位公差值必须为正", values={"value": value})
    ds = _parse_datums(datums)
    rule = CHARS[char]
    if rule == "none" and ds:
        raise InvalidArgument(
            f"{char} 是形状公差，不能带基准（GB/T 1182-2018）", values={"datums": datums}
        )
    if rule == "required" and not ds:
        raise InvalidArgument(f"{char} 必须指定基准（GB/T 1182-2018）", hint="datums=['A']")
    if zone not in (None, "dia", "sphere"):
        raise InvalidArgument("zone 只能是 None、'dia'、'sphere'", candidates=["dia", "sphere"])
    mods = list(modifiers or ())
    for m in mods:
        if m not in MODIFIERS:
            hint = "包容要求 Ⓔ 属于尺寸公差：尺寸上 set(envelope=True)" if m == "E" else None
            raise InvalidArgument(f"修饰符 {m!r} 不支持", candidates=list(MODIFIERS), hint=hint)
    std = d.std.get("tolerancing", {}).get("gtol_std", "GB/T 1182-2018")
    return {"char": char, "value": value, "zone": zone, "modifiers": mods, "datums": ds, "std": std}


def _rough_intent(d, value, param, removal, process):
    if param not in ROUGH_PARAMS:
        raise InvalidArgument(f"粗糙度参数 {param!r} 不支持", candidates=list(ROUGH_PARAMS))
    if removal not in REMOVAL:
        raise InvalidArgument(f"removal 只能是 {REMOVAL}", candidates=list(REMOVAL))
    value = num(value, "value")
    if value <= 0:
        raise InvalidArgument("粗糙度值必须为正", values={"value": value})
    std = d.std.get("rough", {}).get("std", "GB/T 131-2006")
    return {"param": param, "value": value, "removal": removal, "process": process, "std": std}


# ---- constructors behind View / Drawing methods ---------------------------------------------------


def view_datum(view, letter, ref, at=None, length=None):
    d = view._d
    if not (isinstance(letter, str) and re.fullmatch(r"[A-Z]", letter)):
        raise InvalidArgument("基准字母应为一个大写拉丁字母", values={"letter": letter})
    target, rid = _target(d, ref, view.name)
    el = Datum(
        d,
        f"DT.{letter}",
        {"letter": letter, "view": view.name, "target": target, "ref": rid},
        refs=[view.id, rid],
    )
    el._apply_place({"at": at, "length": length})
    return d._add(el)


def view_gtol(
    view, name, char, value, datums=(), ref=None, zone=None, modifiers=(), at=None, length=None
):
    d = view._d
    if ref is None:
        raise InvalidArgument("形位公差需要 ref（被测要素：尺寸 → 轴线，边 → 表面）")
    i = _gtol_intent(d, char, value, datums, zone, modifiers)
    target, rid = _target(d, ref, view.name)
    gid = f"G.{check_name(name)}"
    letters = [x for ds in i["datums"] for x in ds["letters"]]
    el = GTol(d, gid, {**i, "view": view.name, "target": target, "ref": rid}, refs=[view.id, rid])
    el._intent["datum_refs"] = [f"DT.{x}" for x in letters]
    el._apply_place({"at": at, "length": length})
    return d._add(el)


def view_rough(
    view, name, value, ref, param="Ra", removal="required", process=None, at=None, length=None
):
    d = view._d
    i = _rough_intent(d, value, param, removal, process)
    target, rid = _target(d, ref, view.name)
    el = Rough(
        d,
        f"R.{check_name(name)}",
        {**i, "view": view.name, "target": target, "ref": rid},
        refs=[view.id, rid],
    )
    el._apply_place({"at": at, "length": length})
    return d._add(el)


def drawing_rough_default(d, value, param="Ra", removal="required"):
    i = _rough_intent(d, value, param, removal, None)
    return d._add(
        Rough(d, "R.default", {**i, "default": True, "view": None, "target": "rest", "ref": None})
    )


def drawing_chain(d, name, closing, increase=(), decrease=(), require=None):
    from .annotate import Dim

    check_name(closing, "封闭环名")
    members = []
    for sign, ids in ((1, increase), (-1, decrease)):
        for x in ids:
            el = d[x if isinstance(x, str) else x.id]
            if not isinstance(el, Dim):
                raise InvalidArgument(f"尺寸链的环应为尺寸，{el.id} 是 {el.kind}", id=el.id)
            members.append((sign, el.id))
    if not members:
        raise InvalidArgument("尺寸链至少要一个组成环")
    req = None
    if require is not None:
        lo, hi = (num(require[0], "require[0]"), num(require[1], "require[1]"))
        if lo > hi:
            raise InvalidArgument("require 应为 (下偏差, 上偏差)", values={"require": [lo, hi]})
        req = [lo, hi]
    intent = {
        "closing": closing,
        "increase": [m for s, m in members if s > 0],
        "decrease": [m for s, m in members if s < 0],
        "require": req,
    }
    return d._add(Chain(d, f"K.{check_name(name)}", intent, refs=[m for _, m in members]))


def drawing_general_tol(d, cls):
    from .annotate import Note

    if cls not in ("f", "m", "c", "v"):
        raise InvalidArgument(
            "未注公差等级应为 f / m / c / v（GB/T 1804-2000）", candidates=["f", "m", "c", "v"]
        )
    text = d.std["tolerancing"]["general_note"].format(cls=cls)
    nid = d._alloc("N", ("tech",))
    return d._add(Note(d, nid, {"tech": True, "text": text, "gentol": cls}))


def general_class(d):
    for e in d._els.values():
        if e.kind == "note" and e._intent.get("gentol"):
            return e._intent["gentol"]
    return None


def chain_result(d, el):
    from . import res

    cls = general_class(d)
    untol, rows = [], []
    for sign, ids in ((1, el._intent["increase"]), (-1, el._intent["decrease"])):
        for i in ids:
            dim = d._els.get(i)
            if dim is None:
                continue
            t = dim._intent.get("tolerance")
            if t is not None:
                up, lo = t["upper"], t["lower"]
            elif cls is not None:
                g = res.general_tol(cls, dim._intent["value"])
                up, lo = g["upper"], g["lower"]
            else:
                up = lo = 0.0
                untol.append(i)
            rows.append((sign, dim._intent["value"], up, lo))
    nominal = sum(s * v for s, v, _, _ in rows)
    wc_up = sum(up if s > 0 else -lo for s, _, up, lo in rows)
    wc_lo = sum(lo if s > 0 else -up for s, _, up, lo in rows)
    mid = sum(s * (up + lo) / 2 for s, _, up, lo in rows)
    T = math.sqrt(sum((up - lo) ** 2 for _, _, up, lo in rows))
    r = {
        "nominal": round(nominal, 9),
        "wc": {"upper": round(wc_up, 9), "lower": round(wc_lo, 9)},
        "rss": {"upper": round(mid + T / 2, 9), "lower": round(mid - T / 2, 9)},
        "untoleranced": untol,
    }
    req = el._intent.get("require")
    r["ok"] = req is None or (wc_lo >= req[0] - 1e-9 and wc_up <= req[1] + 1e-9)
    return r
