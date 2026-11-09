"""齿轮油泵泵体的 3D 模型（build123d）。模型轴：X 向右（长，进出油口方向），Y 向后（厚，齿轮轴线方向），
Z 向上（高）；原点在泵体中心（两齿轮轴线连线的中点）。"""

from build123d import Box, Cylinder, Pos, Rot


def ycyl(r, y0, y1, x, z):
    """沿 Y 轴的圆柱：y0..y1，轴线 (x, z)。"""
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(r, y1 - y0)


def xcyl(r, x0, x1, z=0.0):
    """沿 X 轴的圆柱：x0..x1，轴线 (y = 0, z)。"""
    return Pos((x0 + x1) / 2, 0, z) * Rot(0, 90, 0) * Cylinder(r, x1 - x0)


def model(L=96, W=30, H=64, cx=14, Rc=17, dp=14, dq=22, cb=6, dh=7, bx=36, bz=24, mz=26):
    y1 = W / 2 + 1
    body = Box(L, W, H)
    for s in (-1, 1):  # 两个齿轮腔（互相相交，8 字形），前后贯通
        body -= ycyl(Rc, -y1, y1, s * cx, 0)
    for s in (-1, 1):  # 进、出油口：油口孔通入齿轮腔，外端沉孔
        xi, xo = s * (cx + Rc - 3), s * (L / 2 + 1)
        body -= xcyl(dp / 2, min(xi, xo), max(xi, xo))
        xc = s * (L / 2 - cb)
        body -= xcyl(dq / 2, min(xc, xo), max(xc, xo))
    for x, z in [(sx * bx, sz * bz) for sx in (-1, 1) for sz in (-1, 1)] + [(0, -mz), (0, mz)]:
        body -= ycyl(dh / 2, -y1, y1, x, z)  # 6 个螺栓孔
    return body
