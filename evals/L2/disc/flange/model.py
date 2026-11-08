"""法兰盘：盘 Φ120×15，凸台 Φ60 到总长 40，中心孔 Φ30，4×Φ12 在 Φ90 圆周上，凸台端 C1 倒角。"""

import math

from build123d import Axis, Cylinder, Face, Polyline, Pos, Rot, revolve


def lathe(pts):
    """Closed (x, r) polygon revolved about the X axis."""
    return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)


def model():
    D, Dh, d0, T, L, pcd, dh = 120, 60, 30, 15, 40, 90, 12
    part = lathe(
        [
            (0, d0 / 2),
            (0, D / 2),
            (T, D / 2),
            (T, Dh / 2),
            (L - 1, Dh / 2),
            (L, Dh / 2 - 1),
            (L, d0 / 2 + 1),
            (L - 1, d0 / 2),
        ]
    )
    for k in range(4):  # holes at 90° + k·90° in the end view (u = −Y, v = Z)
        a = math.radians(90 + 90 * k)
        y, z = -pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)
        part -= Pos(T / 2, y, z) * Rot(0, 90, 0) * Cylinder(dh / 2, T + 2)
    return part
