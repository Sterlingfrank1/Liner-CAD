"""钳口板（机用虎钳）：贴在钳口面上，两个 M6 沉头螺钉固定。装配坐标：整个装配的 XYZ。
x0 为贴合的钳口面所在 X；side=+1 板在面的 +X 侧（固定钳口），side=-1 在 -X 侧（活动钳口）。"""

from build123d import Box, Cone, Cylinder, Pos, Rot


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def model(W=72, x0=20, side=1, t=4, z0=19, z1=49, hd=6, dk=11.3, k=3.3, sz1=26, sz2=42):
    """W 钳身宽（板宽 W-12）；t 板厚、z0~z1 板高；hd 螺钉孔径；dk×k 沉头锥孔（GB/T 68 M6）；
    sz1、sz2 两个螺钉的高度（都在 Y=0 对称面上）。"""
    xa, xb = (x0, x0 + t) if side > 0 else (x0 - t, x0)
    pw = W - 12
    p = box(xa, xb, -pw / 2, pw / 2, z0, z1)
    xo = xb if side > 0 else xa  # 开口面（钳口间隙一侧）
    for sz in (sz1, sz2):
        p = p - Pos((xa + xb) / 2, 0, sz) * Rot(0, 90, 0) * Cylinder(hd / 2, t + 2)
        r0, r1 = (hd / 2, dk / 2) if side > 0 else (dk / 2, hd / 2)
        p = p - Pos(xo - side * k / 2, 0, sz) * Rot(0, 90, 0) * Cone(r0, r1, k)
    return p
