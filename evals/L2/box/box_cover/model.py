"""减速器箱盖（简化）的 3D 模型（build123d）。模型轴：X 向右（长），Y 向后（宽，轴承孔轴线方向），
Z 向上（高）；原点在结合面（箱盖下平面）中心，轴承半圆孔轴线在 Z = 0。"""

from build123d import Box, Cylinder, Pos, Rot


def ycyl(r, y0, y1, x, z=0.0):
    """沿 Y 轴的圆柱：y0..y1，轴线 (x, z)。"""
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(r, y1 - y0)


def model(
    A=100, B=64, H=40, s=6, fw=12, tf=9, xa=26, d1=38, D1=48, d2=30, D2=40, bl=8,
    Dv=28, hv=5, dv=12, dh=9, hx=56, hy=38,
):  # fmt: skip
    yb = B / 2 + bl
    body = Pos(0, 0, H / 2) * Box(A, B, H)  # 箱盖外形
    body += Pos(0, 0, tf / 2) * Box(A + 2 * fw, B + 2 * fw, tf)  # 结合面凸缘
    body += ycyl(D1 / 2, -yb, yb, -xa) + ycyl(
        D2 / 2, -yb, yb, xa
    )  # 轴承凸台（下半在结合面以下，稍后截去）
    body += Pos(0, 0, H + hv / 2) * Cylinder(Dv / 2, hv)  # 通气孔凸台
    body -= Pos(0, 0, (H - s - 1) / 2) * Box(A - 2 * s, B - 2 * s, H - s + 1)  # 内腔，下口敞开
    body -= ycyl(d1 / 2, -yb - 1, yb + 1, -xa) + ycyl(d2 / 2, -yb - 1, yb + 1, xa)  # 轴承半圆孔
    body -= Pos(0, 0, H + hv / 2 - s / 2) * Cylinder(dv / 2, hv + s + 2)  # 通气孔
    for x in (-hx, hx):
        for y in (-hy, hy):
            body -= Pos(x, y, tf / 2) * Cylinder(dh / 2, tf + 2)
    return body - Pos(0, 0, -50) * Box(400, 400, 100)  # 结合面以下不要
