"""螺杆（千斤顶）：螺纹段按大径圆柱，头部有横孔穿铰杠，顶部凸台带防脱环槽。装配坐标：轴线沿 Z。"""

from build123d import Cylinder, Pos, Rot


def cyl(r, z0, z1):
    return Pos(0, 0, (z0 + z1) / 2) * Cylinder(r, z1 - z0)


def model(d=28, z0=18, zh=108, hh=18, hd=40, bd=20, bh=20, hole=12, gz=136, gw=9, gr=6):
    """d 螺纹大径、z0 下端高度；zh 头部下端、hh×hd 头部；bd×bh 顶部凸台；hole 铰杠孔径；
    gz/gw/gr 环槽中心高度、槽宽、槽底半径（紧定螺钉锥端落在槽里）。"""
    s = cyl(d / 2, z0, zh) + cyl(hd / 2, zh, zh + hh) + cyl(bd / 2, zh + hh, zh + hh + bh)
    s = s - Pos(0, 0, zh + hh / 2) * Rot(0, 90, 0) * Cylinder(hole / 2, hd + 2)
    ring = cyl(bd / 2 + 1, gz - gw / 2, gz + gw / 2) - cyl(gr, gz - gw / 2 - 1, gz + gw / 2 + 1)
    return s - ring
