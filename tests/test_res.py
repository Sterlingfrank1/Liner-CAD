"""Resource library linercad.res (SPEC M1 §2, card C1): spot values, boundaries, formula guards."""

import math

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
    assert not gb["verified"] and not iso["verified"]  # both lists are single-lineage (A4)
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
    with pytest.raises(InvalidArgument) as err:
        res.center_hole("X", 2.5)
    assert err.value.candidates == ["A", "B", "R", "C"]


# ------------------------------------------------- GB/T 145-2001 type B (ISO 2540 Annex A)

# ISO 2540:2016 Table 1, column d2 (the 60 deg cone diameter of the centre drill), for d = 1.0 .. 10.0
ISO_2540_D2 = [2.12, 2.65, 3.35, 4.25, 5.30, 6.70, 8.50, 10.60, 13.20, 17.00, 21.20]
B_SIZES = [1.0, 1.25, 1.6, 2.0, 2.5, 3.15, 4.0, 5.0, 6.3, 8.0, 10.0]


def test_center_hole_type_b():
    c = res.center_hole("B", 2.5)
    assert (c["D1"], c["D2"], c["l2"], c["t"], c["l_min"]) == (5.3, 8.0, 3.2, 2.2, 5.5)
    assert (c["D"], c["designation"], c["std"]) == (8.0, "B2.5/8", "GB/T 145-2001")
    assert res.center_hole("B", 1.0)["D2"] == 3.15 and res.center_hole("B", 10)["D2"] == 28.0
    assert res.center_hole("B", 1.25)["avoid"] and not res.center_hole("B", 2.0)["avoid"]
    with pytest.raises(InvalidArgument) as err:
        res.center_hole("B", 2.6)
    assert "2.5" in err.value.candidates


@pytest.mark.parametrize("d", B_SIZES)
def test_center_hole_type_b_consistency(d):
    b = res.center_hole("B", d)
    # D1 is the cone of type A and of the ISO 2540 drill
    assert b["D1"] == res.center_hole("A", d)["D"] == ISO_2540_D2[B_SIZES.index(d)]
    # l2 follows from the 60 deg cone plus the 120 deg protecting chamfer
    cone = (b["D1"] - d) / 2 / math.tan(math.radians(30))
    chamfer = (b["D2"] - b["D1"]) / 2 / math.tan(math.radians(60))
    assert b["l2"] == pytest.approx(cone + chamfer, abs=0.011)
    assert b["t"] == res.center_hole("A", d)["t"] and b["l_min"] > b["t"]


# ---------------------------------------- GB/T 145-2001 types R and C (card A2)

# Cell-by-cell sources of the two tables added by A2, read from the local copies of the pages
# (2026-11-09, re-read 2026-11-21):
#   * SOURCE_164580_*: the GB/T 145-2001 tables reproduced at www.164580.com/info_369427.html
#     (that page titles the R table "table 3" as well - a numbering slip on the page);
#   * SOURCE_HANDBOOK_*: the A/B/R/C combined table of the handbook page at
#     www.jlc-jdgf.com/mcbook/new01368.htm, mirrored at dev.inkcad.com (the mirror is the same
#     handbook, so both handbook pages are one lineage, not two independent sources).
# The two sources agree in every R and C cell. They are kept as separate fixtures so that the
# tests below compare them cell by cell and then check the resource library against the standard
# page. Both lineage notes are in the [meta] of center_holes.toml.
SOURCE_164580_R = {
    "d": [1.00, 1.25, 1.60, 2.00, 2.50, 3.15, 4.00, 5.00, 6.30, 8.00, 10.00],
    "d2": [2.12, 2.65, 3.35, 4.25, 5.30, 6.70, 8.50, 10.60, 13.20, 17.00, 21.20],
    "l_min": [2.3, 2.8, 3.5, 4.4, 5.5, 7.0, 8.9, 11.2, 14.0, 17.9, 22.5],
    "r_max": [3.15, 4.00, 5.00, 6.30, 8.00, 10.00, 12.50, 16.00, 20.00, 25.00, 31.50],
    "r_min": [2.50, 3.15, 4.00, 5.00, 6.30, 8.00, 10.00, 12.50, 16.00, 20.00, 25.00],
    "avoid": [False, True, False, False, False, False, False, True, False, True, False],
}
SOURCE_HANDBOOK_R = {
    "d": [1.00, 1.25, 1.60, 2.00, 2.50, 3.15, 4.00, 5.00, 6.30, 8.00, 10.00],
    "d2": [2.12, 2.65, 3.35, 4.25, 5.30, 6.70, 8.50, 10.60, 13.20, 17.00, 21.20],
    "l_min": [2.3, 2.8, 3.5, 4.4, 5.5, 7.0, 8.9, 11.2, 14.0, 17.9, 22.5],
    "r_max": [3.15, 4.00, 5.00, 6.30, 8.00, 10.00, 12.50, 16.00, 20.00, 25.00, 31.50],
    "r_min": [2.50, 3.15, 4.00, 5.00, 6.30, 8.00, 10.00, 12.50, 16.00, 20.00, 25.00],
    "avoid": [False, True, False, False, False, False, False, True, False, True, False],
}
SOURCE_164580_C = {
    "d": ["M3", "M4", "M5", "M6", "M8", "M10", "M12", "M16", "M20", "M24"],
    "D1": [3.2, 4.3, 5.3, 6.4, 8.4, 10.5, 13.0, 17.0, 21.0, 26.0],
    "D2": [5.3, 6.7, 8.1, 9.6, 12.2, 14.9, 18.1, 23.0, 28.4, 34.2],
    "D3": [5.8, 7.4, 8.8, 10.5, 13.2, 16.3, 19.8, 25.3, 31.3, 38.0],
    "l": [2.6, 3.2, 4.0, 5.0, 6.0, 7.5, 9.5, 12.0, 15.0, 18.0],
    "t": [1.8, 2.1, 2.4, 2.8, 3.3, 3.8, 4.4, 5.2, 6.4, 8.0],
}
SOURCE_HANDBOOK_C = {
    "d": ["M3", "M4", "M5", "M6", "M8", "M10", "M12", "M16", "M20", "M24"],
    "D1": [3.2, 4.3, 5.3, 6.4, 8.4, 10.5, 13.0, 17.0, 21.0, 26.0],
    "D2": [5.3, 6.7, 8.1, 9.6, 12.2, 14.9, 18.1, 23.0, 28.4, 34.2],
    "D3": [5.8, 7.4, 8.8, 10.5, 13.2, 16.3, 19.8, 25.3, 31.3, 38.0],
    "l": [2.6, 3.2, 4.0, 5.0, 6.0, 7.5, 9.5, 12.0, 15.0, 18.0],
    # the handbook heads this reference column l1, the standard page heads it t; same numbers
    "t": [1.8, 2.1, 2.4, 2.8, 3.3, 3.8, 4.4, 5.2, 6.4, 8.0],
}


def test_center_hole_type_r_sources_agree_cell_by_cell():
    assert SOURCE_164580_R == SOURCE_HANDBOOK_R


@pytest.mark.parametrize("i", range(len(SOURCE_164580_R["d"])))
def test_center_hole_type_r_matches_sources(i):
    src, d = SOURCE_164580_R, SOURCE_164580_R["d"][i]
    c = res.center_hole("R", d)
    assert (c["type"], c["d"]) == ("R", d)
    for key in ("d2", "l_min", "r_max", "r_min"):
        assert c[key] == src[key][i], key
    assert c["avoid"] == src["avoid"][i] and c["D"] == c["d2"]
    # cross-checks inside the standard: R's outside diameter is A's D and B's D1, and R's minimum
    # depth is B's l_min
    assert c["d2"] == res.center_hole("A", d)["D"] == res.center_hole("B", d)["D1"]
    assert c["l_min"] == res.center_hole("B", d)["l_min"]
    assert c["std"] == "GB/T 145-2001"
    assert c["verified"] is False  # single GB/T 145 lineage, ISO 2541 not read


def test_center_hole_type_r_designation():
    # GB/T 4459.5-1999 4.1: R + pilot diameter / outside countersink diameter (R3.15/6.7)
    c = res.center_hole("R", 2.5)
    assert (c["designation"], c["D"]) == ("R2.5/5.3", 5.3)
    assert res.center_hole("R", 10)["designation"] == "R10/21.2"
    assert res.center_hole("R", 1.25)["avoid"] and not res.center_hole("R", 2.0)["avoid"]
    with pytest.raises(InvalidArgument) as err:
        res.center_hole("R", 2.6)
    assert "2.5" in err.value.candidates


def test_center_hole_type_c_sources_agree_cell_by_cell():
    assert SOURCE_164580_C == SOURCE_HANDBOOK_C


@pytest.mark.parametrize("i", range(len(SOURCE_164580_C["d"])))
def test_center_hole_type_c_matches_sources(i):
    src, thread = SOURCE_164580_C, SOURCE_164580_C["d"][i]
    c = res.center_hole("C", thread)
    assert (c["type"], c["thread"], c["d"]) == ("C", thread, float(thread[1:]))
    for key in ("D1", "D2", "D3", "l", "t"):
        assert c[key] == src[key][i], key
    assert c["D"] == c["D3"] and not c["avoid"]
    assert c["std"] == "GB/T 145-2001"
    assert c["verified"] is False  # single GB/T 145 lineage, DIN 332-2 not read


def test_center_hole_type_c_designation():
    c = res.center_hole("C", 6)
    assert (c["thread"], c["D1"], c["D2"], c["D3"], c["l"], c["t"], c["D"]) == (
        "M6",
        6.4,
        9.6,
        10.5,
        5.0,
        2.8,
        10.5,
    )
    # GB/T 4459.5-1999: C + thread + L + "/" + face diameter (CM10L30/16.3); the thread length L
    # is chosen with the part, so it is passed in; without it only the type and thread are marked
    assert c["designation"] == "CM6"
    assert res.center_hole("C", "M6", length=10)["designation"] == "CM6L10/10.5"
    assert res.center_hole("C", 10, length=30)["designation"] == "CM10L30/16.3"
    # the same shaft-end diameter M10 gives D3 = 16.3, as in the GB/T 4459.5 example
    with pytest.raises(InvalidArgument) as err:
        res.center_hole("C", 7)
    assert {"M6", "M8"} & set(err.value.candidates)
    with pytest.raises(InvalidArgument) as err:
        res.center_hole("C", 6, length=-1)
    assert err.value.values["length"] == -1
    for bad in (float("nan"), float("inf")):
        with pytest.raises(InvalidArgument):
            res.center_hole("C", 6, length=bad)
    with pytest.raises(InvalidArgument):
        res.center_hole("A", 2.5, length=10)  # L belongs to type C only


def test_center_hole_type_c_cone_geometry():
    # t is the reference depth of the 60 deg cone between D2 and D1 for every row but M24: the
    # printed t = 8.0 does not follow that geometry (7.10). The printed value is kept and the
    # discrepancy is recorded in the [meta] of center_holes.toml for a check against the original.
    for thread in SOURCE_164580_C["d"]:
        c = res.center_hole("C", thread)
        assert c["D3"] > c["D2"] > c["D1"] and c["l"] > c["t"]
        cone = (c["D2"] - c["D1"]) / 2 / math.tan(math.radians(30))
        if thread == "M24":
            assert c["t"] == 8.0 and abs(cone - c["t"]) > 0.5
        else:
            assert c["t"] == pytest.approx(cone, abs=0.06), thread


# ------------------------------------------------------------- GB/T 3-1997 thread undercuts

# ISO 4755:1983 (external thread undercuts): P, dg offset (dg = d - offset), g1 min, g2 max, r
ISO_4755 = [
    (0.25, 0.4, 0.4, 0.75, 0.12), (0.3, 0.5, 0.5, 0.9, 0.16), (0.35, 0.6, 0.6, 1.05, 0.16),
    (0.4, 0.7, 0.6, 1.2, 0.2), (0.45, 0.7, 0.7, 1.35, 0.2), (0.5, 0.8, 0.8, 1.5, 0.2),
    (0.6, 1.0, 0.9, 1.8, 0.4), (0.7, 1.1, 1.1, 2.1, 0.4), (0.75, 1.2, 1.2, 2.25, 0.4),
    (0.8, 1.3, 1.3, 2.4, 0.4), (1, 1.6, 1.6, 3, 0.6), (1.25, 2.0, 2.0, 3.75, 0.6),
    (1.5, 2.3, 2.5, 4.5, 0.8), (1.75, 2.6, 3.0, 5.25, 1.0), (2, 3.0, 3.4, 6, 1.0),
    (2.5, 3.6, 4.4, 7.5, 1.2), (3, 4.4, 5.2, 9, 1.6), (3.5, 5.0, 6.2, 10.5, 1.6),
    (4, 5.7, 7.0, 12, 2.0), (4.5, 6.4, 8.0, 13.5, 2.5), (5, 7.0, 9.0, 15, 2.5),
    (5.5, 7.7, 11.0, 17.5, 3.2), (6, 8.3, 11.0, 18, 3.2),
]  # fmt: skip

# ISO 3508:1976 (external thread run-outs): P, x, x short, a, a short, a long
ISO_3508 = [
    (0.2, 0.5, 0.25, 0.6, 0.4, 0.8), (0.25, 0.6, 0.3, 0.75, 0.5, 1), (0.3, 0.75, 0.4, 0.9, 0.6, 1.2),
    (0.35, 0.9, 0.45, 1.05, 0.7, 1.4), (0.4, 1, 0.5, 1.2, 0.8, 1.6), (0.45, 1.1, 0.6, 1.35, 0.9, 1.8),
    (0.5, 1.25, 0.7, 1.5, 1, 2), (0.6, 1.5, 0.75, 1.8, 1.2, 2.4), (0.7, 1.75, 0.9, 2.1, 1.4, 2.8),
    (0.75, 1.9, 1, 2.25, 1.5, 3), (0.8, 2, 1, 2.4, 1.6, 3.2), (1, 2.5, 1.25, 3, 2, 4),
    (1.25, 3.2, 1.6, 4, 2.5, 5), (1.5, 3.8, 1.9, 4.5, 3, 6), (1.75, 4.3, 2.2, 5.3, 3.5, 7),
    (2, 5, 2.5, 6, 4, 8), (2.5, 6.3, 3.2, 7.5, 5, 10), (3, 7.5, 3.8, 9, 6, 12),
    (3.5, 9, 4.5, 10.5, 7, 14), (4, 10, 5, 12, 8, 16), (4.5, 11, 5.5, 13.5, 9, 18),
    (5, 12.5, 6.3, 15, 10, 20), (5.5, 14, 7, 16.5, 11, 22), (6, 15, 7.5, 18, 12, 24),
]  # fmt: skip


def test_thread_undercut_external():
    u = res.thread_undercut("M24x1.5")
    assert (u["kind"], u["P"], u["d"]) == ("ext", 1.5, 24)
    assert (u["g1_min"], u["g2_max"], u["r"], u["dg_offset"]) == (2.5, 4.5, 0.8, 2.3)
    assert (u["dg"], u["dg_tol"], u["std"]) == (21.7, "h13", "GB/T 3-1997")
    assert res.thread_undercut("M10")["dg"] == 7.7  # coarse pitch 1.5
    assert res.thread_undercut("M3")["dg_tol"] == "h12"  # d <= 3 mm
    bare = res.thread_undercut(2.5)  # pitch only: no diameter, so no dg
    assert (bare["g1_min"], bare["g2_max"], bare["dg_offset"]) == (4.4, 7.5, 3.6)
    assert "dg" not in bare


def test_thread_undercut_internal():
    u = res.thread_undercut("M20x2", kind="int")
    assert (u["kind"], u["G1"], u["G1_short"], u["R"]) == ("int", 8, 4, 1.0)
    assert (u["Dg"], u["Dg_tol"]) == (20.5, "H13")
    assert res.thread_undercut(0.8, kind="int")["Dg_offset"] == 0.3
    assert res.thread_undercut(1, kind="int")["Dg_offset"] == 0.5


def test_thread_undercut_errors():
    with pytest.raises(InvalidArgument) as err:
        res.thread_undercut(0.9)
    assert 1.0 in err.value.candidates and 0.8 in err.value.candidates
    with pytest.raises(InvalidArgument):
        res.thread_undercut(0.2)  # run-outs start at 0.2, undercuts at 0.25
    with pytest.raises(InvalidArgument):
        res.thread_undercut(0.25, kind="int")  # internal undercuts start at 0.5
    with pytest.raises(InvalidArgument) as err:
        res.thread_undercut("M24", kind="inner")
    assert err.value.candidates == ["ext", "int"]


@pytest.mark.parametrize("P, offset, g1, g2, r", ISO_4755)
def test_thread_undercut_matches_iso_4755(P, offset, g1, g2, r):
    u = res.thread_undercut(P)
    assert (u["dg_offset"], u["g1_min"], u["g2_max"], u["r"]) == (offset, g1, g2, r)


def test_thread_undercut_internal_rules():
    for P in (0.5, 0.6, 0.7, 0.75, 0.8, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6):
        u = res.thread_undercut(P, kind="int")
        assert (u["G1"], u["G1_short"]) == (pytest.approx(4 * P), pytest.approx(2 * P))
        assert u["Dg_offset"] == (0.3 if P <= 0.8 else 0.5)
        assert u["R"] == pytest.approx(0.5 * P, abs=0.06)  # the table's reference value is R = 0.5P


def test_thread_runout():
    r = res.thread_runout("M24x1.5")
    assert r["ext"] == {"x": 3.8, "x_short": 1.9, "a": 4.5, "a_short": 3, "a_long": 6}
    assert r["int"] == {"X": 6, "X_short": 3, "A": 7, "A_long": 12}
    assert r["std"] == "GB/T 3-1997" and r["P"] == 1.5
    assert (
        res.thread_runout(1.75)["ext"]["x"] == 4.3
    )  # the GB/T 3 page misprints it; ISO 3508 gives 4.3
    with pytest.raises(InvalidArgument):
        res.thread_runout(0.9)


@pytest.mark.parametrize("P, x, xs, a, a_short, a_long", ISO_3508)
def test_thread_runout_matches_iso_3508(P, x, xs, a, a_short, a_long):
    got = res.thread_runout(P)
    e = got["ext"]
    assert (e["x"], e["x_short"], e["a"], e["a_short"], e["a_long"]) == (x, xs, a, a_short, a_long)
    assert got["int"]["X"] == pytest.approx(4 * P)  # GB/T 3: internal run-out X = 4P, short = 2P
    assert got["int"]["X_short"] == pytest.approx(2 * P)


# ---------------------------------------------------------- GB/T 6403.5 grinding wheel grooves


def test_grinding_groove():
    g = res.grinding_groove(30)
    assert g["d_range"] == [10, 50] and g["std"].startswith("GB/T 6403.5")
    assert (g["b1"], g["b2"], g["h"], g["r"]) == (2.0, 4.0, 0.3, 0.8)  # first (smallest) option
    assert [o["b1"] for o in g["options"]] == [2.0, 3.0]
    assert res.grinding_groove(30, b1=3.0)["h"] == 0.4
    assert [o["b1"] for o in res.grinding_groove(8)["options"]] == [0.6, 1.0, 1.6]
    assert [o["b1"] for o in res.grinding_groove(80)["options"]] == [4.0, 5.0]
    big = res.grinding_groove(250)
    assert [(o["b1"], o["h"], o["r"]) for o in big["options"]] == [(8.0, 0.8, 2.0), (10, 1.2, 3.0)]
    assert big["d_range"] == [100, None]


# GB/T 6403.5-2008, Table 1 as printed: one row per b1 column, b2 / h / r repeated over the b1 columns
# their merged cell spans, and the d band drawn under them: (b1, (over, upto), b2, h, r).
GBT_6403_5_TABLE_1 = [
    (0.6, (0, 10), 2.0, 0.1, 0.2),
    (1.0, (0, 10), 3.0, 0.2, 0.5),
    (1.6, (0, 10), 3.0, 0.2, 0.5),
    (2.0, (10, 50), 4.0, 0.3, 0.8),
    (3.0, (10, 50), 4.0, 0.4, 1.0),
    (4.0, (50, 100), 5.0, 0.4, 1.0),
    (5.0, (50, 100), 5.0, 0.6, 1.6),
    (8.0, (100, None), 8.0, 0.8, 2.0),
    (10.0, (100, None), 10.0, 1.2, 3.0),
]


@pytest.mark.parametrize(
    "d, band", [(5, (0, 10)), (30, (10, 50)), (80, (50, 100)), (250, (100, None))]
)
def test_grinding_groove_matches_gbt_6403_5_table_1(d, band):
    got = res.grinding_groove(d)
    rows = [(o["b1"], tuple(got["d_range"]), o["b2"], o["h"], o["r"]) for o in got["options"]]
    assert rows == [row for row in GBT_6403_5_TABLE_1 if row[1] == band]
    assert got["verified"] is True


def test_grinding_groove_band_edges_and_errors():
    assert res.grinding_groove(10)["d_range"] == [0, 10]
    assert res.grinding_groove(10.001)["d_range"] == [10, 50]
    assert res.grinding_groove(50)["d_range"] == [10, 50]
    assert res.grinding_groove(100)["d_range"] == [50, 100]
    with pytest.raises(InvalidArgument) as err:
        res.grinding_groove(30, b1=1.0)
    assert 3.0 in err.value.candidates
    with pytest.raises(InvalidArgument):
        res.grinding_groove(0)


def test_grinding_groove_standard_rules():
    for d in (5, 30, 80, 200):
        for o in res.grinding_groove(d)["options"]:
            assert o["r"] <= 3 * o["h"]  # note 2 under Table 1: r <= 3h
            assert o["b1"] <= o["b2"]


# --------------------------------- GB/T 1182-2018 / 17851-2010 / 17852-2018 (card A4)

ROW_IDS = [
    "form.straightness",
    "form.flatness",
    "form.circularity",
    "form.cylindricity",
    "form.profile_line",
    "form.profile_surface",
    "orientation.parallelism",
    "orientation.perpendicularity",
    "orientation.angularity",
    "orientation.profile_line",
    "orientation.profile_surface",
    "location.position",
    "location.concentricity",
    "location.coaxiality",
    "location.symmetry",
    "location.profile_line",
    "location.profile_surface",
    "run-out.circular_runout",
    "run-out.total_runout",
]


def test_gtol_rows_are_the_19_rows_of_gbt_1182_table_1():
    from linercad.pmi import CHARS

    rows = res.gtol_rows()
    assert [r["id"] for r in rows] == ROW_IDS
    assert len(rows) == 19
    cats = [r["category"] for r in rows]
    assert (cats.count("form"), cats.count("orientation"), cats.count("location")) == (6, 5, 6)
    assert cats.count("run-out") == 2
    for row in rows:
        assert row["char"] in CHARS, row["id"]
        assert row["zh"] and isinstance(row["zh"], str)
        assert row["clause"] and "17." in row["clause"], row["id"]
        assert row["targets"] and row["zone_shapes"] and row["modifiers"], row["id"]
        assert row["datum"] in ("no", "yes", "optional"), row["id"]


def test_gtol_query_aggregates_the_rows_of_a_characteristic():
    prof = res.gtol("profile_line")
    assert prof["char"] == "profile_line" and prof["zh"] == "线轮廓度"
    assert prof["categories"] == ["form", "orientation", "location"]
    assert prof["datum"] == "optional" and len(prof["rows"]) == 3
    assert "17.6" in prof["clauses"] and "17.7" in prof["clauses"]
    assert prof["std"] == "GB/T 1182-2018" and prof["verified"] is False
    assert len(prof["rows"][0]["zone_shapes"]) >= 1


def test_gtol_datum_rules_match_the_existing_pmi_characters():
    from linercad.pmi import CHARS

    for char, rule in CHARS.items():
        assert res.gtol(char)["datum"] == rule, char


def test_gtol_zone_shapes_and_targets():
    straightness = res.gtol("straightness")
    assert straightness["targets"] == ["line"]
    assert {"two_parallel_lines", "cylinder"} <= set(straightness["zone_shapes"])
    total = res.gtol("total_runout")
    assert total["targets"] == ["surface"]
    assert {"two_coaxial_cylinders", "two_parallel_planes"} <= set(total["zone_shapes"])
    concentric = res.gtol("concentricity")
    assert set(concentric["targets"]) == {"derived_point", "derived_line"}
    position = res.gtol("position")
    assert set(position["targets"]) == {"point", "line", "surface"}
    assert position["datum"] == "optional"
    assert "two_envelope_surfaces" in res.gtol("profile_surface")["zone_shapes"]


def test_gtol_modifiers_separate_unconditional_from_conditional():
    # CZ / SZ / UF apply to any characteristic; UZ / OZ / VA / >< / ACS are gated by conditions
    for char in ("straightness", "profile_line", "position", "total_runout"):
        assert set(res.gtol(char)["modifiers"]) == {"CZ", "SZ", "UF"}
    conditions = {(c["symbol"], c["when"]) for c in res.gtol("straightness")["modifier_conditions"]}
    assert ("UZ", "integral") in conditions and ("ACS", "derived_line") in conditions
    profile = {(c["symbol"], c["when"]) for c in res.gtol("profile_line")["modifier_conditions"]}
    assert {("OZ", "profile"), ("VA", "profile_angle"), ("><", "direction_only")} <= profile
    position = {(c["symbol"], c["when"]) for c in res.gtol("position")["modifier_conditions"]}
    assert {("UZ", "integral_plane"), ("ACS", "derived_line"), ("><", "direction_only")} <= position
    symmetry = {(c["symbol"], c["when"]) for c in res.gtol("symmetry")["modifier_conditions"]}
    assert ("ACS", "nominal_line_point_set") in symmetry
    assert res.gtol("total_runout")["modifier_conditions"] == []
    for char in ("straightness", "profile_line", "position", "concentricity"):
        assert all(c["clause"] for c in res.gtol(char)["modifier_conditions"])


def test_gtol_parameters_are_not_modifiers():
    # P / V / T / Q are parameters (8.2.3.3.2), not frame modifiers
    params = res.gtol("profile_line")["parameters"]
    assert set(params) == {"P", "V", "T", "Q"}
    assert "P" not in res.gtol("profile_line")["modifiers"]
    assert "T" not in {c["symbol"] for c in res.gtol("profile_line")["modifier_conditions"]}


def test_gtol_target_natures_distinguish_integral_and_derived():
    assert res.gtol("total_runout")["target_natures"] == ["integral"]
    assert res.gtol("circularity")["target_natures"] == ["integral"]
    assert res.gtol("concentricity")["target_natures"] == ["derived"]
    position = res.gtol("position")
    assert position["target_natures"] == ["integral", "derived"]
    assert all("target_natures" in row for row in res.gtol_rows())


def test_gtol_modifiers_unverified_are_marked():
    # the symbols of the cross-referenced standards are not "not allowed" but "not extracted"
    for row in res.gtol_rows():
        assert row["modifiers_unverified"] == ["M", "L", "R", "F"]
    runout = res.gtol("total_runout")
    assert runout["modifiers_unverified"] == ["M", "L", "R", "F"]
    assert runout["rows"][0]["modifiers_unverified"] == ["M", "L", "R", "F"]
    assert "M" not in runout["modifiers"] and "F" not in runout["modifiers"]


def test_datum_meta_records_the_gbt_1182_check():
    import tomllib
    from importlib import resources

    data = tomllib.loads(
        (resources.files("linercad.res") / "datum.toml").read_text(encoding="utf-8")
    )
    meta = data["meta"]
    assert meta["checked"] == "2026-11-21"
    assert "GB/T 1182-2018" in meta["stds"] and "GB/T 17851-2010" in meta["stds"]
    assert "1182" in meta["conclusion"] and "8.2.4" in meta["conclusion"]
    assert "6.3.3" in meta["conclusion"] and "verified" in meta["conclusion"]
    assert "6.2" in meta["unread"]
    assert data["GB"]["verified"] is False and data["ISO"]["verified"] is False


def test_gtol_query_results_are_copies():
    first = res.gtol("straightness")
    first["modifier_conditions"][0]["when"] = "bogus"
    first["rows"][0]["targets"].append("bogus")
    again = res.gtol("straightness")
    assert again["modifier_conditions"][0]["when"] != "bogus"
    assert "bogus" not in again["rows"][0]["targets"]


def test_gtol_unknown_characteristic_gives_candidates():
    with pytest.raises(InvalidArgument) as err:
        res.gtol("runout")
    assert "circular_runout" in err.value.candidates
    assert (
        res.gtol("concentricity")["rows"][0]["targets"]
        != res.gtol("position")["rows"][0]["targets"]
    )


def test_gtol_rows_are_copies():
    rows = res.gtol_rows()
    rows[0]["targets"].append("bogus")
    rows[0]["category"] = "bogus"
    rows[0]["modifiers_unverified"].append("bogus")
    rows[0]["modifier_conditions"].append({"symbol": "XX", "when": "integral", "clause": "x"})
    rows[0]["modifier_conditions"][0]["when"] = "bogus"
    again = res.gtol_rows()
    assert "bogus" not in again[0]["targets"] and again[0]["category"] != "bogus"
    assert "bogus" not in again[0]["modifiers_unverified"]
    assert all(c["when"] != "bogus" for c in again[0]["modifier_conditions"])


def test_datum_letters_are_checked_against_gbt_1182_and_17851():
    gb = res.datum_excluded("GB")
    assert gb["clause"] == "6.2"
    assert "1182" in gb["source"] and "8.2.4" in gb["source"]
    iso = res.datum_excluded("ISO")
    assert iso["letters"] == gb["letters"] == ["I", "O", "Q", "X"]


def test_gtol_clause_draft_is_in_the_evidence_folder():
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "milestones"
        / "v0.1.1"
        / "evidence"
        / "gtol-clauses.md"
    )
    text = path.read_text(encoding="utf-8")
    for std in ("GB/T 1182-2018", "GB/T 17851-2010", "GB/T 17852-2018"):
        assert std in text
