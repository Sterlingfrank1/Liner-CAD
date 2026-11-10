"""泵轴：M16 外螺纹按大径圆柱建模，退刀槽 3.5×Ø13，Ø18 轴端键槽 6×6 朝 -Y（主视图观察者），无中心孔。"""

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

PROFILE = [  # (x, r) of the upper half, left to right
    (0, 0), (0, 7), (1, 8), (19.5, 8), (19.5, 6.5), (23, 6.5), (23, 10), (53, 10), (53, 13),
    (61, 13), (61, 10), (96, 10), (96, 9), (135, 9), (136, 8), (136, 0),
]  # fmt: skip


def model():
    part = revolve(Polygon(*PROFILE, align=None), Axis.X)
    x0, length, b, R, t1 = 100.0, 22.0, 6.0, 9.0, 3.5  # GB/T 1095 for Ø18: b×h = 6×6, t1 = 3.5
    with BuildSketch(Plane.XZ.offset(R - t1)) as sk:  # keyway bottom at y = -(R - t1)
        with Locations((x0 + length / 2, 0)):
            SlotCenterToCenter(length - b, b)
    return part - extrude(sk.sketch, amount=t1 + 1)
