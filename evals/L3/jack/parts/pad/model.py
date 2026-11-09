"""顶垫（千斤顶）：套在螺杆顶部凸台上，侧面 M8 紧定螺钉孔。装配坐标：轴线沿 Z，下端 Z=126。"""

from build123d import Cylinder, Pos, Rot


def cyl(r, z0, z1):
    return Pos(0, 0, (z0 + z1) / 2) * Cylinder(r, z1 - z0)


def model(PD=52, pt=10, sd=36, bore=20, sh=20, z0=126, sz=136, sdia=8):
    """PD×pt 承压盘；sd 裙部外径、sh 裙高；bore 凸台孔径（与螺杆凸台相贴）；
    z0 下端高度；sz×sdia 紧定螺钉孔（沿 +X 径向，螺纹按大径）。"""
    p = cyl(PD / 2, z0 + sh, z0 + sh + pt) + cyl(sd / 2, z0, z0 + sh)
    p = p - cyl(bore / 2, z0 - 1, z0 + sh)
    return p - Pos((sd / 2 + 2) / 2, 0, sz) * Rot(0, 90, 0) * Cylinder(sdia / 2, sd / 2 + 2)
