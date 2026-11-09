"""底座（千斤顶）。装配坐标：轴线沿 Z 过原点，底面 Z=0。"""

from build123d import Cone, Cylinder, Pos


def cyl(r, z0, z1):
    return Pos(0, 0, (z0 + z1) / 2) * Cylinder(r, z1 - z0)


def model(Dn=44, R=50, tp=8, Rb=36, Rt=30, H=70, floor=14):
    """Dn 螺套孔径；R 底板半径、tp 底板厚；Rb/Rt 锥身下/上半径；H 座高；floor 孔底高度。"""
    body = cyl(R, 0, tp) + Pos(0, 0, (tp + H) / 2) * Cone(Rb, Rt, H - tp)
    return body - cyl(Dn / 2, floor, H + 1)
