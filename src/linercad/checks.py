"""M0 minimal checks (SPEC §10): overlap, out_of_frame, view_align, stale_op."""

from __future__ import annotations

from .layout import Hatch, Text, box_overlap, prim_segments, seg_in_box, union

STD_OVERLAP = "GB/T 4458.4-2003"
STD_FRAME = "GB/T 14689-2008"
STD_ALIGN = "GB/T 4458.1-2002"

# local axes of each basic view in model axes (SPEC §3.1): (sign, axis) for u and v
VIEW_AXES = {
    "front": ((1, "X"), (1, "Z")),
    "top": ((1, "X"), (1, "Y")),
    "bottom": ((1, "X"), (-1, "Y")),
    "left": ((-1, "Y"), (1, "Z")),
    "right": ((1, "Y"), (1, "Z")),
    "rear": ((-1, "X"), (1, "Z")),
}
AXIS_NAME = {"X": "长对正", "Z": "高平齐", "Y": "宽相等"}
MAX_CORRIDOR = 50.0
OWN_ZONE = ("frame", "table.cell")


def _shapes(e):
    segs, boxes = [], []
    for pr in e._prims:
        if isinstance(pr, Text):
            boxes.append(pr.box)
        elif not isinstance(pr, Hatch):
            segs += prim_segments(pr)
    return segs, boxes


def _corridors(box, obstacles):
    """Free distance from a text box to the nearest obstacle box in each direction."""
    out = {}
    x0, y0, x1, y1 = box
    for name, test in (
        ("right", lambda b: b[1] < y1 and b[3] > y0 and b[0] >= x1 - 1e-9 and b[0] - x1),
        ("left", lambda b: b[1] < y1 and b[3] > y0 and b[2] <= x0 + 1e-9 and x0 - b[2]),
        ("up", lambda b: b[0] < x1 and b[2] > x0 and b[1] >= y1 - 1e-9 and b[1] - y1),
        ("down", lambda b: b[0] < x1 and b[2] > x0 and b[3] <= y0 + 1e-9 and y0 - b[3]),
    ):
        ds = []
        for b in obstacles:
            v = test(b)
            if v is not False and v is not None:
                ds.append(max(0.0, float(v)))
        out[name] = round(min(ds + [MAX_CORRIDOR]), 3)
    return out


def _overlaps(d):
    els = [e for e in d._els.values() if e._prims]
    shapes = {e._id: _shapes(e) for e in els}
    findings = []
    for e in els:
        segs, boxes = shapes[e._id]
        if not boxes:
            continue
        viol = {}
        for o in els:
            if o is e:
                continue
            osegs, oboxes = shapes[o._id]
            for b in boxes:
                for p, q in osegs:
                    v = seg_in_box(p, q, b)
                    if v > 0.05:
                        viol[o._id] = max(viol.get(o._id, 0), v)
                for ob in oboxes:
                    v = box_overlap(b, ob)
                    if v > 0.05:
                        viol[o._id] = max(viol.get(o._id, 0), v)
        if viol:
            obstacles = []
            for o in els:
                if o is not e:
                    osegs, oboxes = shapes[o._id]
                    obstacles += oboxes + [
                        (min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1]))
                        for p, q in osegs
                    ]
            findings.append(
                {
                    "rule": "overlap",
                    "severity": "warn",
                    "id": e._id,
                    "message": f"{e._id} 的文字与 {'、'.join(sorted(viol))} 重叠",
                    "violations": [
                        {"with": k, "overlap": round(v, 3)} for k, v in sorted(viol.items())
                    ],
                    "corridors": _corridors(boxes[0], obstacles),
                    "std": STD_OVERLAP,
                }
            )
    return findings


def _out_of_frame(d):
    F = d.template["frame"]
    tb = d.template["title_block"]
    ox, oy = tb["origin"]
    TB = (ox, oy, ox + tb["size"][0], oy + tb["size"][1])
    tech = [e for e in d._els.values() if e.kind == "note" and e._intent.get("tech")]
    TN = union([e._resolved.get("bbox") for e in tech])
    findings = []
    for e in d._els.values():
        b = e._resolved.get("bbox")
        if not b or e.kind in OWN_ZONE or e.kind in ("view", "feature", "raw") or e in tech:
            continue
        viol = []
        outside = max(F[0] - b[0], F[1] - b[1], b[2] - F[2], b[3] - F[3])
        if outside > 0.01:
            viol.append({"with": "T.frame", "overlap": round(outside, 3)})
        for zid, z in (("T.title", TB), ("N.tech", TN)):
            if z and box_overlap(b, z) > 0.01:
                viol.append({"with": zid, "overlap": round(box_overlap(b, z), 3)})
        if viol:
            findings.append(
                {
                    "rule": "out_of_frame",
                    "severity": "warn",
                    "id": e._id,
                    "message": f"{e._id} 越出图框或压到标题栏 / 技术要求区",
                    "violations": viol,
                    "corridors": {},
                    "std": STD_FRAME,
                }
            )
    return findings


def _view_align(d):
    ranges = {}  # view -> {axis: (lo, hi)} in model units
    for v in d.views():
        pts = []
        for e in d._els.values():
            if e.kind != "edge" or e._intent.get("view") != v.name:
                continue
            i = e._intent
            if i["shape"] == "line":
                pts += [i["p1"], i["p2"]]
            else:
                c, r = i["c"], i["r"]
                pts += [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
        if not pts or v.name not in VIEW_AXES:
            continue
        (su, au), (sv, av) = VIEW_AXES[v.name]
        us = [p[0] * su for p in pts]
        vs = [p[1] * sv for p in pts]
        ranges[v.name] = {au: (min(us), max(us)), av: (min(vs), max(vs))}
    findings = []
    order = [n for n in ("front", "top", "left", "bottom", "right", "rear") if n in ranges]
    for axis in ("X", "Z", "Y"):
        holders = [n for n in order if axis in ranges[n]]
        if len(holders) < 2:
            continue
        ref = holders[0]
        r0 = ranges[ref][axis]
        for n in holders[1:]:
            r = ranges[n][axis]
            diff = max(abs(r[0] - r0[0]), abs(r[1] - r0[1]))
            if diff > 0.01:
                findings.append(
                    {
                        "rule": "view_align",
                        "severity": "warn",
                        "id": f"V.{n}",
                        "message": f"V.{n} 的 {axis} 范围 [{r[0]:g}, {r[1]:g}] 与 V.{ref} 的 [{r0[0]:g}, {r0[1]:g}] 不一致（{AXIS_NAME[axis]}）",
                        "violations": [{"with": f"V.{ref}", "overlap": round(diff, 3)}],
                        "corridors": {},
                        "std": STD_ALIGN,
                    }
                )
    return findings


def _stale(stale_ops):
    out = []
    for s in stale_ops:
        out.append(
            {
                "rule": "stale_op",
                "severity": "warn",
                "id": s.get("id"),
                "message": f"日志 {s['edit']} 第 {s['line']} 行的 {s['op']} 失效：{s['reason']}",
                "violations": [],
                "corridors": {},
                "std": "DESIGN §3.2",
                "edit": s["edit"],
                "line": s["line"],
                "op": s["op"],
                "candidates": s.get("candidates", []),
            }
        )
    return out


def run(d, stale_ops=()):
    """All M0 checks; sets element status; returns findings not accepted."""
    raw = _overlaps(d) + _out_of_frame(d) + _view_align(d) + _stale(stale_ops)
    accepted = getattr(d, "_accepted", {})
    findings = []
    for e in d._els.values():
        e._status = "ok"
    for f in raw:
        reason = accepted.get((f["rule"], f["id"]))
        el = d._els.get(f["id"])
        if reason is not None:
            if el is not None:
                el._status = f"accepted({reason})"
            continue
        findings.append(f)
        if el is not None and not el._status.startswith("accepted"):
            el._status = "warn"
    return findings
