"""叉形接头：杆部 Φ30×40（左端 M16 螺孔，按小径 Φ13.835 建盲孔，钻深 28，120° 钻尖），叉部 40×40×50，
开口槽宽 20、深 30（沿 Z 贯通），销孔 Φ12 沿 Y 贯穿两叉，距叉端 15。轴线沿 X，销孔轴线沿 Y。"""

import math

from build123d import Axis, Box, Cylinder, Face, Polyline, Pos, Rot, revolve


def lathe(pts):
    return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)


def model():
    shank = Pos(20, 0, 0) * Rot(0, 90, 0) * Cylinder(15, 40)  # x 0..40
    block = Pos(65, 0, 0) * Box(50, 40, 40)  # x 40..90
    slot = Pos(75.1, 0, 0) * Box(30.2, 20, 50)  # x 60..90.2
    pin = Pos(75, 0, 0) * Rot(90, 0, 0) * Cylinder(6, 50)
    r1, dd = 13.835 / 2, 28.0  # M16 minor diameter (GB/T 196), drilled depth
    tip = r1 / math.tan(math.radians(60))
    tap = lathe([(-1, 0), (-1, r1), (dd, r1), (dd + tip, 0)])
    return shank + block - slot - pin - tap
