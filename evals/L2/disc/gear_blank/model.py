"""齿轮坯：齿顶圆 Φ126×30（两端 C1.5），轮毂 Φ60 总长 45，孔 Φ32 带 GB/T 1095 键槽（b=10，深 d+3.3，朝 +Z），
6×Φ16 减轻孔均布在 Φ92 圆周上（首个在正上方）。"""

import math

from build123d import Axis, Box, Cylinder, Face, Polyline, Pos, Rot, revolve


def lathe(pts):
    """Closed (x, r) polygon revolved about the X axis."""
    return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)


def model():
    da, B, L, Dh, d0, pcd, dl = 126, 30, 45, 60, 32, 92, 16
    R, Rh, r0 = da / 2, Dh / 2, d0 / 2
    part = lathe(
        [(0, r0), (0, R - 1.5), (1.5, R), (B - 1.5, R), (B, R - 1.5), (B, Rh), (L, Rh), (L, r0)]
    )
    for k in range(6):  # end view (u = −Y, v = Z): 90° + k·60°
        a = math.radians(90 + 60 * k)
        part -= (
            Pos(B / 2, -pcd / 2 * math.cos(a), pcd / 2 * math.sin(a))
            * Rot(0, 90, 0)
            * Cylinder(dl / 2, B + 2)
        )
    key = 3.3  # GB/T 1095: hub keyway depth t2 for d = 32, width b = 10
    part -= Pos(L / 2, 0, (r0 + key) / 2) * Box(L + 2, 10, r0 + key)
    return part
