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
    "datum_excluded",
    "fit",
    "general_tol",
    "it",
    "key",
    "rough_series",
    "spline",
    "thread",
    "thread_classes",
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
