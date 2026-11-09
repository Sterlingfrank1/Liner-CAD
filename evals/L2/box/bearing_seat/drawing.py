"""轴承座（箱体类 L2，3D 来源）：主视图看轴承孔端面（反映形状特征），左视图沿对称面全剖，
肋板纵剖不画剖面线（ribs=），俯视图看底板孔。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(120, min=100, max=160, step=2, label="底板长"),
    W=Param(80, min=64, max=110, step=2, label="底板宽", rule="W > Ly"),
    t=Param(14, min=10, max=20, step=1, label="底板厚"),
    Hc=Param(60, min=50, max=80, step=1, label="轴承孔中心高", rule="Hc - R > t + 8"),
    R=Param(32, min=28, max=40, step=1, label="轴承座外半径", rule="R > db / 2 + 6"),
    Ly=Param(64, min=50, max=76, step=2, label="轴承座长"),
    db=Param(40, min=30, max=50, step=1, label="轴承孔径", tol="H7", rule="db < dc"),
    dc=Param(46, min=36, max=58, step=1, label="密封沉孔径"),
    cd=Param(3, min=2, max=5, step=0.5, label="沉孔深"),
    rw=Param(10, min=8, max=14, step=1, label="肋厚"),
    dh=Param(13, min=9, max=16, step=0.5, label="底板孔径"),
    ex=Param(45, min=36, max=54, step=1, label="孔 x 向位置"),
    ey=Param(28, min=20, max=34, step=1, label="孔 y 向位置"),
    Db=Param(18, min=14, max=24, step=1, label="油孔凸台直径"),
    hb=Param(4, min=3, max=8, step=1, label="凸台高"),
    dp=Param(8, min=5, max=10, step=1, label="油孔径", rule="dp < Db - 4"),
)
L, W, t, Hc, R, Ly, db = P.L, P.W, P.t, P.Hc, P.R, P.Ly, P.db
y1 = Ly / 2
H = Hc + R + P.hb
d.model("model.py")

# ---- 主视图 (X, Z)：轴承孔端面（不画虚线）
front = d.view("front")
front.project(hidden=False)
front.move(dx=10, dy=-8)
front.centerline((-R - 6, Hc), (R + 6, Hc), name="axis_h")
front.centerline((0, Hc - R - 6), (0, H + 6), name="axis_v")
front.center_mark((0, Hc), R, name="bore")
front.dim.linear("L", (-L / 2, 0), (L / 2, 0), value=L, role="overall", side="bottom")
front.dim.linear("H", (L / 2, 0), (0, H), dir="v", value=H, role="overall", side="right")
front.dim.linear("Hc", (-L / 2, 0), (-L / 2, Hc), dir="v", value=Hc, side="left")
front.dim.linear("t", (-L / 2, 0), (-L / 2, t), dir="v", value=t, side="left", row=2)
rim = (
    d.q.arcs(view="front", r=R.value)
    .near(-R.value * 0.7071, Hc.value - R.value * 0.7071, r=0.5)
    .one()
)
front.dim.dia("R2", circle=rim, value=2 * R, at=45)
front.dim.dia("dc", circle=d.q.circles(view="front", r=P.dc.value / 2).one(), value=P.dc, at=135)
front.dim.linear(
    "rw", (-P.rw / 2, (t + Hc - R) / 2), (P.rw / 2, (t + Hc - R) / 2), value=P.rw, side="inside"
)

# ---- 左视图 (-Y, Z)：沿 x = 0 全剖，肋板纵剖（只画轮廓不画剖面线）
left = d.view("left")
rib = [(-y1, t), (y1, t), (y1, Hc - R), (-y1, Hc - R)]
left.project(cut="full", ribs=[rib], hidden=False)
left.centerline((-y1 - 6, Hc), (y1 + 6, Hc), name="axis")
left.centerline((0, H + 4), (0, Hc + R - 10), name="oil")
left.dim.linear("W", (-W / 2, 0), (W / 2, 0), value=W, role="overall", side="bottom")
left.dim.linear("Ly", (-y1, Hc + R), (y1, Hc + R), value=Ly, side="top")
left.dim.dia("db", (y1, Hc + db / 2), (y1, Hc - db / 2), value=db, tol="H7", side="right")
left.dim.dia("dcs", (y1, Hc + P.dc / 2), (y1, Hc - P.dc / 2), value=P.dc, side="right", row=2)
left.dim.linear("cd", (y1 - P.cd, Hc + P.dc / 2), (y1, Hc + P.dc / 2), value=P.cd, side="inside")
left.rough("bore", 1.6, ref="D.db")

# ---- 俯视图 (X, Y)：底板孔和油孔凸台
top = d.view("top")
top.project(hidden=False)
top.centerline((-L / 2 - 5, 0), (L / 2 + 5, 0), name="sym_x")
top.centerline((0, -W / 2 - 5), (0, W / 2 + 5), name="sym_y")
top.center_mark((0, 0), P.Db / 2, name="oil")
for k, (x, y) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), 1):
    top.center_mark((x * P.ex, y * P.ey), P.dh / 2, name=f"hole{k}")
top.dim.linear(
    "px",
    (-P.ex, P.ey),
    (P.ex, P.ey),
    value=2 * P.ex,
    role="position",
    datum="C.top.sym_y",
    side="top",
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
)
top.dim.dia("dh", circle=d.q.circles(view="top", r=P.dh.value / 2).first(), value=P.dh, prefix="4×")
top.dim.dia("Db", circle=d.q.circles(view="top", r=P.Db.value / 2).one(), value=P.Db, at=45)
top.dim.dia("dp", circle=d.q.circles(view="top", r=P.dp.value / 2).one(), value=P.dp, at=135)

d.rough_default(12.5)
d.general_tol("m")
d.notes.tech(["未注铸造圆角 R3~R5。", "铸件不得有砂眼、裂纹。", "时效处理。"])
d.title(name="轴承座", drawing_no="LC-BS-01", material="HT200", designer="Liner-CAD")
