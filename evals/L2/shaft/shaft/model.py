"""减速器输出轴：旋转体，M24×1.5 外螺纹按大径圆柱建模，键槽朝 -Y（主视图观察者），无中心孔。"""

from build123d import (
    Axis,
    BuildSketch,
    Locations,
    Plane,
    Polygon,
    SlotCenterToCenter,
    extrude,
    revolve,
)

PROFILE = [  # (x, r) of the upper half, left to right; the groove 28..32 is Ø21.7
    (0, 0), (0, 10.5), (1.5, 12), (28, 12), (28, 10.85), (32, 10.85), (32, 15), (62, 15), (62, 22),
    (72, 22), (72, 18), (142, 18), (142, 15), (198.5, 15), (200, 13.5), (200, 0),
]  # fmt: skip


def model():
    part = revolve(Polygon(*PROFILE, align=None), Axis.X)
    x0, length, b, R, t1 = 77.0, 50.0, 10.0, 18.0, 5.0  # Ø36 seat, GB/T 1095 b×h = 10×8, t1 = 5
    with BuildSketch(Plane.XZ.offset(R - t1)) as sk:  # keyway bottom at y = -(R - t1)
        with Locations((x0 + length / 2, 0)):
            SlotCenterToCenter(length - b, b)
    return part - extrude(sk.sketch, amount=t1 + 1)
