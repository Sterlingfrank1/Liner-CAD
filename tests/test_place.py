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
    w = _dim_line(_el(d, "D.W"))
    ln = _dim_line(_el(d, "D.L"))
    _set_line(_el(d, "D.W"), w, (w.p[0], ln.p[1]), (w.q[0], ln.q[1]))
    _set_line(_el(d, "D.L"), ln, (ln.p[0], w.p[1]), (ln.q[0], w.q[1]))
    findings, _ = _run(d, "place_nesting")
    assert findings
    _assert_finding(findings[0], "place_nesting", findings[0]["id"])


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
    findings, _ = _run(d, "place_balloon_align")
    hit = next(f for f in findings if f["id"] == "B.b1")
    _assert_finding(hit, "place_balloon_align", "B.b1")


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
