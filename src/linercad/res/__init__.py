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

__all__ = ["fit", "general_tol", "it"]


@cache
def _table(name: str) -> dict:
    """The parsed ``<name>.toml``; cached, so callers must not modify it."""
    return tomllib.loads((resources.files(__package__) / f"{name}.toml").read_text(encoding="utf-8"))


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
                candidates=[x for x in _SHAFT_LETTERS if x in ("h", "js") or _fundamental(x, size) is not None],
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
        raise InvalidArgument(f"未知一般公差类型 {kind!r}", candidates=["linear", "chamfer", "angle"])
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
