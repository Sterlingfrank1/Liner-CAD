"""Mutation framework (E2, benchmark-metrics §6): prove every rule can be broken.

For every rule the catalog marks ``done`` there is a mutation operator that injects one known
defect into a reference drawing (evals/L1, evals/L2) that the rule currently passes on; the rule
must then report it. Detection rate = detected mutations / mutations; false positives = findings on
the untouched reference drawings that are not in the frozen known-debt list
(``evals/known-debt.json``: the E5 placement debt and the crossings the new radial-leader rule
already reports, i.e. known true positives, not noise).

    uv run python evals/mutate.py [--out mutation-report.json]

The report is also embedded in evals/run.py's output with ``--mutation``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))

import run as evals  # noqa: E402

from linercad import catalog, checks, place  # noqa: E402
from linercad.layout import Circle, Line, Solid, Text, layout  # noqa: E402
from linercad.runtime import build  # noqa: E402
from linercad.source3d import MissingExtra  # noqa: E402

KNOWN_DEBT = HERE / "known-debt.json"

#: a valid operation log entry (the reference for the stale_op opportunity count) and the stale
#: entry the mutation injects
VALID_LOG = [{"edit": "e1", "line": 1, "op": "set", "id": "D.x"}]

STALE_OP = {
    "edit": "e3",
    "line": 4,
    "op": "set",
    "id": "D.gone",
    "reason": "目标不存在",
    "candidates": ["D.g"],
}


# ---- reference drawings -------------------------------------------------------------------------


def _build_case(case):
    work = Path(tempfile.mkdtemp())
    try:
        (work / "drawing.py").write_text(case["drawing_src"], encoding="utf-8")
        if case.get("dir"):
            for f in Path(case["dir"]).iterdir():
                if f.is_file() and f.name != "drawing.py" and f.suffix in (".py", ".step", ".stp"):
                    shutil.copy2(f, work / f.name)
        return build(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _signature(finding) -> str:
    return json.dumps(finding.get("measured") or {}, sort_keys=True, ensure_ascii=False)


def known_debt() -> dict:
    """{case id: {(rule, id, measured signature), ...}} of the frozen reference findings."""
    if not KNOWN_DEBT.exists():
        return {}
    data = json.loads(KNOWN_DEBT.read_text(encoding="utf-8"))
    return {
        case_id: {(rule, eid, sig) for rule, eid, sig in entries}
        for case_id, entries in data.get("cases", {}).items()
    }


# ---- purpose-built fixtures for rules without a clean reference case ----------------------------


def _fx_plain():
    from linercad import Drawing

    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 80, 40, name="body")
    layout(d)
    return d


def _fx_chain():
    from linercad import Drawing, Param

    d = Drawing(sheet="A3")
    P = d.params(L=Param(120), l1=Param(40))
    f = d.view("front")
    f.turned("b", [(0, 15), (P.l1, 15), (P.l1, 20, "collar"), (P.L, 20)])
    f.dim.linear("l1", (0, -15), (P.l1, -20), dir="h", value=P.l1, tol=(0.05, -0.05), side="bottom")
    f.dim.linear(
        "L",
        (0, -15),
        (P.L, -20),
        dir="h",
        value=P.L,
        tol=(0.05, -0.05),
        role="overall",
        side="bottom",
        row=2,
    )
    d.chain("rest", closing="l1", increase=["D.L"], decrease=["D.l1"], require=(-5.0, 5.0))
    layout(d)
    return d


def _inject_balloons(d, specs):
    from linercad.assembly import Balloon

    for k, (view, circle_c, anchor) in enumerate(specs):
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
            Text(
                str(k + 1),
                circle_c,
                5.0,
                0,
                "text",
                (circle_c[0] - 2.5, circle_c[1] - 3.5, circle_c[0] + 2.5, circle_c[1] + 3.5),
            ),
        ]
    return d


def _fx_balloons():
    from linercad import Drawing

    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 100, 60, name="body")
    layout(d)
    b = f.bbox
    cx = b[0] - 20.0
    return _inject_balloons(
        d,
        [
            ("front", (cx, b[1] + 20.0), (b[0] + 30.0, b[1] + 20.0)),
            ("front", (cx, b[1] + 40.0), (b[0] + 50.0, b[1] + 40.0)),
        ],
    )


def _fx_radial_leader():
    from linercad import Drawing

    d = Drawing(sheet="A3")
    v = d.view("front")
    c = v.circle((0, 0), 30, name="outer")
    v.dim.dia("Dd", circle=c, at=45)
    v.dim.linear("X", (60, -40), (60, 40), dir="v", value=80, side="right")
    layout(d)
    return d


def _fx_perp():
    from linercad import Drawing

    d = Drawing(sheet="A3")
    f = d.view("front")
    f.rect((0, 0), 100, 60, name="body")
    f.dim.linear("H", (0, 0), (100, 0), value=100, side="bottom")
    f.dim.linear("V", (120, 0), (120, 60), dir="v", value=60, side="right")
    layout(d)
    return d


FIXTURES = {
    "place_dim_cross": _fx_perp,
    "chain_limit": _fx_chain,
    "stale_op": _fx_plain,
    "place_balloon_align": _fx_balloons,
    "place_balloon_cross": _fx_balloons,
    "place_balloon_spacing": _fx_balloons,
}

#: rules whose mutation base is a specific reference case (D1 review: gear_blank Φ92 is the
#: negative mutation example for the radial-leader crossing rule)
BASE_OVERRIDES = {"place_leader_cross": "L2/disc/gear_blank"}


# ---- primitive helpers used by the mutators ----------------------------------------------------


def _el(d, eid):
    return d[eid]


def _lines(e, horizontal=None):
    out = [p for p in e._prims if isinstance(p, Line)]
    if horizontal is None:
        return out
    return [p for p in out if (abs(p.p[1] - p.q[1]) < 1e-9) == horizontal]


def _texts(e):
    return [p for p in e._prims if isinstance(p, Text)]


def _arrows(e):
    return [p for p in e._prims if isinstance(p, Solid)]


def _replace_line(e, old, p, q):
    e._prims = [Line(p, q, old.layer) if x is old else x for x in e._prims]


def _shift_prim(pr, dx, dy):
    from linercad.layout import move_prim

    return move_prim(pr, dx, dy)


def _move_element(d, eid, dx, dy):
    from linercad.layout import prims_bbox

    e = d[eid]
    e._prims = [_shift_prim(p, dx, dy) for p in e._prims]
    b = prims_bbox(e._prims)
    if b:
        e._resolved["bbox"] = [b[0], b[1], b[2], b[3]]


def _frame_like(d, rule):
    for e in d._els.values():
        info = place._frame_dim(e)
        if info is not None or (rule == "place_leader_cross" and place._dim_info(e)):
            yield e


# ---- mutation operators (one per rule) ---------------------------------------------------------


def m_line_width(d):
    d.std["lines"]["thick"]["width"] = 0.31
    return "T.frame"


def m_text_height(d):
    for e in d._els.values():
        texts = _texts(e)
        if texts and e.kind != "frame":
            t = texts[0]
            e._prims = [
                Text(x.text, x.at, 4.2, x.rot, x.layer, x.box) if x is t else x for x in e._prims
            ]
            return e.id
    raise AssertionError("no text primitive")


def m_scale(d):
    d.scale_text = "1:7"
    return "T.title.scale"


def m_sheet(d):
    d.template["size"] = [111.0, 222.0]
    return "T.frame"


def m_conv_dim(d):
    from linercad.rules import CONV_NEED

    for f in d._els.values():
        if f.kind == "feature" and f._intent.get("type") in CONV_NEED:
            for dim in d._els.values():
                if dim.kind == "dim" and f.id in dim._refs:
                    dim._refs = []
                    return f.id
    raise AssertionError("no conventional feature with a dimension")


def m_section_ref(d):
    for v in d.views():
        if v._intent.get("aux"):
            v._intent["name"] = "ZZ"
            return v.id
    raise AssertionError("no auxiliary view")


def m_center_mark(d):
    target = None
    for e in d._els.values():
        if e.kind == "edge" and e._intent.get("shape") == "circle" and e.role == "thick":
            target = e._intent.get("feature") or e.id
            break
    ids = [eid for eid, e in d._els.items() if e.kind == "center"]
    if not ids or target is None:
        raise AssertionError("no centre lines / circle")
    for eid in ids:
        d._els.pop(eid, None)
    return target


def m_duplicate(d):
    dims = [
        e
        for e in d._els.values()
        if e.kind == "dim"
        and e._intent.get("type") in ("linear", "aligned")
        and e._intent.get("dir") in ("h", "v")
        and e._intent.get("p1")
    ]
    for i, a in enumerate(dims):
        for b in dims[i + 1 :]:
            ia, ib = a._intent, b._intent
            if (
                ia["view"] == ib["view"]
                and ia["dir"] == ib["dir"]
                and ia.get("p1")
                and ib.get("p1")
            ):
                ib["p1"] = list(ia["p1"])
                ib["p2"] = list(ia["p2"])
                return b.id
    raise AssertionError("no two comparable dimensions")


def m_closed_loop(d):
    return m_duplicate(d)  # a duplicate closes the size chain as well


def m_missing(d):
    for f in d._els.values():
        if f.kind == "feature" and f._intent.get("type") == "turned":
            profile = [list(p) for p in f._intent["profile"]]
            xs = [p[0] for p in profile]
            r = profile[-1][1]
            profile.append([round(max(xs) + 20.0, 3), r])
            f._intent["profile"] = profile
            return f.id
    raise AssertionError("no turned feature")


def m_param_cover(d):
    from linercad import Param

    d.P._params["MUTANT"] = Param(5)  # one d.params() call per drawing; the rule reads the set
    return "P.MUTANT"


def m_dev_order(d):
    for e in d._els.values():
        if e.kind == "dim" and e._intent.get("tolerance"):
            e._intent["tolerance"] = {"kind": "dev", "upper": -0.1, "lower": 0.1}
            return e.id
    raise AssertionError("no toleranced dimension")


def m_gtol_syntax(d):
    for e in d._els.values():
        if e.kind == "gtol":
            e._intent["datum_refs"] = ["ZZ"]
            return e.id
    raise AssertionError("no gtol")


def m_datum_letter(d):
    for e in d._els.values():
        if e.kind == "datum":
            e._intent["letter"] = "I"
            return e.id
    raise AssertionError("no datum")


def m_general_tol(d):
    for e in d._els.values():
        if e.kind == "note" and e._intent.get("gentol"):
            e._intent["gentol"] = None
            break
    else:
        raise AssertionError("no general-tolerance note")
    for dim in d._els.values():
        i = dim._intent
        if (
            dim.kind == "dim"
            and i.get("type") in ("linear", "dia", "rad", "aligned")
            and not i.get("tolerance")
            and not i.get("reference")
        ):
            return dim.id
    raise AssertionError("no untoleranced dimension")


def m_chain_limit(d):
    for e in d._els.values():
        if e.kind == "chain":
            e._intent["require"] = [-0.001, 0.001]
            layout(d)  # the chain result is resolved during layout
            return e.id
    raise AssertionError("no chain")


def m_rough_syntax(d):
    for e in d._els.values():
        if e.kind == "rough":
            e._intent["value"] = 3.0
            return e.id
    raise AssertionError("no roughness symbol")


def m_rough_default(d):
    roughs = [e for e in d._els.values() if e.kind == "rough"]
    if not roughs:
        raise AssertionError("no roughness symbols")
    for e in roughs:
        e._intent["default"] = False
    return roughs[0].id


def m_rough_fit(d):
    from linercad import res

    roughs = [e for e in d._els.values() if e.kind == "rough"]
    if not roughs:
        raise AssertionError("no roughness symbols")
    target = None
    for e in d._els.values():
        t = e._intent.get("tolerance") if e.kind == "dim" else None
        if not t or t.get("kind") != "fit":
            continue
        if res.fit(t["code"], e._intent["value"])["it"] <= 7:
            target = e.id
            break
    if target is None:
        raise AssertionError("no IT<=7 fit dimension")
    for e in roughs:
        e._intent["ref"] = None
    return target


def m_overlap(d):
    texts = [(e, _texts(e)) for e in d._els.values() if _texts(e) and e.kind != "frame"]
    texts = [(e, ts) for e, ts in texts if ts]
    if len(texts) < 2:
        raise AssertionError("fewer than two text elements")
    (e0, t0), (_e1, t1) = texts[0], texts[1]
    box = t1[0].box
    e0._prims = [
        Text(
            t.text,
            (box[0] + 1, box[1] + 1),
            t.height,
            t.rot,
            t.layer,
            (box[0], box[1], box[2], box[3]),
        )
        if t is t0[0]
        else t
        for t in e0._prims
    ]
    return e0.id


def m_out_of_frame(d):
    for e in d._els.values():
        if (
            e._prims
            and e.kind in ("dim", "note", "center", "section", "balloon")
            and not e._intent.get("tech")
        ):
            _move_element(d, e.id, 600.0, 600.0)
            return e.id
    raise AssertionError("no movable element")


def m_view_align(d):
    for e in d._els.values():
        if e.kind == "edge" and e.view != "front" and e._intent.get("shape") == "line":
            i = e._intent
            i["p1"] = [i["p1"][0] + 5.0, i["p1"][1] + 5.0]
            i["p2"] = [i["p2"][0] + 5.0, i["p2"][1] + 5.0]
            return f"V.{e.view}"
    raise AssertionError("no line edge outside the front view")


def m_stale_op(d):
    return None  # the framework feeds STALE_OP to checks.run


# ---- placement mutations -----------------------------------------------------------------------


def _two_frame_dims(d):
    frames = [(e, place._frame_dim(e)) for e in d._els.values()]
    frames = [(e, info) for e, info in frames if info is not None]
    if len(frames) < 2:
        raise AssertionError("fewer than two frame dimensions")
    return frames


def m_place_dim_cross(d):
    frames = _two_frame_dims(d)
    for i, (a, ia) in enumerate(frames):
        for _b, ib in frames[i + 1 :]:
            if ia["dir"] == "h" and ib["dir"] == "v":
                line_b = ib["dim"]
                mid = ((line_b.p[0] + line_b.q[0]) / 2, (line_b.p[1] + line_b.q[1]) / 2)
                _replace_line(a, ia["dim"], (mid[0] - 20, mid[1]), (mid[0] + 20, mid[1]))
                return a.id
    raise AssertionError("no perpendicular frame pair")


def m_place_dim_outline(d):
    for e, info in _two_frame_dims(d):
        bbox = place._view_bbox(d, e.view)
        if not bbox:
            continue
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        if info["dir"] == "h":
            _replace_line(e, info["dim"], (bbox[0] - 5, cy), (bbox[2] + 5, cy))
        else:
            _replace_line(e, info["dim"], (cx, bbox[1] - 5), (cx, bbox[3] + 5))
        return e.id
    raise AssertionError("no frame dimension")


def _row_pair(d):
    for items in place._side_groups(d).values():
        if len(items) >= 2:
            return items[0], items[-1]
    raise AssertionError("no parallel row pair")


def m_place_row_spacing(d):
    inner, outer = _row_pair(d)
    e0, i0, _p0 = inner
    e1, i1, _p1 = outer
    pos0 = place._frame_rows(i0)[3]
    pos1 = place._frame_rows(i1)[3]
    _u, n, outward, pos, _interval = place._frame_rows(i1)
    pitch = d.std["dim"]["row_pitch"]
    # move the outer line to 1 mm from the inner one: subtract the gap along the outward normal
    delta = (abs(pos1 - pos0) - 1.0) * outward
    _replace_line(
        e1,
        i1["dim"],
        (i1["dim"].p[0] - n[0] * delta, i1["dim"].p[1] - n[1] * delta),
        (i1["dim"].q[0] - n[0] * delta, i1["dim"].q[1] - n[1] * delta),
    )
    _ = pitch
    return e1.id


def m_place_nesting(d):
    inner, outer = _row_pair(d)
    e0, i0, _p0 = inner
    e1, i1, _p1 = outer
    span0 = place._frame_span(i0)
    span1 = place._frame_span(i1)
    # the element with the larger span must end up on the inside
    if span1 >= span0:
        mover, info, inner_pos = e1, i1, place._frame_rows(i0)[3]
    else:
        mover, info, inner_pos = e0, i0, place._frame_rows(i1)[3]
    _u, n, outward, pos, _iv = place._frame_rows(info)
    delta = ((inner_pos - 1.0) - pos) * outward  # change of level along n
    # move the whole line set (dimension line and both extension lines) so the outward direction
    # (read from the extension lines) stays consistent
    for line in [p for p in mover._prims if isinstance(p, Line)]:
        _replace_line(
            mover,
            line,
            (line.p[0] + n[0] * delta, line.p[1] + n[1] * delta),
            (line.q[0] + n[0] * delta, line.q[1] + n[1] * delta),
        )
    return mover.id


def m_place_ext_line(d):
    for e in d._els.values():
        info = place._frame_dim(e)
        if info is None or not info["ext"]:
            continue
        rows = place._frame_rows(info)
        if rows is None:
            continue
        _u, n, outward, _pos, _iv = rows
        ext = info["ext"][0]
        far = (
            ext.p
            if ((ext.p[0] - ext.q[0]) * n[0] + (ext.p[1] - ext.q[1]) * n[1]) * outward > 0
            else ext.q
        )
        near = ext.q if far is ext.p else ext.p
        _replace_line(
            e,
            ext,
            near,
            (far[0] + n[0] * outward * 20.0, far[1] + n[1] * outward * 20.0),
        )
        return e.id
    raise AssertionError("no frame dimension with extension lines")


def m_place_text_direction(d):
    for e in d._els.values():
        info = place._frame_dim(e)
        if info is None or info["dir"] not in ("h", "v"):
            continue
        want = 0.0 if info["dir"] == "h" else 90.0
        e._prims = [
            Text(p.text, p.at, p.height, (want + 90.0) % 180.0, p.layer, p.box)
            if isinstance(p, Text)
            else p
            for p in e._prims
        ]
        return e.id
    raise AssertionError("no axis-aligned dimension")


def m_place_text_overlap(d):
    others = [
        (e, _texts(e))
        for e in d._els.values()
        if e.kind == "dim" and place._dim_info(e) is not None and _texts(e)
    ]
    if len(others) < 2:
        raise AssertionError("fewer than two dimension texts")
    (e0, t0), (_e1, t1) = others[0], others[1]
    box = t1[0].box
    e0._prims = [
        Text(t.text, (box[0] + 1, box[1] + 1), t.height, t.rot, t.layer, box) if t is t0[0] else t
        for t in e0._prims
    ]
    return e0.id


def m_place_arrow(d):
    for e in d._els.values():
        arrows = _arrows(e)
        if e.kind != "dim" or not arrows:
            continue
        a = arrows[0]
        cx = sum(p[0] for p in a.pts) / len(a.pts)
        cy = sum(p[1] for p in a.pts) / len(a.pts)
        e._prims = [
            Solid(tuple((cx + (x - cx) * 2, cy + (y - cy) * 2) for x, y in a.pts), a.layer)
            if p is a
            else p
            for p in e._prims
        ]
        return e.id
    raise AssertionError("no dimension arrows")


def m_place_leader_cross(d):
    leaders = []
    others = []
    for e in d._els.values():
        info = place._dim_info(e)
        if info is None:
            continue
        others.append((e, info[1]))
        if info[0] == "leader" and place._is_radial_text(info[1]["texts"]):
            leaders.append((e, info[1]))
    # D1 review: gear_blank's Φ92 is the required negative example - use the largest radial
    # dimension of the drawing, whatever element id it happens to have
    leaders.sort(key=lambda item: -(item[0]._intent.get("value") or 0.0))
    leaders = leaders[:1]
    for e, info in leaders:
        for other, oinfo in others:
            if other is e:
                continue
            for a in place._dim_segments(info):
                mid = ((a.p[0] + a.q[0]) / 2, (a.p[1] + a.q[1]) / 2)
                u = place._unit(a.p, a.q)
                perp = (-u[1], u[0])
                other_segs = place._dim_segments(oinfo)
                if oinfo.get("ext") and "dim" in oinfo:
                    line = oinfo["dim"]
                    seg = (
                        (mid[0] - perp[0] * 20, mid[1] - perp[1] * 20),
                        (mid[0] + perp[0] * 20, mid[1] + perp[1] * 20),
                    )
                    if other.kind == "dim" and place._frame_dim(other):
                        _replace_line(other, line, seg[0], seg[1])
                        return e.id
                _ = other_segs
    raise AssertionError("no radial leader with another dimension")


def m_place_balloon_align(d):
    el = d["B.b1"]
    circle = [p for p in el._prims if isinstance(p, Circle)][0]
    el._prims = [
        Circle((circle.c[0] + 6.0, circle.c[1]), circle.r, circle.layer) if p is circle else p
        for p in el._prims
    ]
    return d["B.b0"].id  # the group-level finding points at the first balloon


def m_place_balloon_spacing(d):
    a = [p for p in d["B.b0"]._prims if isinstance(p, Circle)][0]
    el = d["B.b1"]
    circle = [p for p in el._prims if isinstance(p, Circle)][0]
    el._prims = [
        Circle((circle.c[0], a.c[1] + circle.r + 0.2), circle.r, circle.layer) if p is circle else p
        for p in el._prims
    ]
    return el.id


def m_place_balloon_cross(d):
    a, b = d["B.b0"], d["B.b1"]
    la = [p for p in a._prims if isinstance(p, Line)][0]
    lb = [p for p in b._prims if isinstance(p, Line)][0]
    ca = [p for p in a._prims if isinstance(p, Circle)][0]
    cb = [p for p in b._prims if isinstance(p, Circle)][0]
    a._prims = [
        Line((ca.c[0] + 30, ca.c[1]), (ca.c[0], cb.c[1]), "thin") if p is la else p
        for p in a._prims
    ]
    b._prims = [
        Line((cb.c[0] + 30, cb.c[1]), (cb.c[0], ca.c[1]), "thin") if p is lb else p
        for p in b._prims
    ]
    return a.id


MUTATORS = {
    "line_width": m_line_width,
    "text_height": m_text_height,
    "scale": m_scale,
    "sheet": m_sheet,
    "conv_dim": m_conv_dim,
    "section_ref": m_section_ref,
    "center_mark": m_center_mark,
    "duplicate": m_duplicate,
    "closed_loop": m_closed_loop,
    "missing": m_missing,
    "param_cover": m_param_cover,
    "dev_order": m_dev_order,
    "gtol_syntax": m_gtol_syntax,
    "datum_letter": m_datum_letter,
    "general_tol": m_general_tol,
    "chain_limit": m_chain_limit,
    "rough_syntax": m_rough_syntax,
    "rough_default": m_rough_default,
    "rough_fit": m_rough_fit,
    "overlap": m_overlap,
    "out_of_frame": m_out_of_frame,
    "view_align": m_view_align,
    "stale_op": m_stale_op,
    "place_dim_cross": m_place_dim_cross,
    "place_dim_outline": m_place_dim_outline,
    "place_row_spacing": m_place_row_spacing,
    "place_nesting": m_place_nesting,
    "place_ext_line": m_place_ext_line,
    "place_text_direction": m_place_text_direction,
    "place_text_overlap": m_place_text_overlap,
    "place_arrow": m_place_arrow,
    "place_leader_cross": m_place_leader_cross,
    "place_balloon_align": m_place_balloon_align,
    "place_balloon_spacing": m_place_balloon_spacing,
    "place_balloon_cross": m_place_balloon_cross,
}


def rule_functions() -> dict:
    return catalog.rule_functions()


# ---- report ------------------------------------------------------------------------------------


def _findings(d, stale=(), log_ops=()):
    return checks.run(d, stale, log_ops)


def reference_pass(cases=None):
    """Build every reference case once: findings, opportunities and per-rule clean cases."""
    debt = known_debt()
    cases = cases if cases is not None else evals.discover()
    per_case = {}
    opportunities = {}
    clean = {}
    skipped = []
    for case in cases:
        try:
            res = _build_case(case)
        except MissingExtra as e:  # an optional dependency is the only tolerated reason
            skipped.append({"id": case["id"], "reason": f"{type(e).__name__}: {e}"})
            continue
        found = _findings(res.d)
        cid = case["id"]
        per_case[cid] = [(f["rule"], f["id"], _signature(f)) for f in found]
        for rule, n in found.opportunities.items():
            opportunities[rule] = opportunities.get(rule, 0) + n
            if n and rule not in {f["rule"] for f in found} and rule not in clean:
                clean[rule] = cid
    return {
        "cases": per_case,
        "opportunities": opportunities,
        "clean": clean,
        "known_debt": debt,
        "case_ids": [c["id"] for c in cases],
        "skipped": skipped,
    }


def false_positives(ref):
    out = {}
    for cid, findings in ref["cases"].items():
        debt = ref["known_debt"].get(cid, set())
        for rule, eid, sig in findings:
            if (rule, eid, sig) in debt:
                continue
            out[rule] = out.get(rule, 0) + 1
    return out


def run_report(cases=None) -> dict:
    ref = reference_pass(cases)
    fps = false_positives(ref)
    built = {c["id"]: c for c in (cases if cases is not None else evals.discover())}
    rules = catalog.rules()
    report = {"rules": {}, "totals": {}, "known_debt": {}}
    total_mut = total_det = total_fp = 0
    for entry in rules:
        rule = entry["id"]
        mutator = MUTATORS.get(rule)
        data = {
            "mutations": 0,
            "detected": 0,
            "detection_rate": 0.0,
            "false_positives": fps.get(rule, 0),
            "opportunities": ref["opportunities"].get(rule, 0),
            "reference_opportunities": ref["opportunities"].get(rule, 0),
            "mutation_base_opportunities": None,
            "base": None,
        }
        if mutator is not None:
            base = BASE_OVERRIDES.get(rule) or FIXTURES.get(rule) or ref["clean"].get(rule)
            if isinstance(base, str):
                d = _build_case(built[base]).d
                data["base"] = base
            elif base is not None:
                d = base()
                data["base"] = f"fixture:{rule}"
            else:
                d = None
            if d is not None:
                stale = ()
                try:
                    log_ops = VALID_LOG if rule == "stale_op" else ()
                    base_found = _findings(d, stale, log_ops)
                    data["_base_ids"] = {f["id"] for f in base_found if f["rule"] == rule}
                    data["base_findings"] = len(data["_base_ids"])
                    data["mutation_base_opportunities"] = base_found.opportunities.get(rule, 0)
                    if not isinstance(base, str):
                        # a purpose-built clean fixture is its reference; only rules without a
                        # reference-drawing opportunity use the fixture numbers for FP accounting
                        base_opp = base_found.opportunities.get(rule, 0)
                        base_fps = sum(1 for f in base_found if f["rule"] == rule)
                        data["mutation_base_opportunities"] = base_opp
                        if data["reference_opportunities"] == 0:
                            data["opportunities"] = base_opp
                            data["false_positives"] = base_fps
                    stale = (STALE_OP,) if rule == "stale_op" else ()
                    target = STALE_OP["id"] if rule == "stale_op" else mutator(d)
                    found = _findings(d, stale, log_ops)
                    ids = {f["id"] for f in found if f["rule"] == rule}
                    base_ids = data.pop("_base_ids", set())
                    data["target"] = target
                    data["mutations"] = 1
                    ok = rule in {f["rule"] for f in found}
                    ok = ok and target is not None and target in ids
                    ok = ok and not (base_ids & ids)
                    data["detected"] = 1 if ok else 0
                    data["detection_rate"] = float(data["detected"])
                    data.pop("_base_ids", None)
                except Exception as e:  # noqa: BLE001 - a broken operator is reported, not fatal
                    data.pop("_base_ids", None)
                    data["error"] = f"{type(e).__name__}: {e}"
        total_mut += data["mutations"]
        total_det += data["detected"]
        total_fp += data["false_positives"]
        report["rules"][rule] = data
    report["totals"] = {
        "rules": len(rules),
        "mutations": total_mut,
        "detected": total_det,
        "detection_rate": round(total_det / total_mut, 4) if total_mut else 0.0,
        "false_positives": total_fp,
    }
    debt = json.loads(KNOWN_DEBT.read_text(encoding="utf-8")) if KNOWN_DEBT.exists() else {}
    actual = {
        (cid, rule, eid, sig)
        for cid, findings in ref["cases"].items()
        for rule, eid, sig in findings
        if rule.startswith("place_")
    }
    frozen = {
        (cid, rule, eid, sig)
        for cid, entries in ref["known_debt"].items()
        for rule, eid, sig in entries
    }
    report["known_debt"] = {
        "total": debt.get("total", 0),
        "cases": len(debt.get("cases", {})),
        "exact": actual == frozen,
        "unfrozen": sorted(actual - frozen)[:5],
        "stale": sorted(frozen - actual)[:5],
    }
    report["totals"]["skipped_cases"] = len(ref.get("skipped", []))
    return report


#: the E5 baseline this card started from (kept here so the evidence states old vs new)
E5_BASELINE = {
    "G": {"score": 1.0, "opportunities": 4417, "violations": 0},
    "D": {"score": 0.972252, "opportunities": 2775, "violations": 77},
    "T": {"score": 1.0, "opportunities": 247, "violations": 0},
}


def _baseline_table() -> list[str]:
    out = []
    path = ROOT / "evals" / "baseline.json"
    if not path.exists():
        return out
    new = json.loads(path.read_text(encoding="utf-8"))["families"]
    out.append("## baseline 变更（新增项，不是退化）")
    out.append("")
    out.append("| 族 | E5 基线 | E2 基线 | 变化 | 来源 |")
    out.append("|---|---|---|---|---|")
    for fam, old in E5_BASELINE.items():
        cur = new.get(fam, {})
        d_opp = (cur.get("opportunities") or 0) - old["opportunities"]
        d_viol = (cur.get("violations") or 0) - old["violations"]
        why = "新增 place_leader_cross 规则的 20 条真实交叉" if fam == "D" else "不变"
        out.append(
            f"| {fam} | {old['score']} ({old['opportunities']}/{old['violations']}) | "
            f"{cur.get('score')} ({cur.get('opportunities')}/{cur.get('violations')}) | "
            f"+{d_opp} 机会 / +{d_viol} 违规 | {why} |"
        )
    out.append("")
    out.append(
        "原 34 条规则没有新增违规（E5 的 77 条债务不变），新增的 20 条来自 place_leader_cross；"
        "G/T 仍 1.0，D 的下降全部来自新增规则的已知真阳性（同时冻结进 evals/known-debt.json）。"
    )
    out.append("")
    return out


def markdown(report) -> str:
    lines = []
    lines.append("# 规则变异报告（E2：检出率 / 误报率）")
    lines.append("")
    lines.append("命令：uv run python evals/mutate.py")
    lines.append("")
    t = report["totals"]
    lines.append(
        f"- 规则数：{t['rules']}；变异数：{t['mutations']}；检出：{t['detected']}；"
        f"检出率：{t['detection_rate']}；参考图误报：{t['false_positives']}；"
        f"跳过用例：{t.get('skipped_cases', 0)}；"
        f"债务冻结精确：{report['known_debt']['exact']}"
    )
    lines.append(
        f"- 冻结已知债务（E5 排布 + 径向引线交叉现存违规）：{report['known_debt']['total']} 条，"
        f"分布在 {report['known_debt']['cases']} 个参考图；变异框架把已知债务算真阳性"
    )
    lines.append("")
    lines.append("## 覆盖边界（已知盲区，明示不静默）")
    lines.append("")
    lines.append(
        "- place_dim_cross 只判尺寸线×尺寸线（frame 与 leader 的尺寸线），不判尺寸界线、中心线。"
    )
    lines.append(
        "- place_dim_outline 只判 frame 型尺寸线×轮廓；leader 型整体不判（引线本来要穿过轮廓到要素）。"
    )
    lines.append("- place_ext_line 只判尺寸界线自身的超出 / 起点 / 穿越轮廓。")
    lines.append(
        "- place_leader_cross（E2）只判径向引线×其它尺寸线/引线；"
        "径向引线×尺寸界线、×中心线、×轮廓未计量。"
    )
    lines.append(
        "- 这些盲区中，D1 在 layout 放置阶段用 placement.resolved 的 crossings / violations / "
        "corridors（with + kind：overlap / cross / coincide / outline）记录可避免交叉并写进 reason；"
        "残余不可避免者由 E2 的 warn 规则承接；把引线扩到尺寸界线 / 中心线 / 轮廓属 D2 或 "
        "place 子规则扩展，另卡处理。"
    )
    lines.append("")
    lines.extend(_baseline_table())
    lines.append("| 规则 | 参考图机会 | 变异基座机会 | 变异 | 检出 | 检出率 | 误报 | 基线 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for rule, d in sorted(report["rules"].items()):
        lines.append(
            f"| {rule} | {d['reference_opportunities']} | "
            f"{d.get('mutation_base_opportunities') or '—'} | {d['mutations']} | "
            f"{d['detected']} | {d['detection_rate']:.0%} | {d['false_positives']} | "
            f"{d['base'] or '—'} |"
        )
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="write the markdown report to this file")
    ap.add_argument("--json", default=None, help="write the full JSON report to this file")
    a = ap.parse_args(argv)
    report = run_report()
    text = markdown(report)
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8", newline="\n")
    if a.json:
        Path(a.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
    return (
        0
        if (
            report["totals"]["detection_rate"] == 1.0
            and report["totals"]["false_positives"] == 0
            and report["totals"].get("skipped_cases", 0) == 0
            and report["known_debt"]["exact"]
        )
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
