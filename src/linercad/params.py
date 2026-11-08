"""Parameters and safe parameter expressions (M0 SPEC §4.1, §7.1).

* ``Param`` is declared in drawing.py and remembers the line it was written on.
* ``ParamSet`` is what ``d.params(...)`` returns: ``P.D`` is an ``Expr``, read-only.
* ``Expr`` carries a value *and* a source string (``"D / 2 - 1"``). The source is what the
  action log stores, and ``eval_expr`` can evaluate every source an ``Expr`` produces.
* ``eval_expr`` walks an ``ast`` whitelist; nothing here uses ``eval`` or ``exec``.
"""

from __future__ import annotations

import ast
import difflib
import functools
import keyword
import math
import numbers
import operator
import sys
import warnings
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from .errors import InvalidArgument, LinerError, NotFound, ParamError

__all__ = ["Expr", "Param", "ParamSet", "eval_expr", "validate"]

# --------------------------------------------------------------------------- numbers

# Binding strength of the top node of an expression source (higher binds tighter).
_ADD, _MUL, _NEG, _POW, _ATOM = 10, 20, 30, 40, 100

_BINOPS: dict[type, str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
}
_BIN_PREC = {"+": _ADD, "-": _ADD, "*": _MUL, "/": _MUL, "//": _MUL, "%": _MUL, "**": _POW}
_COMPARES: dict[type, Any] = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_ALLOWED = "表达式只允许数字、参数名、+ - * / // % **、一元 + -、比较、and / or / not，以及 abs(x)"


def _is_real(x: object) -> bool:
    return isinstance(x, numbers.Real) and not isinstance(x, bool)


def _finite_float(x: object) -> float | None:
    """``float(x)`` when ``x`` is a finite real number (not a bool), otherwise ``None``."""
    if not _is_real(x):
        return None
    try:
        f = float(x)  # type: ignore[arg-type]
    except OverflowError:
        return None
    return f if math.isfinite(f) else None


def _fmt_num(x: float) -> str:
    """Short, re-parseable number text: ``2`` for 2.0, ``0.5``, ``1e-07``."""
    x = float(x)
    if x == 0:
        return "0"
    if x.is_integer() and abs(x) < 1e16:
        return str(int(x))
    return repr(x)


class _CalcError(Exception):
    """Internal: an operation with no finite real result."""


def _arith(op: str, a: float, b: float) -> float:
    try:
        if op == "+":
            r = a + b
        elif op == "-":
            r = a - b
        elif op == "*":
            r = a * b
        elif op == "/":
            r = a / b
        elif op == "//":
            r = a // b
        elif op == "%":
            r = a % b
        else:
            r = a**b
    except ZeroDivisionError:
        raise _CalcError("除数为 0") from None
    except OverflowError:
        raise _CalcError("结果太大") from None
    except ValueError:
        raise _CalcError("数值无效") from None
    if isinstance(r, complex):
        raise _CalcError("结果不是实数（负数的非整数次幂）")
    if not math.isfinite(r):
        raise _CalcError("结果不是有限数")
    return r


def _calc_failure(src: str, op: str, a: float, b: float, why: str) -> InvalidArgument:
    def show(x: float) -> str:
        return _paren(_fmt_num(x), x < 0)

    return InvalidArgument(
        f"表达式 {src!r} 无法计算：{why}（{show(a)} {op} {show(b)}）",
        values={"op": op, "left": a, "right": b},
        hint="检查除数、幂的底数和指数，或修改 drawing.py 里的参数值",
    )


def _candidates(name: str, names) -> list[str]:
    """Names that look like ``name`` (case-insensitive); all names if none does."""
    names = [str(n) for n in names]
    scored = []
    for n in names:
        ratio = difflib.SequenceMatcher(None, name.lower(), n.lower()).ratio()
        if ratio >= 0.5:
            scored.append((ratio, n))
    scored.sort(key=lambda t: -t[0])
    return [n for _, n in scored[:5]] or names[:10]


def _show(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _paren(text: str, needed: bool) -> str:
    return f"({text})" if needed else text


def _join(op: str, ls: str, lp: int, rs: str, rp: int) -> tuple[str, int]:
    """Source and precedence of ``left op right``, with the fewest parentheses that keep
    the same expression tree (so the text evaluates back to the very same float)."""
    if op == "**":  # right-associative; the exponent may itself be a unary minus
        return f"{_paren(ls, lp < _ATOM)} ** {_paren(rs, rp < _NEG)}", _POW
    prec = _BIN_PREC[op]  # left-associative
    return f"{_paren(ls, lp < prec)} {op} {_paren(rs, rp <= prec)}", prec


# ----------------------------------------------------------------------- eval_expr


def _parse(src: object) -> ast.Expression:
    if not isinstance(src, str):
        raise InvalidArgument(
            f"表达式必须是字符串，收到 {type(src).__name__}", values={"type": type(src).__name__}
        )
    try:
        with warnings.catch_warnings():  # e.g. invalid escape sequences: keep stderr clean
            warnings.simplefilter("ignore")
            return ast.parse(src.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
        why = e.msg if isinstance(e, SyntaxError) else (str(e) or type(e).__name__)
        raise InvalidArgument(f"表达式 {src!r} 语法有误：{why}", hint=_ALLOWED) from None


class _Eval:
    """Evaluates a whitelisted ``ast`` tree. Anything not handled below is rejected."""

    def __init__(self, src: str, values: Mapping[str, Any]):
        self.src = src
        self.values = values

    def run(self, node: ast.AST) -> float | bool:
        try:
            return self.visit(node)
        except RecursionError:
            raise InvalidArgument(f"表达式 {self.src!r} 嵌套太深", hint="拆成几步或简化") from None

    def visit(self, node: ast.AST):
        if isinstance(node, ast.Constant):
            return self.constant(node)
        if isinstance(node, ast.Name):
            return self.name(node)
        if isinstance(node, ast.BinOp):
            return self.binop(node)
        if isinstance(node, ast.UnaryOp):
            return self.unary(node)
        if isinstance(node, ast.Compare):
            return self.compare(node)
        if isinstance(node, ast.BoolOp):
            return self.boolop(node)
        if isinstance(node, ast.Call):
            return self.call(node)
        raise self.reject(node)

    def reject(self, node: ast.AST) -> InvalidArgument:
        return InvalidArgument(
            f"表达式 {self.src!r} 里有不允许的写法 {_show(node)!r}（{type(node).__name__}）",
            values={"node": type(node).__name__},
            hint=_ALLOWED,
        )

    def number(self, node: ast.AST) -> float:
        v = self.visit(node)
        if isinstance(v, bool):
            raise InvalidArgument(
                f"表达式 {self.src!r} 里 {_show(node)!r} 是真假值，不能参与算术", hint=_ALLOWED
            )
        return v

    def constant(self, node: ast.Constant) -> float:
        v = node.value
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise self.reject(node)  # strings, None, complex, ...
        f = _finite_float(v)
        if f is None:
            raise InvalidArgument(f"表达式 {self.src!r} 里有超出范围的数字（不是有限数）")
        return f

    def name(self, node: ast.Name) -> float:
        n = node.id
        if n not in self.values:
            raise NotFound(
                f"表达式 {self.src!r} 里的参数 {n} 不存在",
                id=n,
                candidates=_candidates(n, self.values),
                hint="参数名要和 drawing.py 里 d.params(...) 的键一致",
            )
        f = _finite_float(self.values[n])
        if f is None:
            raise InvalidArgument(
                f"表达式 {self.src!r} 里参数 {n} 的值 {self.values[n]!r} 不是有限数字",
                id=n,
                values={"value": repr(self.values[n])},
            )
        return f

    def binop(self, node: ast.BinOp) -> float:
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise self.reject(node)
        a, b = self.number(node.left), self.number(node.right)
        try:
            return _arith(op, a, b)
        except _CalcError as e:
            raise _calc_failure(self.src, op, a, b, str(e)) from None

    def unary(self, node: ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return -self.number(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +self.number(node.operand)
        raise self.reject(node)  # ~x

    def compare(self, node: ast.Compare) -> bool:
        if any(type(op) not in _COMPARES for op in node.ops):
            raise self.reject(node)  # in / is
        left = self.visit(node.left)
        for op, right_node in zip(node.ops, node.comparators, strict=True):
            right = self.visit(right_node)  # chained comparisons stop at the first False
            if not _COMPARES[type(op)](left, right):
                return False
            left = right
        return True

    def boolop(self, node: ast.BoolOp):
        is_and = isinstance(node.op, ast.And)
        result = None
        for operand in node.values:
            result = self.visit(operand)
            if bool(result) is not is_and:  # `and` stops at a falsy, `or` at a truthy operand
                return result
        return result

    def call(self, node: ast.Call) -> float:
        f = node.func
        if (
            isinstance(f, ast.Name)
            and f.id == "abs"
            and len(node.args) == 1
            and not node.keywords
            and not isinstance(node.args[0], ast.Starred)
        ):
            return abs(self.number(node.args[0]))
        raise InvalidArgument(
            f"表达式 {self.src!r} 里不允许调用 {_show(f)}(...)：只能调用 abs(x)（一个参数）",
            values={"call": _show(f)},
            hint=_ALLOWED,
        )


def eval_expr(src: str, values: Mapping[str, float]) -> float | bool:
    """Evaluate a parameter expression such as ``"D / 2 - 1"`` or ``"d1 < D"``.

    Only numbers, names (looked up in ``values``), ``+ - * / // % **``, unary ``+ -``,
    comparisons (chains allowed), ``and / or / not`` and ``abs(x)`` are allowed. Numbers
    come back as ``float``, comparisons and ``not`` as ``bool``. Never uses ``eval``.
    """
    tree = _parse(src)
    return _Eval(src, values).run(tree.body)


def _render(node: ast.AST, src: str) -> tuple[str, int, frozenset[str]]:
    """Canonical source, precedence and parameter names of a numeric (already evaluated) tree."""
    if isinstance(node, ast.Constant):
        return _fmt_num(float(node.value)), _ATOM, frozenset()
    if isinstance(node, ast.Name):
        return node.id, _ATOM, frozenset({node.id})
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        text, prec, names = _render(node.operand, src)
        if isinstance(node.op, ast.UAdd):
            return text, prec, names
        return "-" + _paren(text, prec < _NEG), _NEG, names
    if isinstance(node, ast.BinOp):
        ls, lp, ln = _render(node.left, src)
        rs, rp, rn = _render(node.right, src)
        text, prec = _join(_BINOPS[type(node.op)], ls, lp, rs, rp)
        return text, prec, ln | rn
    if isinstance(node, ast.Call):  # abs(x): the evaluator has checked the shape
        text, _, names = _render(node.args[0], src)
        return f"abs({text})", _ATOM, names
    raise InvalidArgument(
        f"表达式 {src!r} 里的 {_show(node)!r} 不是数值表达式",
        hint="Expr 只表示数值；比较和 and / or / not 请用 eval_expr",
    )


# ------------------------------------------------------------------------------ Expr


def _coerce(x: object) -> Expr | None:
    """An ``Expr`` for a supported operand, ``None`` for an unsupported type."""
    if isinstance(x, Expr):
        return x
    if not _is_real(x):
        return None
    f = _finite_float(x)
    if f is None:
        raise InvalidArgument(
            f"参数表达式里不能使用 {x!r}（不是有限数）", values={"value": repr(x)}
        )
    return Expr(f, _fmt_num(f), frozenset(), _NEG if f < 0 else _ATOM)


def _binop(op: str, left: object, right: object):
    a, b = _coerce(left), _coerce(right)
    if a is None or b is None:
        return NotImplemented
    src, prec = _join(op, a._src, a._prec, b._src, b._prec)
    try:
        value = _arith(op, a._value, b._value)
    except _CalcError as e:
        raise _calc_failure(src, op, a._value, b._value, str(e)) from None
    return Expr(value, src, a._params | b._params, prec)


def _arith_ops(op: str):
    def forward(self, other):
        return _binop(op, self, other)

    def reverse(self, other):
        return _binop(op, other, self)

    return forward, reverse


def _comparison(fn):
    def compare(self, other):
        if isinstance(other, Expr):
            other = other._value
        elif not _is_real(other):
            return NotImplemented
        return bool(fn(self._value, other))

    return compare


class Expr:
    """A number that remembers how it was computed from parameters. Immutable.

    ``.value`` is the float, ``.src`` the expression text (``"D / 2 - 1"``, what the action
    log stores), ``.params`` the names it depends on. Comparisons give plain ``bool``;
    ``float() / int() / round()`` give plain numbers. Build one from ``P.<name>``, from
    arithmetic on those, or from text with ``Expr.from_src``.
    """

    __slots__ = ("_value", "_src", "_params", "_prec")
    __array_ufunc__ = None  # let numpy scalars defer to our reflected operators

    def __init__(
        self, value: float, src: str, params: frozenset[str] = frozenset(), prec: int = _ATOM
    ):
        set_ = object.__setattr__
        set_(self, "_value", float(value))
        set_(self, "_src", str(src))
        set_(self, "_params", frozenset(params))
        set_(self, "_prec", prec)

    @classmethod
    def from_src(cls, src: str, values: Mapping[str, float]) -> Expr:
        """Evaluate ``src`` against ``values``; the result carries the canonical source."""
        tree = _parse(src)
        value = _Eval(src, values).run(tree.body)
        if isinstance(value, bool):
            raise InvalidArgument(
                f"表达式 {src!r} 的结果是真假值，不是数值",
                hint="Expr 只表示数值；比较和 and / or / not 请用 eval_expr",
            )
        text, prec, names = _render(tree.body, src)
        return cls(value, text, names, prec)

    @property
    def value(self) -> float:
        return self._value

    @property
    def src(self) -> str:
        return self._src

    @property
    def params(self) -> frozenset[str]:
        return self._params

    # immutability
    def __setattr__(self, name, value):
        raise AttributeError(f"Expr 不可变（{self._src}）；用运算得到新的 Expr")

    def __delattr__(self, name):
        raise AttributeError(f"Expr 不可变（{self._src}）")

    # arithmetic
    __add__, __radd__ = _arith_ops("+")
    __sub__, __rsub__ = _arith_ops("-")
    __mul__, __rmul__ = _arith_ops("*")
    __truediv__, __rtruediv__ = _arith_ops("/")
    __floordiv__, __rfloordiv__ = _arith_ops("//")
    __pow__, __rpow__ = _arith_ops("**")

    def __neg__(self) -> Expr:
        text = "-" + _paren(self._src, self._prec < _NEG)
        return Expr(-self._value, text, self._params, _NEG)

    def __pos__(self) -> Expr:
        return self

    def __abs__(self) -> Expr:
        return Expr(abs(self._value), f"abs({self._src})", self._params, _ATOM)

    # comparisons give plain bool
    __lt__ = _comparison(operator.lt)
    __le__ = _comparison(operator.le)
    __gt__ = _comparison(operator.gt)
    __ge__ = _comparison(operator.ge)
    __eq__ = _comparison(operator.eq)
    __ne__ = _comparison(operator.ne)

    def __hash__(self) -> int:
        return hash(self._value)  # equal to the hash of the equal int / float

    def __bool__(self) -> bool:
        return self._value != 0

    # conversions give plain numbers
    def __float__(self) -> float:
        return self._value

    def __int__(self) -> int:
        return int(self._value)

    def __round__(self, ndigits: int | None = None):
        return round(self._value) if ndigits is None else round(self._value, ndigits)

    def __format__(self, spec: str) -> str:
        return format(self._value, spec)

    def __str__(self) -> str:
        return format(self._value)

    def __repr__(self) -> str:
        return f"Expr({self._src} = {_fmt_num(self._value)})"

    def __reduce__(self):  # copy / pickle despite immutability
        return (Expr, (self._value, self._src, self._params, self._prec))


# ---------------------------------------------------------------------------- Param


def _call_site() -> dict:
    """``{"file", "line"}`` of the first frame outside the linercad package."""
    frame = sys._getframe(1)
    while frame is not None:
        filename = frame.f_code.co_filename
        if not _inside_package(filename):
            return {"file": Path(filename).name, "line": frame.f_lineno}
        frame = frame.f_back
    return {"file": "<unknown>", "line": 0}


_PKG_DIR = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=256)
def _inside_package(filename: str) -> bool:
    try:
        return Path(filename).resolve().is_relative_to(_PKG_DIR)
    except (OSError, ValueError):
        return False


class Param:
    """A named, adjustable dimension declared in drawing.py (SPEC §4.1).

    ``.src`` is ``{"file", "line"}`` of the ``Param(...)`` call, recorded at construction.
    """

    def __init__(
        self,
        value,
        min=None,
        max=None,
        step=None,
        unit="mm",
        label="",
        tol=None,
        rule=None,
        group=None,
    ):
        self.value = value
        self.min = min
        self.max = max
        self.step = step
        self.unit = unit
        self.label = label
        self.tol = tol
        self.rule = rule
        self.group = group
        self.src = _call_site()

    def to_dict(self, name: str) -> dict:
        return {
            "name": name,
            "value": self.value,
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "unit": self.unit,
            "label": self.label,
            "tol": self.tol,
            "rule": self.rule,
            "group": self.group,
            "src": dict(self.src),
        }

    def __repr__(self) -> str:
        parts = [repr(self.value)]
        for key in ("min", "max", "step", "tol", "rule", "group"):
            if getattr(self, key) is not None:
                parts.append(f"{key}={getattr(self, key)!r}")
        if self.unit != "mm":
            parts.append(f"unit={self.unit!r}")
        if self.label:
            parts.append(f"label={self.label!r}")
        return f"Param({', '.join(parts)})"


# -------------------------------------------------------------------------- validate


def _range_text(lo, hi) -> str:
    left = "(-∞" if lo is None else f"[{_fmt_num(lo)}"
    right = "+∞)" if hi is None else f"{_fmt_num(hi)}]"
    return f"{left}, {right}"


def validate(params: Mapping[str, Param]) -> None:
    """Check every value against its ``[min, max]`` and its ``rule``; raise ``ParamError``."""
    values: dict[str, float] = {}
    for name, p in params.items():
        v = _finite_float(p.value)
        if v is None:
            raise ParamError(
                f"参数 {name} 的值 {p.value!r} 不是有限数字",
                id=name,
                values={"value": repr(p.value)},
                hint=f"在 drawing.py 里把 {name} 改成数字",
            )
        values[name] = v
    for name, p in params.items():
        v = values[name]
        for bound in (p.min, p.max):
            if bound is not None and _finite_float(bound) is None:
                raise ParamError(
                    f"参数 {name} 的范围 min={p.min!r} max={p.max!r} 必须是数字",
                    id=name,
                    values={"min": repr(p.min), "max": repr(p.max)},
                )
        if (p.min is not None and v < p.min) or (p.max is not None and v > p.max):
            raise ParamError(
                f"参数 {name} 的值 {_fmt_num(v)} 超出范围 {_range_text(p.min, p.max)}",
                id=name,
                values={"value": p.value, "min": p.min, "max": p.max},
                hint=f"在 drawing.py 里把 {name} 改到范围内，或调整它的 min / max",
            )
        if p.rule is not None:
            _check_rule(name, p.rule, v, values)


def _check_rule(name: str, rule: str, value: float, values: dict[str, float]) -> None:
    try:
        ok = eval_expr(rule, values)
        names = [n.id for n in ast.walk(_parse(rule)) if isinstance(n, ast.Name)]
    except LinerError as e:
        raise ParamError(
            f"参数 {name} 的 rule {rule!r} 无法求值：{e.message}",
            id=name,
            candidates=e.candidates,
            values={"value": value, "rule": rule},
            hint="rule 只能用参数名、数字、算术、比较、and / or / not 和 abs()",
        ) from e
    refs = {n: values[n] for n in dict.fromkeys(names) if n in values}
    if not isinstance(ok, bool):
        raise ParamError(
            f"参数 {name} 的 rule {rule!r} 不是真假表达式（结果 {_fmt_num(ok)}）",
            id=name,
            values={"value": value, "rule": rule, "result": ok},
            hint='rule 应该是比较，例如 "d1 < D"',
        )
    if not ok:
        shown = ", ".join(f"{n}={_fmt_num(v)}" for n, v in refs.items())
        raise ParamError(
            f"参数 {name}={_fmt_num(value)} 违反 rule {rule!r}（{shown}）",
            id=name,
            values={"value": value, "rule": rule, "refs": refs},
            hint=f"在 drawing.py 里改 {name} 或相关参数，使 {rule} 成立",
        )


# -------------------------------------------------------------------------- ParamSet

_RESERVED = frozenset({"names", "values"})


class ParamSet:
    """Read-only view of the parameters: ``P.D`` is an ``Expr``, ``P["D"]`` the ``Param``."""

    __slots__ = ("_params",)

    def __init__(self, params: Mapping[str, Param]):
        items = dict(params)
        for name in items:
            if (
                not isinstance(name, str)
                or not name.isidentifier()
                or keyword.iskeyword(name)
                or name.startswith("_")
                or name in _RESERVED
            ):
                raise InvalidArgument(
                    f"参数名 {name!r} 不能用在表达式里",
                    id=str(name),
                    hint="参数名必须是 Python 标识符，不以下划线开头，且不能叫 names / values",
                )
        object.__setattr__(self, "_params", items)

    def _param(self, name: str) -> Param:
        try:
            return self._params[name]
        except (KeyError, TypeError):
            raise NotFound(
                f"找不到参数 {name}",
                id=str(name),
                candidates=_candidates(str(name), self._params),
                hint="参数名要和 drawing.py 里 d.params(...) 的键一致",
            ) from None

    def _number(self, name: str) -> float:
        p = self._param(name)
        v = _finite_float(p.value)
        if v is None:
            raise ParamError(
                f"参数 {name} 的值 {p.value!r} 不是有限数字",
                id=name,
                values={"value": repr(p.value)},
                hint=f"在 drawing.py 里把 {name} 改成数字",
            )
        return v

    def __getattr__(self, name: str) -> Expr:
        if name.startswith("_"):
            raise AttributeError(name)
        return Expr(self._number(name), name, frozenset({name}), _ATOM)

    def __getitem__(self, name: str) -> Param:
        if not isinstance(name, str):
            raise InvalidArgument(f"参数名必须是字符串，收到 {name!r}")
        return self._param(name)

    def names(self) -> list[str]:
        return list(self._params)

    def values(self) -> dict[str, float]:
        return {name: self._number(name) for name in self._params}

    def __iter__(self) -> Iterator[str]:
        return iter(self._params)

    def __len__(self) -> int:
        return len(self._params)

    def __contains__(self, name: object) -> bool:
        return name in self._params

    # read-only: scratch scripts must edit drawing.py instead
    def _read_only(self, name: object) -> ParamError:
        p = self._params.get(name) if isinstance(name, str) else None
        if p is None:
            return ParamError(
                f"参数表在临时脚本里是只读的，不能新增或修改 {name!r}",
                candidates=list(self._params),
                hint="参数只在 drawing.py 里用 Param(...) 定义；改好后运行 `lcad build -m`",
            )
        line = p.src.get("line")
        return ParamError(
            f"参数 {name} 在临时脚本里是只读的：它的默认值在 drawing.py 第 {line} 行。"
            f"请去 drawing.py 第 {line} 行改默认值，然后运行 `lcad build -m`",
            id=str(name),
            values={"file": p.src.get("file"), "line": line},
        )

    def __setattr__(self, name, value):
        raise self._read_only(name)

    def __delattr__(self, name):
        raise self._read_only(name)

    def __setitem__(self, name, value):
        raise self._read_only(name)

    def __delitem__(self, name):
        raise self._read_only(name)

    def __reduce__(self):  # copy / pickle despite __setattr__
        return (ParamSet, (self._params,))

    def __repr__(self) -> str:
        return "ParamSet(" + ", ".join(f"{n}={p.value!r}" for n, p in self._params.items()) + ")"
