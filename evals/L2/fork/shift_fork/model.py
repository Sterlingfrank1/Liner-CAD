"""拨叉：轴孔 Φ22 的套筒（Φ40×36，轴线沿 Y）、矩形臂（厚 12、宽 28）和带 U 形槽的叉口（厚 24、高 44，
槽宽 24，槽底半圆圆心距孔轴线 88）。未注铸造圆角不建模。"""

from build123d import Box, Cylinder, Pos, Rot


def model():
    hub = Rot(90, 0, 0) * Cylinder(20, 36)
    arm = Pos(33, 0, 0) * Box(66, 12, 28)  # x 0..66
    jaw = Pos(81, 0, 0) * Box(38, 24, 44)  # x 62..100
    slot = Pos(94.1, 0, 0) * Box(12.2, 30, 24) + Pos(88, 0, 0) * Rot(90, 0, 0) * Cylinder(12, 30)
    bore = Rot(90, 0, 0) * Cylinder(11, 40)
    return hub + arm + jaw - slot - bore
