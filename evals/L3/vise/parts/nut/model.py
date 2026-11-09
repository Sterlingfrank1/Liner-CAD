"""方块螺母（机用虎钳）：装在活动钳身的方槽里，内孔为螺杆螺纹（按大径）。"""

from build123d import Box, Cylinder, Pos, Rot


def model(x0=76, x1=96, gw=12, z0=18, z1=42, ax=30, bore=16):
    """x0~x1 长、gw 半宽、z0~z1 高（与活动钳身方槽相贴，底面落在舌块顶面）；ax 轴线高度、bore 螺纹孔大径。"""
    n = Pos((x0 + x1) / 2, 0, (z0 + z1) / 2) * Box(x1 - x0, 2 * gw, z1 - z0)
    return n - Pos((x0 + x1) / 2, 0, ax) * Rot(0, 90, 0) * Cylinder(bore / 2, x1 - x0 + 2)
