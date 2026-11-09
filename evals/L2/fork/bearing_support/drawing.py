"""范例：轴承支架（叉架类）。主视图沿孔轴线方向看，左边一个底板孔用局部剖表达（波浪线为界），右边
一个孔仍用虚线；左视图过对称面全剖，肋板纵剖不画剖面线，与邻接面的分界线画粗实线（GB/T 4458.6）；
俯视图表达底板孔位和肋板。基准 A 是孔轴线，B 是底板底面；孔 Φ32H7 标粗糙度和平行度。
模型轴：X 向右，Y 向后，Z 向上。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)；孔轴线是 Y 轴。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(100, min=80, max=140, step=1, label="底板长", rule="L > 2 * xh + dh + 6"),
    W=Param(70, min=50, max=100, step=1, label="底板宽"),
    t=Param(12, min=8, max=20, step=1, label="底板厚"),
    xh=Param(40, min=20, max=60, step=1, label="孔距的一半"),
    yh=Param(30, min=15, max=50, step=1, label="孔距底板前缘"),
    dh=Param(11, min=6, max=16, step=0.5, label="底板孔径"),
    bw=Param(70, min=50, max=90, step=1, label="竖板宽（上缘半径的两倍）", rule="bw > D + 8"),
    tw=Param(12, min=8, max=20, step=1, label="竖板厚"),
    H=Param(55, min=40, max=80, step=1, label="孔轴线高", rule="H - bw / 2 > t"),
    D=Param(52, min=40, max=64, step=1, label="凸台外径", rule="D > d + 8"),
    d=Param(32, min=20, max=48, step=1, label="轴承孔径", tol="H7"),
    Lb=Param(38, min=24, max=60, step=1, label="凸台长（竖板前面起）"),
    rt=Param(10, min=6, max=16, step=1, label="肋板厚"),
    ry=Param(8, min=4, max=16, step=1, label="肋板前端距底板前缘"),
)
L, W, t, xh, dh = P.L, P.W, P.t, P.xh, P.dh
bw, tw, H, D, r = P.bw, P.tw, P.H, P.D, P.d / 2
R = bw / 2  # 竖板上缘圆弧半径
rB = D / 2
YB = 30  # 底板和竖板的后表面
yf = YB - W  # 底板前缘
yw = YB - tw  # 竖板前面
ye = yw - P.Lb  # 凸台前端面
yh = yf + P.yh  # 底板孔中心
yr = yf + P.ry  # 肋板前端
zb = H - rB  # 凸台最低点（肋板顶）
xw = -xh + dh / 2 + 5  # 局部剖的波浪线

# ---- 主视图 (X, Z)：沿孔轴线（Y）看
front = d.view("front")
front.move(dx=10, dy=-8)
front.rect((-L / 2, 0), L, t, name="base")
front.line((-R, t), (-R, H), name="wall_l")
front.line((R, t), (R, H), name="wall_r")
front.arc((0, H), R, 0, 180, name="wall")
front.circle((0, H), rB, name="boss")
front.circle((0, H), r, name="bore")
front.center_mark((0, H), R, name="axis")
front.line((-P.rt / 2, t), (-P.rt / 2, zb), name="rib_l")
front.line((P.rt / 2, t), (P.rt / 2, zb), name="rib_r")
front.line((-P.rt / 2, zb), (P.rt / 2, zb), name="rib_t")
# 底板孔：左边局部剖（孔壁画粗实线，波浪线为界），右边虚线
front.line((-xh - dh / 2, 0), (-xh - dh / 2, t), name="hl_a")
front.line((-xh + dh / 2, 0), (-xh + dh / 2, t), name="hl_b")
front.line((xh - dh / 2, 0), (xh - dh / 2, t), role="hidden", name="hr_a")
front.line((xh + dh / 2, 0), (xh + dh / 2, t), role="hidden", name="hr_b")
front.wavy("cut", [(xw, t), (xw, 0)])
front.hatch("la", loops=[[(-L / 2, 0), (-xh - dh / 2, 0), (-xh - dh / 2, t), (-L / 2, t)]])
front.hatch("lb", loops=[[(-xh + dh / 2, 0), (xw, 0), (xw, t), (-xh + dh / 2, t)]])
front.centerline((-xh, -3), (-xh, t + 3), name="hl")
front.centerline((xh, -3), (xh, t + 3), name="hr")

# ---- 俯视图 (X, Y)
top = d.view("top")
top.rect((-L / 2, yf), L, W, name="base")
top.line((-R, yw), (-R, YB), name="wall_l")
top.line((R, yw), (R, YB), name="wall_r")
top.line((-R, yw), (R, yw), name="wall_f")
top.line((-rB, yw), (-rB, ye), name="boss_l")
top.line((rB, yw), (rB, ye), name="boss_r")
top.line((-rB, ye), (rB, ye), name="boss_e")
top.line((-P.rt / 2, yr), (-P.rt / 2, ye), name="rib_l")
top.line((P.rt / 2, yr), (P.rt / 2, ye), name="rib_r")
top.line((-P.rt / 2, yr), (P.rt / 2, yr), name="rib_e")
top.line((-r, ye), (-r, YB), role="hidden", name="bore_l")
top.line((r, ye), (r, YB), role="hidden", name="bore_r")
top.line((-P.rt / 2, ye), (-P.rt / 2, yw), role="hidden", name="rib_hl")
top.line((P.rt / 2, ye), (P.rt / 2, yw), role="hidden", name="rib_hr")
top.circle((-xh, yh), dh / 2, name="h1")
top.circle((xh, yh), dh / 2, name="h2")
top.center_mark((-xh, yh), dh / 2, name="h1")
top.center_mark((xh, yh), dh / 2, name="h2")
top.centerline((0, yf - 4), (0, YB + 4), name="axis")

# ---- 左视图 (-Y, Z)：对称面全剖
left = d.view("left")
ub, uw, ue, uf = -YB, -yw, -ye, -yf  # 竖板后面、竖板前面、凸台前端、底板前缘（u = -y）
ur = -yr
left.polygon([(uw, t), (ur, t), (-ye, zb), (uw, zb)], name="rib")  # 肋板：纵剖不画剖面线
left.polyline([(ub, H - r), (ub, 0), (uf, 0), (uf, t), (ur, t)], name="main")
left.polyline([(ue, zb), (ue, H - r), (ub, H - r)], name="bore_b")
left.line((ub, H + r), (ue, H + r), name="bore_t")
left.line((ub, 0), (ub, H + R), name="back")
left.line((ue, zb), (ue, H + rB), name="boss_e")
left.line((uw, H + rB), (ue, H + rB), name="boss_t")
left.polyline([(uw, H + rB), (uw, H + R), (ub, H + R)], name="top")
left.hatch(
    "lo",
    loops=[
        [(ub, 0), (uf, 0), (uf, t), (ur, t), (uw, t), (uw, zb), (ue, zb), (ue, H - r), (ub, H - r)]
    ],
)
left.hatch(
    "up",
    loops=[[(ub, H + r), (ue, H + r), (ue, H + rB), (uw, H + rB), (uw, H + R), (ub, H + R)]],
)
left.centerline((ub - 5, H), (ue + 5, H), name="axis")

# ---- 尺寸：主视图
front.dim.linear("L", (-L / 2, 0), (L / 2, 0), value=L, role="overall", side="bottom")
front.dim.linear("t", (-L / 2, 0), (-L / 2, t), dir="v", value=t, side="left")
front.dim.linear(
    "H",
    (L / 2, 0),
    (R, H),
    dir="v",
    value=H,
    role="position",
    datum="E.front.base.1",
    side="right",
)
front.dim.linear(
    "Hs", (L / 2, 0), (0, H + R), dir="v", value=H + R, reference=True, side="right", row=2
)
front.dim.dia("D", circle="E.front.boss.1", value=D, at=-40)
front.dim.dia("d", circle="E.front.bore.1", value=P.d, tol="H7", at=200)
front.dim.rad("R", circle="E.front.wall.1", value=R, at=135)

# ---- 尺寸：俯视图
top.dim.linear("W", (L / 2, yf), (L / 2, YB), dir="v", value=W, role="overall", side="right")
top.dim.dia("dh", circle="E.top.h1.1", value=dh, prefix="2×")
top.dim.linear(
    "px",
    (-xh, yh),
    (xh, yh),
    dir="h",
    value=2 * xh,
    role="position",
    datum="C.top.axis",
    side="bottom",
)
top.dim.linear(
    "yh",
    (-xh, yf),
    (-xh, yh),
    dir="v",
    value=P.yh,
    role="position",
    datum="E.top.base.1",
    side="left",
)
top.dim.linear("rt", (-P.rt / 2, yr), (P.rt / 2, yr), dir="h", value=P.rt, side="bottom", row=2)
top.dim.linear(
    "ry",
    (P.rt / 2, yf),
    (P.rt / 2, yr),
    dir="v",
    value=P.ry,
    role="position",
    datum="E.top.base.1",
    side="right",
)

# ---- 尺寸：左视图
left.dim.linear("tw", (ub, H + R), (uw, H + R), dir="h", value=tw, side="top")
left.dim.linear("Lb", (uw, H + rB), (ue, H + rB), dir="h", value=P.Lb, side="top", row=2)

# ---- 剖切符号：左视图的剖切平面在主视图里是过孔轴线的铅垂面（对称面）
d.section("C", view="left", cut_in="front", through=[(0, -8), (0, H + R + 8)])

# ---- PMI：A = 孔轴线，B = 底板底面
front.datum("A", ref="D.d", at=0, length=8)
left.datum("B", ref="E.left.main.2", at=0.5)
front.gtol("par", "parallelism", 0.05, datums=["B"], zone="dia", ref="D.d", at=1, length=40)
top.gtol("perp", "perpendicularity", 0.04, datums=["A"], ref="E.top.boss_e.1", at=0.8, length=14)
front.rough("bore", 1.6, ref="D.d")
top.rough("end", 3.2, ref="E.top.boss_e.1", at=0.2, length=10)
left.rough("bottom", 6.3, ref="E.left.main.2", at=0.8)
d.rough_default(12.5)

d.notes.tech(["铸件不得有砂眼、气孔、裂纹。", "未注铸造圆角 R3~R5。", "时效处理。"])
d.general_tol("m")
d.title(name="轴承支架", drawing_no="LC-BS-01", material="HT200", designer="Liner-CAD")
