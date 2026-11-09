"""连杆：大头 Φ44（长 24，孔 Φ24）、小头 Φ28（长 18，孔 Φ12），中心距 100；杆身是两圆的外公切线围成的
平板（厚 8），正面（-Y 侧）有一条宽 6、高 3 的加强筋。孔轴线沿 Y。"""

import math

from build123d import Box, BuildSketch, Cylinder, Plane, Polygon, Pos, Rot, extrude


def model():
    L, R1, R2 = 100.0, 22.0, 14.0
    nx = (R1 - R2) / L
    ny = math.sqrt(1 - nx * nx)
    t1 = (R1 * nx, R1 * ny)  # tangent points on the big / small circle (upper side)
    t2 = (L + R2 * nx, R2 * ny)
    with BuildSketch(Plane.XZ) as sk:  # sketch plane normal is -Y: extrude both ways for the web
        Polygon((t1[0], t1[1]), (t2[0], t2[1]), (t2[0], -t2[1]), (t1[0], -t1[1]), align=None)
    web = extrude(sk.sketch, 4, both=True)  # y -4..4
    big = Rot(90, 0, 0) * Cylinder(R1, 24)
    small = Pos(L, 0, 0) * Rot(90, 0, 0) * Cylinder(R2, 18)
    rib = Pos(L / 2, -5.5, 0) * Box(L, 3, 6)  # y -7..-4
    part = web + big + small + rib
    part -= Rot(90, 0, 0) * Cylinder(12, 40)
    part -= Pos(L, 0, 0) * Rot(90, 0, 0) * Cylinder(6, 40)
    return part
