"""V 带轮：轮缘宽 40，2 个 V 槽（槽口宽 11、深 11、槽角 34°，槽距 18，f=11），轮缘外径 Φ120
两端 C1，轮缘内径 Φ84，轮毂 Φ60，孔 Φ28 带 GB/T 1095 轮毂键槽（b=8，深 d+3.3，朝 +Z），
腹板厚 10、两侧各凹进 15。"""

import math

from build123d import Axis, Box, Face, Polyline, Pos, revolve


def lathe(pts):
    """Closed (x, r) polygon revolved about the X axis."""
    return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)


def model():
    da, di, Dh, d0 = 120, 84, 60, 28
    e, f, bg, hg, ang, tw = 18, 11, 11, 11, 34, 10
    Ro, Ri, Rh, r0 = da / 2, di / 2, Dh / 2, d0 / 2
    B = 2 * f + e
    w = bg / 2
    wb = w - hg * math.tan(math.radians(ang / 2))
    c1, c2 = f, f + e
    outline = [(0, Ro - 1), (1, Ro)]
    for c in (c1, c2):
        outline += [(c - w, Ro), (c - wb, Ro - hg), (c + wb, Ro - hg), (c + w, Ro)]
    outline += [(B - 1, Ro), (B, Ro - 1)]
    part = lathe([(0, r0)] + outline + [(B, r0)])
    xa, xb = (B - tw) / 2, (B + tw) / 2
    part -= lathe([(-1, Rh), (-1, Ri), (xa, Ri), (xa, Rh)])  # left recess
    part -= lathe([(xb, Rh), (xb, Ri), (B + 1, Ri), (B + 1, Rh)])  # right recess
    key = 3.3  # GB/T 1095: hub keyway depth t2 for d = 28, width b = 8
    part -= Pos(B / 2, 0, (r0 + key) / 2) * Box(B + 2, 8, r0 + key)
    return part
