"""下轴衬（半圆筒，带两端凸缘）。装配坐标：轴线沿 Y 过原点，Z ≤ 0。"""

from build123d import Box, Cylinder, Pos, Rot


def model(D=48, d=40, L=44, fl=3, fd=62):
    """D 外径（与座孔相贴）、d 内径、L 衬长（等于座宽）、fl 凸缘厚、fd 凸缘外径。"""
    tube = Rot(90, 0, 0) * Cylinder(D / 2, L)
    for s in (-1, 1):
        tube = tube + Pos(0, s * (L + fl) / 2, 0) * Rot(90, 0, 0) * Cylinder(fd / 2, fl)
    tube = tube - Rot(90, 0, 0) * Cylinder(d / 2, L + 2 * fl + 2)
    return tube & (Pos(0, 0, -fd / 2) * Box(fd + 2, L + 2 * fl + 2, fd))
