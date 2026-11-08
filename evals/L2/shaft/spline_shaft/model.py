"""花键轴：左端矩形花键 6×23×26×6（齿顶在 ±Z 方向），其余为回转台阶；无中心孔，右端倒角 C1.5。"""

from build123d import Axis, Box, Cylinder, Polygon, Pos, Rot, revolve

N, d, D, B = 6, 23.0, 26.0, 6.0  # GB/T 1144 6×23×26×6
SPLINE_LEN = 36.0
BODY = [  # (x, r) of the upper half right of the spline
    (36, 0), (36, 15), (66, 15), (66, 19), (76, 19), (76, 15), (118.5, 15), (120, 13.5), (120, 0),
]  # fmt: skip


def splined(x0, x1):
    """Rectangular spline: minor cylinder + N teeth of width B, trimmed to the major diameter."""
    length = x1 - x0
    ax = Rot(0, 90, 0)
    core = Pos((x0 + x1) / 2, 0, 0) * ax * Cylinder(d / 2, length)
    for k in range(N):
        core = core + Rot(360 / N * k, 0, 0) * Pos((x0 + x1) / 2, 0, (D / 2 + 1) / 2) * Box(
            length, B, D / 2 + 1
        )
    return core & (Pos((x0 + x1) / 2, 0, 0) * ax * Cylinder(D / 2, length))


def model():
    return revolve(Polygon(*BODY, align=None), Axis.X) + splined(0, SPLINE_LEN)
