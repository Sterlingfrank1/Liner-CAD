"""Resource library: standard tables as package data (SPEC M1 §2, DESIGN §2.3).

Each standard is one TOML file in this package with a ``[meta]`` block (``std`` GB number with year,
``iso`` equivalent, ``source`` = where the numbers were checked, ``unit``). The functions below are thin
queries over those files; results are in mm and carry ``std``. A code or size that is not in the tables
raises ``InvalidArgument`` with ``candidates``. Only what the standard itself defines as a rule is computed
(hole deviations from the shaft table, thread d2/d1).
"""

from __future__ import annotations

import re
import tomllib
from bisect import bisect_left
from functools import cache
from importlib import resources

from ..errors import InvalidArgument

__all__ = [
    "center_hole",
    "datum_excluded",
    "std_part",
    "fit",
    "general_tol",
    "grinding_groove",
    "it",
    "key",
    "rough_series",
    "spline",
    "thread",
    "thread_classes",
    "thread_runout",
    "thread_undercut",
]


@cache
def _table(name: str) -> dict:
    """The parsed ``<name>.toml``; cached, so callers must not modify it."""
    return tomllib.loads(
        (resources.files(__package__) / f"{name}.toml").read_text(encoding="utf-8")
    )


def _mm(um: float) -> float:
    return round(um / 1000, 5)


def _band(upto: list, size: float, what: str, lower: float = 0, closed: bool = True) -> int:
    """Index of the band "over a, up to and including b" that holds ``size``: above 0, or from
    ``lower`` on when that is given; with ``closed`` False the last band has no upper limit."""
    size = round(size, 6)  # measured sizes carry float noise; band edges are inclusive
    inside = lower <= size if lower else size > 0
    if not inside or (closed and size > upto[-1]):
        raise InvalidArgument(
            f"{what}：尺寸 {size} 不在表格范围内",
            values={"size": size},
            hint=f"表格覆盖 {lower if lower else '大于 0'} 至 {upto[-1] if closed else '无上限'} mm",
        )
    return bisect_left(upto, size)


# ------------------------------------------------------------------------ GB/T 1800 fits

_SHAFT_LETTERS = "a b c d e f g h js k m n p r s t u".split()
_FIT_CODE = re.compile(r"(js|JS|[a-zA-Z])(\d+)")


def _it_um(grade: int, size: float) -> float:
    table = _table("fits")["it"]
    if not isinstance(grade, int) or f"IT{grade}" not in table:
        raise InvalidArgument(f"未知公差等级 {grade!r}", candidates=list(range(1, 19)))
    return table[f"IT{grade}"][_band(table["ranges"], size, "标准公差")]


def it(grade: int, size: float) -> float:
    """Standard tolerance IT``grade`` (1..18) in mm for a nominal size up to 500 mm."""
    return _mm(_it_um(grade, size))


def _fundamental(letter: str, size: float) -> int | None:
    """Tabulated fundamental deviation in um of the shaft ``letter`` (es for a-g, ei for k-u);
    None where the letter does not exist at this size (t at 24 mm and below)."""
    dev = _table("fits")["dev"]
    i = _band(dev["ranges"], size, "基本偏差")
    values = dev["es"].get(letter) or dev["ei"][letter]
    i -= len(dev["ranges"]) - len(values)  # a short array covers the last ranges only
    return values[i] if i >= 0 else None


def fit(code: str, size: float) -> dict:
    """Limit deviations of the tolerance class ``code`` ("H7", "k6", "JS9") at ``size`` mm:
    ``{"code", "upper", "lower", "it", "std"}``, deviations in mm. Upper case = hole, lower = shaft."""
    match = _FIT_CODE.fullmatch(code) if isinstance(code, str) else None
    if not match or match.group(1).lower() not in _SHAFT_LETTERS:
        raise InvalidArgument(
            f"公差带代号 {code!r} 不是 字母 + 公差等级（如 H7、k6、JS9）",
            candidates=_SHAFT_LETTERS + [x.upper() for x in _SHAFT_LETTERS],
            hint="大写 = 孔，小写 = 轴；等级 1..18",
        )
    letter, grade = match.group(1), int(match.group(2))
    low, hole = letter.lower(), letter.isupper()
    tol = _it_um(grade, size)
    if low == "js":
        upper, lower = tol / 2, -tol / 2
    elif low == "h":
        upper, lower = (tol, 0) if hole else (0, -tol)
    else:
        base = _fundamental(low, size)
        if base is None:
            raise InvalidArgument(
                f"{letter} 在公称尺寸 {size} mm 无基本偏差（{low} 只用于大于 24 mm）",
                candidates=[
                    x
                    for x in _SHAFT_LETTERS
                    if x in ("h", "js") or _fundamental(x, size) is not None
                ],
                values={"size": size},
            )
        if low in "abcdefg":  # es; the hole letter has EI = -es
            upper, lower = (tol - base, -base) if hole else (base, base - tol)
        elif not hole:  # ei; k applies to IT4..IT7 only
            ei = 0 if low == "k" and not 4 <= grade <= 7 else base
            upper, lower = ei + tol, ei
        else:  # ES = -ei, plus delta = IT(n) - IT(n-1) for K M N to IT8 and P..U to IT7 above 3 mm
            special = grade <= 8 if low in "kmn" else grade <= 7
            delta = tol - _it_um(grade - 1, size) if special and grade >= 3 and size > 3 else 0
            upper = 0 if low in "kn" and grade > 8 else delta - base
            lower = upper - tol
    return {
        "code": code,
        "upper": _mm(upper),
        "lower": _mm(lower),
        "it": grade,
        "std": _table("fits")["meta"]["limits_std"],
    }


# ---------------------------------------------------------------------- GB/T 1804 general


def general_tol(cls: str, size: float, kind: str = "linear") -> dict:
    """General tolerance (symmetric) of class ``cls`` ("f", "m", "c", "v") for ``size`` mm.

    ``kind``: "linear" (dimension), "chamfer" (external radius / chamfer height) or "angle" (``size`` =
    length of the shorter leg; ``upper`` / ``lower`` in degrees, ``text`` = the printed form "±0°30'").
    """
    data = _table("general_tol")
    if kind not in ("linear", "chamfer", "angle"):
        raise InvalidArgument(
            f"未知一般公差类型 {kind!r}", candidates=["linear", "chamfer", "angle"]
        )
    table = data[kind]
    if cls not in ("f", "m", "c", "v"):
        raise InvalidArgument(f"未知一般公差等级 {cls!r}", candidates=["f", "m", "c", "v"])
    closed = len(table[cls]) == len(table["upto"])
    i = _band(table["upto"], size, "一般公差", lower=table["min"], closed=closed)
    value = table[cls][i]
    if not value:
        raise InvalidArgument(
            f"一般公差等级 {cls} 在尺寸 {size} mm 处未定义",
            candidates=[c for c in "fmcv" if table[c][i]],
            values={"size": size},
        )
    out = {"class": cls, "std": data["meta"]["std"], "unit": table["unit"]}
    if kind == "linear" or kind == "chamfer":
        return out | {"upper": value, "lower": -value}
    degrees, minutes = divmod(value, 60)
    text = f"±{degrees}°" + (f"{minutes}'" if minutes else "")
    return out | {"upper": value / 60, "lower": -value / 60, "unit": "deg", "text": text}


# ------------------------------------------------------------------ threads (193 / 196 / 197)

_THREAD = re.compile(r"M(\d+(?:\.\d+)?)(?:[x×X](\d+(?:\.\d+)?))?")


def thread_classes(kind: str = "ext") -> list[str]:
    """Selectable tolerance classes (GB/T 197) of external ("ext") or internal ("int") threads."""
    classes = _table("threads")["classes"]
    if kind not in classes:
        raise InvalidArgument(f"未知螺纹类别 {kind!r}", candidates=list(classes))
    return list(classes[kind])


def thread(spec: str, cls: str | None = None) -> dict:
    """Dimensions of the metric thread ``spec`` ("M10" coarse, "M20x1.5" or "M20×1.5" fine) as
    ``{"designation", "d", "P", "d2", "d1", "coarse", "first", "std"}``; with ``cls`` ("6g", "6H") the
    class is checked and returned as ``cls`` / ``cls_kind``."""
    data = _table("threads")
    sizes = {row["d"]: row for row in data["size"]}
    match = _THREAD.fullmatch(spec) if isinstance(spec, str) else None
    if not match:
        raise InvalidArgument(
            f"螺纹规格 {spec!r} 不是 M直径 或 M直径x螺距（如 M10、M20x1.5）",
            candidates=[f"M{d:g}" for d in sizes],
        )
    row = sizes.get(float(match.group(1)))
    if row is None:
        near = sorted(sizes, key=lambda d: abs(d - float(match.group(1))))[:4]
        raise InvalidArgument(
            f"{spec} 的直径不在 GB/T 193 的第一、二选择直径系列（M1–M64）",
            candidates=[f"M{d:g}" for d in sorted(near)],
        )
    pitch = float(match.group(2)) if match.group(2) else row["coarse"]
    if pitch != row["coarse"] and pitch not in row["fine"]:
        raise InvalidArgument(
            f"M{row['d']:g} 没有螺距 {pitch:g}",
            candidates=[f"M{row['d']:g}x{p:g}" for p in [row["coarse"], *row["fine"]]],
            hint=f"粗牙螺距 {row['coarse']:g}，写 M{row['d']:g}",
        )
    d, formula = row["d"], data["formula"]
    out = {
        "designation": f"M{d:g}"
        if pitch == row["coarse"] and not match.group(2)
        else f"M{d:g}x{pitch:g}",
        "d": d,
        "P": pitch,
        "d2": round(d - formula["d2"] * pitch, 3),
        "d1": round(d - formula["d1"] * pitch, 3),
        "coarse": pitch == row["coarse"],
        "first": row["first"],
        "std": data["meta"]["std"],
    }
    if cls is not None:
        kinds = {c: kind for kind, names in data["classes"].items() for c in names}
        if cls not in kinds:
            raise InvalidArgument(f"未知螺纹公差带 {cls!r}", candidates=list(kinds))
        out |= {"cls": cls, "cls_kind": kinds[cls], "cls_std": data["meta"]["classes_std"]}
    return out


# ------------------------------------------------------------------------- keys (GB/T 1095)


def key(d: float) -> dict:
    """Parallel key and keyways for a shaft of diameter ``d`` mm (over 6, up to and including 130):
    ``b h t1 t2``, ``d_range`` = [over, upto], the deviations ``t1_dev`` / ``t2_dev`` = [upper, lower],
    the dimensions ``d_t1`` / ``d_t2`` with their deviations, and the key width fits."""
    data = _table("keys")
    row = next((r for r in data["key"] if r["over"] < d <= r["upto"]), None)
    if row is None:
        first, last = data["key"][0]["over"], data["key"][-1]["upto"]
        raise InvalidArgument(
            f"轴径 {d} mm 不在平键表范围内",
            values={"d": d},
            hint=f"表格覆盖轴径大于 {first} 至 {last} mm",
        )
    tol = row["tol"]
    return {
        "b": row["b"],
        "h": row["h"],
        "t1": row["t1"],
        "t2": row["t2"],
        "d_range": [row["over"], row["upto"]],
        "t1_dev": [tol, 0.0],
        "t2_dev": [tol, 0.0],
        "d_t1": {"nominal": round(d - row["t1"], 4), "upper": 0.0, "lower": -tol},
        "d_t2": {"nominal": round(d + row["t2"], 4), "upper": tol, "lower": 0.0},
        "width_fit": {name: dict(fit) for name, fit in data["width_fit"].items()},
        "std": data["meta"]["std"],
    }


# ---------------------------------------------------------------- splines (GB/T 1144)

_SPLINE = re.compile(r"(\d+)[x×X](\d+)[x×X](\d+)[x×X](\d+(?:\.\d+)?)")


def spline(spec: str) -> dict:
    """Rectangular spline "NxdxDxB" (e.g. "6x23x26x6"): ``N d D B``, ``series`` ("light" / "medium") and
    the general-use tolerance classes ``tol``."""
    data = _table("splines")
    names = {f"{s['N']}x{s['d']}x{s['D']}x{s['B']:g}": s for s in data["spline"]}
    match = _SPLINE.fullmatch(spec) if isinstance(spec, str) else None
    got = match and names.get("x".join(f"{float(g):g}" for g in match.groups()))
    if not got:
        same_d = [n for n, s in names.items() if match and s["d"] == int(match.group(2))]
        raise InvalidArgument(
            f"花键规格 {spec!r} 不在 GB/T 1144 轻、中系列中",
            candidates=same_d or list(names),
            hint="格式 键数x小径x大径x键宽，如 6x23x26x6",
        )
    meta = data["meta"]
    return {
        "designation": f"{got['N']}x{got['d']}x{got['D']}x{got['B']:g}",
        **got,
        "tol": {
            "hole": dict(data["tol"]["hole"]),
            "shaft": {fit: dict(c) for fit, c in data["tol"]["shaft"].items()},
        },
        "std": meta["std"],
        "iso": meta["iso"],
    }


# ---------------------------------------------------------------- datum letters, roughness


def datum_excluded(std: str = "GB") -> dict:
    """Letters that must not be datum letters under ``std`` ("GB" or "ISO"): ``{"std", "letters",
    "verified", "source"}``; ``verified`` False = the list could not be checked against the standard."""
    data = _table("datum")
    if std not in data:
        raise InvalidArgument(f"未知标准档 {std!r}", candidates=list(data))
    return {**data[std], "letters": list(data[std]["letters"])}


def rough_series(param: str = "Ra") -> dict:
    """Preferred values (um) of the roughness parameter ``param``: ``{"param", "preferred", "unit", "std"}``."""
    data = _table("rough")
    if param not in data or param == "meta":
        raise InvalidArgument(
            f"资源库没有粗糙度参数 {param!r} 的数值系列",
            candidates=[k for k in data if k != "meta"],
        )
    return {
        "param": param,
        "preferred": list(data[param]["preferred"]),
        "unit": data["meta"]["unit"],
        "std": data["meta"]["std"],
    }


# ---------------------------------------------------------------------- GB/T 145 centre holes

_THREAD_MARKING = re.compile(r"[Mm]\s*(\d+(?:\.\d+)?)")


def _thread_marking(d) -> str:
    """Normalise a type C thread argument (6, 6.0, "M6", "m6") to the table marking "M6"."""
    if isinstance(d, (int, float)) and not isinstance(d, bool):
        return f"M{d:g}"
    match = _THREAD_MARKING.fullmatch(str(d).strip()) if d is not None else None
    if match:
        return f"M{float(match.group(1)):g}"
    raise InvalidArgument(
        f"C 型中心孔：d 应为螺纹公称直径（6）或螺纹代号（M6），得到 {d!r}",
        values={"d": d},
        hint="GB/T 145 的 C 型螺纹从 M3 到 M24",
    )


def center_hole(type: str = "A", d=2.5, length: float | None = None) -> dict:
    """Centre hole of ``type`` ("A", "B", "R" or "C", GB/T 145-2001) with pilot diameter ``d`` mm.

    Every type returns ``{"type", "d", "D", "t", "avoid", "designation", "std"}``; ``D`` is the
    diameter in the designation as in GB/T 4459.5:

    - A: ``D`` = cone diameter, designation "A2.5/5.3";
    - B: adds ``D1`` (cone), ``D2`` (protecting chamfer, = ``D``), ``l2`` and ``l_min`` (minimum
      depth), designation "B2.5/8";
    - R: ``d`` is ``d1``; adds ``d2`` (= ``D``, the outside countersink diameter), ``l_min``,
      ``r_max`` and ``r_min``, designation "R2.5/5.3";
    - C: ``d`` is the thread marking (6 or "M6") and ``length`` is the thread length L of the
      designation; adds ``thread``, ``D1``, ``D2``, ``D3`` (= ``D``, the outside diameter at the
      end face), ``l`` (unthreaded depth from the end face) and ``t`` (reference depth of the
      60 deg cone). With ``length`` the designation is "CM6L10/10.5", without it only "CM6".

    ``avoid`` = True for a size the standard brackets as "avoid". The designations follow
    GB/T 4459.5-1999. The numbers and the verification state (``verified = false``: reproductions
    of GB/T 145 rather than the standard itself) are recorded in the [meta] of center_holes.toml.
    """
    data = _table("center_holes")
    types = [k for k in data if k != "meta"]
    if type not in types:
        raise InvalidArgument(
            f"中心孔型式 {type!r} 未录入（只录了 {'、'.join(types)} 型）", candidates=types
        )
    row = data[type]
    if type == "C":
        if length is not None and (
            not isinstance(length, (int, float)) or isinstance(length, bool) or length <= 0
        ):
            raise InvalidArgument(
                f"C 型中心孔的螺纹长度 length 应为正数（mm），得到 {length!r}",
                values={"length": length},
            )
        spec = _thread_marking(d)
        if spec not in row["d"]:
            near = sorted(row["d"], key=lambda s: abs(float(s[1:]) - float(spec[1:])))[:4]
            raise InvalidArgument(
                f"C 型中心孔没有螺纹 {spec}",
                candidates=near,
                values={"d": d},
                hint="GB/T 145 的 C 型螺纹从 M3 到 M24，写 6 或 M6",
            )
        k = row["d"].index(spec)
        out = {
            "type": "C",
            "d": float(spec[1:]),
            "thread": spec,
            "t": row["t"][k],
            "avoid": False,
        }
        out |= {key: row[key][k] for key in ("D1", "D2", "D3", "l")}
        out["D"] = out["D3"]
        out["designation"] = f"C{spec}" + (
            f"L{length:g}/{out['D']:g}" if length is not None else ""
        )
        out["std"] = data["meta"]["std"]
        return out
    if length is not None:
        raise InvalidArgument("length（螺纹长度）只用于 C 型中心孔", values={"length": length})
    if not isinstance(d, (int, float)) or isinstance(d, bool):
        raise InvalidArgument(
            f"{type} 型中心孔的 d 应为数（导向孔直径，mm），得到 {d!r}",
            values={"d": d},
            candidates=[f"{v:g}" for v in row["d"]],
        )
    for k, dv in enumerate(row["d"]):
        if abs(dv - d) < 1e-9:
            out = {"type": type, "d": dv, "avoid": row["avoid"][k]}
            if "t" in row:  # type R has no reference depth t
                out["t"] = row["t"][k]
            if type == "A":
                out["D"] = row["D"][k]
            elif type == "B":
                out |= {key: row[key][k] for key in ("D1", "D2", "l2", "l_min")}
                out["D"] = out["D2"]
            else:  # R
                out |= {key: row[key][k] for key in ("d2", "l_min", "r_max", "r_min")}
                out["D"] = out["d2"]
            out["designation"] = f"{type}{dv:g}/{out['D']:g}"
            out["std"] = data["meta"]["std"]
            return out
    raise InvalidArgument(
        f"{type} 型中心孔没有 d = {d}", candidates=[f"{v:g}" for v in row["d"]], values={"d": d}
    )


# ------------------------------------------------ GB/T 3 thread run-outs, shoulders, undercuts


def _pitch(spec) -> tuple[float, float | None]:
    """(P, d) of a pitch (number) or of a thread designation ("M24x1.5", "M10"); d is None for a pitch."""
    if isinstance(spec, str):
        t = thread(spec)
        return t["P"], t["d"]
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        return float(spec), None
    raise InvalidArgument(
        f"螺距应为数或螺纹规格（如 M24x1.5），得到 {spec!r}", values={"spec": spec}
    )


def _by_pitch(rows: list, P: float, what: str) -> dict:
    row = next((r for r in rows if abs(r["P"] - P) < 1e-9), None)
    if row is None:
        near = sorted((r["P"] for r in rows), key=lambda p: abs(p - P))[:4]
        raise InvalidArgument(
            f"螺距 {P:g} 不在 GB/T 3 的{what}表中",
            candidates=sorted(near),
            values={"P": P},
            hint=f"表中螺距 {rows[0]['P']:g} 至 {rows[-1]['P']:g}",
        )
    return row


def thread_undercut(spec, kind: str = "ext") -> dict:
    """Thread undercut (GB/T 3-1997) for a pitch or a thread designation ("M24x1.5"; "M10" = coarse).

    External (``kind="ext"``): ``g1_min`` (groove width, at least), ``g2_max`` (at most), ``r``, ``dg_offset``
    and, for a designation, ``d``, ``dg`` = d - dg_offset (the groove diameter) and ``dg_tol`` ("h13",
    "h12" up to d = 3). Internal (``"int"``): ``G1`` (normal), ``G1_short``, ``R``, ``Dg_offset`` and,
    for a designation, ``D``, ``Dg`` = D + Dg_offset with ``Dg_tol`` "H13". ``verified`` False: single source."""
    if kind not in ("ext", "int"):
        raise InvalidArgument(f"未知螺纹类别 {kind!r}", candidates=["ext", "int"])
    data = _table("thread_relief")
    P, d = _pitch(spec)
    row = _by_pitch(
        data[f"{kind}_undercut"], P, "外螺纹退刀槽" if kind == "ext" else "内螺纹退刀槽"
    )
    tol, std = data["tol"], data["meta"]["std"]
    verified = data["meta"]["verified"][f"{kind}_undercut"]
    if kind == "ext":
        out = {"kind": kind, "P": P, "g1_min": row["g1"], "g2_max": row["g2"], "r": row["r"]}
        out["dg_offset"] = row["dg_offset"]
        if d is not None:
            out |= {"d": d, "dg": round(d - row["dg_offset"], 3)}
            out["dg_tol"] = tol["ext_dg"] if d > tol["ext_dg_over"] else tol["ext_dg_small"]
    else:
        out = {"kind": kind, "P": P, "G1": row["G1"], "G1_short": row["G1_short"], "R": row["R"]}
        out["Dg_offset"] = row["Dg_offset"]
        if d is not None:
            out |= {"D": d, "Dg": round(d + row["Dg_offset"], 3), "Dg_tol": tol["int_Dg"]}
    return out | {"std": std, "verified": verified}


def thread_runout(spec) -> dict:
    """Thread run-out and shoulder distance (GB/T 3-1997) for a pitch or a thread designation:
    ``{"P", "ext": {"x", "x_short", "a", "a_short", "a_long"}, "int": {"X", "X_short", "A", "A_long"},
    "std", "verified": {"ext", "int"}}``; x / X = run-out (max), a / A = shoulder distance (max)."""
    data = _table("thread_relief")
    P, _ = _pitch(spec)
    ext = _by_pitch(data["ext_runout"], P, "外螺纹收尾")
    inner = _by_pitch(data["int_runout"], P, "内螺纹收尾")
    meta = data["meta"]
    return {
        "P": P,
        "ext": {k: v for k, v in ext.items() if k != "P"},
        "int": {k: v for k, v in inner.items() if k != "P"},
        "std": meta["std"],
        "verified": {"ext": meta["verified"]["ext_runout"], "int": meta["verified"]["int_runout"]},
    }


# -------------------------------------------------------------- GB/T 6403.5 grinding grooves


def grinding_groove(d: float, b1: float | None = None) -> dict:
    """Grinding wheel relief groove (GB/T 6403.5) for a turned surface of diameter ``d`` mm: the sizes the
    table offers for that diameter as ``options`` (``b1``, ``b2``, ``h``, ``r``), ``d_range`` = [over, upto]
    (upto None = unlimited), and the chosen one at top level: the smallest, or the one with ``b1``.
    ``verified``: True - Table 1 was read cell by cell from GB/T 6403.5-2008; only the turned surface and
    end face table is recorded."""
    data = _table("grinding_grooves")
    if not isinstance(d, (int, float)) or isinstance(d, bool) or d <= 0:
        raise InvalidArgument(f"磨削直径 d 应为正数，得到 {d!r}", values={"d": d})
    d = round(float(d), 6)
    band = [r for r in data["groove"] if r["over"] < d <= r.get("upto", float("inf"))]
    options = [{k: r[k] for k in ("b1", "b2", "h", "r")} for r in band]
    pick = options[0]
    if b1 is not None:
        pick = next((o for o in options if abs(o["b1"] - b1) < 1e-9), None)
        if pick is None:
            raise InvalidArgument(
                f"d = {d:g} 的越程槽没有 b1 = {b1}",
                candidates=[o["b1"] for o in options],
                values={"d": d, "b1": b1},
            )
    meta = data["meta"]
    return {
        "d": d,
        "d_range": [band[0]["over"], band[0].get("upto")],
        **pick,
        "options": options,
        "std": meta["std"],
        "verified": meta["verified"],
    }


_SPEC = {
    "bolt": r"M(\d+)\s*[x×X*]\s*(\d+(?:\.\d+)?)",
    "csk_screw": r"M(\d+)\s*[x×X*]\s*(\d+(?:\.\d+)?)",
    "set_screw": r"M(\d+)\s*[x×X*]\s*(\d+(?:\.\d+)?)",
    "nut": r"M(\d+)",
    "washer": r"M?(\d+)",
    "pin": r"(\d+)\s*(?:[a-z]\d+)?\s*[x×X*]\s*(\d+(?:\.\d+)?)",
}


def std_part(std: str, spec: str) -> dict:
    """A standard part by number and marking, e.g. ``std_part("GB/T 5782", "M10×90")`` →
    dimensions (mm) with ``kind``, ``name``, ``std``, ``iso``, ``d`` and ``l`` where the marking has one."""
    data = _table("std_parts")
    norm = re.sub(r"\s+", " ", str(std)).strip()
    kinds = {k: v for k, v in data.items() if k != "meta"}
    kind = next(
        (k for k, v in kinds.items() if norm in (v["std"], v["std"].rsplit("-", 1)[0])), None
    )
    if kind is None:
        raise InvalidArgument(
            f"标准件 {std!r} 不在资源库（M3 只录 L3 用到的）",
            values={"std": std},
            candidates=[v["std"] for v in kinds.values()],
        )
    t = kinds[kind]
    m = re.fullmatch(_SPEC[kind], str(spec).strip())
    if m is None:
        raise InvalidArgument(
            f"{t['std']} 的规格 {spec!r} 写法不对",
            values={"spec": spec},
            hint={
                "bolt": "M10×90",
                "csk_screw": "M6×16",
                "set_screw": "M8×12",
                "nut": "M10",
                "washer": "10",
                "pin": "6m6×30",
            }[kind],
        )
    d = float(m.group(1))
    row = next((r for r in t["sizes"] if r["d"] == d), None)
    if row is None:
        raise InvalidArgument(
            f"{t['std']} 资源库没有 d={d:g} 的规格",
            values={"d": d},
            candidates=[f"{r['d']:g}" for r in t["sizes"]],
        )
    out = {
        "kind": kind,
        "name": t["name"],
        "std": t["std"],
        "iso": t["iso"],
        "spec": str(spec),
        **{k: float(v) for k, v in row.items()},
    }
    if m.lastindex and m.lastindex >= 2:
        out["l"] = float(m.group(2))
    return out
