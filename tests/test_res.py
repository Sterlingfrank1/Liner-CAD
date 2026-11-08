"""Resource library linercad.res (SPEC M1 §2, card C1): spot values, boundaries, formula guards."""

import pytest

from linercad import res
from linercad.errors import InvalidArgument

RANGES = [0, 3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500]  # main size ranges, mm
GEO = [(max(a, 1) * b) ** 0.5 for a, b in zip(RANGES, RANGES[1:])]  # D of each range
FACTOR = dict(zip(range(5, 19), [7, 10, 16, 25, 40, 64, 100, 160, 250, 400, 640, 1000, 1600, 2500]))


def close(value, expected, rel, floor=1.0):
    """Within ``rel`` relative or ``floor`` micrometres (values in um)."""
    return abs(value - expected) <= max(rel * abs(expected), floor)


# ---------------------------------------------------------------------------- IT / fits


@pytest.mark.parametrize(
    "grade, size, expected",
    [(7, 30, 0.021), (7, 30.001, 0.025), (6, 3, 0.006), (6, 3.001, 0.008), (7, 6, 0.012),
     (7, 10, 0.015), (7, 18, 0.018), (7, 50, 0.025), (7, 80, 0.030), (7, 120, 0.035),
     (7, 120.5, 0.040), (1, 1, 0.0008), (12, 500, 0.63), (18, 2, 1.4), (5, 400, 0.025)],
)
def test_it_values_and_inclusive_upper_bounds(grade, size, expected):
    assert res.it(grade, size) == expected


@pytest.mark.parametrize(
    "code, size, upper, lower",
    [("H7", 30, 0.021, 0.0), ("k6", 30, 0.015, 0.002), ("f7", 25, -0.020, -0.041),
     ("p6", 100, 0.059, 0.037), ("r6", 60, 0.060, 0.041), ("K7", 30, 0.006, -0.015),
     ("g6", 40, -0.009, -0.025), ("H7", 40, 0.025, 0.0), ("e9", 110, -0.072, -0.159),
     ("H11", 110, 0.220, 0.0), ("K7", 300, 0.016, -0.036), ("js6", 30, 0.0065, -0.0065),
     ("JS9", 8, 0.018, -0.018), ("h6", 30, 0.0, -0.013), ("m6", 30, 0.021, 0.008),
     ("s6", 60, 0.072, 0.053), ("u6", 30, 0.061, 0.048), ("t6", 28, 0.054, 0.041),
     ("c11", 35, -0.120, -0.280), ("a11", 5, -0.270, -0.345), ("n6", 30, 0.028, 0.015),
     ("D9", 30, 0.117, 0.065), ("F8", 30, 0.053, 0.020), ("G7", 30, 0.028, 0.007),
     ("M7", 30, 0.0, -0.021), ("N7", 30, -0.007, -0.028), ("P7", 30, -0.014, -0.035),
     ("R7", 30, -0.020, -0.041), ("U7", 30, -0.040, -0.061), ("K8", 30, 0.010, -0.023),
     ("N9", 30, 0.0, -0.052), ("P7", 3, -0.006, -0.016), ("k8", 30, 0.033, 0.0),
     ("k5", 10, 0.007, 0.001)],
)
def test_fit_known_values(code, size, upper, lower):
    got = res.fit(code, size)
    assert (got["upper"], got["lower"]) == (pytest.approx(upper), pytest.approx(lower))
    assert got["code"] == code and got["std"].startswith("GB/T 1800.2")
    assert got["it"] == int("".join(ch for ch in code if ch.isdigit()))


@pytest.mark.parametrize("grade", range(5, 19))
def test_it_matches_formula(grade):
    for hi, d in zip(RANGES[2:], GEO[1:]):  # sizes > 3 mm
        unit = 0.45 * d ** (1 / 3) + 0.001 * d
        assert close(res.it(grade, hi) * 1000, FACTOR[grade] * unit, 0.06), (grade, hi)


@pytest.mark.parametrize("letter, formula", [
    ("d", lambda d: -16 * d**0.44), ("e", lambda d: -11 * d**0.41),
    ("f", lambda d: -5.5 * d**0.41), ("g", lambda d: -2.5 * d**0.34)])
def test_shaft_deviation_matches_formula(letter, formula):
    for hi, d in zip(RANGES[2:], GEO[1:]):  # above 3 mm; the 0-3 row is table-only
        assert close(res.fit(letter + "8", hi)["upper"] * 1000, formula(d), 0.08), (letter, hi)


def test_unknown_input_gives_candidates():
    for args in (("x7", 30), ("H19", 30), ("H7", 600), ("H7", 0), ("t6", 20), ("K", 30)):
        with pytest.raises(InvalidArgument) as err:
            res.fit(*args)
        assert err.value.candidates or err.value.hint, args
    with pytest.raises(InvalidArgument):
        res.it(19, 30)


# ---------------------------------------------------------------------------- GB/T 1804


@pytest.mark.parametrize(
    "cls, size, kind, bound",
    [("m", 45, "linear", 0.3), ("f", 0.5, "linear", 0.05), ("f", 3, "linear", 0.05),
     ("m", 3.1, "linear", 0.1), ("c", 100, "linear", 0.8), ("v", 1000, "linear", 4),
     ("v", 4000, "linear", 8), ("m", 2, "chamfer", 0.2), ("c", 5, "chamfer", 1),
     ("m", 30, "chamfer", 1), ("v", 9, "chamfer", 2), ("m", 8, "angle", 1.0),
     ("c", 30, "angle", 1.0), ("v", 500, "angle", 20 / 60), ("f", 100, "angle", 20 / 60)],
)
def test_general_tol_values(cls, size, kind, bound):
    got = res.general_tol(cls, size, kind=kind)
    assert got["upper"] == pytest.approx(bound) and got["lower"] == pytest.approx(-bound)
    assert got["class"] == cls and got["std"] == "GB/T 1804-2000"


def test_general_tol_angle_keeps_original_text():
    assert res.general_tol("m", 30, kind="angle")["text"] == "±0°30'"
    assert res.general_tol("c", 5, kind="angle")["text"] == "±1°30'"


def test_general_tol_errors_have_candidates():
    for args, kw in [(("x", 10), {}), (("m", 10), {"kind": "volume"}), (("m", 5000), {}),
                     (("v", 1), {}), (("m", 0.2), {})]:
        with pytest.raises(InvalidArgument) as err:
            res.general_tol(*args, **kw)
        assert err.value.candidates or err.value.hint, args
