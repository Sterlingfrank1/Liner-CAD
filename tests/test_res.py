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
    [
        (7, 30, 0.021),
        (7, 30.001, 0.025),
        (6, 3, 0.006),
        (6, 3.001, 0.008),
        (7, 6, 0.012),
        (7, 10, 0.015),
        (7, 18, 0.018),
        (7, 50, 0.025),
        (7, 80, 0.030),
        (7, 120, 0.035),
        (7, 120.5, 0.040),
        (1, 1, 0.0008),
        (12, 500, 0.63),
        (18, 2, 1.4),
        (5, 400, 0.025),
    ],
)
def test_it_values_and_inclusive_upper_bounds(grade, size, expected):
    assert res.it(grade, size) == expected


@pytest.mark.parametrize(
    "code, size, upper, lower",
    [
        ("H7", 30, 0.021, 0.0),
        ("k6", 30, 0.015, 0.002),
        ("f7", 25, -0.020, -0.041),
        ("p6", 100, 0.059, 0.037),
        ("r6", 60, 0.060, 0.041),
        ("K7", 30, 0.006, -0.015),
        ("g6", 40, -0.009, -0.025),
        ("H7", 40, 0.025, 0.0),
        ("e9", 110, -0.072, -0.159),
        ("H11", 110, 0.220, 0.0),
        ("K7", 300, 0.016, -0.036),
        ("js6", 30, 0.0065, -0.0065),
        ("JS9", 8, 0.018, -0.018),
        ("h6", 30, 0.0, -0.013),
        ("m6", 30, 0.021, 0.008),
        ("s6", 60, 0.072, 0.053),
        ("u6", 30, 0.061, 0.048),
        ("t6", 28, 0.054, 0.041),
        ("c11", 35, -0.120, -0.280),
        ("a11", 5, -0.270, -0.345),
        ("n6", 30, 0.028, 0.015),
        ("D9", 30, 0.117, 0.065),
        ("F8", 30, 0.053, 0.020),
        ("G7", 30, 0.028, 0.007),
        ("M7", 30, 0.0, -0.021),
        ("N7", 30, -0.007, -0.028),
        ("P7", 30, -0.014, -0.035),
        ("R7", 30, -0.020, -0.041),
        ("U7", 30, -0.040, -0.061),
        ("K8", 30, 0.010, -0.023),
        ("N9", 30, 0.0, -0.052),
        ("P7", 3, -0.006, -0.016),
        ("k8", 30, 0.033, 0.0),
        ("k5", 10, 0.007, 0.001),
    ],
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


@pytest.mark.parametrize(
    "letter, formula",
    [
        ("d", lambda d: -16 * d**0.44),
        ("e", lambda d: -11 * d**0.41),
        ("f", lambda d: -5.5 * d**0.41),
        ("g", lambda d: -2.5 * d**0.34),
    ],
)
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
    [
        ("m", 45, "linear", 0.3),
        ("f", 0.5, "linear", 0.05),
        ("f", 3, "linear", 0.05),
        ("m", 3.1, "linear", 0.1),
        ("c", 100, "linear", 0.8),
        ("v", 1000, "linear", 4),
        ("v", 4000, "linear", 8),
        ("m", 2, "chamfer", 0.2),
        ("c", 5, "chamfer", 1),
        ("m", 30, "chamfer", 1),
        ("v", 9, "chamfer", 2),
        ("m", 8, "angle", 1.0),
        ("c", 30, "angle", 1.0),
        ("v", 500, "angle", 20 / 60),
        ("f", 100, "angle", 20 / 60),
    ],
)
def test_general_tol_values(cls, size, kind, bound):
    got = res.general_tol(cls, size, kind=kind)
    assert got["upper"] == pytest.approx(bound) and got["lower"] == pytest.approx(-bound)
    assert got["class"] == cls and got["std"] == "GB/T 1804-2000"


def test_general_tol_angle_keeps_original_text():
    assert res.general_tol("m", 30, kind="angle")["text"] == "±0°30'"
    assert res.general_tol("c", 5, kind="angle")["text"] == "±1°30'"


def test_general_tol_errors_have_candidates():
    for args, kw in [
        (("x", 10), {}),
        (("m", 10), {"kind": "volume"}),
        (("m", 5000), {}),
        (("v", 1), {}),
        (("m", 0.2), {}),
    ]:
        with pytest.raises(InvalidArgument) as err:
            res.general_tol(*args, **kw)
        assert err.value.candidates or err.value.hint, args


# ---------------------------------------------------------------------- threads (196 / 193 / 197)


@pytest.mark.parametrize(
    "spec, d2, d1, pitch, coarse",
    [
        ("M10", 9.026, 8.376, 1.5, True),
        ("M20x1.5", 19.026, 18.376, 1.5, False),
        ("M20×1.5", 19.026, 18.376, 1.5, False),
        ("M6", 5.350, 4.917, 1, True),
        ("M12", 10.863, 10.106, 1.75, True),
        ("M16", 14.701, 13.835, 2, True),
        ("M24", 22.051, 20.752, 3, True),
        ("M30", 27.727, 26.211, 3.5, True),
        ("M8x1", 7.350, 6.917, 1, False),
        ("M1.6", 1.373, 1.221, 0.35, True),
        ("M64", 60.103, 57.505, 6, True),
        ("M20x2.5", 18.376, 17.294, 2.5, True),
    ],
)
def test_thread_dimensions(spec, d2, d1, pitch, coarse):
    got = res.thread(spec)
    assert (got["P"], got["d2"], got["d1"], got["coarse"]) == (pitch, d2, d1, coarse)
    assert got["std"] == "GB/T 196-2003"


def test_thread_series_membership():
    assert res.thread("M10")["first"] and not res.thread("M14")["first"]
    for spec in ("M10x1.2", "M5.5", "M70", "M10x"):
        with pytest.raises(InvalidArgument) as err:
            res.thread(spec)
        assert err.value.candidates, spec
    with pytest.raises(InvalidArgument) as err:
        res.thread("M10x1.2")
    assert "M10x1.25" in err.value.candidates


def test_thread_classes():
    assert {"4h", "6h", "6g", "6f", "6e", "8g", "5g6g", "7g6g"} <= set(res.thread_classes("ext"))
    assert {"4H", "5H", "6H", "7H", "6G"} <= set(res.thread_classes("int"))
    assert res.thread("M10", cls="6g")["cls"] == "6g"
    assert res.thread("M10", cls="6H")["cls"] == "6H"
    with pytest.raises(InvalidArgument) as err:
        res.thread("M10", cls="6z")
    assert "6g" in err.value.candidates
    with pytest.raises(InvalidArgument):
        res.thread_classes("both")


# ---------------------------------------------------------------------------- keys (1095)


@pytest.mark.parametrize(
    "d, b, h, t1, t2, rng",
    [
        (32, 10, 8, 5.0, 3.3, [30, 38]),
        (30, 8, 7, 4.0, 3.3, [22, 30]),
        (8, 2, 2, 1.2, 1.0, [6, 8]),
        (8.1, 3, 3, 1.8, 1.4, [8, 10]),
        (45, 14, 9, 5.5, 3.8, [44, 50]),
        (60, 18, 11, 7.0, 4.4, [58, 65]),
        (100, 28, 16, 10.0, 6.4, [95, 110]),
        (130, 32, 18, 11.0, 7.4, [110, 130]),
    ],
)
def test_key_values(d, b, h, t1, t2, rng):
    got = res.key(d)
    assert (got["b"], got["h"], got["t1"], got["t2"], got["d_range"]) == (b, h, t1, t2, rng)
    assert got["std"] == "GB/T 1095-2003"


def test_key_depth_deviations_and_derived_dimensions():
    small, big = res.key(8), res.key(32)
    assert (small["t1_dev"], small["t2_dev"]) == ([0.1, 0.0], [0.1, 0.0])
    assert big["t1_dev"] == [0.2, 0.0]
    assert big["d_t1"] == {"nominal": 27.0, "upper": 0.0, "lower": -0.2}
    assert big["d_t2"] == {"nominal": 35.3, "upper": 0.2, "lower": 0.0}
    assert (big["width_fit"]["normal"], big["width_fit"]["close"]) == (
        {"shaft": "N9", "hub": "JS9"},
        {"shaft": "P9", "hub": "P9"},
    )


def test_key_table_is_contiguous_and_depths_add_up():
    sizes = [6, 8, 10, 12, 17, 22, 30, 38, 44, 50, 58, 65, 75, 85, 95, 110, 130]
    for lo, hi in zip(sizes, sizes[1:]):
        got = res.key(hi)
        assert got["d_range"] == [lo, hi]
        assert (
            0.19 <= got["t1"] + got["t2"] - got["h"] <= 0.41
        )  # keyway depths leave 0.2-0.4 clearance
    for bad in (5.9, 131):
        with pytest.raises(InvalidArgument):
            res.key(bad)


# ------------------------------------------------------------------- splines, datums, roughness


@pytest.mark.parametrize(
    "spec, n, d, big_d, b, series",
    [
        ("6x23x26x6", 6, 23, 26, 6, "light"),
        ("6×23×28×6", 6, 23, 28, 6, "medium"),
        ("8x56x65x10", 8, 56, 65, 10, "medium"),
        ("10x112x120x18", 10, 112, 120, 18, "light"),
        ("6x13x16x3.5", 6, 13, 16, 3.5, "medium"),
        ("8x42x46x8", 8, 42, 46, 8, "light"),
    ],
)
def test_spline(spec, n, d, big_d, b, series):
    got = res.spline(spec)
    assert (got["N"], got["d"], got["D"], got["B"], got["series"]) == (n, d, big_d, b, series)
    assert got["std"] == "GB/T 1144-2001"
    assert got["tol"]["hole"] == {"d": "H7", "D": "H10", "B": ["H9", "H11"]}
    assert got["tol"]["shaft"]["sliding"] == {"d": "f7", "D": "a11", "B": "d10"}


def test_spline_unknown_gives_candidates():
    with pytest.raises(InvalidArgument) as err:
        res.spline("6x23x27x6")
    assert "6x23x26x6" in err.value.candidates


def test_datum_excluded_letters_and_roughness_series():
    iso = res.datum_excluded("ISO")
    assert iso["letters"] == ["I", "O", "Q", "X"] and "5459" in iso["std"] and iso["source"]
    gb = res.datum_excluded("GB")
    assert gb["std"] == "GB/T 17851-2010" and gb["letters"] == ["I", "O", "Q", "X"]
    assert gb["verified"] is True and not iso["verified"]
    with pytest.raises(InvalidArgument):
        res.datum_excluded("DIN")
    ra = res.rough_series()
    assert {0.025, 0.1, 0.4, 0.8, 1.6, 3.2, 6.3, 12.5, 25, 50} <= set(ra["preferred"])
    assert ra["param"] == "Ra" and ra["std"] == "GB/T 1031-2009"
    with pytest.raises(InvalidArgument) as err:
        res.rough_series("Rq")
    assert "Ra" in err.value.candidates


def test_center_hole_type_a():
    c = res.center_hole("A", 2.5)
    assert (c["D"], c["t"], c["designation"]) == (5.3, 2.2, "A2.5/5.3")
    assert res.center_hole("A", 4)["D"] == 8.5 and res.center_hole("A", 10)["D"] == 21.2
    with pytest.raises(InvalidArgument):
        res.center_hole("B", 2.5)
