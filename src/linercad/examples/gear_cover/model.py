"""齿轮箱盖的 3D 模型（build123d）。model(**P) 接收图纸参数，返回实体。
模型轴：X 向右（长），Y 向后（宽），Z 向上（高）；原点在底面中心。"""

from build123d import Box, Cylinder, Pos


def model(L=150, W=110, t=10, A=110, B=70, H=55, s=5, D=46, h=12, d=28, dh=11, e=10):
    body = Pos(0, 0, t / 2) * Box(L, W, t) + Pos(0, 0, H / 2) * Box(A, B, H)
    body = body - Pos(0, 0, (H - s) / 2 - 1) * Box(A - 2 * s, B - 2 * s, H - s + 2)
    body = body + Pos(0, 0, H + h / 2) * Cylinder(D / 2, h)
    body = body - Pos(0, 0, H + h / 2) * Cylinder(d / 2, h + 2 * s)
    for x in (-L / 2 + e, L / 2 - e):
        for y in (-W / 2 + e, W / 2 - e):
            body = body - Pos(x, y, t / 2) * Cylinder(dh / 2, t + 2)
    return body
