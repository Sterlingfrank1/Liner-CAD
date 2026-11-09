"""轴承座的 3D 模型（build123d）。模型轴：X 向右（长），Y 向后（宽，轴承孔轴线方向），Z 向上；
原点在底面中心，轴承孔轴线在 Z = Hc。"""

from build123d import Box, Cylinder, Pos, Rot


def ycyl(r, y0, y1, hc, x=0.0):
    """沿 Y 轴的圆柱：y0..y1，轴线 (x, hc)。"""
    return Pos(x, (y0 + y1) / 2, hc) * Rot(90, 0, 0) * Cylinder(r, y1 - y0)


def model(
    L=120, W=80, t=14, Hc=60, R=32, Ly=64, db=40, dc=46, cd=3,
    rw=10, dh=13, ex=45, ey=28, Db=18, hb=4, dp=8,
):  # fmt: skip
    y1 = Ly / 2
    body = Pos(0, 0, t / 2) * Box(L, W, t)
    body += Pos(0, 0, (t + Hc) / 2) * Box(rw, Ly, Hc - t)  # 竖向肋板（x = 0 平面内）
    body += ycyl(R, -y1, y1, Hc)
    body += Pos(0, 0, Hc + R + hb / 2) * Cylinder(Db / 2, hb)  # 油孔凸台
    body -= ycyl(db / 2, -y1 - 1, y1 + 1, Hc)  # 轴承孔
    for s in (-1, 1):  # 两端密封沉孔
        body -= ycyl(dc / 2, min(s * y1, s * (y1 - cd)), max(s * y1, s * (y1 - cd)), Hc)
    body -= Pos(0, 0, Hc + (R + hb) / 2) * Cylinder(dp / 2, R + hb + 2)  # 油孔
    for x in (-ex, ex):
        for y in (-ey, ey):
            body -= Pos(x, y, t / 2) * Cylinder(dh / 2, t + 2)
    return body
