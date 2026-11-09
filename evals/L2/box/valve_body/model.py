"""阀体的 3D 模型（build123d）。模型轴：X 向右（通道方向），Y 向后，Z 向上；原点在通道轴线中点。"""

import math

from build123d import Cylinder, Pos, Rot


def xcyl(r, x0, x1):
    return Pos((x0 + x1) / 2, 0, 0) * Rot(0, 90, 0) * Cylinder(r, x1 - x0)


def zcyl(r, z0, z1):
    return Pos(0, 0, (z0 + z1) / 2) * Cylinder(r, z1 - z0)


def model(
    Lm=100, Do=44, Di=28, Fd=76, Ft=10, pcd=58, fh=9,
    Dn=40, Hn=56, Bd=64, Bt=8, bpcd=50, bh=7, Dv=22, Ds=30, ds=8,
):  # fmt: skip
    x1 = Lm / 2
    body = xcyl(Do / 2, -x1, x1)
    for s in (-1, 1):  # 两端法兰
        body += xcyl(Fd / 2, min(s * x1, s * (x1 - Ft)), max(s * x1, s * (x1 - Ft)))
    body += zcyl(Dn / 2, 0, Hn - Bt)  # 上部阀颈
    body += zcyl(Bd / 2, Hn - Bt, Hn)  # 阀盖法兰
    body -= xcyl(Di / 2, -x1 - 1, x1 + 1)  # 通道
    body -= zcyl(Dv / 2, 0, Hn + 1)  # 阀杆孔
    body -= zcyl(Ds / 2, Hn - ds, Hn + 1)  # 填料函沉孔
    for k in range(4):
        a = math.radians(90 * k)  # 管口法兰孔在水平 / 竖直轴上
        y, z = pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)
        for s in (-1, 1):
            body -= Pos(s * (x1 - Ft / 2), y, z) * Rot(0, 90, 0) * Cylinder(fh / 2, Ft + 2)
        a = math.radians(45 + 90 * k)  # 阀盖法兰孔跨轴线
        x, y = bpcd / 2 * math.cos(a), bpcd / 2 * math.sin(a)
        body -= Pos(x, y, Hn - Bt / 2) * Cylinder(bh / 2, Bt + 2)
    return body
