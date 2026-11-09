"""螺套（千斤顶）：压入底座孔，带上端凸缘。装配坐标：轴线沿 Z，凸缘座在底座顶面 Z=H。"""

from build123d import Cylinder, Pos


def cyl(r, z0, z1):
    return Pos(0, 0, (z0 + z1) / 2) * Cylinder(r, z1 - z0)


def model(Dn=44, ID=28, floor=14, H=70, FD=60, ft=6):
    """Dn 外径（与底座孔相贴）；ID 内孔（螺纹按大径）；floor 套底高度；H 底座顶面高度；FD×ft 凸缘。"""
    s = cyl(Dn / 2, floor, H) + cyl(FD / 2, H, H + ft)
    return s - cyl(ID / 2, floor - 1, H + ft + 1)
