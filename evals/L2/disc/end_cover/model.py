"""端盖：盖板 Φ110×16，止口 Φ70 长 8（端部 C1），孔 Φ40 通、Φ52 沉孔自止口端深 6，
3×M8 螺孔（按小径 Φ6.647 建光圆孔，钻深 12.5，120° 钻尖）均布在 Φ85 圆周上，首个在正上方。"""

import math

from build123d import Axis, Face, Polyline, Pos, revolve


def lathe(pts):
    """Closed (x, r) polygon revolved about the X axis."""
    return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)


def model():
    D, T, Ls, ds, d0, lb, dc, pcd = 110, 16, 24, 70, 40, 18, 52, 85
    d1, depth = 6.647, 12.5  # M8 minor diameter (GB/T 196), drilled depth
    part = lathe(
        [
            (0, d0 / 2),
            (0, D / 2),
            (T, D / 2),
            (T, ds / 2),
            (Ls - 1, ds / 2),
            (Ls, ds / 2 - 1),
            (Ls, dc / 2),
            (lb, dc / 2),
            (lb, d0 / 2),
        ]
    )
    tip = d1 / 2 / math.tan(math.radians(60))
    tool = lathe([(-1, 0), (-1, d1 / 2), (depth, d1 / 2), (depth + tip, 0)])
    for k in range(3):  # end view (u = −Y, v = Z): 90°, 210°, 330°
        a = math.radians(90 + 120 * k)
        part -= Pos(0, -pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)) * tool
    return part
