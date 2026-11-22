"""E5 (v0.1.1): D.place / A.place placement metrics.

Every rule is judged on the laid-out primitives (never on the intent) and reports findings in the
E1 shape: clause / measured / expected / candidates + the number of checks it performed. The
negative fixtures below take a cleanly laid-out drawing and move one primitive at a time, so a rule
that does not look at the geometry cannot pass.

The positive counterpart is the same drawing untouched: every rule must stay silent on it.
"""

from __future__ import annotations

import math

from linercad import Drawing, checks, place
from linercad.assembly import Balloon
from linercad.layout import Circle, Line, Solid, Text, layout

# ---- fixture helpers -----------------------------------------------------------------------------


def _dims():
    """One clean drawing with a horizontal pair (W inside L) and one vertical dimension."""
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 120, 60, name="body")
    f.dim.linear("W", (0, 0), (60, 0), value=60, side="bottom", row=1)
    f.dim.linear("L", (0, 0), (120, 0), value=120, side="bottom", row=2)
    f.dim.linear("H", (120, 0), (120, 60), dir="v", value=60, side="right", row=1)
    layout(d)
    return d


def _el(d, eid):
    return d[eid]


def _lines(e, horizontal=True):
    return [
        p for p in e._prims if isinstance(p, Line) and (abs(p.p[1] - p.q[1]) < 1e-9) == horizontal
    ]


def _dim_line(e):
    """The single line perpendicular to the two parallel extension lines."""
    h, v = _lines(e, True), _lines(e, False)
    if len(h) == 1 and len(v) == 2:
        return h[0]
    if len(v) == 1 and len(h) == 2:
        return v[0]
    raise AssertionError(f"{e.id}: {len(h)} horizontal / {len(v)} vertical lines")


def _ext_lines(e):
    h, v = _lines(e, True), _lines(e, False)
    return v if len(h) == 1 else h


def _texts(e):
    return [p for p in e._prims if isinstance(p, Text)]


def _arrows(e):
    return [p for p in e._prims if isinstance(p, Solid) and p.layer == "dim"]


def _set_line(e, old, p, q):
    e._prims = [
        Line(p, q, old.layer) if (isinstance(x, Line) and x is old) else x for x in e._prims
    ]


def _shift_line(e, old, extend=0.0):
    p, q = old.p, old.q
    if extend:  # stretch the far end by this many mm along the line
        L = math.dist(p, q) or 1.0
        u = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
        q = (q[0] + u[0] * extend, q[1] + u[1] * extend)
    _set_line(e, old, p, q)


def _rules():
    return {fn.__name__: fn for fn in place.RULES}


def _run(d, rule):
    return _rules()[rule](d)


def _assert_finding(f, rule, eid):
    assert f["rule"] == rule
    assert f["id"] == eid
    for key in ("clause", "measured", "expected", "candidates", "std"):
        assert key in f, (rule, key)
    assert isinstance(f["clause"], str) and f["clause"]
    assert isinstance(f["measured"], dict) and f["measured"]
    assert isinstance(f["expected"], dict) and f["expected"]
    assert isinstance(f["candidates"], list)


# ---- registry ------------------------------------------------------------------------------------


def test_every_place_rule_is_registered_and_documented():
    assert place.RULES
    names = {fn.__name__ for fn in place.RULES}
    assert names <= set(checks.RULES)
    for name in names:
        assert checks.RULES[name] == "placement"
        assert name in place.CLAUSES and place.CLAUSES[name]
        assert checks.family(name) in ("D", "A")
    assert {checks.family(n) for n in names} == {"D", "A"}


def test_clean_drawing_passes_every_d_place_rule():
    d = _dims()
    for name, fn in _rules().items():
        findings, opportunities = fn(d)
        assert findings == [], (name, findings)
        assert isinstance(opportunities, int) and opportunities >= 0


def test_place_rules_report_opportunities_in_checks_run():
    d = _dims()
    found = checks.run(d)
    for fn in place.RULES:
        assert fn.__name__ in found.opportunities
        assert isinstance(found.opportunities[fn.__name__], int)


# ---- D.place ------------------------------------------------------------------------------------


def test_dim_lines_must_not_cross():
    d = _dims()
    assert _run(d, "place_dim_cross")[0] == []
    h = _dim_line(_el(d, "D.L"))
    v = _dim_line(_el(d, "D.H"))
    mid = (v.p[1] + v.q[1]) / 2
    _set_line(_el(d, "D.L"), h, (v.p[0] - 20, mid), (v.p[0] + 20, mid))
    findings, opportunities = _run(d, "place_dim_cross")
    assert "D.L" in [f["id"] for f in findings]
    _assert_finding(findings[0], "place_dim_cross", findings[0]["id"])
    assert opportunities >= len(findings)


def test_dim_line_must_not_cross_the_outline():
    d = _dims()
    assert _run(d, "place_dim_outline")[0] == []
    edges = [
        pr
        for e in d._els.values()
        if e.kind == "edge" and e.view == "front"
        for pr in e._prims
        if isinstance(pr, Line)
    ]
    xs = [q[0] for pr in edges for q in (pr.p, pr.q)]
    ys = [q[1] for pr in edges for q in (pr.p, pr.q)]
    old = _dim_line(_el(d, "D.L"))
    y = (min(ys) + max(ys)) / 2
    _set_line(_el(d, "D.L"), old, (min(xs) - 5, y), (max(xs) + 5, y))
    findings, _ = _run(d, "place_dim_outline")
    assert findings and findings[0]["id"] == "D.L"
    _assert_finding(findings[0], "place_dim_outline", "D.L")


def test_parallel_dimension_rows_keep_the_row_pitch():
    d = _dims()
    assert _run(d, "place_row_spacing")[0] == []
    w = _dim_line(_el(d, "D.W"))
    ln = _dim_line(_el(d, "D.L"))
    dy = -0.4 * d.std["dim"]["row_pitch"]
    _set_line(_el(d, "D.L"), ln, (ln.p[0], w.p[1] + dy), (ln.q[0], w.q[1] + dy))
    findings, opportunities = _run(d, "place_row_spacing")
    assert "D.L" in [f["id"] for f in findings]
    _assert_finding(findings[0], "place_row_spacing", findings[0]["id"])
    assert opportunities >= 1


def test_small_dimensions_stay_inside_large_ones():
    d = _dims()
    assert _run(d, "place_nesting")[0] == []
    w_dim = _dim_line(_el(d, "D.W"))
    base_y = max(pt[1] for line in _ext_lines(_el(d, "D.W")) for pt in (line.p, line.q))
    ln = _el(d, "D.L")  # 120, outer row: rebuild its lines one row closer to the outline
    dim = _dim_line(ln)
    left, right = sorted((dim.p[0], dim.q[0]))
    level = w_dim.p[1] + d.std["dim"]["row_pitch"]
    ln._prims = [p for p in ln._prims if not isinstance(p, Line)] + [
        Line((left, base_y), (left, level - 2), "dim"),
        Line((right, base_y), (right, level - 2), "dim"),
        Line((left, level), (right, level), "dim"),
    ]
    findings, _ = _run(d, "place_nesting")
    assert findings and findings[0]["id"] == "D.L"  # 120 is now the inner (nearer) dimension


def test_extension_lines_stop_at_the_standard_beyond():
    d = _dims()
    assert _run(d, "place_ext_line")[0] == []
    ext = max(_ext_lines(_el(d, "D.L")), key=lambda p: math.dist(p.p, p.q))
    _shift_line(_el(d, "D.L"), ext, extend=6.0)
    findings, _ = _run(d, "place_ext_line")
    assert findings and findings[0]["id"] == "D.L"
    _assert_finding(findings[0], "place_ext_line", "D.L")


def test_dimension_text_keeps_the_reading_direction():
    d = _dims()
    assert _run(d, "place_text_direction")[0] == []
    e = _el(d, "D.H")
    bad = [
        Text(p.text, p.at, p.height, 180.0 if abs(p.rot - 90) < 1e-6 else p.rot, p.layer, p.box)
        for p in e._prims
        if isinstance(p, Text)
    ]
    e._prims = [p for p in e._prims if not isinstance(p, Text)] + bad
    findings, _ = _run(d, "place_text_direction")
    assert findings and findings[0]["id"] == "D.H"
    _assert_finding(findings[0], "place_text_direction", "D.H")


def test_dimension_text_must_not_overlap_other_primitives():
    d = _dims()
    assert _run(d, "place_text_overlap")[0] == []
    other = _texts(_el(d, "D.H"))[0]
    e = _el(d, "D.W")
    moved = [
        Text(p.text, other.at, p.height, p.rot, p.layer, other.box)
        for p in e._prims
        if isinstance(p, Text)
    ]
    e._prims = [p for p in e._prims if not isinstance(p, Text)] + moved
    findings, _ = _run(d, "place_text_overlap")
    assert "D.W" in [f["id"] for f in findings]
    _assert_finding(findings[0], "place_text_overlap", findings[0]["id"])


def test_all_dimension_arrows_use_the_same_size():
    d = _dims()
    assert _run(d, "place_arrow")[0] == []
    e = _el(d, "D.W")
    a = _arrows(e)[0]
    cx = sum(p[0] for p in a.pts) / len(a.pts)
    cy = sum(p[1] for p in a.pts) / len(a.pts)
    e._prims = [
        Solid(tuple((cx + (x - cx) * 2, cy + (y - cy) * 2) for x, y in a.pts), a.layer)
        if (isinstance(p, Solid) and p is a)
        else p
        for p in e._prims
    ]
    findings, _ = _run(d, "place_arrow")
    assert findings and findings[0]["id"] == "D.W"
    _assert_finding(findings[0], "place_arrow", "D.W")


# ---- A.place (balloons) -------------------------------------------------------------------------


def _balloons():
    """A part drawing with two hand-placed balloons left of the view (clean leaders)."""
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 100, 60, name="body")
    layout(d)
    b = f.bbox
    cx = b[0] - 20.0
    anchors = [(b[0] + 30.0, b[1] + 20.0), (b[0] + 50.0, b[1] + 40.0)]
    circles_y = [b[1] + 20.0, b[1] + 40.0]
    for k in range(2):
        anchor = anchors[k]
        el = Balloon(
            d,
            f"B.b{k}",
            {"view": "front", "component": f"A.b{k}", "anchor": list(anchor)},
            refs=["V.front"],
        )
        d._add(el)
        cy = circles_y[k]
        q = (cx + 4.5, cy)
        el._prims = [
            Circle((cx, cy), 4.5, "thin"),
            Line(anchor, q, "thin"),
            Solid(
                (
                    (anchor[0] - 0.7, anchor[1]),
                    (anchor[0], anchor[1] + 0.7),
                    (anchor[0] + 0.7, anchor[1]),
                ),
                "thin",
            ),
            Solid(
                (
                    (anchor[0] - 0.7, anchor[1]),
                    (anchor[0] + 0.7, anchor[1]),
                    (anchor[0], anchor[1] - 0.7),
                ),
                "thin",
            ),
            Text(str(k + 1), (cx, cy), 5.0, 0, "text", (cx - 2.5, cy - 3.5, cx + 2.5, cy + 3.5)),
        ]
    return d


def _balloon_prims(el):
    leader = [p for p in el._prims if isinstance(p, Line)][0]
    circle = [p for p in el._prims if isinstance(p, Circle)][0]
    return leader, circle


def test_balloon_leaders_must_not_cross():
    d = _balloons()
    assert _run(d, "place_balloon_cross")[0] == []
    a, b = _el(d, "B.b0"), _el(d, "B.b1")
    la, lb = _balloon_prims(a)[0], _balloon_prims(b)[0]
    ca, cb = _balloon_prims(a)[1], _balloon_prims(b)[1]
    # explicit X: each leader leaves the other balloon's side and crosses its neighbour
    _set_line(a, la, (ca.c[0] + 30, ca.c[1]), (ca.c[0], cb.c[1]))
    _set_line(b, lb, (cb.c[0] + 30, cb.c[1]), (cb.c[0], ca.c[1]))
    findings, _ = _run(d, "place_balloon_cross")
    assert findings
    _assert_finding(findings[0], "place_balloon_cross", findings[0]["id"])


def test_balloons_on_one_side_stay_aligned():
    d = _balloons()
    assert _run(d, "place_balloon_align")[0] == []
    el = _el(d, "B.b1")
    leader, circle = _balloon_prims(el)
    shifted = Circle((circle.c[0] + 6.0, circle.c[1]), circle.r, circle.layer)
    el._prims = [shifted if p is circle else p for p in el._prims]
    findings, checks = _run(d, "place_balloon_align")
    assert len(findings) == 1 and checks == 1  # one check per view side, one finding for the group
    f = findings[0]
    _assert_finding(f, "place_balloon_align", f["id"])
    assert set(f["measured"]["balloons"]) == {"B.b0", "B.b1"}
    assert f["measured"]["spread"] > 0.5


def test_balloons_keep_a_minimum_spacing():
    d = _balloons()
    assert _run(d, "place_balloon_spacing")[0] == []
    el = _el(d, "B.b1")
    leader, circle = _balloon_prims(el)
    other = _balloon_prims(_el(d, "B.b0"))[1]
    close = Circle((circle.c[0], other.c[1] + circle.r + 0.2), circle.r, circle.layer)
    el._prims = [close if p is circle else p for p in el._prims]
    findings, _ = _run(d, "place_balloon_spacing")
    assert findings and findings[0]["id"] == "B.b1"
    _assert_finding(findings[0], "place_balloon_spacing", "B.b1")


def test_placement_tolerances_come_from_the_std_profile():
    # the profile (GB, or an enterprise overlay) owns the numeric conventions
    d = _balloons()
    assert _run(d, "place_balloon_spacing")[0] == []
    d.std["placement"]["balloon_clearance"] = 50.0
    findings, _ = _run(d, "place_balloon_spacing")
    assert findings  # the clean pair now violates the overridden clearance
    d2 = _dims()
    w = _dim_line(_el(d2, "D.W"))
    ln = _dim_line(_el(d2, "D.L"))
    dy = -(d2.std["dim"]["row_pitch"] - 1.0)  # 6 mm between the rows
    _set_line(_el(d2, "D.L"), ln, (ln.p[0], w.p[1] + dy), (ln.q[0], w.q[1] + dy))
    assert _run(d2, "place_row_spacing")[0]  # the default 0.05 slack rejects 6 mm
    d2.std["placement"]["row_tol"] = 5.0  # a 5 mm slack accepts it (the profile value decides)
    assert _run(d2, "place_row_spacing")[0] == []


def test_dimension_text_may_not_sit_on_its_own_primitives():
    d = _dims()
    assert _run(d, "place_text_overlap")[0] == []
    e = _el(d, "D.W")
    line = _dim_line(e)
    moved = [
        Text(
            p.text,
            ((line.p[0] + line.q[0]) / 2, line.p[1]),
            p.height,
            p.rot,
            p.layer,
            (
                (line.p[0] + line.q[0]) / 2 - 2,
                line.p[1] - 1.5,
                (line.p[0] + line.q[0]) / 2 + 2,
                line.p[1] + 1.5,
            ),
        )
        for p in e._prims
        if isinstance(p, Text)
    ]
    e._prims = [p for p in e._prims if not isinstance(p, Text)] + moved
    findings, _ = _run(d, "place_text_overlap")
    assert "D.W" in [f["id"] for f in findings]


def _three_rows():
    """Three parallel dimensions in one row stack: A (10 mm out), B (12, disjoint span),
    C (15). A and C overlap but are not neighbours in the distance order."""
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 300, 60, name="body")
    f.dim.linear("A", (0, 0), (40, 0), value=40, side="bottom", row=1)
    f.dim.linear("B", (200, 0), (260, 0), value=60, side="bottom", row=1, offset=2)
    f.dim.linear("C", (0, 0), (120, 0), value=120, side="bottom", row=1, offset=5)
    layout(d)
    return d


def test_row_spacing_checks_all_overlapping_pairs():
    d = _three_rows()
    findings, _ = _run(d, "place_row_spacing")
    assert findings  # A and C overlap and are only 5 mm apart, with B between them
    ids = {f["id"] for f in findings}
    assert ids & {"D.A", "D.C"}


def test_nesting_checks_all_overlapping_pairs():
    d = _three_rows()
    assert _run(d, "place_nesting")[0] == []  # A (40) inside C (120) is the correct order
    # make the inner one the long one while C stays between A and B in the distance order:
    # widen A's extension lines and narrow C's, keeping the two spans overlapping
    bbox = place._view_bbox(d, "front")
    left = bbox[0]

    def set_span(eid, x0, x1):
        ext = _ext_lines(_el(d, eid))
        for k, line in enumerate(ext):
            _set_line(
                _el(d, eid),
                line,
                (x0 if k == 0 else x1, line.p[1]),
                (x0 if k == 0 else x1, line.q[1]),
            )

    set_span("D.A", left, left + 120)
    set_span("D.C", left, left + 40)
    findings, _ = _run(d, "place_nesting")
    assert findings and findings[0]["id"] == "D.A"  # the non-adjacent A / C pair is judged


# ---- round 2 review: generality regressions ------------------------------------------------


def test_inside_dimension_is_classified_and_judged():
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 120, 60, name="body")
    f.dim.linear("inside", (20, 20), (100, 20), value=80, side="inside")
    layout(d)
    e = _el(d, "D.inside")
    info = place._frame_dim(e)
    assert info is not None and info["dir"] == "h" and info["ext"] == []
    assert _run(d, "place_text_direction")[0] == []
    bad = [
        Text(p.text, p.at, p.height, 90.0, p.layer, p.box) for p in e._prims if isinstance(p, Text)
    ]
    e._prims = [p for p in e._prims if not isinstance(p, Text)] + bad
    findings, _ = _run(d, "place_text_direction")
    assert "D.inside" in [f["id"] for f in findings]


def test_leader_with_collinear_shoulder_is_classified():
    d = Drawing(sheet="A3")
    v = d.view("front")
    c = v.circle((0, 0), 30, name="outer")
    v.dim.dia("D", circle=c, at=0)  # shoulder collinear with the diameter line
    layout(d)
    info = place._leader_dim(_el(d, "D.D"))
    assert info is not None and len(info["lines"]) == 2
    _, opportunities = _run(d, "place_dim_cross")
    assert opportunities == 1  # the leader takes part in the crossing check


def test_aligned_dimensions_take_part_in_the_row_metrics():
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 100, 60, name="body")
    f.dim.aligned("A", (0, 0), (100, 60))
    f.dim.aligned("B", (0, 10), (100, 70))
    layout(d)
    for eid in ("D.A", "D.B"):
        e = _el(d, eid)
        info = place._frame_dim(e)
        assert info is not None and info["dir"] == "d"
        assert place._frame_rows(info) is not None
    groups = place._side_groups(d)
    assert any(key[1] not in (0.0, 90.0) for key in groups)  # diagonal frames join the row groups


def test_extension_line_that_does_not_reach_the_contour():
    d = _dims()
    ext = _ext_lines(_el(d, "D.L"))[0]
    _set_line(
        _el(d, "D.L"),
        ext,
        (ext.p[0], ext.p[1] - 30.0),
        (ext.q[0], ext.q[1] - 30.0),
    )
    findings, _ = _run(d, "place_ext_line")
    assert findings and findings[0]["id"] == "D.L"


def test_dimension_text_over_section_lining():
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 120, 60, name="body")
    f.hatch("h", loops=["F.front.body"])
    f.dim.linear("inside", (20, 20), (100, 20), value=80, side="inside")
    layout(d)
    findings, _ = _run(d, "place_text_overlap")
    assert "D.inside" in [f["id"] for f in findings]


def test_balloon_alignment_groups_per_view():
    d = Drawing(sheet="A3")
    front, left = d.view("front"), d.view("left")
    front.rect((0, 0), 100, 60, name="b1")
    left.rect((0, 0), 60, 40, name="b2")
    layout(d)
    bf, bl = front.bbox, left.bbox
    injected = []
    for k, (view, circle_c, anchor) in enumerate(
        [
            ("front", (bf[0] - 20.0, bf[1] + 20.0), (bf[0] + 30.0, bf[1] + 20.0)),
            ("front", (bf[0] - 20.0, bf[1] + 40.0), (bf[0] + 50.0, bf[1] + 40.0)),
            ("left", (bl[0] - 20.0, bl[1] + 15.0), (bl[0] + 20.0, bl[1] + 15.0)),
        ]
    ):
        el = Balloon(
            d,
            f"B.b{k}",
            {"view": view, "component": f"A.b{k}", "anchor": list(anchor)},
            refs=[f"V.{view}"],
        )
        d._add(el)
        q = (circle_c[0] + 4.5, circle_c[1])
        el._prims = [
            Circle(circle_c, 4.5, "thin"),
            Line(anchor, q, "thin"),
            Text(
                str(k + 1),
                circle_c,
                5.0,
                0,
                "text",
                (circle_c[0] - 2.5, circle_c[1] - 3.5, circle_c[0] + 2.5, circle_c[1] + 3.5),
            ),
        ]
        injected.append(el)
    # the two front balloons are a column, the single left one is its own group: no misalignment
    assert _run(d, "place_balloon_align")[0] == []


def test_profile_values_inherit_and_override():
    from linercad.std import load_std

    gb = load_std("GB")["placement"]
    iso = load_std("ISO")["placement"]
    for key in ("balloon_clearance", "balloon_align_tol", "ext_gap_max", "row_tol"):
        assert key in gb
        assert iso[key] == gb[key]  # ISO inherits the GB conventions
    assert load_std("GB", [{"placement": {"row_tol": 1.0}}])["placement"]["row_tol"] == 1.0
    # a 0.2 mm offset is inside the default tolerance and outside an overridden one
    d = _balloons()
    el = _el(d, "B.b1")
    _leader, circle = _balloon_prims(el)
    shifted = Circle((circle.c[0] + 0.2, circle.c[1]), circle.r, circle.layer)
    el._prims = [shifted if p is circle else p for p in el._prims]
    assert _run(d, "place_balloon_align")[0] == []
    d.std["placement"]["balloon_align_tol"] = 0.1
    assert _run(d, "place_balloon_align")[0]


# ---- round 3 review: rows use the dimension-line positions, own texts, hatch parity, global
# balloon spacing, cross-view outlines, collinear leaders, aligned results ---------------------


def test_row_spacing_uses_the_dimension_line_positions():
    d = _dims()
    w = _dim_line(_el(d, "D.W"))
    ln = _dim_line(_el(d, "D.L"))
    # move only L's dimension line: 6 mm from W's line, whatever the extension lines record
    _set_line(_el(d, "D.L"), ln, (ln.p[0], w.p[1] - 6.0), (ln.q[0], w.q[1] - 6.0))
    findings, _ = _run(d, "place_row_spacing")
    assert "D.L" in [f["id"] for f in findings]


def test_own_tolerance_texts_must_not_overlap_each_other():
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 120, 60, name="body")
    f.dim.linear("t", (0, 0), (60, 0), value=60, side="bottom", tol=("+0.1", "-0.1"))
    layout(d)
    e = _el(d, "D.t")
    texts = [p for p in e._prims if isinstance(p, Text)]
    assert len(texts) >= 2  # the number plus the deviation text
    first, second = texts[0], texts[1]
    moved = Text(
        second.text,
        (first.at[0] + 0.3, first.at[1]),
        second.height,
        second.rot,
        second.layer,
        (first.box[0] + 0.3, first.box[1], first.box[2] + 0.3, first.box[3]),
    )
    e._prims = [moved if p is second else p for p in e._prims]
    findings, _ = _run(d, "place_text_overlap")
    assert "D.t" in [f["id"] for f in findings]


def _circle_centre(d, view="front"):
    for e in d._els.values():
        if e.kind == "edge" and e.view == view:
            for p in e._prims:
                if isinstance(p, Circle):
                    return p.c
    raise AssertionError("no circle")


def test_hatch_even_odd_region():
    d = Drawing(sheet="A3")
    f = d.view("front")
    body = f.rect((0, 0), 120, 60, name="body")
    hole = f.circle((60, 30), 12, name="hole")
    f.hatch("h", loops=[body, hole])
    f.dim.linear("inside", (10, 30), (110, 30), value=100, side="inside")
    layout(d)
    e = _el(d, "D.inside")
    centre = _circle_centre(d)
    text = [p for p in e._prims if isinstance(p, Text)][0]

    def moved_text(at):
        box = (at[0] - 2, at[1] - 1.5, at[0] + 2, at[1] + 1.5)
        return Text(text.text, at, text.height, text.rot, text.layer, box)

    def hatch_hits():
        findings, _ = _run(d, "place_text_overlap")
        return [f for f in findings if "H.front.h" in f["measured"].get("with", [])]

    e._prims = [moved_text(centre) if p is text else p for p in e._prims]
    assert hatch_hits() == []  # the hole centre is empty in the even-odd region
    text = next(p for p in e._prims if isinstance(p, Text))
    e._prims = [moved_text((centre[0], centre[1] + 22.0)) if p is text else p for p in e._prims]
    assert hatch_hits()  # between the hole and the outline the lining is drawn


def test_balloon_spacing_is_checked_across_views():
    d = Drawing(sheet="A3")
    front, left = d.view("front"), d.view("left")
    front.rect((0, 0), 100, 60, name="b1")
    left.rect((0, 0), 60, 40, name="b2")
    layout(d)
    bf = front.bbox
    shared = (bf[0] - 20.0, bf[1] + 20.0)
    for k, (view, circle_c, anchor) in enumerate(
        [
            ("front", shared, (bf[0] + 30.0, bf[1] + 20.0)),
            ("left", shared, (left.bbox[0] + 20.0, left.bbox[1] + 15.0)),
        ]
    ):
        el = Balloon(
            d,
            f"B.b{k}",
            {"view": view, "component": f"A.b{k}", "anchor": list(anchor)},
            refs=[f"V.{view}"],
        )
        d._add(el)
        el._prims = [
            Circle(circle_c, 4.5, "thin"),
            Line(anchor, (circle_c[0] + 4.5, circle_c[1]), "thin"),
            Text(
                str(k + 1),
                circle_c,
                5.0,
                0,
                "text",
                (circle_c[0] - 2.5, circle_c[1] - 3.5, circle_c[0] + 2.5, circle_c[1] + 3.5),
            ),
        ]
    findings, _ = _run(d, "place_balloon_spacing")
    assert findings  # the two circles overlap on the sheet even though they belong to two views


def test_dimension_line_crosses_another_views_outline():
    d = Drawing(sheet="A3")
    front, left = d.view("front"), d.view("left")
    front.rect((0, 0), 100, 60, name="b1")
    left.rect((0, 0), 60, 40, name="b2")
    front.dim.linear("L", (0, 0), (100, 0), value=100, side="bottom")
    layout(d)
    lb = left.bbox
    ln = _dim_line(_el(d, "D.L"))
    y = (lb[1] + lb[3]) / 2
    _set_line(_el(d, "D.L"), ln, (lb[0] - 5, y), (lb[2] + 5, y))
    findings, _ = _run(d, "place_dim_outline")
    assert "D.L" in [f["id"] for f in findings]


def test_leader_shoulder_takes_part_in_crossing():
    d = Drawing(sheet="A3")
    v = d.view("front")
    c = v.circle((0, 0), 30, name="outer")
    v.dim.dia("Dd", circle=c, at=0)
    v.dim.linear("X", (40, -40), (40, 40), dir="v", value=80, side="right")
    layout(d)
    shoulder = place._leader_dim(_el(d, "D.Dd"))["lines"][1]
    midx = (shoulder.p[0] + shoulder.q[0]) / 2
    y = shoulder.p[1]
    x = _dim_line(_el(d, "D.X"))
    # pull the second dimension's line across the leader's short shoulder (not the long part)
    _set_line(_el(d, "D.X"), x, (midx, y - 20.0), (midx, y + 20.0))
    findings, _ = _run(d, "place_dim_cross")
    hit = {(f["id"], f["measured"]["with"]) for f in findings}
    assert ("D.Dd", "D.X") in hit or ("D.X", "D.Dd") in hit


def test_aligned_dimensions_row_spacing_is_judged():
    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 100, 60, name="body")
    f.dim.aligned("A", (0, 0), (100, 60))
    f.dim.aligned("B", (0, 10), (100, 70))
    layout(d)
    assert _run(d, "place_row_spacing")[0] == []
    a = place._frame_dim(_el(d, "D.A"))["dim"]
    b = place._frame_dim(_el(d, "D.B"))["dim"]
    u = place._unit(a.p, a.q)
    n = (-u[1], u[0])
    dx = b.p[0] - a.p[0]
    dist = dx * n[0] + (b.p[1] - a.p[1]) * n[1]
    shift = 1.0 - abs(dist)  # bring B one millimetre from A
    sign = 1.0 if dist >= 0 else -1.0
    ddx, ddy = n[0] * shift * sign, n[1] * shift * sign
    e = _el(d, "D.B")
    e._prims = [
        Line((p.p[0] + ddx, p.p[1] + ddy), (p.q[0] + ddx, p.q[1] + ddy), p.layer)
        if isinstance(p, Line)
        else p
        for p in e._prims
    ]
    findings, _ = _run(d, "place_row_spacing")
    assert "D.B" in [f["id"] for f in findings]
