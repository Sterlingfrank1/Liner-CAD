"""减速器箱座（简化）的 3D 模型（build123d）。模型轴：X 向右（长），Y 向后（宽，轴承孔轴线方向），
Z 向上（高）；原点在底面中心，两个轴承孔轴线在 Z = Hc，X = ±xa。"""

from build123d import Box, Cylinder, Pos, Rot


def ycyl(r, y0, y1, hc, x):
    """沿 Y 轴的圆柱：y0..y1，轴线 (x, hc)。"""
    return Pos(x, (y0 + y1) / 2, hc) * Rot(90, 0, 0) * Cylinder(r, y1 - y0)


def model(
    L=160, W=108, t=10, A=100, B=64, H=64, s=6, fw=12, tf=9, Hc=32, xa=26,
    d1=38, D1=46, d2=30, D2=40, bl=8, dh=12, ex=70, ey=45, fh=7, fx=35, fy=38,
):  # fmt: skip
    yb = B / 2 + bl  # 轴承凸台外端面
    body = Pos(0, 0, t / 2) * Box(L, W, t)  # 底板
    body += Pos(0, 0, H / 2) * Box(A, B, H)  # 箱体外形
    body += Pos(0, 0, H - tf / 2) * Box(A + 2 * fw, B + 2 * fw, tf)  # 上部结合面凸缘
    body += ycyl(D1 / 2, -yb, yb, Hc, -xa) + ycyl(D2 / 2, -yb, yb, Hc, xa)  # 轴承凸台
    body -= Pos(0, 0, (H + t) / 2 + 0.5) * Box(A - 2 * s, B - 2 * s, H - t + 1)  # 内腔，上口敞开
    body -= ycyl(d1 / 2, -yb - 1, yb + 1, Hc, -xa) + ycyl(d2 / 2, -yb - 1, yb + 1, Hc, xa)
    for x in (-ex, ex):
        for y in (-ey, ey):
            body -= Pos(x, y, t / 2) * Cylinder(dh / 2, t + 2)
    for x in (-fx, 0, fx):
        for y in (-fy, fy):
            body -= Pos(x, y, H - tf / 2) * Cylinder(fh / 2, tf + 2)
    return body
