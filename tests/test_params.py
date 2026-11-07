"""Card C3: Param, ParamSet, Expr, eval_expr and validate (M0 SPEC §4.1, §7.1)."""

from __future__ import annotations

import ast
import copy
import pickle
import random
import re
import sys
from pathlib import Path

import pytest

import linercad
from linercad import Param
from linercad.errors import InvalidArgument, LinerError, NotFound, ParamError
from linercad.params import Expr, ParamSet, eval_expr, validate

THIS_FILE = Path(__file__).name


def _next_line() -> int:
    """Line number right after the caller's current line."""
    return sys._getframe(1).f_lineno + 1


@pytest.fixture
def P() -> ParamSet:
    return ParamSet(
        {
            "D": Param(30, min=10, max=60, step=0.5, unit="mm", label="外径", tol="h7"),
            "d1": Param(20, min=8, max=50, step=0.5, label="轴颈", rule="d1 < D"),
            "L": Param(100),
            "a": Param(7),
            "b": Param(3),
        }
    )


@pytest.fixture
def V(P) -> dict:
    return P.values()


# --------------------------------------------------------------------------- Param


def test_param_is_exported_from_package():
    assert linercad.Param is Param
    assert "Param" in linercad.__all__


def test_param_defaults():
    p = Param(30)
    assert p.value == 30
    assert p.min is None and p.max is None and p.step is None
    assert p.unit == "mm"
    assert p.label == ""
    assert p.tol is None and p.rule is None and p.group is None


def test_param_keeps_all_attributes():
    p = Param(
        30, min=10, max=60, step=0.5, unit="mm", label="外径", tol="h7", rule="D > 5", group="主体"
    )
    assert (p.value, p.min, p.max, p.step) == (30, 10, 60, 0.5)
    assert (p.unit, p.label, p.tol, p.rule, p.group) == ("mm", "外径", "h7", "D > 5", "主体")


def test_param_records_call_site():
    line = _next_line()
    p = Param(30)
    assert p.src == {"file": THIS_FILE, "line": line}


def test_param_records_first_line_of_a_multiline_call():
    line = _next_line()
    p = Param(
        30,
        min=10,
        max=60,
    )
    assert p.src == {"file": THIS_FILE, "line": line}


def test_param_records_each_call_separately():
    params = {}
    first = _next_line()
    params["a"] = Param(1)
    params["b"] = Param(2)
    assert params["a"].src["line"] == first
    assert params["b"].src["line"] == first + 1


def _make_param():
    return Param(1)


def test_param_src_skips_frames_inside_the_linercad_package(monkeypatch):
    # Pretend the helper lives inside the package: its frame must be skipped, so the
    # recorded location is the first frame outside the package (this test).
    pkg_dir = Path(linercad.__file__).resolve().parent
    fake = _make_param.__code__.replace(co_filename=str(pkg_dir / "fake_internal.py"))
    monkeypatch.setattr(_make_param, "__code__", fake)
    line = _next_line()
    p = _make_param()
    assert p.src == {"file": THIS_FILE, "line": line}


def test_param_to_dict():
    p = Param(30, min=10, max=60, step=0.5, label="外径", tol="h7", rule="D > 5", group="主体")
    d = p.to_dict("D")
    assert list(d) == [
        "name",
        "value",
        "min",
        "max",
        "step",
        "unit",
        "label",
        "tol",
        "rule",
        "group",
        "src",
    ]
    assert d["name"] == "D" and d["value"] == 30 and d["min"] == 10 and d["max"] == 60
    assert d["step"] == 0.5 and d["unit"] == "mm" and d["label"] == "外径"
    assert d["tol"] == "h7" and d["rule"] == "D > 5" and d["group"] == "主体"
    assert d["src"] == p.src


def test_param_to_dict_is_a_copy():
    p = Param(30)
    p.to_dict("D")["src"]["line"] = -1
    assert p.src["line"] != -1


# ------------------------------------------------------------------------ validate


def test_validate_accepts_good_params(P):
    assert validate({n: P[n] for n in P.names()}) is None


@pytest.mark.parametrize("value", [10, 60, 10.0, 35.5])
def test_validate_range_is_inclusive(value):
    validate({"D": Param(value, min=10, max=60)})


@pytest.mark.parametrize("value", [9.99, 60.01, 70, -3])
def test_validate_out_of_range(value):
    with pytest.raises(ParamError) as ei:
        validate({"D": Param(value, min=10, max=60)})
    e = ei.value
    assert e.code == "param"
    assert "D" in e.message and "10" in e.message and "60" in e.message
    assert f"{value:g}" in e.message
    assert e.values["value"] == value and e.values["min"] == 10 and e.values["max"] == 60
    assert e.id == "D"


def test_validate_one_sided_ranges():
    validate({"x": Param(5, min=0)})
    validate({"x": Param(5, max=9)})
    with pytest.raises(ParamError) as ei:
        validate({"x": Param(-1, min=0)})
    assert "x" in ei.value.message and "-1" in ei.value.message and "0" in ei.value.message
    with pytest.raises(ParamError) as ei:
        validate({"x": Param(10, max=9)})
    assert "x" in ei.value.message and "10" in ei.value.message and "9" in ei.value.message


def test_validate_rule_violation_names_param_value_and_rule():
    params = {"D": Param(30), "d1": Param(40, rule="d1 < D")}
    with pytest.raises(ParamError) as ei:
        validate(params)
    e = ei.value
    assert "d1" in e.message and "d1 < D" in e.message
    assert "40" in e.message and "30" in e.message
    assert e.values["value"] == 40 and e.values["rule"] == "d1 < D"
    assert e.values["refs"] == {"d1": 40, "D": 30}
    assert e.id == "d1"


def test_validate_rule_sees_all_params_whatever_the_order():
    # the rule of the first parameter refers to one defined after it
    validate({"d1": Param(20, rule="d1 < D"), "D": Param(30)})


def test_validate_rule_can_use_and_or_not_abs_and_chains():
    validate({"x": Param(5, rule="0 < x < 10 and not x == 6"), "y": Param(1, rule="abs(y) < 2")})
    with pytest.raises(ParamError):
        validate({"x": Param(5, rule="x < 2 or x > 9")})


def test_validate_rule_that_cannot_be_evaluated_is_a_param_error():
    with pytest.raises(ParamError) as ei:
        validate({"D": Param(30), "d1": Param(20, rule="d1 < DD")})
    assert "d1" in ei.value.message and "DD" in ei.value.message
    assert "D" in ei.value.candidates
    with pytest.raises(ParamError):
        validate({"d1": Param(20, rule="d1 <")})
    with pytest.raises(ParamError):
        validate({"d1": Param(20, rule="__import__('os')")})


def test_validate_rule_must_be_boolean():
    with pytest.raises(ParamError) as ei:
        validate({"d1": Param(20, rule="d1 + 1")})
    assert "d1" in ei.value.message and "d1 + 1" in ei.value.message


@pytest.mark.parametrize("bad", ["30", None, True, float("nan"), float("inf")])
def test_validate_value_must_be_a_finite_number(bad):
    with pytest.raises(ParamError) as ei:
        validate({"D": Param(bad)})
    assert "D" in ei.value.message


# ------------------------------------------------------------------------ ParamSet


def test_paramset_attribute_is_an_expr(P):
    e = P.D
    assert isinstance(e, Expr)
    assert e.value == 30.0 and isinstance(e.value, float)
    assert e.src == "D"
    assert e.params == frozenset({"D"})
    assert isinstance(e.params, frozenset)


def test_paramset_getitem_returns_the_param(P):
    assert isinstance(P["D"], Param)
    assert P["D"].label == "外径"
    assert P["D"] is P["D"]


def test_paramset_names_and_values(P):
    assert P.names() == ["D", "d1", "L", "a", "b"]
    v = P.values()
    assert v == {"D": 30.0, "d1": 20.0, "L": 100.0, "a": 7.0, "b": 3.0}
    assert all(isinstance(x, float) for x in v.values())


def test_paramset_container_protocol(P):
    assert len(P) == 5
    assert list(P) == P.names()
    assert "D" in P and "zzz" not in P


def test_paramset_copies_the_dict():
    src = {"D": Param(30)}
    P = ParamSet(src)
    src["X"] = Param(1)
    assert P.names() == ["D"]


@pytest.mark.parametrize("name", ["DD", "d", "d2", "l"])
def test_unknown_param_is_not_found_with_candidates(P, name):
    with pytest.raises(NotFound) as ei:
        getattr(P, name)
    e = ei.value
    assert name in e.message
    assert e.id == name
    assert e.candidates and all(c in P.names() for c in e.candidates)
    with pytest.raises(NotFound) as ei2:
        P[name]
    assert ei2.value.candidates == e.candidates


def test_unknown_param_close_matches_come_first(P):
    with pytest.raises(NotFound) as ei:
        _ = P.DD
    assert ei.value.candidates[0] == "D"
    with pytest.raises(NotFound) as ei:
        _ = P.d2
    assert "d1" in ei.value.candidates


def test_paramset_private_names_are_plain_attribute_errors(P):
    with pytest.raises(AttributeError):
        _ = P._nothing
    assert not hasattr(P, "__deepcopy__")


def test_assigning_a_param_raises_param_error_with_the_source_line():
    line = _next_line()
    P = ParamSet({"D": Param(30), "d1": Param(20)})
    with pytest.raises(ParamError) as ei:
        P.D = 5
    e = ei.value
    assert e.code == "param"
    assert "D" in e.message
    assert "drawing.py" in e.message
    assert re.search(rf"(?<!\d){line}(?!\d)", e.message)
    assert "lcad build -m" in str(e)
    assert e.values["line"] == line
    assert P.values()["D"] == 30.0


def test_item_assignment_and_deletion_also_raise_param_error():
    line = _next_line()
    P = ParamSet({"D": Param(30)})
    with pytest.raises(ParamError) as ei:
        P["D"] = 5
    assert re.search(rf"(?<!\d){line}(?!\d)", ei.value.message)
    with pytest.raises(ParamError):
        del P["D"]
    with pytest.raises(ParamError):
        del P.D
    assert P.names() == ["D"]


def test_assigning_a_new_name_raises_param_error_pointing_to_drawing_py(P):
    with pytest.raises(ParamError) as ei:
        P.extra = 1
    assert "drawing.py" in str(ei.value) and "extra" in ei.value.message
    with pytest.raises(ParamError):
        P["extra"] = 1
    assert "extra" not in P


@pytest.mark.parametrize("name", ["values", "names", "1x", "a-b", "class", "", "_p"])
def test_paramset_rejects_names_that_cannot_be_used_in_expressions(name):
    with pytest.raises(InvalidArgument) as ei:
        ParamSet({name: Param(1)})
    assert ei.value.code == "invalid_arg"


def test_paramset_survives_copy_and_pickle(P):
    for clone in (copy.copy(P), copy.deepcopy(P), pickle.loads(pickle.dumps(P))):
        assert clone.names() == P.names()
        assert clone.values() == P.values()
        assert clone.D.src == "D"


def test_paramset_repr(P):
    r = repr(P)
    assert r.startswith("ParamSet(") and "D=30" in r


# -------------------------------------------------------------- Expr: arithmetic and src

# (builder, expected src, expected value) with D=30, d1=20, L=100, a=7, b=3
EXPR_CASES = [
    (lambda P: P.D / 2 - 1, "D / 2 - 1", 14.0),
    (lambda P: (P.D - P.d1) * 2, "(D - d1) * 2", 20.0),
    (lambda P: 2 * P.D, "2 * D", 60.0),
    (lambda P: P.L - (P.a - P.b), "L - (a - b)", 96.0),
    (lambda P: -(P.a + P.b), "-(a + b)", -10.0),
    (lambda P: abs(P.D - 40), "abs(D - 40)", 10.0),
    (lambda P: P.D + P.d1 + P.L, "D + d1 + L", 150.0),
    (lambda P: (P.D + P.d1) + P.L, "D + d1 + L", 150.0),
    (lambda P: P.D + (P.d1 + P.L), "D + (d1 + L)", 150.0),
    (lambda P: P.L - P.a - P.b, "L - a - b", 90.0),
    (lambda P: (P.L - P.a) - P.b, "L - a - b", 90.0),
    (lambda P: P.L / (P.a * P.b), "L / (a * b)", 100 / 21),
    (lambda P: P.L / P.a * P.b, "L / a * b", 100 / 7 * 3),
    (lambda P: P.a * (P.b + 1), "a * (b + 1)", 28.0),
    (lambda P: P.a + P.b * 2, "a + b * 2", 13.0),
    (lambda P: (P.a + P.b) * (P.a - P.b), "(a + b) * (a - b)", 40.0),
    (lambda P: P.L // P.a, "L // a", 14.0),
    (lambda P: P.L // (P.a - P.b), "L // (a - b)", 25.0),
    (lambda P: P.a**2, "a ** 2", 49.0),
    (lambda P: 2**P.b, "2 ** b", 8.0),
    (lambda P: (P.a**P.b) ** 2, "(a ** b) ** 2", 117649.0),
    (lambda P: P.a**P.b**2, "a ** b ** 2", 40353607.0),
    (lambda P: P.a ** (P.b**2), "a ** b ** 2", 40353607.0),
    (lambda P: (P.a + P.b) ** 2, "(a + b) ** 2", 100.0),
    (lambda P: (-P.a) ** 2, "(-a) ** 2", 49.0),
    (lambda P: -(P.a**2), "-a ** 2", -49.0),
    (lambda P: (-2) ** P.b, "(-2) ** b", -8.0),
    (lambda P: -(2**P.b), "-2 ** b", -8.0),
    (lambda P: -P.a * P.b, "-a * b", -21.0),
    (lambda P: -(P.a * P.b), "-(a * b)", -21.0),
    (lambda P: P.a * -P.b, "a * -b", -21.0),
    (lambda P: P.a - -P.b, "a - -b", 10.0),
    (lambda P: P.D + -3, "D + -3", 27.0),
    (lambda P: abs(-P.a), "abs(-a)", 7.0),
    (lambda P: abs(P.a - P.b) * 2, "abs(a - b) * 2", 8.0),
    (lambda P: abs(abs(P.a - 10)), "abs(abs(a - 10))", 3.0),
    (lambda P: P.D / 2.0, "D / 2", 15.0),
    (lambda P: P.D * 0.5, "D * 0.5", 15.0),
    (lambda P: 1 - P.D / 100, "1 - D / 100", 0.7),
    (lambda P: 10 / P.b, "10 / b", 10 / 3),
    (lambda P: 3 - P.a, "3 - a", -4.0),
    (lambda P: P.a - 3, "a - 3", 4.0),
    (lambda P: 100 // P.a, "100 // a", 14.0),
    (lambda P: P.D * 1e20, "D * 1e+20", 3e21),
    (lambda P: P.D * 1e-7, "D * 1e-07", 3e-6),
    (lambda P: +P.a, "a", 7.0),
]


@pytest.mark.parametrize(
    "build,src,value",
    [pytest.param(b, s, v, id=s) for b, s, v in EXPR_CASES],
)
def test_expr_src_and_value(P, V, build, src, value):
    e = build(P)
    assert isinstance(e, Expr)
    assert e.src == src
    assert e.value == pytest.approx(value, rel=1e-12)
    assert isinstance(e.value, float)
    # the src evaluates back to the very same number, and re-canonicalises to itself
    assert eval_expr(e.src, V) == e.value
    again = Expr.from_src(e.src, V)
    assert again.src == e.src and again.value == e.value and again.params == e.params


def test_expr_params_is_the_union_of_names(P):
    assert (P.D - P.d1).params == frozenset({"D", "d1"})
    assert (2 * P.D).params == frozenset({"D"})
    assert abs(P.a - P.b * P.a).params == frozenset({"a", "b"})
    assert (-P.D).params == frozenset({"D"})
    assert (P.D / P.D).params == frozenset({"D"})


def test_expr_is_immutable(P):
    e = P.D / 2
    with pytest.raises(AttributeError):
        e.value = 1.0
    with pytest.raises(AttributeError):
        e.src = "x"
    with pytest.raises(AttributeError):
        e.params = frozenset()
    with pytest.raises(AttributeError):
        e.other = 1
    with pytest.raises(AttributeError):
        del e.value


def test_expr_operations_do_not_modify_the_operands(P):
    d = P.D
    _ = d / 2 - 1
    _ = abs(-d)
    assert d.src == "D" and d.value == 30.0


def test_expr_unsupported_operands_raise_type_error(P):
    with pytest.raises(TypeError):
        _ = P.D + "x"
    with pytest.raises(TypeError):
        _ = "x" * P.D
    with pytest.raises(TypeError):
        _ = P.D + True
    with pytest.raises(TypeError):
        _ = P.D + [1]
    with pytest.raises(TypeError):
        _ = P.D < "x"


def test_expr_bad_numbers_raise_invalid_argument_with_context(P):
    with pytest.raises(InvalidArgument) as ei:
        _ = P.D / 0
    assert "D / 0" in ei.value.message
    with pytest.raises(InvalidArgument):
        _ = P.D // 0
    with pytest.raises(InvalidArgument):
        _ = 5 / (P.D - 30)
    with pytest.raises(InvalidArgument):
        _ = (P.D - 40) ** 0.5  # would be complex
    with pytest.raises(InvalidArgument):
        _ = P.D**1000
    with pytest.raises(InvalidArgument):
        _ = P.D + float("inf")
    with pytest.raises(InvalidArgument):
        _ = P.D * float("nan")


def test_expr_comparisons_return_plain_bool(P):
    checks = [
        (P.D > 20, True),
        (P.D < 20, False),
        (P.D >= 30, True),
        (P.D <= 29.9, False),
        (P.D == 30, True),
        (30 == P.D, True),
        (P.D != 30, False),
        (P.D != 31, True),
        (20 < P.D, True),
        (40 <= P.D, False),
        (P.d1 < P.D, True),
        (P.D == P.D, True),
        (P.D / 2 == P.d1 - 5, True),
        (P.D == "30", False),
    ]
    for got, want in checks:
        assert got is want


def test_expr_float_int_round_return_numbers(P):
    e = P.D / 7  # 4.2857...
    assert float(P.D) == 30.0 and type(float(P.D)) is float
    assert int(e) == 4 and type(int(e)) is int
    assert round(e) == 4 and type(round(e)) is int
    assert round(e, 2) == 4.29 and type(round(e, 2)) is float
    assert round(P.D / 4) == 8 and round(P.D / 4, 0) == 8.0
    assert int(-(P.D / 7)) == -4


def test_expr_truthiness_follows_the_value(P):
    assert bool(P.D) is True
    assert bool(P.D - 30) is False


def test_expr_format_uses_the_value(P):
    assert f"{P.D:.2f}" == "30.00"
    assert f"{P.D / 7:.3f}" == "4.286"
    assert f"{P.D:>6.1f}" == "  30.0"
    assert f"{P.D:g}" == "30"
    assert f"{P.D}" == "30.0" and str(P.D) == "30.0" and format(P.D) == "30.0"


def test_expr_repr_shows_src_and_value(P):
    r = repr(P.D / 2 - 1)
    assert "D / 2 - 1" in r and "14" in r
    assert "Expr" in r


def test_expr_hash_matches_equal_numbers(P):
    assert hash(P.D) == hash(30.0) == hash(30)
    assert {P.D: 1}[30] == 1


def test_expr_survives_copy_and_pickle(P):
    e = (P.D - P.d1) * 2
    for clone in (copy.copy(e), copy.deepcopy(e), pickle.loads(pickle.dumps(e))):
        assert isinstance(clone, Expr)
        assert clone.src == e.src and clone.value == e.value and clone.params == e.params


def test_expr_from_src_builds_an_expr(P, V):
    e = Expr.from_src("D/2 - 1", V)
    assert isinstance(e, Expr)
    assert e.value == 14.0
    assert e.src == "D / 2 - 1"
    assert e.params == frozenset({"D"})


def test_expr_from_src_result_composes_with_correct_parentheses(V):
    e = Expr.from_src("D - d1", V)
    assert (e * 2).src == "(D - d1) * 2"
    assert (2 - e).src == "2 - (D - d1)"
    assert (-e).src == "-(D - d1)"
    assert Expr.from_src("(D)", V).src == "D"
    assert Expr.from_src("-3", V).src == "-3"
    assert (Expr.from_src("-3", V) ** 2).src == "(-3) ** 2"
    assert Expr.from_src("abs(D - 40)", V).src == "abs(D - 40)"
    assert Expr.from_src("7", V).params == frozenset()


def test_expr_from_src_errors(V):
    with pytest.raises(NotFound) as ei:
        Expr.from_src("DD / 2", V)
    assert "D" in ei.value.candidates
    with pytest.raises(InvalidArgument):
        Expr.from_src("D < 5", V)  # a comparison is not a numeric Expr
    with pytest.raises(InvalidArgument):
        Expr.from_src("D.real", V)
    with pytest.raises(InvalidArgument):
        Expr.from_src("D +", V)


def _random_expr(rng: random.Random, P: ParamSet, depth: int):
    leaves = [P.D, P.d1, P.L, P.a, P.b]
    if depth == 0 or rng.random() < 0.2:
        return rng.choice(leaves)
    kind = rng.choice(["bin", "bin", "bin", "bin", "neg", "abs", "pow"])
    if kind == "neg":
        return -_random_expr(rng, P, depth - 1)
    if kind == "abs":
        return abs(_random_expr(rng, P, depth - 1))
    if kind == "pow":
        return _random_expr(rng, P, depth - 1) ** rng.choice([2, 3, 0.5, P.b, -1])
    left = _random_expr(rng, P, depth - 1)
    right = _random_expr(rng, P, depth - 1)
    if rng.random() < 0.3:
        left = rng.choice([2, 0.5, 3, -4, 1.5, 10])
    elif rng.random() < 0.3:
        right = rng.choice([2, 0.5, 3, -4, 1.5, 10])
    return rng.choice(
        [
            lambda x, y: x + y,
            lambda x, y: x - y,
            lambda x, y: x * y,
            lambda x, y: x / y,
            lambda x, y: x // y,
        ]
    )(left, right)


def test_random_nested_expressions_round_trip_through_eval_expr(P, V):
    rng = random.Random(20261107)
    checked = 0
    for _ in range(600):
        try:
            e = _random_expr(rng, P, depth=4)
        except InvalidArgument:  # division by zero, complex result, overflow
            continue
        if not isinstance(e, Expr):
            continue
        checked += 1
        assert eval_expr(e.src, V) == e.value, e.src
        again = Expr.from_src(e.src, V)
        assert again.src == e.src, e.src
        assert again.value == e.value and again.params == e.params, e.src
    assert checked > 100


# --------------------------------------------------------------------------- eval_expr


@pytest.mark.parametrize(
    "src,want",
    [
        ("1 + 2 * 3", 7.0),
        ("(1 + 2) * 3", 9.0),
        ("7 / 2", 3.5),
        ("7 // 2", 3.0),
        ("-7 // 2", -4.0),
        ("7 % 4", 3.0),
        ("2 ** 10", 1024.0),
        ("2 ** 3 ** 2", 512.0),
        ("-2 ** 2", -4.0),
        ("-3 + +5", 2.0),
        ("0.5 + .5", 1.0),
        ("1e3", 1000.0),
        ("abs(-3)", 3.0),
        ("abs(D - 40)", 10.0),
        ("D / 2 - 1", 14.0),
        ("D", 30.0),
        ("(D)", 30.0),
        ("abs(d1 - D) * 2", 20.0),
    ],
)
def test_eval_expr_numbers(src, want):
    got = eval_expr(src, {"D": 30, "d1": 20})
    assert got == want
    assert type(got) is float


@pytest.mark.parametrize(
    "src,want",
    [
        ("d1 < D", True),
        ("D < d1", False),
        ("d1 <= 20", True),
        ("D >= 31", False),
        ("D == 30", True),
        ("D != 30", False),
        ("0 < d1 < D", True),
        ("0 < d1 < 10", False),
        ("0 < d1 < D < 31", True),
        ("d1 < D and D < 60", True),
        ("d1 < D and D > 60", False),
        ("D > 100 or d1 < D", True),
        ("D > 100 or d1 > D", False),
        ("not D > 100", True),
        ("not (d1 < D)", False),
        ("not d1 < D or D == 30", True),
        ("d1 * 2 > D and abs(D - d1) == 10", True),
    ],
)
def test_eval_expr_booleans(src, want):
    got = eval_expr(src, {"D": 30, "d1": 20})
    assert got is want


def test_eval_expr_short_circuits():
    # the right side would divide by zero if it were evaluated
    assert eval_expr("D > 100 and 1 / 0 > 1", {"D": 30}) is False
    assert eval_expr("D < 100 or 1 / 0 > 1", {"D": 30}) is True
    assert eval_expr("D > 100 < 1 / 0", {"D": 30}) is False


REJECTED = [
    "__import__('os').system('echo hi')",
    "__import__('os')",
    "D.real",
    "D.__class__",
    "(1).__class__.__mro__",
    "D[0]",
    "[D][0]",
    "open('f')",
    "print(D)",
    "max(D, 1)",
    "D(1)",
    "abs(1, 2)",
    "abs()",
    "abs(x=1)",
    "abs(*[1])",
    "abs.__call__(1)",
    "(lambda: 1)()",
    "lambda: 1",
    "exec('x = 1')",
    "eval('1')",
    "'abc'",
    "b'abc'",
    "None",
    "True",
    "False",
    "...",
    "1j",
    "[1, 2]",
    "(1, 2)",
    "{1, 2}",
    "{1: 2}",
    "D if d1 else 1",
    "(x := 1)",
    "D @ d1",
    "D << 1",
    "D >> 1",
    "D & 1",
    "D | 1",
    "D ^ 1",
    "~D",
    "D in d1",
    "D not in d1",
    "D is d1",
    "D is not d1",
    "f'{D}'",
    "[D for D in d1]",
    "(D for D in d1)",
    "await D",
    "(yield)",
    "*D",
]


@pytest.mark.parametrize("src", REJECTED)
def test_eval_expr_rejects_everything_outside_the_whitelist(src):
    with pytest.raises(InvalidArgument) as ei:
        eval_expr(src, {"D": 30, "d1": 20, "x": 1})
    assert ei.value.code == "invalid_arg"
    assert ei.value.message


def test_eval_expr_reject_message_names_the_offending_call():
    with pytest.raises(InvalidArgument) as ei:
        eval_expr("__import__('os').getcwd()", {})
    assert "__import__" in str(ei.value)
    with pytest.raises(InvalidArgument) as ei:
        eval_expr("max(1, 2)", {})
    assert "max" in str(ei.value) and "abs" in str(ei.value)


@pytest.mark.parametrize("src", ["", "   ", "D +", "D = 1", "import os", "D; d1", "1 +* 2", "(("])
def test_eval_expr_syntax_errors_are_invalid_argument(src):
    with pytest.raises(InvalidArgument):
        eval_expr(src, {"D": 30, "d1": 20})


def test_eval_expr_rejects_non_string_source():
    with pytest.raises(InvalidArgument):
        eval_expr(None, {})
    with pytest.raises(InvalidArgument):
        eval_expr(30, {})


def test_eval_expr_unknown_name_is_not_found_with_candidates():
    with pytest.raises(NotFound) as ei:
        eval_expr("DD / 2", {"D": 30, "d1": 20})
    e = ei.value
    assert e.id == "DD" and "DD" in e.message
    assert e.candidates[0] == "D"
    with pytest.raises(NotFound) as ei:
        eval_expr("abs", {"D": 30})  # `abs` is only callable, never a value
    assert ei.value.id == "abs"


def test_eval_expr_does_not_expose_python_builtins_or_globals():
    for name in ["__builtins__", "__name__", "True_", "len", "os"]:
        with pytest.raises(NotFound):
            eval_expr(name, {"D": 30})


@pytest.mark.parametrize(
    "src",
    [
        "1 / 0",
        "D // 0",
        "D % 0",
        "0 ** -1",
        "(-8) ** 0.5",
        "9 ** 9 ** 9",
        "10 ** 400",
        "1e308 * 10",
    ],
)
def test_eval_expr_arithmetic_failures_are_invalid_argument(src):
    with pytest.raises(InvalidArgument) as ei:
        eval_expr(src, {"D": 30})
    assert src in ei.value.message  # the whole expression is quoted back to the agent


def test_eval_expr_zero_division_message_has_the_expression():
    with pytest.raises(InvalidArgument) as ei:
        eval_expr("D / (d1 - 20)", {"D": 30, "d1": 20})
    assert "D / (d1 - 20)" in ei.value.message


def test_eval_expr_arithmetic_on_booleans_is_rejected():
    with pytest.raises(InvalidArgument):
        eval_expr("(D < 5) + 1", {"D": 30})
    with pytest.raises(InvalidArgument):
        eval_expr("-(D < 5)", {"D": 30})
    with pytest.raises(InvalidArgument):
        eval_expr("abs(D < 5)", {"D": 30})


def test_eval_expr_values_must_be_numbers():
    with pytest.raises(InvalidArgument):
        eval_expr("D + 1", {"D": "30"})
    with pytest.raises(InvalidArgument):
        eval_expr("D + 1", {"D": True})


def test_eval_expr_deeply_nested_input_is_rejected_not_crashed():
    with pytest.raises(InvalidArgument):
        eval_expr("-" * 5000 + "1", {})
    with pytest.raises(InvalidArgument):
        eval_expr("(" * 500 + "1" + ")" * 500, {})
    with pytest.raises(InvalidArgument):
        eval_expr("1" + "+1" * 5000, {})


def test_eval_expr_errors_are_liner_errors():
    for src in ["D.real", "DD", "1 / 0", "D +"]:
        with pytest.raises(LinerError):
            eval_expr(src, {"D": 30})


def test_expr_src_of_abs_is_accepted_by_eval_expr(P):
    # the case spelled out in the card
    e = abs(P.D - 40)
    assert e.src == "abs(D - 40)"
    assert eval_expr(e.src, P.values()) == 10.0


# --------------------------------------------------------------------- implementation


def test_implementation_never_calls_eval_or_exec():
    import linercad.params as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    banned = {"eval", "exec", "compile", "__import__"}
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert not (called & banned), called & banned
