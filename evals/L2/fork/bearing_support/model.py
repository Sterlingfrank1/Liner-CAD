"""轴承支架：底板 100×70×12，后侧竖板（厚 12，上缘 R35 圆弧）上有 Φ52 凸台（伸出到 y = -20）和 Φ32 通孔，
凸台下方在对称面上有一块梯形肋板（厚 10）。底板两个 Φ11 孔。肋板与其余部分分成两个实体：
左视图沿对称面全剖时肋板纵剖不画剖面线，肋板与邻接面的分界线按规定画粗实线（GB/T 4458.6）。"""

from build123d import Box, BuildSketch, Compound, Cylinder, Plane, Polygon, Pos, Rot, extrude


def model():
    base = Pos(0, -5, 6) * Box(100, 70, 12)  # y -40..30
    wall = Pos(0, 24, 27.5) * Box(70, 12, 55) + Pos(0, 24, 55) * Rot(90, 0, 0) * Cylinder(35, 12)
    boss = Pos(0, -1, 55) * Rot(90, 0, 0) * Cylinder(26, 38)  # y -20..18
    main = base + wall + boss
    main -= Pos(0, 0, 55) * Rot(90, 0, 0) * Cylinder(16, 80)
    for sx in (-40, 40):
        main -= Pos(sx, -10, 6) * Cylinder(5.5, 20)
    with BuildSketch(Plane.YZ) as sk:  # sketch (y, z) of the rib, extruded ±5 along x
        Polygon((18, 12), (-32, 12), (-20, 29), (18, 29), align=None)
    rib = extrude(sk.sketch, 5, both=True)
    return Compound([main, rib - main])
