"""Geometry comparison: 2D drawing edges of one view vs the HLR projection of the 3D model
(SPEC M1 §8). Development / evaluation only."""

from __future__ import annotations

import math

import numpy as np

TOL = 0.05  # mm: a sample point within this distance of the other side counts as matched
STEP = 0.5  # mm: sampling step along drawing edges
PASS = 0.98  # both coverages must reach this


def _edge_points(e, step=STEP):
    i = e._intent
    if i["shape"] == "line":
        (x0, y0), (x1, y1) = i["p1"], i["p2"]
        n = max(1, int(math.ceil(math.dist((x0, y0), (x1, y1)) / step)))
        return [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
    c, r = i["c"], i["r"]
    a0, a1 = (0.0, 360.0) if i["shape"] == "circle" else (i["start"], i["end"])
    sweep = (a1 - a0) % 360 or 360
    n = max(4, int(math.ceil(math.radians(sweep) * r / step)))
    return [
        (
            c[0] + r * math.cos(math.radians(a0 + sweep * k / n)),
            c[1] + r * math.sin(math.radians(a0 + sweep * k / n)),
        )
        for k in range(n + 1)
    ]


def drawing_edges(d, view, roles=("thick",)):
    """{edge id: polyline} of the view's real outline edges (conventional lines excluded)."""
    out = {}
    for e in d._els.values():
        if e.kind == "edge" and e._intent.get("view") == view and e._intent["role"] in roles:
            if "conv" not in e._tags:
                out[e.id] = _edge_points(e)
    return out


def masks(d, view):
    return [
        [tuple(p) for p in e._intent["mask"]]
        for e in d._els.values()
        if e.kind == "feature" and e._intent.get("view") == view and e._intent.get("mask")
    ]


def _in_poly(pts, poly):
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), bool)
    n = len(poly)
    for k in range(n):
        (x1, y1), (x2, y2) = poly[k], poly[(k + 1) % n]
        cond = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        inside ^= cond & (x < xi)
    return inside


def _segments(polylines):
    segs = [(p, q) for pl in polylines for p, q in zip(pl, pl[1:]) if p != q]
    if not segs:
        return np.zeros((0, 2)), np.zeros((0, 2))
    a = np.array([s[0] for s in segs], float)
    b = np.array([s[1] for s in segs], float)
    return a, b


def _dist(pts, a, b):
    """Distance of each point to the nearest segment (chunked to bound memory)."""
    if len(a) == 0:
        return np.full(len(pts), np.inf)
    ab = b - a
    L2 = np.maximum((ab**2).sum(1), 1e-18)
    out = np.empty(len(pts))
    for s in range(0, len(pts), 512):
        p = pts[s : s + 512, None, :]
        t = np.clip(((p - a) * ab).sum(2) / L2, 0, 1)
        q = a + t[..., None] * ab
        out[s : s + 512] = np.sqrt(((p - q) ** 2).sum(2)).min(1)
    return out


def compare(d, view, proj, roles=("thick",), tol=TOL, extra_mask=()):
    """→ {"cov_drawing", "cov_model", "pass", "unmatched_drawing": [ids], "unmatched_model": [bbox]}"""
    dr = drawing_edges(d, view, roles)
    model = list(proj.get("visible", []))
    if "hidden" in roles:
        model += proj.get("hidden", [])
    mk = masks(d, view) + [list(m) for m in extra_mask]
    dpts = [(eid, p) for eid, pl in dr.items() for p in pl]
    mpts = np.array([p for pl in model for p in pl], float).reshape(-1, 2)
    if len(mpts) and mk:
        keep = np.ones(len(mpts), bool)
        for poly in mk:
            keep &= ~_in_poly(mpts, poly)
        mpts = mpts[keep]
    da, db = _segments(list(dr.values()))
    ma, mb = _segments(model)
    P = np.array([p for _, p in dpts], float).reshape(-1, 2)
    d1 = _dist(P, ma, mb) if len(P) else np.zeros(0)
    d2 = _dist(mpts, da, db) if len(mpts) else np.zeros(0)
    cov_d = float((d1 <= tol).mean()) if len(d1) else 0.0
    cov_m = float((d2 <= tol).mean()) if len(d2) else 0.0
    bad_ids = sorted({dpts[k][0] for k in np.nonzero(d1 > tol)[0]})
    bad_m = mpts[d2 > tol]
    um = []
    if len(bad_m):
        um = [
            [
                round(float(v), 3)
                for v in (
                    bad_m[:, 0].min(),
                    bad_m[:, 1].min(),
                    bad_m[:, 0].max(),
                    bad_m[:, 1].max(),
                )
            ]
        ]
    return {
        "cov_drawing": round(cov_d, 4),
        "cov_model": round(cov_m, 4),
        "pass": cov_d >= PASS and cov_m >= PASS,
        "unmatched_drawing": bad_ids,
        "unmatched_model": um,
    }
