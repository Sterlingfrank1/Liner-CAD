"""Layout of PMI and the M1 dimension types: composite dimension text (stacked deviations,
envelope), aligned / angle dimensions, datum symbols, geometric tolerance frames, roughness
symbols. Symbols are drawn with lines, arcs and solids — no special font glyphs."""

from __future__ import annotations

import math

from .layout import Arc, Circle, Line, Solid, arrow, make_text, prims_bbox, union
from .text import text_size


def _rot(p, ang, o=(0.0, 0.0)):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    x, y = p[0] - o[0], p[1] - o[1]
    return (o[0] + x * c - y * s, o[1] + x * s + y * c)


def transform(prims, ang, dx, dy):
    """Rotate prims (built about the origin) by ``ang`` degrees, then move by (dx, dy)."""
    out = []
    for p in prims:
        if isinstance(p, Line):
            out.append(
                Line(_mv(_rot(p.p, ang), dx, dy), _mv(_rot(p.q, ang), dx, dy), p.layer, p.ltscale)
            )
        elif isinstance(p, Circle):
            out.append(Circle(_mv(_rot(p.c, ang), dx, dy), p.r, p.layer, p.ltscale))
        elif isinstance(p, Arc):
            out.append(Arc(_mv(_rot(p.c, ang), dx, dy), p.r, p.a0 + ang, p.a1 + ang, p.layer))
        elif isinstance(p, Solid):
            out.append(Solid(tuple(_mv(_rot(q, ang), dx, dy) for q in p.pts), p.layer))
        else:  # Text
            at = _mv(_rot(p.at, ang), dx, dy)
            out.append(
                make_text(p.text, at, p.height, STD[0], rot=(p.rot + ang) % 360, layer=p.layer)
            )
    return out


STD = [None]  # the std used by transform() for text boxes (set by callers)


def _mv(p, dx, dy):
    return (p[0] + dx, p[1] + dy)


# ---- dimension text ------------------------------------------------------------------------


def label_parts(i, std):
    """Unrotated pieces of a dimension text centred on the origin → (prims, w, h)."""
    STD[0] = std
    dm = std["dim"]
    h, th = dm["text_height"], std["tolerancing"]["tol_height"]
    main = i["text"]
    w0, h0 = text_size(main, h, std)
    dev = i.get("dev")
    wd = 0.0
    if dev:
        wd = max(text_size(t, th, std)[0] for t in dev)
    tail = i.get("tail") or ""
    wt = text_size(tail, h, std)[0] if tail else 0.0
    env = (i.get("tolerance") or {}).get("envelope")
    we = h * 1.3 if env else 0.0
    gap = 0.6
    W = w0 + (gap + wd if dev else 0) + (wt if tail else 0) + (gap + we if env else 0)
    H = max(h0, 2 * th * 1.15 if dev else 0)
    x = -W / 2
    prims = [make_text(main, (x + w0 / 2, 0.0), h, std)]
    x += w0
    if dev:
        x += gap
        up, lo = dev
        prims.append(make_text(up, (x + text_size(up, th, std)[0] / 2, th * 0.6), th, std))
        prims.append(make_text(lo, (x + text_size(lo, th, std)[0] / 2, -th * 0.6), th, std))
        x += wd
    if tail:
        prims.append(make_text(tail, (x + wt / 2, 0.0), h, std))
        x += wt
    if env:
        x += gap
        prims.append(make_text("E", (x + we / 2, 0.0), h * 0.7, std))
        prims.append(Circle((x + we / 2, 0.0), we / 2, "dim"))
    return prims, W, H


def dim_label(i, at, std, rot=0.0):
    """Composite dimension text centred at ``at`` rotated by ``rot`` → (prims, box)."""
    parts, _, _ = label_parts(i, std)
    prims = transform(parts, rot, at[0], at[1])
    return prims, prims_bbox(prims)


def label_size(i, std):
    _, w, h = label_parts(i, std)
    return w, h


# ---- aligned and angle dimensions -------------------------------------------------------------

SIDE_VEC = {"top": (0, 1), "bottom": (0, -1), "left": (-1, 0), "right": (1, 0)}


def aligned_cands(vl, el):
    i, lay = el._intent, el._layout
    std, dm = vl.std, vl.std["dim"]
    a, b = vl.P(i["p1"]), vl.P(i["p2"])
    if b[0] < a[0] - 1e-9 or (abs(b[0] - a[0]) <= 1e-9 and b[1] < a[1]):
        a, b = b, a
    L = math.dist(a, b)
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    n = (-u[1], u[0])
    side = lay.get("side")
    if side is None:
        G = vl.G
        m = ((a[0] + b[0]) / 2 - (G[0] + G[2]) / 2, (a[1] + b[1]) / 2 - (G[1] + G[3]) / 2)
        sg = 1 if m[0] * n[0] + m[1] * n[1] >= 0 else -1
        v = (n[0] * sg, n[1] * sg)
        side = max(SIDE_VEC, key=lambda k: SIDE_VEC[k][0] * v[0] + SIDE_VEC[k][1] * v[1])
    sv = SIDE_VEC[side]
    sg = 1 if n[0] * sv[0] + n[1] * sv[1] >= 0 else -1
    N = (n[0] * sg, n[1] * sg)
    off = lay.get("offset") or 0.0
    rows = [lay["row"]] if lay.get("row") else range(1, int(dm["max_rows"]) + 1)
    ang = math.degrees(math.atan2(u[1], u[0]))
    w, hh = label_size(i, std)
    out = []
    for row in rows:
        dist = dm["first_row"] + (row - 1) * dm["row_pitch"] + off
        A = (a[0] + N[0] * dist, a[1] + N[1] * dist)
        B = (b[0] + N[0] * dist, b[1] + N[1] * dist)
        prims, segs = [], []
        for p, q in ((a, A), (b, B)):
            e = (q[0] + N[0] * dm["ext_beyond"], q[1] + N[1] * dm["ext_beyond"])
            prims.append(Line(p, e, "dim"))
            segs.append((p, e))
        prims += [Line(A, B, "dim"), arrow(A, (-u[0], -u[1]), std), arrow(B, u, std)]
        segs.append((A, B))
        tg = dm["text_gap"] + hh / 2
        ctr = ((A[0] + B[0]) / 2 + N[0] * tg, (A[1] + B[1]) / 2 + N[1] * tg)
        tp, box = dim_label(i, ctr, std, ang if N[0] * -u[1] + N[1] * u[0] >= 0 else ang)
        prims += tp
        out.append(
            {
                "prims": prims,
                "boxes": [box],
                "segs": segs,
                "dimline": (A, B),
                "fields": {"side": side, "row": row, "offset": off},
                "ends": [A, B],
                "why": "",
            }
        )
    return out


def angle_cands(vl, el):
    i, lay = el._intent, el._layout
    std, _dm = vl.std, vl.std["dim"]
    V = vl.P(i["vertex"])
    a1, sweep = i["a1"], i["measured"]
    radii = [lay["r"]] if lay.get("r") else [12.0, 16.0, 20.0, 25.0, 30.0, 40.0]
    w, hh = label_size(i, std)
    out = []
    for r in radii:
        prims, segs = [Arc(V, r, a1, a1 + sweep, "dim")], []
        for ang, sgn in ((a1, 1), (a1 + sweep, -1)):
            p = (V[0] + r * math.cos(math.radians(ang)), V[1] + r * math.sin(math.radians(ang)))
            t = (-math.sin(math.radians(ang)) * sgn, math.cos(math.radians(ang)) * sgn)
            prims.append(arrow(p, (-t[0], -t[1]), std))
        mid = math.radians(a1 + sweep / 2)
        um = (math.cos(mid), math.sin(mid))
        k = r + 1.5 + (abs(um[0]) * w + abs(um[1]) * hh) / 2
        ctr = (V[0] + um[0] * k, V[1] + um[1] * k)
        tp, box = dim_label(i, ctr, std, 0.0)
        prims += tp
        out.append({"prims": prims, "boxes": [box], "segs": segs, "fields": {"r": r}, "why": ""})
    return out


# ---- leader anchors ---------------------------------------------------------------------------

AT_FRACS = (0.5, 0.35, 0.65, 0.2, 0.8)


def _anchor(vl, el, frac):
    """(anchor point, outward unit normal) in view-local sheet coordinates."""
    d = vl.d
    ref = d._els.get(el._intent["ref"])
    if ref is None:
        return None
    if ref.kind == "dim":
        ends = ref._resolved.get("ends")
        if not ends:
            return None
        a, b = ends
        L = math.dist(a, b) or 1.0
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        return (a, (-u[0], -u[1])) if frac == 0 else (b, u)
    if ref.kind == "feature":
        es = [e for e in ref.edges if e.shape == "line"]
        if not es:
            return None
        ref = es[0]
    it = ref._intent
    G = vl.G
    gc = ((G[0] + G[2]) / 2, (G[1] + G[3]) / 2)
    if it["shape"] == "line":
        p, q = vl.P(it["p1"]), vl.P(it["p2"])
        A = (p[0] + (q[0] - p[0]) * frac, p[1] + (q[1] - p[1]) * frac)
        L = math.dist(p, q) or 1.0
        n = (-(q[1] - p[1]) / L, (q[0] - p[0]) / L)
        if (A[0] - gc[0]) * n[0] + (A[1] - gc[1]) * n[1] < 0:
            n = (-n[0], -n[1])
        return A, n
    c, r = vl.P(it["c"]), it["r"] * vl.s
    ang = math.radians(45 + 90 * (frac - 0.5) * 2)
    n = (math.cos(ang), math.sin(ang))
    return (c[0] + n[0] * r, c[1] + n[1] * r), n


def _lens(lay, std):
    if lay.get("length"):
        return [lay["length"]]
    return list(std["tolerancing"]["leader_lengths"])


def _fracs(el):
    lay = el._layout
    ref = el._d._els.get(el._intent["ref"])
    if lay.get("at") is not None:
        return [lay["at"]]
    if ref is not None and ref.kind == "dim":
        return [1, 0]  # either end of the dimension line (axis features)
    return list(AT_FRACS)


def _cand(prims, fields, why=""):
    from .layout import Text

    boxes = [p.box for p in prims if isinstance(p, Text)]
    segs = []
    for p in prims:
        if isinstance(p, Line):
            segs.append((p.p, p.q))
    box = prims_bbox(prims)
    return {
        "prims": prims,
        "boxes": boxes + ([box] if box else []),
        "segs": segs,
        "fields": fields,
        "why": why,
    }


def _shift(el):
    return el._layout.get("shift") or (0.0, 0.0)


def datum_cands(vl, el):
    std = vl.std
    dt = std["datum"]
    out = []
    for frac in _fracs(el):
        an = _anchor(vl, el, frac)
        if an is None:
            return []
        A, n = an
        t = (-n[1], n[0])
        s = dt["triangle"]
        hgt = s * math.sqrt(3) / 2
        for L in _lens(el._layout, std):
            sx, sy = _shift(el)
            apex = (A[0] + n[0] * hgt, A[1] + n[1] * hgt)
            tri = Solid(
                (
                    (A[0] + t[0] * s / 2, A[1] + t[1] * s / 2),
                    (A[0] - t[0] * s / 2, A[1] - t[1] * s / 2),
                    apex,
                ),
                "thin",
            )
            E = (apex[0] + n[0] * L + sx, apex[1] + n[1] * L + sy)
            B = dt["box"]
            C = (E[0] + n[0] * B / 2, E[1] + n[1] * B / 2)
            box = [
                (C[0] - B / 2, C[1] - B / 2),
                (C[0] + B / 2, C[1] - B / 2),
                (C[0] + B / 2, C[1] + B / 2),
                (C[0] - B / 2, C[1] + B / 2),
            ]
            prims = [tri, Line(apex, E, "thin")] + [
                Line(p, q, "thin") for p, q in zip(box, box[1:] + box[:1])
            ]
            prims.append(
                make_text(el._intent["letter"], C, std["dim"]["text_height"], std, layer="text")
            )
            fields = {"length": L, "at": frac}
            out.append(_cand(prims, fields))
    return out


# -- geometric tolerance symbols, drawn in a cell of size c centred on the origin ----------------


def gtol_symbol(char, c):
    k = c * 0.32
    L = lambda a, b: Line(a, b, "thin")  # noqa: E731
    if char == "straightness":
        return [L((-k, 0), (k, 0))]
    if char == "flatness":
        p = [(-k, -k * 0.5), (k * 0.6, -k * 0.5), (k, k * 0.5), (-k * 0.6, k * 0.5)]
        return [L(a, b) for a, b in zip(p, p[1:] + p[:1])]
    if char == "circularity":
        return [Circle((0, 0), k * 0.8, "thin")]
    if char == "cylindricity":
        return [
            Circle((0, 0), k * 0.6, "thin"),
            L((-k, -k), (-k * 0.2, k)),
            L((k * 0.2, -k), (k, k)),
        ]
    if char == "profile_line":
        return [Arc((0, -k * 0.4), k * 0.9, 0, 180, "thin")]
    if char == "profile_surface":
        return [
            Arc((0, -k * 0.4), k * 0.9, 0, 180, "thin"),
            L((-k * 0.9, -k * 0.4), (k * 0.9, -k * 0.4)),
        ]
    if char == "parallelism":
        return [L((-k, -k), (-k * 0.2, k)), L((k * 0.2, -k), (k, k))]
    if char == "perpendicularity":
        return [L((-k, -k), (k, -k)), L((0, -k), (0, k))]
    if char == "angularity":
        return [L((-k, -k), (k, -k)), L((-k, -k), (k, k * 0.2))]
    if char == "position":
        return [Circle((0, 0), k * 0.6, "thin"), L((-k, 0), (k, 0)), L((0, -k), (0, k))]
    if char == "concentricity":
        return [Circle((0, 0), k * 0.8, "thin"), Circle((0, 0), k * 0.4, "thin")]
    if char == "symmetry":
        return [
            L((-k * 0.6, k * 0.6), (k * 0.6, k * 0.6)),
            L((-k, 0), (k, 0)),
            L((-k * 0.6, -k * 0.6), (k * 0.6, -k * 0.6)),
        ]
    if char == "circular_runout":
        return [
            L((-k * 0.6, -k), (k * 0.6, k)),
            Solid(((k * 0.6, k), (k * 0.15, k * 0.55), (k * 0.6, k * 0.35)), "thin"),
        ]
    # total runout
    return [
        L((-k, -k), (k * 0.2, -k)),
        L((-k, -k), (-k * 0.4, k)),
        L((-k * 0.2, -k), (k * 0.4, k)),
        Solid(((-k * 0.4, k), (-k * 0.75, k * 0.45), (-k * 0.4, k * 0.3)), "thin"),
        Solid(((k * 0.4, k), (k * 0.05, k * 0.45), (k * 0.4, k * 0.3)), "thin"),
    ]


def gtol_frame(i, std):
    """Frame prims with its lower-left corner at the origin → (prims, w, h)."""
    from .annotate import fmt_num

    STD[0] = std
    c = std["tolerancing"]["frame_height"]
    h = std["dim"]["text_height"]
    prims = [p for p in transform(gtol_symbol(i["char"], c), 0, c / 2, c / 2)]
    x = c
    val = ("Φ" if i["zone"] == "dia" else "SΦ" if i["zone"] == "sphere" else "") + fmt_num(
        i["value"], 4
    )
    tw = text_size(val, h, std)[0]
    mods = [m for m in i["modifiers"]]
    mw = sum(h * 1.2 for _ in mods)
    w1 = tw + mw + 2.0
    prims.append(make_text(val, (x + 1 + tw / 2, c / 2), h, std, layer="text"))
    mx = x + 1 + tw + h * 0.6
    for m in mods:
        if m in ("M", "L", "P", "F"):
            prims.append(Circle((mx, c / 2), h * 0.55, "thin"))
            prims.append(make_text(m, (mx, c / 2), h * 0.7, std, layer="text"))
        else:
            prims.append(make_text(m, (mx, c / 2), h * 0.7, std, layer="text"))
        mx += h * 1.2
    x += w1
    cells = [c, x]
    for ds in i["datums"]:
        t = "-".join(ds["letters"]) + "".join(f"({m})" for m in ds["modifiers"])
        tw = text_size(t, h, std)[0]
        cw = max(c, tw + 2.0)
        prims.append(make_text(t, (x + cw / 2, c / 2), h, std, layer="text"))
        x += cw
        cells.append(x)
    W = x
    prims += [
        Line((0, 0), (W, 0), "thin"),
        Line((0, c), (W, c), "thin"),
        Line((0, 0), (0, c), "thin"),
    ]
    prims += [Line((cx, 0), (cx, c), "thin") for cx in cells]
    return prims, W, c


def gtol_cands(vl, el):
    std = vl.std
    frame, W, H = gtol_frame(el._intent, std)
    out = []
    for frac in _fracs(el):
        an = _anchor(vl, el, frac)
        if an is None:
            return []
        A, n = an
        for L in _lens(el._layout, std):
            sx, sy = _shift(el)
            E = (A[0] + n[0] * L + sx, A[1] + n[1] * L + sy)
            prims = [Line(E, A, "thin"), arrow(A, (-n[0], -n[1]), std, "thin")]
            if abs(n[1]) >= abs(n[0]):  # leader meets the frame's bottom / top at the first cell
                ox = E[0] - H / 2
                oy = E[1] if n[1] > 0 else E[1] - H
            else:
                ox = E[0] if n[0] > 0 else E[0] - W
                oy = E[1] - H / 2
            prims += transform(frame, 0, ox, oy)
            fields = {"length": L, "at": frac}
            out.append(_cand(prims, fields))
    return out


# -- roughness ------------------------------------------------------------------------------------


def rough_symbol(i, std, with_text=True):
    """Symbol with its tip at the origin, upright → prims (GB/T 131-2006)."""
    from .annotate import fmt_num

    STD[0] = std
    rg = std["rough"]
    h = std["dim"]["text_height"]
    H1, H2 = rg["h1"], rg["h2"]
    t60 = math.tan(math.radians(30))
    p_short = (-H1 * t60, H1)
    p_long = (H2 * t60, H2)
    prims = [Line((0, 0), p_short, "thin"), Line((0, 0), p_long, "thin")]
    if i["removal"] == "required":
        prims.append(Line(p_short, (H1 * t60, H1), "thin"))
    elif i["removal"] == "forbidden":
        prims.append(Circle((0, H1 * 0.55), H1 * 0.3, "thin"))
    if with_text:
        txt = f"{i['param']} {fmt_num(i['value'], 4)}"
        w = text_size(txt, h, std)[0]
        proc = i.get("process")
        wp = text_size(proc, h, std)[0] if proc else 0
        Lh = max(w, wp) + 2
        prims.append(Line(p_long, (p_long[0] + Lh, H2), "thin"))
        prims.append(make_text(txt, (p_long[0] + 1 + w / 2, H2 - 1 - h / 2), h, std, layer="text"))
        if proc:
            prims.append(
                make_text(proc, (p_long[0] + 1 + wp / 2, H2 + 1 + h * 0.55), h, std, layer="text")
            )
    return prims


def rough_cands(vl, el):
    std = vl.std
    sym = rough_symbol(el._intent, std)
    out, direct = [], []
    for frac in _fracs(el):
        an = _anchor(vl, el, frac)
        if an is None:
            return []
        A, n = an
        direct_up = n[1] > 0.85
        direct_left = n[0] < -0.85
        if direct_up or direct_left:
            prims = transform(sym, 0 if direct_up else 90, A[0], A[1])
            fields = {"at": frac}
            c = _cand(prims, fields)
            c["mode"] = "direct"
            direct.append(c)
        lift = std["rough"]["h2"] + 3 if n[1] < -0.3 else 0.0  # symbol stands clear of the part
        bx0, _, bx1, _ = prims_bbox(sym)
        for L in _lens(el._layout, std):
            L = L + lift if not el._layout.get("length") else L
            for tilt in (0, 35, -35):
                u = _rot(n, tilt)
                for side in (1, -1) if n[0] >= 0 else (-1, 1):
                    sx, sy = _shift(el)
                    E = (A[0] + u[0] * L + sx, A[1] + u[1] * L + sy)
                    if side > 0:
                        tip = (E[0] - bx0 + 1, E[1])
                        S = (tip[0] + bx1 + 1, E[1])
                    else:
                        S = (E[0] - (bx1 - bx0) - 2, E[1])
                        tip = (S[0] - bx0 + 1, E[1])
                    prims = [Line(E, A, "thin"), arrow(A, (-u[0], -u[1]), std, "thin"), Line(E, S, "thin")]
                    prims += transform(sym, 0, tip[0], tip[1])
                    c = _cand(prims, {"length": L, "at": frac})
                    c["mode"] = "leader"
                    out.append(c)
    return direct + out  # standing on the surface first, a leader when that is crowded


def rough_default_prims(el, std, right, bottom):
    """'Symbol + (basic symbol)' with its right end at x=right, bottom at y=bottom."""
    sym = rough_symbol(el._intent, std)
    basic = rough_symbol({"removal": "any", "param": "", "value": 0}, std, with_text=False)
    h = std["dim"]["text_height"]
    b1 = prims_bbox(sym)
    b2 = prims_bbox(basic)
    hp = next((v for v in std["text"]["heights"] if v > h), h)  # brackets one size up
    wpar = text_size("(", hp, std)[0]
    total = (b1[2] - b1[0]) + 2 + wpar * 2 + (b2[2] - b2[0]) + 1
    x0 = right - total
    prims = transform(sym, 0, x0 - b1[0], bottom - b1[1])
    x = x0 + (b1[2] - b1[0]) + 2
    mid = bottom + (b2[3] - b2[1]) / 2
    prims.append(make_text("(", (x + wpar / 2, mid), hp, std, layer="text"))
    x += wpar
    prims += transform(basic, 0, x - b2[0], bottom - b2[1])
    x += b2[2] - b2[0]
    prims.append(make_text(")", (x + wpar / 2, mid), hp, std, layer="text"))
    return prims


def union_box(prims):
    return union([prims_bbox(prims)])


# ---- rich text: drafting symbols drawn as geometry (depth ↧, spline ⨅) ---------------------------

SYMBOLS = "↧⨅"


def _symbol(ch, x, h):
    """Symbol in an em box [x, x + 0.8h] centred on y = 0."""
    w = 0.8 * h
    m = x + w / 2
    if ch == "↧":  # depth: stem down to a bar (GB/T 16675.2)
        return [
            Line((m, h * 0.45), (m, -h * 0.45), "text"),
            Line((x + w * 0.15, -h * 0.45), (x + w * 0.85, -h * 0.45), "text"),
        ]
    # ⨅ rectangular spline symbol
    return [
        Line((x + w * 0.1, -h * 0.4), (x + w * 0.1, h * 0.4), "text"),
        Line((x + w * 0.1, h * 0.4), (x + w * 0.9, h * 0.4), "text"),
        Line((x + w * 0.9, h * 0.4), (x + w * 0.9, -h * 0.4), "text"),
    ]


def _runs(s):
    out, cur = [], ""
    for ch in s:
        if ch in SYMBOLS:
            if cur:
                out.append(cur)
                cur = ""
            out.append(ch)
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def rich_size(s, h, std):
    w = 0.0
    hh = text_size("M", h, std)[1]
    for r in _runs(s):
        if r in SYMBOLS:
            w += 0.8 * h + 0.3
        else:
            tw, th = text_size(r, h, std)
            w, hh = w + tw, max(hh, th)
    return w, hh


def rich_text(s, at, h, std, layer="text"):
    """Text with drafting symbols, centred at ``at`` → (prims, box)."""
    STD[0] = std
    w, hh = rich_size(s, h, std)
    x = -w / 2
    prims = []
    for r in _runs(s):
        if r in SYMBOLS:
            prims += _symbol(r, x + 0.15, h)
            x += 0.8 * h + 0.3
        else:
            tw = text_size(r, h, std)[0]
            prims.append(make_text(r, (x + tw / 2, 0.0), h, std, layer=layer))
            x += tw
    prims = transform(prims, 0, at[0], at[1])
    return prims, (at[0] - w / 2, at[1] - hh / 2, at[0] + w / 2, at[1] + hh / 2)


def center_hole_cands(vl, el):
    """GB/T 4459.5 simplified representation: leader from the axis end, keep symbol, designation."""
    i = el._intent
    std = vl.std
    h = std["dim"]["text_height"]
    A = vl.P((i["x"], i["axis"]))
    sg = -1 if i["end"] == "left" else 1
    text = f"{i['mark_std']}-{i['designation']}"
    w, hh = text_size(text, h, std)
    out = []
    for ang, L in [(a, L) for L in (8.0, 14.0, 20.0) for a in (60, 45, -60, -45)]:
        u = (sg * math.cos(math.radians(ang)), math.sin(math.radians(ang)))
        E = (A[0] + u[0] * L, A[1] + u[1] * L)
        sym = 4.0 if i["keep"] is not None else 0.0
        S = (E[0] + sg * (w + sym + 2), E[1])
        prims = [Line(A, E, "thin"), arrow(A, (-u[0], -u[1]), std, "thin"), Line(E, S, "thin")]
        if (
            i["keep"] is not None
        ):  # 60° mark opening toward the text; crossed when it must not remain
            ap = (E[0] + sg * 0.8, E[1] + 1.2)
            k = 3.0
            p1 = (ap[0] + sg * k, ap[1] + k * math.tan(math.radians(30)))
            p2 = (ap[0] + sg * k, ap[1] - k * math.tan(math.radians(30)))
            prims += [Line(ap, p1, "thin"), Line(ap, p2, "thin")]
            if i["keep"] is False:
                prims.append(
                    Line((ap[0] + sg * 1.5, ap[1] + 2), (ap[0] + sg * 1.5, ap[1] - 2), "thin")
                )
        prims.append(
            make_text(
                text, (E[0] + sg * (sym + 1 + w / 2), E[1] + 1 + hh / 2), h, std, layer="text"
            )
        )
        out.append(_cand(prims, {"dir": ang, "length": L}))
    return out
