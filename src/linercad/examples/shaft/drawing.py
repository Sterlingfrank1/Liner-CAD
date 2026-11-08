"""范例：减速器输出轴（轴套类）。主视图轴线水平、螺纹端在左；外螺纹 M24×1.5 + 退刀槽（局部放大 I）、
Ø36 键槽 + 移出断面 B-B、两端中心孔、k6 / n6 配合、跳动、粗糙度。直径标在轴段上（inside），
轴向长度链式标在下方（留最右一段不注），螺纹长度和键槽尺寸在上方，总长另起一排。"""

from linercad import Drawing, Param, res

THREAD = "M24x1.5"

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(200, min=160, max=320, step=1, label="总长"),
    l1=Param(32, min=20, max=60, step=1, label="螺纹段长（含退刀槽）", rule="l1 > tg + 10"),
    l2=Param(30, min=20, max=60, step=1, label="左轴颈长"),
    l3=Param(10, min=6, max=30, step=1, label="轴肩长"),
    l4=Param(70, min=50, max=120, step=1, label="齿轮段长", rule="l4 > ks + kl"),
    d2=Param(30, min=26, max=50, step=1, label="轴颈直径", tol="k6", rule="d2 < d4"),
    d3=Param(44, min=30, max=70, step=1, label="轴肩直径", rule="d3 > d4"),
    d4=Param(36, min=28, max=60, step=1, label="齿轮段直径", tol="n6"),
    tg=Param(4, min=2, max=6, step=0.5, label="退刀槽宽"),
    dg=Param(21, min=14, max=22, step=0.5, label="退刀槽底径"),
    ks=Param(5, min=3, max=12, step=1, label="键槽距轴肩"),
    kl=Param(50, min=30, max=100, step=1, label="键槽长"),
)
x1 = P.l1
x2 = x1 + P.l2
x3 = x2 + P.l3
x4 = x3 + P.l4
r1 = res.thread(THREAD)["d"] / 2
r2, r3, r4 = P.d2 / 2, P.d3 / 2, P.d4 / 2
C = 1.5  # 倒角
lt = x1 - P.tg  # 螺纹长度（到退刀槽）
kx = x3 + P.ks  # 键槽起点

front = d.view("front")
front.move(dx=12)
front.turned(
    "body",
    [
        (0, r1 - C, "ch1"),
        (C, r1, "t"),
        (x1, r1),
        (x1, r2, "j1"),
        (x2, r2),
        (x2, r3, "sh"),
        (x3, r3),
        (x3, r4, "g"),
        (x4, r4),
        (x4, r2, "j2"),
        (P.L - C, r2, "ch2"),
        (P.L, r2 - C),
    ],
    grooves=[{"name": "ug", "x": x1, "w": P.tg, "d": P.dg, "side": "left"}],
)
front.thread("thr", THREAD, 0, lt)
front.keyway("kw", kx, P.kl, P.d4)
front.center_hole("chl", on="F.front.body", end="left", type="A", d=3.15)
front.center_hole("chr", on="F.front.body", end="right", type="A", d=3.15)

# 直径：标在各轴段中部
front.dim.thread("d1", "F.front.thr", side="inside")
front.dim.dia("d2", (x1 + P.l2 / 2, r2), (x1 + P.l2 / 2, -r2), value=P.d2, tol="k6", side="inside")
front.dim.dia("d3", (x2 + P.l3 / 2, r3), (x2 + P.l3 / 2, -r3), value=P.d3, side="inside")
xd = (kx + P.kl + x4) / 2  # 键槽末端与台阶之间
front.dim.dia("d4", (xd, r4), (xd, -r4), value=P.d4, tol="n6", side="inside")
front.dim.dia(
    "d5", ((x4 + P.L) / 2, r2), ((x4 + P.L) / 2, -r2), value=P.d2, tol="k6", side="inside"
)

# 轴向长度：下方链式（最右一段不注），总长另起一排
front.dim.linear("l2", (x1, -r2), (x2, -r3), dir="h", value=P.l2, side="bottom")
front.dim.linear("l3", (x2, -r3), (x3, -r4), dir="h", value=P.l3, side="bottom")
front.dim.linear("l4", (x3, -r4), (x4, -r2), dir="h", value=P.l4, side="bottom")
front.dim.linear(
    "L", (0, -r1), (P.L, -r2), dir="h", value=P.L, role="overall", side="bottom", row=2
)
# 上方：键槽位置和长度
front.dim.linear("lt", (0, -r1), (lt, -r1), dir="h", value=lt, side="bottom")
front.dim.linear(
    "ks",
    (x3, r4),
    (kx, r4),
    dir="h",
    value=P.ks,
    role="position",
    datum="E.front.body.8",
    side="top",
)
front.dim.linear("kl", (kx, r4), (kx + P.kl, r4), dir="h", value=P.kl, side="top")
front.dim.chamfer("c1", "E.front.body.ch1")
front.dim.chamfer("c2", "E.front.body.ch2")

# 局部放大 I：退刀槽
det = d.detail("I", parent="front", center=(x1 - P.tg / 2, 12), r=5, scale="5:1")
det.place(at=(212, 64))
front.dim.groove("ug", "F.front.ug", dir=90, length=26)
det.dim.linear("gw", (x1 - P.tg, r1), (x1, r1), dir="h", value=P.tg, side="top")
det.dim.linear(
    "gh", (x1 - P.tg / 2, r1), (x1 - P.tg / 2, P.dg / 2), dir="v", value=r1 - P.dg / 2, side="left"
)

# 移出断面 B-B：键槽
xm = kx + P.kl / 2
sec = d.removed_section("B", parent="front", through=[(xm, -r4 - 8), (xm, r4 + 8)], look="left")
sec.shaft_cut("s", P.d4, keyway="F.front.kw")
sec.dim.keyway("kb", "F.B.s", what="b")
sec.dim.keyway("kd", "F.B.s", what="depth")

# PMI：基准 A-B（两轴颈），跳动，粗糙度
front.datum("A", ref="D.d2")
front.datum("B", ref="D.d5")
front.gtol("rg", "circular_runout", 0.02, datums=["A-B"], ref="E.front.body.g", at=0.92)
front.rough("j1", 0.8, ref="E.front.body.j1", process="磨")
front.rough("j2", 0.8, ref="E.front.body.j2", process="磨")
front.rough("g", 1.6, ref="E.front.body.g", process="磨")
d.rough_default(6.3)

d.notes.tech(["调质处理 220~250HBW。", "未注圆角 R1。"])
d.general_tol("m")
d.accept("conv_dim", "F.front.kw", "键槽宽度 b（D.kb）和深度 d−t1（D.kd）标在移出断面 B-B 上")
d.title(name="输出轴", drawing_no="LC-SH-01", material="45", designer="Liner-CAD")
