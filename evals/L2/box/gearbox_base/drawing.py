"""减速器箱座（箱体类 L2，3D 来源，简化）：主视图看轴承凸台端面，左视图过一根轴承孔轴线全剖，
俯视图看结合面和底板孔。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)。"""

import math

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(160, min=140, max=200, step=2, label="底板长"),
    W=Param(108, min=96, max=140, step=2, label="底板宽"),
    t=Param(10, min=8, max=14, step=1, label="底板厚"),
    A=Param(100, min=88, max=130, step=2, label="箱体长"),
    B=Param(64, min=56, max=90, step=2, label="箱体宽"),
    H=Param(64, min=52, max=80, step=1, label="箱体高（含底板）"),
    s=Param(6, min=5, max=9, step=0.5, label="壁厚"),
    fw=Param(12, min=10, max=16, step=1, label="结合面凸缘宽"),
    tf=Param(9, min=8, max=12, step=1, label="结合面凸缘厚"),
    Hc=Param(32, min=26, max=40, step=1, label="轴承孔中心高", rule="Hc > D1 / 2"),
    xa=Param(26, min=24, max=34, step=1, label="轴承孔到箱体中心距", rule="xa > D1 / 2 + 2"),
    d1=Param(38, min=30, max=44, step=1, label="大轴承孔径", tol="H7", rule="d1 < D1 - 6"),
    D1=Param(46, min=36, max=52, step=1, label="大轴承凸台径"),
    d2=Param(30, min=24, max=38, step=1, label="小轴承孔径", tol="H7", rule="d2 < D2 - 6"),
    D2=Param(40, min=30, max=46, step=1, label="小轴承凸台径", rule="D2 / 2 + D1 / 2 < 2 * xa"),
    bl=Param(8, min=6, max=12, step=1, label="凸台伸出量"),
    dh=Param(12, min=9, max=15, step=0.5, label="底板孔径"),
    ex=Param(70, min=66, max=76, step=1, label="底板孔 x 向位置"),
    ey=Param(45, min=40, max=50, step=1, label="底板孔 y 向位置"),
    fh=Param(7, min=6, max=10, step=0.5, label="结合面孔径"),
    fx=Param(35, min=28, max=42, step=1, label="结合面孔 x 间距"),
    fy=Param(
        38, min=35, max=42, step=1, label="结合面孔 y 向位置", rule="fy + fh / 2 < B / 2 + fw"
    ),
)
L, W, t, A, B, H, s, fw, tf, Hc, xa = P.L, P.W, P.t, P.A, P.B, P.H, P.s, P.fw, P.tf, P.Hc, P.xa
d1, D1, d2, D2, bl = P.d1, P.D1, P.d2, P.D2, P.bl
d.model("model.py")


def rim(view, cx, cy, r, deg):
    """投影出的圆边（跨接缝时是两段圆弧）：取过圆周上 deg 方向那一点的边。"""
    a = math.radians(deg)
    pt = (cx + r * math.cos(a), cy + r * math.sin(a))
    return d.q.edges(view=view).where(r=r).near(*pt, r=0.3).one()


# ---- 主视图 (X, Z)：轴承凸台端面
front = d.view("front")
front.project(hidden=False)
front.move(dx=10, dy=-4)
for x, r, n in ((-xa, D1 / 2, "a"), (xa, D2 / 2, "b")):
    front.centerline((x - r - 5, Hc), (x + r + 5, Hc), name=f"axis_{n}")
    front.centerline((x, Hc - r - 5), (x, Hc + r + 5), name=f"axis_v{n}")
    front.center_mark((x, Hc), r, name=f"bore_{n}")
front.dim.linear("L", (-L / 2, 0), (L / 2, 0), value=L, role="overall", side="bottom")
front.dim.linear("H", (L / 2, 0), (A / 2, H), dir="v", value=H, role="overall", side="right")
front.dim.linear("Hc", (-L / 2, 0), (-xa, Hc), dir="v", value=Hc, side="left")
front.dim.linear("t", (-L / 2, 0), (-L / 2, t), dir="v", value=t, side="left", row=2)
front.dim.linear(
    "pitch",
    (-xa, Hc + D1 / 2),
    (xa, Hc + D1 / 2),
    value=2 * xa,
    role="position",
    datum="C.front.axis_va",
    side="top",
)
front.dim.dia(
    "d1", circle=rim("front", -xa.value, Hc.value, d1.value / 2, 135), value=d1, tol="H7", at=135
)
front.dim.dia("D1", circle=rim("front", -xa.value, Hc.value, D1.value / 2, 225), value=D1, at=225)
front.dim.dia(
    "d2", circle=rim("front", xa.value, Hc.value, d2.value / 2, 45), value=d2, tol="H7", at=45
)
front.dim.dia("D2", circle=rim("front", xa.value, Hc.value, D2.value / 2, 315), value=D2, at=315)

# ---- 左视图 (-Y, Z)：过大轴承孔轴线（x = -xa）全剖
left = d.view("left")
# 剖切面过大轴承孔轴线 x = -xa；恰好过轴线时 OCC 剖面带退化内环（S1 缺口），depth 偏 0.01 mm 绕开
left.project(cut="full", depth=xa - 0.01, hidden=False)
yb = B / 2 + bl
left.centerline((-yb - 6, Hc), (yb + 6, Hc), name="axis")
left.dim.linear("W", (-W / 2, 0), (W / 2, 0), value=W, role="overall", side="bottom")
left.dim.linear("B", (-B / 2, t + 6), (B / 2, t + 6), value=B, side="inside")
left.dim.linear("s", (B / 2 - s, H / 2 + 8), (B / 2, H / 2 + 8), value=s, side="inside")
left.dim.linear("Bb", (-yb, Hc - 8), (yb, Hc - 8), value=B + 2 * bl, side="inside")
left.dim.linear("tf", (B / 2 + fw, H - tf), (B / 2 + fw, H), dir="v", value=tf, side="right")
left.dim.dia("d1s", (yb, Hc + d1 / 2), (yb, Hc - d1 / 2), value=d1, tol="H7", side="right", row=2)
left.rough("bore", 1.6, ref="D.d1s")
front.rough("b1", 1.6, ref="D.d1")
front.rough("b2", 1.6, ref="D.d2")

# ---- 俯视图 (X, Y)：结合面与底板孔
top = d.view("top")
top.project(hidden=False)
top.centerline((-L / 2 - 5, 0), (L / 2 + 5, 0), name="sym_x")
top.centerline((0, -W / 2 - 5), (0, W / 2 + 5), name="sym_y")
for k, (x, y) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), 1):
    top.center_mark((x * P.ex, y * P.ey), P.dh / 2, name=f"hole{k}")
for k, (x, y) in enumerate([(x, y) for x in (-1, 0, 1) for y in (-1, 1)], 1):
    top.center_mark((x * P.fx, y * P.fy), P.fh / 2, name=f"fh{k}")
top.dim.linear(
    "px",
    (-P.ex, P.ey),
    (P.ex, P.ey),
    value=2 * P.ex,
    role="position",
    datum="C.top.sym_y",
    side="top",
    row=2,
)
top.dim.linear(
    "py",
    (P.ex, -P.ey),
    (P.ex, P.ey),
    dir="v",
    value=2 * P.ey,
    role="position",
    datum="C.top.sym_x",
    side="right",
    row=2,
)
top.dim.linear(
    "Ai", (-A / 2 + s, -B / 2 + s), (A / 2 - s, -B / 2 + s), value=A - 2 * s, side="bottom"
)
top.dim.linear(
    "Af", (-A / 2 - fw, B / 2 + fw), (A / 2 + fw, B / 2 + fw), value=A + 2 * fw, side="top"
)
top.dim.linear(
    "fx",
    (-P.fx, -P.fy),
    (0, -P.fy),
    value=P.fx,
    role="position",
    datum="C.top.sym_y",
    side="bottom",
    row=2,
)
top.dim.linear(
    "fy",
    (P.fx, -P.fy),
    (P.fx, P.fy),
    dir="v",
    value=2 * P.fy,
    role="position",
    datum="C.top.sym_x",
    side="right",
)
top.dim.dia("dh", circle=d.q.circles(view="top", r=P.dh.value / 2).first(), value=P.dh, prefix="4×")
top.dim.dia("fh", circle=d.q.circles(view="top", r=P.fh.value / 2).first(), value=P.fh, prefix="6×")

d.rough_default(12.5)
d.general_tol("m")
d.notes.tech(
    [
        "未注铸造圆角 R3~R5。",
        "铸件不得有砂眼、裂纹。",
        "时效处理。",
        "结合面不平度 0.05，涂密封胶。",
    ]
)
d.title(name="减速器箱座", drawing_no="LC-GB-01", material="HT200", designer="Liner-CAD")
