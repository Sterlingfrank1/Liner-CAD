"""范例：泵体（箱体类，3D 来源）。主视图沿前后对称面全剖，肋板纵剖不画剖面线（`ribs=`）；俯视图看外形，
左视图看法兰端面；几何全部由 model.py 投影，尺寸、粗糙度、基准和形位公差照常标在投影出的边上。
模型轴：X 向右（泵轴），Y 向后，Z 向上；原点在底面中心。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)。"""

import math

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(120, min=100, max=180, step=2, label="底板长"),
    W=Param(84, min=70, max=120, step=2, label="底板宽", rule="W >= Df"),
    t=Param(10, min=8, max=16, step=1, label="底板厚"),
    Hc=Param(60, min=52, max=80, step=1, label="轴线中心高", rule="Hc > t + Df / 2"),
    Ro=Param(26, min=22, max=34, step=1, label="壳体外半径", rule="Ro > Rc + 5"),
    Rc=Param(18, min=14, max=24, step=1, label="泵腔半径"),
    Lh=Param(80, min=64, max=100, step=2, label="壳体长"),
    tw=Param(18, min=12, max=26, step=1, label="端壁厚"),
    Df=Param(76, min=64, max=90, step=2, label="法兰外径", rule="Df > pcd + dfh"),
    tf=Param(10, min=8, max=16, step=1, label="法兰厚"),
    pcd=Param(62, min=56, max=80, step=1, label="螺栓孔分布圆", rule="pcd > 2 * Ro + dfh"),
    dfh=Param(8, min=6, max=12, step=0.5, label="法兰孔径"),
    dr=Param(20, min=14, max=30, step=1, label="轴承孔径", tol="H7", rule="dr < dcb"),
    dcb=Param(30, min=20, max=40, step=1, label="密封沉孔径", rule="dcb < 2 * Ro - 12"),
    cbd=Param(6, min=4, max=10, step=1, label="沉孔深"),
    Db=Param(30, min=24, max=40, step=1, label="进油凸台直径"),
    hb=Param(6, min=4, max=12, step=1, label="凸台高"),
    bx=Param(-8, min=-20, max=10, step=1, label="凸台位置"),
    dp=Param(14, min=8, max=20, step=1, label="进油孔径", rule="dp < Db - 8"),
    rw=Param(8, min=6, max=12, step=1, label="肋厚"),
    dh=Param(11, min=8, max=14, step=0.5, label="底板孔径"),
    ex=Param(50, min=40, max=56, step=1, label="孔 x 向位置"),
    ey=Param(30, min=20, max=38, step=1, label="孔 y 向位置"),
)
L, W, t, Hc, Ro, Rc, Lh, tw = P.L, P.W, P.t, P.Hc, P.Ro, P.Rc, P.Lh, P.tw
Df, tf, bx, Db, hb = P.Df, P.tf, P.bx, P.Db, P.hb
x0, x1 = -Lh / 2, Lh / 2  # 壳体两端（法兰端 / 轴承端）
H = Hc + Df / 2  # 总高（法兰顶）
zb = Hc + Ro + hb  # 进油凸台顶面
d.model("model.py")

# ---- 主视图 (X, Z)：沿 y = 0 全剖；肋板纵剖，只画轮廓不画剖面线（ribs=）
front = d.view("front")
rib = [(x0 + tf, t), (x1 - tf, t), (x1 - tf, Hc - Ro), (x0 + tf, Hc - Ro)]
front.project(cut="full", ribs=[rib], hidden=False)
front.move(dx=14, dy=-6)
front.centerline((x0 - 6, Hc), (x1 + 6, Hc), name="axis")
front.centerline((bx, Hc - 2), (bx, zb + 6), name="port")
front.dim.linear("L", (-L / 2, 0), (L / 2, 0), value=L, role="overall", side="bottom")
front.dim.linear("H", (L / 2, 0), (x0, H), dir="v", value=H, role="overall", side="right", row=5)
front.dim.linear("Hb", (L / 2, 0), (bx + Db / 2, zb), dir="v", value=zb, side="right", row=4)
front.dim.linear("Hc", (-L / 2, 0), (-L / 2, Hc), dir="v", value=Hc, side="left", row=3)
front.dim.linear("t", (-L / 2, 0), (-L / 2, t), dir="v", value=t, side="left", row=3)
front.dim.dia("Rc2", (x0, Hc + Rc), (x0, Hc - Rc), value=2 * Rc, side="left")
front.dim.dia("Df", (x0, Hc + Df / 2), (x0, Hc - Df / 2), value=Df, side="left", row=2)
front.dim.dia("dr", (x1, Hc + P.dr / 2), (x1, Hc - P.dr / 2), value=P.dr, tol="H7", side="right")
front.dim.dia("dcb", (x1, Hc + P.dcb / 2), (x1, Hc - P.dcb / 2), value=P.dcb, side="right", row=2)
front.dim.linear("tw", (x1 - tw, Hc + Rc), (x1, Hc + Rc), value=tw, side="top")
front.dim.linear(
    "cbd", (x1 - P.cbd, Hc + P.dcb / 2), (x1, Hc + P.dcb / 2), value=P.cbd, side="top", row=2
)
front.dim.linear(
    "bx", (x0, zb), (bx, zb), value=bx + Lh / 2, role="position", datum="C.front.axis", side="top"
)

# PMI：轴承孔轴线为基准 A，底面为基准 B；法兰端面对 A 垂直，轴承孔轴线对底面平行
foot = d.q.lines(view="front").where(dir="h", length=L).near(0, 0, r=1).one()
face = d.q.lines(view="front").where(dir="v").near(x0, Hc + Rc + 5, r=1).one()
front.datum("A", ref="D.dr", at=1)
front.datum("B", ref=foot.id)
front.gtol("perp", "perpendicularity", 0.05, datums=["A"], ref=face.id)
front.gtol("par", "parallelism", 0.04, datums=["B"], ref="D.dr", at=0)
front.rough("bore", 1.6, ref="D.dr")
front.rough("face", 3.2, ref=face.id)

# ---- 俯视图 (X, Y)：外形（不画虚线）
top = d.view("top")
top.project(hidden=False)
top.centerline((-L / 2 - 5, 0), (L / 2 + 5, 0), name="sym_x")
top.centerline((bx, -Ro - 6), (bx, Ro + 6), name="port")
top.center_mark((bx, 0), Db / 2, name="boss")
for k, (x, y) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), 1):
    top.center_mark((x * P.ex, y * P.ey), P.dh / 2, name=f"hole{k}")
top.dim.linear("W", (L / 2, -W / 2), (L / 2, W / 2), dir="v", value=W, role="overall", side="right")
top.dim.dia("Do", (0, -Ro), (0, Ro), value=2 * Ro, side="right", row=2)
top.dim.linear("Lh", (x0, -W / 2), (x1, -W / 2), value=Lh, side="bottom")
top.dim.linear("tf", (x0, W / 2), (x0 + tf, W / 2), value=tf, side="top")
top.dim.linear(
    "px",
    (-P.ex, P.ey),
    (P.ex, P.ey),
    value=2 * P.ex,
    role="position",
    datum="C.top.sym_x",
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
    row=3,
)
top.dim.dia("dh", circle=d.q.circles(view="top", r=P.dh.value / 2).first(), value=P.dh, prefix="4×")
top.dim.dia("Db", circle=d.q.circles(view="top", r=Db.value / 2).one(), value=Db, at=45)
top.dim.dia("dp", circle=d.q.circles(view="top", r=P.dp.value / 2).one(), value=P.dp, at=135)

# ---- 左视图 (-Y, Z)：法兰端面（4 个法兰孔在分布圆上）
left = d.view("left")
left.project(hidden=False)
left.centerline((-Df / 2 - 6, Hc), (Df / 2 + 6, Hc), name="axis_h")
left.centerline((0, Hc - Df / 2 - 6), (0, Hc + Df / 2 + 6), name="axis_v")
left.circle((0, Hc), P.pcd / 2, role="center", name="pcd")
left.center_mark((0, Hc), Df / 2, name="axis")
for k in range(4):
    a = math.radians(45 + 90 * k)
    left.center_mark(
        (P.pcd / 2 * math.cos(a), Hc + P.pcd / 2 * math.sin(a)), P.dfh / 2, name=f"fh{k + 1}"
    )
left.dim.dia("pcd", circle="F.left.pcd", value=P.pcd, at=200)
left.dim.dia(
    "dfh",
    circle=d.q.circles(view="left", r=P.dfh.value / 2).first(),
    value=P.dfh,
    prefix="4×",
    suffix=" EQS",
    at=60,
)
left.dim.linear("rw", (-P.rw / 2, t), (P.rw / 2, t), value=P.rw, side="bottom")

d.rough_default(12.5)
d.general_tol("m")
d.notes.tech(["未注铸造圆角 R3~R5。", "铸件不得有砂眼、裂纹。", "时效处理。"])
d.title(name="泵体", drawing_no="LC-PB-01", material="HT200", designer="Liner-CAD")
