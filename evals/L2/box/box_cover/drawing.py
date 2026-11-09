"""减速器箱盖（箱体类 L2，3D 来源，简化）：主视图看轴承半圆孔和凸台，左视图沿对称面 x = 0 全剖
（通气孔、壁厚、凸缘），俯视图看通气孔凸台和凸缘孔。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    A=Param(100, min=88, max=130, step=2, label="箱盖长"),
    B=Param(64, min=56, max=90, step=2, label="箱盖宽"),
    H=Param(40, min=34, max=60, step=1, label="箱盖高", rule="H > D1 / 2 + s + 4"),
    s=Param(6, min=5, max=9, step=0.5, label="壁厚"),
    fw=Param(12, min=10, max=16, step=1, label="凸缘宽"),
    tf=Param(9, min=8, max=12, step=1, label="凸缘厚"),
    xa=Param(26, min=24, max=34, step=1, label="轴承孔到中心距", rule="xa + D1 / 2 <= A / 2 + 2"),
    d1=Param(38, min=30, max=44, step=1, label="大轴承孔径", tol="H7", rule="d1 < D1 - 6"),
    D1=Param(48, min=40, max=52, step=1, label="大轴承凸台径"),
    d2=Param(30, min=24, max=38, step=1, label="小轴承孔径", tol="H7", rule="d2 < D2 - 6"),
    D2=Param(40, min=30, max=46, step=1, label="小轴承凸台径", rule="D2 / 2 + D1 / 2 < 2 * xa"),
    bl=Param(8, min=6, max=12, step=1, label="凸台伸出量"),
    Dv=Param(28, min=20, max=36, step=1, label="通气孔凸台径"),
    hv=Param(5, min=3, max=8, step=1, label="通气孔凸台高"),
    dv=Param(12, min=8, max=18, step=1, label="通气孔径", rule="dv < Dv - 6"),
    dh=Param(9, min=6, max=12, step=0.5, label="凸缘孔径"),
    hx=Param(56, min=52, max=60, step=1, label="凸缘孔 x 向位置"),
    hy=Param(38, min=35, max=42, step=1, label="凸缘孔 y 向位置"),
)
A, B, H, s, fw, tf, xa = P.A, P.B, P.H, P.s, P.fw, P.tf, P.xa
d1, D1, d2, D2, bl, Dv, hv, dv = P.d1, P.D1, P.d2, P.D2, P.bl, P.Dv, P.hv, P.dv
Ht = H + hv  # 总高
d.model("model.py")


# ---- 主视图 (X, Z)：轴承半圆孔与凸台（结合面朝下，半圆开口向下）
front = d.view("front")
front.project(hidden=False)
front.move(dx=6, dy=-8)
for x, r, n in ((-xa, D1 / 2, "a"), (xa, D2 / 2, "b")):
    front.centerline((x, -4), (x, r + 4), name=f"axis_v{n}")
front.centerline((-A / 2 - fw - 5, 0), (A / 2 + fw + 5, 0), name="axis_h")
front.dim.linear(
    "L",
    (-A / 2 - fw, 0),
    (A / 2 + fw, 0),
    value=A + 2 * fw,
    role="overall",
    side="bottom",
    row=3,
    offset=2,
)
front.dim.linear("H", (A / 2 + fw, 0), (0, Ht), dir="v", value=Ht, role="overall", side="right")
front.dim.linear(
    "pitch",
    (-xa, D1 / 2),
    (xa, D1 / 2),
    value=2 * xa,
    role="position",
    datum="C.front.axis_va",
    side="top",
)
front.dim.linear("tf", (-A / 2 - fw, 0), (-A / 2 - fw, tf), dir="v", value=tf, side="left")
# 半圆孔、半圆凸台：直径标在开口线（z = 0）的两个端点上，尺寸线在下方
front.dim.dia("d1", (-xa - d1 / 2, 0), (-xa + d1 / 2, 0), value=d1, tol="H7", side="bottom")
front.dim.dia("d2", (xa - d2 / 2, 0), (xa + d2 / 2, 0), value=d2, tol="H7", side="bottom")
front.dim.dia("D1", (-xa - D1 / 2, 0), (-xa + D1 / 2, 0), value=D1, side="bottom", row=2)
front.dim.dia("D2", (xa - D2 / 2, 0), (xa + D2 / 2, 0), value=D2, side="bottom", row=2)
front.rough("b1", 1.6, ref="D.d1")
front.rough("b2", 1.6, ref="D.d2")

# ---- 左视图 (-Y, Z)：沿 x = 0 全剖（过通气孔轴线）
left = d.view("left")
left.project(cut="full", hidden=False)
left.centerline((0, -4), (0, Ht + 5), name="vent")
left.dim.linear(
    "W", (-B / 2 - fw, 0), (B / 2 + fw, 0), value=B + 2 * fw, role="overall", side="bottom"
)
left.dim.linear("s", (B / 2 - s, H / 2), (B / 2, H / 2), value=s, side="inside")
left.dim.linear("Bb", (-B / 2 - bl, 8), (B / 2 + bl, 8), value=B + 2 * bl, side="inside")
left.dim.linear("fw", (B / 2, tf / 2), (B / 2 + fw, tf / 2), value=fw, side="inside")
left.dim.dia("Dv", (-Dv / 2, Ht), (Dv / 2, Ht), value=Dv, side="top")
left.dim.dia("dv", (-dv / 2, Ht), (dv / 2, Ht), value=dv, side="top", row=2)
left.dim.linear("hv", (Dv / 2, H), (Dv / 2, Ht), dir="v", value=hv, side="right")

# ---- 俯视图 (X, Y)：通气孔凸台与凸缘孔
top = d.view("top")
top.project(hidden=False)
top.centerline((-A / 2 - fw - 5, 0), (A / 2 + fw + 5, 0), name="sym_x")
top.centerline((0, -B / 2 - fw - 5), (0, B / 2 + fw + 5), name="sym_y")
top.center_mark((0, 0), Dv / 2, name="vent")
for k, (x, y) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), 1):
    top.center_mark((x * P.hx, y * P.hy), P.dh / 2, name=f"hole{k}")
top.dim.linear(
    "px",
    (-P.hx, P.hy),
    (P.hx, P.hy),
    value=2 * P.hx,
    role="position",
    datum="C.top.sym_y",
    side="top",
)
top.dim.linear(
    "py",
    (P.hx, -P.hy),
    (P.hx, P.hy),
    dir="v",
    value=2 * P.hy,
    role="position",
    datum="C.top.sym_x",
    side="right",
)
top.dim.linear(
    "A", (-A / 2 + s, -B / 2 + s), (A / 2 - s, -B / 2 + s), value=A - 2 * s, side="bottom"
)
top.dim.dia("dh", circle=d.q.circles(view="top", r=P.dh.value / 2).first(), value=P.dh, prefix="4×")
top.dim.dia("Dvt", circle=d.q.circles(view="top", r=Dv.value / 2).one(), value=Dv, at=45)
top.dim.dia("dvt", circle=d.q.circles(view="top", r=dv.value / 2).one(), value=dv, at=135)

d.rough_default(12.5)
d.general_tol("m")
d.notes.tech(
    [
        "未注铸造圆角 R3~R5。",
        "铸件不得有砂眼、裂纹。",
        "时效处理。",
        "与箱座配作，结合面不平度 0.05。",
    ]
)
d.title(name="减速器箱盖", drawing_no="LC-GC-02", material="HT200", designer="Liner-CAD")
