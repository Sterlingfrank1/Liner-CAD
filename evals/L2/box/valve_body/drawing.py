"""阀体（箱体类 L2，3D 来源）：主视图沿前后对称面全剖，俯视图看阀盖法兰，左视图看管口法兰。
模型轴：X 向右（通道），Y 向后，Z 向上；原点在通道轴线中点。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)。"""

import math

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    Lm=Param(100, min=80, max=140, step=2, label="总长"),
    Do=Param(44, min=36, max=56, step=1, label="阀体外径"),
    Di=Param(28, min=20, max=36, step=1, label="通道直径", tol="H11", rule="Di < Do - 8"),
    Fd=Param(76, min=64, max=96, step=2, label="管口法兰外径", rule="Fd > pcd + fh"),
    Ft=Param(10, min=8, max=16, step=1, label="法兰厚"),
    pcd=Param(58, min=48, max=76, step=1, label="管口孔分布圆", rule="pcd > Do + fh"),
    fh=Param(9, min=6, max=12, step=0.5, label="管口孔径"),
    Dn=Param(40, min=32, max=50, step=1, label="阀颈外径"),
    Hn=Param(56, min=50, max=70, step=1, label="阀盖法兰顶面高", rule="Hn > Fd / 2 + Bt + 6"),
    Bd=Param(64, min=50, max=80, step=2, label="阀盖法兰外径", rule="Bd > bpcd + bh"),
    Bt=Param(8, min=6, max=12, step=1, label="阀盖法兰厚"),
    bpcd=Param(50, min=40, max=66, step=1, label="阀盖孔分布圆", rule="bpcd > Dn + bh"),
    bh=Param(7, min=5, max=10, step=0.5, label="阀盖孔径"),
    Dv=Param(22, min=14, max=28, step=1, label="阀杆孔径", tol="H8", rule="Dv < Ds"),
    Ds=Param(30, min=20, max=36, step=1, label="填料函孔径", rule="Ds < Dn - 4"),
    ds=Param(8, min=5, max=12, step=1, label="填料函深"),
)
Lm, Do, Di, Fd, Ft, Dn, Hn, Bd, Bt = P.Lm, P.Do, P.Di, P.Fd, P.Ft, P.Dn, P.Hn, P.Bd, P.Bt
x1 = Lm / 2
d.model("model.py")

# ---- 主视图 (X, Z)：沿 y = 0 全剖
front = d.view("front")
front.project(cut="full", hidden=False)
front.move(dx=14, dy=-10)
front.centerline((-x1 - 6, 0), (x1 + 6, 0), name="axis")
front.centerline((0, -Do / 2 - 4), (0, Hn + 6), name="stem")
front.dim.linear("L", (-x1, -Fd / 2), (x1, -Fd / 2), value=Lm, role="overall", side="bottom")
front.dim.linear(
    "H", (x1, -Fd / 2), (0, Hn), dir="v", value=Hn + Fd / 2, role="overall", side="right"
)
front.dim.linear("Hn", (x1, 0), (Bd / 2, Hn), dir="v", value=Hn, side="right", row=2)
front.dim.dia("Di", (-x1, Di / 2), (-x1, -Di / 2), value=Di, tol="H11", side="left")
front.dim.dia("Fd", (-x1, Fd / 2), (-x1, -Fd / 2), value=Fd, side="left", row=2)
front.dim.linear("Ft", (-x1, -Fd / 2), (-x1 + Ft, -Fd / 2), value=Ft, side="bottom", row=2)
front.dim.dia(
    "Dv", (-P.Dv / 2, Hn - P.ds), (P.Dv / 2, Hn - P.ds), value=P.Dv, tol="H8", side="top", row=2
)
front.dim.dia("Ds", (-P.Ds / 2, Hn), (P.Ds / 2, Hn), value=P.Ds, side="top")
front.dim.linear(
    "ds", (P.Ds / 2, Hn - P.ds), (P.Ds / 2, Hn), dir="v", value=P.ds, side="right", row=3
)
front.rough("bore", 3.2, ref="D.Di")

# ---- 俯视图 (X, Y)：阀盖法兰
top = d.view("top")
top.project(hidden=False)
top.centerline((-x1 - 6, 0), (x1 + 6, 0), name="sym_x")
top.centerline((0, -Fd / 2 - 6), (0, Fd / 2 + 6), name="sym_y")
top.circle((0, 0), P.bpcd / 2, role="center", name="bpcd")
top.center_mark((0, 0), Bd / 2, name="stem")
for k in range(4):
    a = math.radians(45 + 90 * k)
    top.center_mark(
        (P.bpcd / 2 * math.cos(a), P.bpcd / 2 * math.sin(a)), P.bh / 2, name=f"bh{k + 1}"
    )
top.dim.linear("W", (x1, -Fd / 2), (x1, Fd / 2), dir="v", value=Fd, role="overall", side="right")
top.dim.dia("Bd", circle=d.q.circles(view="top", r=Bd.value / 2).one(), value=Bd, at=20)
top.dim.dia("bpcd", circle="F.top.bpcd", value=P.bpcd, at=250)
hole = (
    d.q.circles(view="top", r=P.bh.value / 2)
    .near(P.bpcd / 2 * math.cos(math.pi / 4), P.bpcd / 2 * math.sin(math.pi / 4), r=P.bh.value)
    .one()
)
top.dim.dia("bh", circle=hole, value=P.bh, prefix="4×", suffix=" EQS", at=45)
top.dim.dia("Do", (-x1 + Ft + 4, -Do / 2), (-x1 + Ft + 4, Do / 2), value=Do, side="left")

# ---- 左视图 (-Y, Z)：管口法兰
left = d.view("left")
left.project(hidden=False)
left.centerline((-Fd / 2 - 6, 0), (Fd / 2 + 6, 0), name="axis_h")
left.centerline((0, -Fd / 2 - 6), (0, Fd / 2 + 6), name="axis_v")
left.circle((0, 0), P.pcd / 2, role="center", name="pcd")
left.center_mark((0, 0), Fd / 2, name="axis")
for k in range(4):
    a = math.radians(90 * k)
    left.center_mark(
        (P.pcd / 2 * math.cos(a), P.pcd / 2 * math.sin(a)), P.fh / 2, name=f"fh{k + 1}"
    )
left.dim.dia("Dn", (-Dn / 2, Hn - Bt - 8), (Dn / 2, Hn - Bt - 8), value=Dn, side="inside")
left.dim.linear("Bt", (Bd / 2, Hn - Bt), (Bd / 2, Hn), dir="v", value=Bt, side="right")
left.dim.dia("pcd", circle="F.left.pcd", value=P.pcd, at=200)
left.dim.dia(
    "fh",
    circle=d.q.circles(view="left", r=P.fh.value / 2).near(P.pcd / 2, 0, r=P.fh.value).one(),
    value=P.fh,
    prefix="4×",
    suffix=" EQS",
    at=30,
)

d.rough_default(12.5)
d.general_tol("m")
d.notes.tech(["未注铸造圆角 R3~R5。", "铸件不得有砂眼、气孔、裂纹。", "水压试验 1.5 MPa。"])
d.title(name="阀体", drawing_no="LC-VB-01", material="ZG230-450", designer="Liner-CAD")
