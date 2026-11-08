"""轴承透盖：盖板 Φ100×12，止口 Φ62 总长 22（端部 C1），通孔 Φ36（端面 C1）带矩形密封槽
Φ44×5（距外端面 4），4×Φ9 安装孔均布在 Φ80 圆周上（首个在正上方）。"""

import math

from build123d import Axis, Cylinder, Face, Polyline, Pos, Rot, revolve


def lathe(pts):
    """Closed (x, r) polygon revolved about the X axis."""
    return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)


def model():
    D, T, Ls, ds, d0, g0, gw, hg, pcd, dh = 100, 12, 22, 62, 36, 4, 5, 4, 80, 9
    R, rs, r0 = D / 2, ds / 2, d0 / 2
    rg = r0 + hg
    part = lathe(
        [
            (0, r0 + 1),
            (0, R),
            (T, R),
            (T, rs),
            (Ls - 1, rs),
            (Ls, rs - 1),
            (Ls, r0),
            (g0 + gw, r0),
            (g0 + gw, rg),
            (g0, rg),
            (g0, r0),
            (1, r0),
        ]
    )
    for k in range(4):  # end view (u = −Y, v = Z): 90° + k·90°
        a = math.radians(90 + 90 * k)
        part -= (
            Pos(T / 2, -pcd / 2 * math.cos(a), pcd / 2 * math.sin(a))
            * Rot(0, 90, 0)
            * Cylinder(dh / 2, T + 2)
        )
    return part
