"""隔套：外径 Ø42、内孔 Ø30、长 28，外倒角和内孔倒角均为 C1。"""

from build123d import Axis, Polygon, revolve

SECTION = [  # (x, r) of the wall cross-section
    (0, 16), (0, 20), (1, 21), (27, 21), (28, 20), (28, 16), (27, 15), (1, 15),
]  # fmt: skip


def model():
    return revolve(Polygon(*SECTION, align=None), Axis.X)
