"""斜撑托架：底板 80×60×10（两个 Φ10 孔），后缘上斜 45° 接一块宽 56、厚 10 的斜板（沿斜面长 44），
斜板上开 26×16 的长方窗口。斜板的真形只能在垂直于斜面的方向（斜视图）看到。"""

import math

from build123d import Box, BuildSketch, Cylinder, Plane, Polygon, Pos, Rot, extrude


def model():
    c = s = math.sqrt(0.5)  # 45°
    t, Ls, ws, wl, w0 = 10.0, 44.0, 56.0, 16.0, 14.0  # 厚、斜面长、宽、窗口沿斜面长、窗口起点
    base = Pos(0, 0, 5) * Box(80, 60, 10)
    for sx in (-26, 26):
        base -= Pos(sx, -15, 5) * Cylinder(5, 20)
    b0 = (30.0, 10.0)  # (y, z)：斜板背面与底板上表面的交点，正好在底板后缘
    n = (-c, s)  # 斜板前表面的法向
    ext = 12.0  # 斜板下端埋进底板
    d0 = (b0[0] - ext * c, b0[1] - ext * s)
    d1 = (b0[0] + Ls * c, b0[1] + Ls * s)
    pts = [d0, d1, (d1[0] + t * n[0], d1[1] + t * n[1]), (d0[0] + t * n[0], d0[1] + t * n[1])]
    with BuildSketch(Plane.YZ) as sk:  # 在 (y, z) 平面画斜板断面，沿 X 对称拉伸
        Polygon(*pts, align=None)
    plate = extrude(sk.sketch, ws / 2, both=True)
    # 窗口：在斜面局部坐标（x = X，y = 沿斜面向上，z = 法向）建盒子，再转到斜面上
    mid = (w0 + wl / 2, t / 2)  # 沿斜面距离、沿法向距离
    cy = b0[0] + mid[0] * c + mid[1] * n[0]
    cz = b0[1] + mid[0] * s + mid[1] * n[1]
    window = Pos(0, cy, cz) * Rot(45, 0, 0) * Box(26, wl, 30)
    return base + plate - window
