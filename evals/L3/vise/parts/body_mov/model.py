"""活动钳身（机用虎钳）：钳口在左（X=60），底部舌块插入固定钳身导向槽，中部方槽装方块螺母。"""

from build123d import Box, Cylinder, Pos, Rot


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def xcyl(r, x0, x1, y, z):
    return Pos((x0 + x1) / 2, y, z) * Rot(0, 90, 0) * Cylinder(r, x1 - x0)


def model(
    W=72, x0=60, x1=106, H=50, tb=18, gw=12, gz=10, ax=30, bore=16, px0=76, px1=96, pz1=42, hd=6
):
    """W 钳身宽；x0~x1 钳身长；tb 以下为舌块（半宽 gw、底高 gz，与固定钳身导向槽相贴）；
    px0~px1 × pz1 方槽（装方块螺母）；ax 螺杆轴线高度、bore 螺杆孔径；hd 钳口板螺钉孔。"""
    s = box(x0, x1, -W / 2, W / 2, tb, H) + box(x0, x1, -gw, gw, gz, tb)
    s = s - box(px0, px1, -gw, gw, tb, pz1)
    s = s - xcyl(bore / 2, px1 - 1, x1 + 1, 0, ax)  # 螺杆只穿过右壁（左端止于方槽内）
    for z in (26, 42):
        s = s - xcyl(hd / 2, x0 - 0.5, x0 + 12, 0, z)  # 沉头螺钉 M6×16 的螺纹孔，深 12
    return s
