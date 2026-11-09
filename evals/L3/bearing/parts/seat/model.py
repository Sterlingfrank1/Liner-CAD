"""轴承座（滑动轴承）。装配坐标：轴线沿 Y 过原点，剖分面 Z=0，座在剖分面之下，Z 向上。"""

from build123d import Box, Cylinder, Pos, Rot


def model(D=48, L=120, W=44, H=45, FL=170, ft=12, hd=13, bs=42, bd=10, pw=24, pd=14):
    """D 轴衬外径（座孔径）；L×W×H 座体；FL 底板长、ft 底板厚、hd 安装孔径；
    bs 螺栓中心到轴线的距离、bd 螺栓孔径（取螺栓大径，与螺栓相贴）、pw×pd 螺母凹槽。"""
    body = Pos(0, 0, -H / 2) * Box(L, W, H) + Pos(0, 0, -H + ft / 2) * Box(FL, W, ft)
    body = body - Rot(90, 0, 0) * Cylinder(D / 2, W + 2)
    for s in (-1, 1):
        body = body - Pos(s * bs, 0, -H / 2) * Cylinder(bd / 2, H + 2)  # 螺栓孔
        body = body - Pos(s * bs, 0, -H + pd / 2) * Box(pw, pw, pd)  # 螺母凹槽
        body = body - Pos(s * (FL / 2 - 13), 0, -H + ft / 2) * Cylinder(hd / 2, ft + 2)  # 安装孔
    return body
