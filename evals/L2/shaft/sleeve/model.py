"""带肩衬套：肩 Ø50×6，体 Ø40，内孔 Ø32，两端内孔倒角 C1、体端外倒角 C1。"""

from build123d import Axis, Polygon, revolve

SECTION = [  # (x, r) of the wall cross-section
    (0, 17), (0, 25), (6, 25), (6, 20), (44, 20), (45, 19), (45, 17), (44, 16), (1, 16),
]  # fmt: skip


def model():
    return revolve(Polygon(*SECTION, align=None), Axis.X)
