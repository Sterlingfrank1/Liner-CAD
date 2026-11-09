"""铰杠（千斤顶）：沿 X 穿过螺杆头部横孔，两端圆球。装配坐标：杆心在 X=Y=0，高度 Z=z。"""

from build123d import Cylinder, Pos, Rot, Sphere


def model(d=12, L=150, bd=16, z=117):
    """d 杆径（与螺杆横孔相贴）、L 杆长（两球心距）、bd 端球直径、z 杆心高度。"""
    bar = Pos(0, 0, z) * Rot(0, 90, 0) * Cylinder(d / 2, L)
    for s in (-1, 1):
        bar = bar + Pos(s * L / 2, 0, z) * Sphere(bd / 2)
    return bar
