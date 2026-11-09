"""泵体的 3D 模型（build123d）。model(**P) 接收图纸参数，返回实体。
模型轴：X 向右（泵轴方向），Y 向后（宽），Z 向上（高）；原点在底面中心，泵轴在 Z = Hc。"""

import math

from build123d import Box, Cylinder, Pos, Rot


def xcyl(r, x0, x1, hc):
    """沿 X 轴的圆柱：x0..x1，轴线 (y = 0, z = hc)。"""
    return Pos((x0 + x1) / 2, 0, hc) * Rot(0, 90, 0) * Cylinder(r, x1 - x0)


def model(
    L=120, W=84, t=10, Hc=60, Ro=26, Rc=18, Lh=80, tw=18,
    Df=76, tf=10, pcd=62, dfh=8, dr=20, dcb=30, cbd=6,
    Db=30, hb=6, bx=-8, dp=14, rw=8, dh=11, ex=50, ey=30,
):  # fmt: skip
    x0, x1 = -Lh / 2, Lh / 2
    body = Pos(0, 0, t / 2) * Box(L, W, t)
    # 肋板在 y = 0 平面内（厚 rw）：从底板上表面到壳体底部，向上伸到轴线以便并入壳体
    body += Pos(0, 0, (t + Hc) / 2) * Box(Lh - 2 * tf, rw, Hc - t)
    body += xcyl(Ro, x0, x1, Hc)
    body += xcyl(Df / 2, x0, x0 + tf, Hc)
    body += Pos(bx, 0, Hc + (Ro + hb) / 2) * Cylinder(Db / 2, Ro + hb)
    # 内腔：泵腔 + 轴承孔 + 密封沉孔 + 进油孔
    body -= xcyl(Rc, x0 - 1, x1 - tw, Hc)
    body -= xcyl(dr / 2, x1 - tw - 1, x1 + 1, Hc)
    body -= xcyl(dcb / 2, x1 - cbd, x1 + 1, Hc)
    body -= Pos(bx, 0, Hc + (Ro + hb) / 2) * Cylinder(dp / 2, Ro + hb + 2)
    # 法兰螺栓孔：4 × dfh，分布圆 pcd，45° 起
    for k in range(4):
        a = math.radians(45 + 90 * k)
        y, z = pcd / 2 * math.cos(a), Hc + pcd / 2 * math.sin(a)
        body -= Pos(x0 + tf / 2, y, z) * Rot(0, 90, 0) * Cylinder(dfh / 2, tf + 2)
    # 底板安装孔
    for x in (-ex, ex):
        for y in (-ey, ey):
            body -= Pos(x, y, t / 2) * Cylinder(dh / 2, t + 2)
    return body
