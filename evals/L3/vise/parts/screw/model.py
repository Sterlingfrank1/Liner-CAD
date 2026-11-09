"""螺杆（机用虎钳）：左端伸入活动钳身的方块螺母，螺纹段按大径；轴肩贴固定钳身凸台内侧，右端有销孔。
装配坐标：轴线沿 X、Z=30。"""

from build123d import Cylinder, Pos, Rot


def xcyl(r, x0, x1, y, z):
    return Pos((x0 + x1) / 2, y, z) * Rot(0, 90, 0) * Cylinder(r, x1 - x0)


def model(x0=78, x1=172, d=16, ax=30, cx0=124, cx1=130, cd=22, px=156, pd=6):
    """x0~x1 全长、d 螺纹大径、ax 轴线高度；cx0~cx1 × cd 轴肩（右端面贴凸台内侧 X=130）；
    px 处 Φpd 横销孔（沿 Z）。"""
    s = xcyl(d / 2, x0, x1, 0, ax) + xcyl(cd / 2, cx0, cx1, 0, ax)
    return s - Pos(px, 0, ax) * Cylinder(pd / 2, d + 2)
