"""固定钳身（机用虎钳）。装配坐标：螺杆轴线沿 X、高度 Z=30；X=0 为钳身左端，Y=0 为对称面，底面 Z=0。"""

from build123d import Box, Cylinder, Pos, Rot


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def xcyl(r, x0, x1, y, z):
    return Pos((x0 + x1) / 2, y, z) * Rot(0, 90, 0) * Cylinder(r, x1 - x0)


def model(W=72, L=150, H=50, tb=18, jt=20, bx=130, bh=46, gw=12, gz=10, ax=30, bore=16, hd=6):
    """W 钳身宽；L 导轨长、tb 导轨厚；jt 固定钳口厚、H 钳口高；bx 起为轴承座凸台（高 bh）；
    gw×gz 导向槽（半宽 × 槽底高度）；ax 螺杆轴线高度、bore 螺杆孔径；hd 钳口板螺钉孔（螺纹按大径）。"""
    s = box(0, L, -W / 2, W / 2, 0, tb) + box(0, jt, -W / 2, W / 2, 0, H)
    s = s + box(bx, L, -W / 2, W / 2, 0, bh)
    s = s - box(jt, bx, -gw, gw, gz, tb + 1)
    s = s - xcyl(bore / 2, bx - 1, L + 1, 0, ax)
    for z in (26, 42):
        s = s - xcyl(hd / 2, 8, jt + 0.5, 0, z)  # 沉头螺钉 M6×16 的螺纹孔，深 12
    return s
