"""Revolved parts in the axial view (SPEC M1 §4 `turned`): grooves spliced into the profile,
bores, full / half sections with automatic section regions, axial holes on a pitch circle.

All coordinates are (x along the axis, r from the axis); callers mirror with the axis offset.
"""

from __future__ import annotations

from .errors import InvalidArgument

EPS = 1e-9


def _num(v):
    return float(v)


def splice_grooves(pts, names, grooves):
    """Insert rectangular grooves into the outer profile. ``names``: {segment start index: name}.
    Returns (points, names) with names re-indexed; the groove dicts get x0/x1/r/rg filled in."""
    out = []
    for g in grooves:
        x, w = _num(g["x"]), _num(g["w"])
        side = g.get("side", "left")
        if side not in ("left", "right") or w <= 0:
            raise InvalidArgument(
                f"退刀槽 {g.get('name')} 的 side 应为 left/right、w > 0", values=dict(g)
            )
        x0, x1 = (x - w, x) if side == "left" else (x, x + w)
        seg = None
        for i in range(len(pts) - 1):
            (xa, ra), (xb, rb) = pts[i], pts[i + 1]
            if abs(ra - rb) < EPS and xa <= x0 + EPS and xb >= x1 - EPS and xb - xa > EPS:
                seg = i
                break
        if seg is None:
            raise InvalidArgument(
                f"退刀槽 {g.get('name')} 的 [{x0:g}, {x1:g}] 不在轮廓的某一段圆柱面上",
                values={"x0": x0, "x1": x1},
                hint="x 是台阶位置，side=left 时槽在台阶左侧",
            )
        r = pts[seg][1]
        if "d" in g and g["d"] is not None:
            rg = _num(g["d"]) / 2
        elif "depth" in g and g["depth"] is not None:
            rg = r - _num(g["depth"])
        else:
            raise InvalidArgument(f"退刀槽 {g.get('name')} 需要 d（槽底直径）或 depth")
        if not 0 < rg < r:
            raise InvalidArgument(
                f"退刀槽 {g.get('name')} 的槽底半径 {rg:g} 应在 0 与 {r:g} 之间", values={"rg": rg}
            )
        ins = [(x0, r), (x0, rg), (x1, rg), (x1, r)]
        tagged = [(p, names.get(i)) for i, p in enumerate(pts)]
        tagged = tagged[: seg + 1] + [(p, None) for p in ins] + tagged[seg + 1 :]
        tagged = _clean(tagged)
        pts = [p for p, _ in tagged]
        names = {i: n for i, (_, n) in enumerate(tagged) if n}
        out.append({**g, "x0": x0, "x1": x1, "r": r, "rg": rg})
    return pts, names, out


def _clean(tagged):
    """Drop repeated points and middle points of straight vertical runs (keeping names)."""
    res = []
    for p, n in tagged:
        if res and abs(res[-1][0][0] - p[0]) < EPS and abs(res[-1][0][1] - p[1]) < EPS:
            if n and not res[-1][1]:
                res[-1] = (res[-1][0], n)
            continue
        res.append((p, n))
    k = 1
    while k < len(res) - 1:
        (a, _), (b, nb), (c, _) = res[k - 1], res[k], res[k + 1]
        if abs(a[0] - b[0]) < EPS and abs(b[0] - c[0]) < EPS and not nb:
            del res[k]
        else:
            k += 1
    return res


def _r_at(prof, x, side):
    """Radius of a profile polyline at x approached from 'left' or 'right' (None outside)."""
    for (xa, ra), (xb, rb) in zip(prof, prof[1:]):
        if xb - xa <= EPS:
            continue
        inside = xa - EPS <= x < xb - EPS if side == "right" else xa + EPS < x <= xb + EPS
        if inside:
            return ra + (rb - ra) * (x - xa) / (xb - xa)
    return None


def _corners(prof):
    """x positions of profile corners: ends, steps, and slope changes."""
    xs = []
    n = len(prof)
    for i, (x, _) in enumerate(prof):
        idx = [k for k in range(n) if abs(prof[k][0] - x) <= EPS]
        if idx[0] != i:
            continue
        corner = idx[0] == 0 or idx[-1] == n - 1 or len(idx) > 1
        if not corner:
            (xa, ra), (xb, rb), (xc, rc) = prof[i - 1], prof[i], prof[i + 1]
            corner = abs((xb - xa) * (rc - rb) - (rb - ra) * (xc - xb)) > 1e-9
        if corner:
            xs.append((x, [prof[k][1] for k in idx], idx[0] == 0 or idx[-1] == n - 1, len(idx) > 1))
    return xs


def _merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out if b - a > 1e-6]


def build(outer, bore, cut, half, holes, hidden, role):
    """Edges (dicts: p1, p2 in (x, y) with y about axis 0, role, seg) and section loops.

    Returns (edges, loops, hole_centers) where ``seg`` = index of the outer/bore profile segment
    (for naming, ("o", i, side) / ("b", i, side))."""
    if cut not in (None, "full", "half"):
        raise InvalidArgument(f"cut 只能是 None、'full'、'half'，收到 {cut!r}")
    if half not in ("top", "bottom"):
        raise InvalidArgument(f"half 只能是 'top' 或 'bottom'，收到 {half!r}")
    sides = {1: "ext", -1: "ext"}
    if cut == "full":
        sides = {1: "cut", -1: "cut"}
    elif cut == "half":
        s = 1 if half == "top" else -1
        sides = {s: "cut", -s: "ext"}
    xs0, xs1 = outer[0][0], outer[-1][0]
    if bore:
        if bore[0][0] < xs0 - EPS or bore[-1][0] > xs1 + EPS:
            raise InvalidArgument(
                "bore 的 x 范围超出外轮廓", values={"bore": [bore[0][0], bore[-1][0]]}
            )
        for x, r in bore:
            ro = max(
                [v for v in (_r_at(outer, x, "left"), _r_at(outer, x, "right")) if v is not None],
                default=0,
            )
            if r >= ro - EPS:
                raise InvalidArgument(
                    f"bore 在 x={x:g} 处半径 {r:g} 不小于外径 {ro:g}", values={"x": x}
                )
    for h in holes:
        for k in ("r", "d", "x0", "x1"):
            if k not in h:
                raise InvalidArgument(f"holes 每项需要 r、d、x0、x1，缺 {k}", values=dict(h))
    edges, loops, vert = [], [], {}

    def add(p1, p2, rl, seg=None):
        edges.append({"p1": list(p1), "p2": list(p2), "role": rl, "seg": seg})

    def vadd(x, a, b, rl):
        if b - a > 1e-6:
            vert.setdefault((round(x, 9), rl), []).append((a, b))

    def holes_on(s):
        return [h for h in holes if h.get("at", "both") in ("both", "top" if s > 0 else "bottom")]

    hidden = hidden and cut is None  # half sections omit hidden lines in the outside half
    for s, mode in sides.items():
        sl = "" if s > 0 else "_lo"
        # outer profile, along the axis
        for i, ((xa, ra), (xb, rb)) in enumerate(zip(outer, outer[1:])):
            if xb - xa > EPS:
                add((xa, s * ra), (xb, s * rb), role, ("o", i, sl))
        if mode == "ext":
            for x, rs, _end, _step in _corners(outer):
                vadd(x, *sorted((0, s * max(rs))), role)
            if hidden and bore:
                for i, ((xa, ra), (xb, rb)) in enumerate(zip(bore, bore[1:])):
                    if xb - xa > EPS:
                        add((xa, s * ra), (xb, s * rb), "hidden", ("b", i, sl))
                for x, rs, _e, _st in _corners(bore):
                    vadd(x, *sorted((0, s * max(rs))), "hidden")
            if hidden:
                for h in holes_on(s):
                    for rr in (h["r"] - h["d"] / 2, h["r"] + h["d"] / 2):
                        add((h["x0"], s * rr), (h["x1"], s * rr), "hidden")
            continue
        # cut half: bore lines, cut-edge verticals, far edges across the hollow, hole walls
        for i, ((xa, ra), (xb, rb)) in enumerate(zip(bore, bore[1:])):
            if xb - xa > EPS:
                add((xa, s * ra), (xb, s * rb), role, ("b", i, sl))
        for x, rs, end, step in _corners(outer):
            if step:
                vadd(x, *sorted((s * min(rs), s * max(rs))), role)
            if end:
                rb = _bore_at(bore, x)
                vadd(x, *sorted((s * rb, s * min(rs) if step else s * rs[0])), role)
        for x, rs, _e, _st in _corners(bore):
            vadd(x, *sorted((0, s * max(rs))), role)
        for h in holes_on(s):
            r0, r1 = h["r"] - h["d"] / 2, h["r"] + h["d"] / 2
            for rr in (r0, r1):
                add((h["x0"], s * rr), (h["x1"], s * rr), role)
            for x in (h["x0"], h["x1"]):
                if xs0 + EPS < x < xs1 - EPS:
                    vadd(x, *sorted((s * r0, s * r1)), role)
        loops += [[[x, s * y] for x, y in lp] for lp in _region(outer, bore, holes_on(s), xs0, xs1)]
    for (x, rl), iv in sorted(vert.items()):
        merged = _merge(iv)
        if rl == "hidden":  # visible lines win where both fall on the same x
            merged = _subtract(merged, _merge(vert.get((x, role), [])))
        for a, b in merged:
            add((x, a), (x, b), rl)
    centers = []
    for h in holes:
        if not (hidden or cut):
            continue
        for s in (1, -1):
            if h in holes_on(s):
                centers.append(((h["x0"], s * h["r"]), (h["x1"], s * h["r"]), h.get("name")))
    return edges, loops, centers


def _subtract(ivs, cuts):
    out = []
    for a, b in ivs:
        pieces = [(a, b)]
        for c0, c1 in cuts:
            nxt = []
            for p0, p1 in pieces:
                if c1 <= p0 or c0 >= p1:
                    nxt.append((p0, p1))
                    continue
                if c0 > p0:
                    nxt.append((p0, c0))
                if c1 < p1:
                    nxt.append((c1, p1))
            pieces = nxt
        out += [(p0, p1) for p0, p1 in pieces if p1 - p0 > 1e-6]
    return out


def _bore_at(bore, x):
    if not bore:
        return 0.0
    vals = [r for bx, r in bore if abs(bx - x) <= EPS]
    if vals:
        return max(vals)
    v = _r_at(bore, x, "right")
    if v is None:
        v = _r_at(bore, x, "left")
    return v or 0.0


def _region(outer, bore, holes, xs0, xs1):
    """Section region of one half in (x, r) as slab polygons, holes cut out."""
    bps = {x for x, _ in outer} | {x for x, _ in bore}
    for h in holes:
        bps |= {h["x0"], h["x1"]}
    bps = sorted(x for x in bps if xs0 - EPS <= x <= xs1 + EPS)
    loops = []
    for a, b in zip(bps, bps[1:]):
        if b - a <= EPS:
            continue
        oa, ob = _r_at(outer, a, "right"), _r_at(outer, b, "left")
        ia, ib = _r_at(bore, a, "right") or 0.0, _r_at(bore, b, "left") or 0.0
        if bore and not (bore[0][0] - EPS <= a and b <= bore[-1][0] + EPS):
            ia = ib = 0.0
        bands = [(ia, ib, oa, ob)]
        for h in sorted(holes, key=lambda h: h["r"]):
            if h["x0"] - EPS <= a and b <= h["x1"] + EPS:
                r0, r1 = h["r"] - h["d"] / 2, h["r"] + h["d"] / 2
                nb = []
                for lo_a, lo_b, hi_a, hi_b in bands:
                    if r0 > max(lo_a, lo_b) and r1 < min(hi_a, hi_b):
                        nb += [(lo_a, lo_b, r0, r0), (r1, r1, hi_a, hi_b)]
                    else:
                        nb.append((lo_a, lo_b, hi_a, hi_b))
                bands = nb
        for lo_a, lo_b, hi_a, hi_b in bands:
            if hi_a - lo_a > 1e-6 or hi_b - lo_b > 1e-6:
                loops.append([(a, lo_a), (b, lo_b), (b, hi_b), (a, hi_a)])
    return loops
