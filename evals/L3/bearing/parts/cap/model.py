"""轴承盖（滑动轴承）。装配坐标：轴线沿 Y 过原点，剖分面 Z=0，盖在剖分面之上。"""

from build123d import Box, Cylinder, Pos, Rot


def model(D=48, L=120, W=44, bs=42, bd=10, od=8):
    """D 轴衬外径（盖孔径）；盖高 = D/2 + 8；bs 螺栓中心距轴线、bd 螺栓孔径；od 油杯孔径。"""
    T = D / 2 + 8
    cap = Pos(0, 0, T / 2) * Box(L, W, T)
    cap = cap - Rot(90, 0, 0) * Cylinder(D / 2, W + 2)
    for s in (-1, 1):
        cap = cap - Pos(s * bs, 0, T / 2) * Cylinder(bd / 2, T + 2)
    cap = cap - Pos(0, 0, T - 4) * Cylinder(od / 2, 10)  # 油杯孔：从盖孔顶穿到盖顶
    return cap
