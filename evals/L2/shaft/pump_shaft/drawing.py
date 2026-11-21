"""泵轴（轴套类 L2 参考图）：M16 外螺纹 + 退刀槽，两个 Ø20k6 轴承位，轴端 Ø18k6 带键槽（移出断面 B-B）。"""

from linercad import Drawing, Param, res

THREAD = "M16"

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(136, min=100, max=200, step=1, label="总长"),
    l1=Param(23, min=15, max=40, step=1, label="螺纹段长（含退刀槽）", rule="l1 > tg + 8"),
    l2=Param(30, min=20, max=50, step=1, label="左轴承位长"),
    l3=Param(8, min=4, max=16, step=1, label="轴肩长"),
    l4=Param(35, min=20, max=60, step=1, label="右轴承位长"),
    d2=Param(20, min=16, max=30, step=1, label="轴承位直径", tol="k6"),
    d3=Param(26, min=20, max=40, step=1, label="轴肩直径", rule="d3 > d2"),
    d5=Param(18, min=17, max=22, step=1, label="轴端直径", tol="k6", rule="d5 < d2"),
    tg=Param(3.5, min=3.4, max=6, step=0.1, label="退刀槽宽"),
    ks=Param(4, min=2, max=10, step=1, label="键槽距轴端台阶"),
    kl=Param(22, min=14, max=30, step=1, label="键槽长"),
)
C = 1.0  # 倒角
DG = 13  # 退刀槽底径 = d − 3（res.thread_undercut("M16")：P = 2，槽宽 3.4–6，GB/T 3-1997）
x1 = P.l1
x2 = x1 + P.l2
x3 = x2 + P.l3
x4 = x3 + P.l4
r1 = res.thread(THREAD)["d"] / 2
r2, r3, r5 = P.d2 / 2, P.d3 / 2, P.d5 / 2
lt = x1 - P.tg  # 螺纹长度（到退刀槽）
kx = x4 + P.ks  # 键槽起点

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
        (x3, r2, "j2"),
        (x4, r2),
        (x4, r5, "e"),
        (P.L - C, r5, "ch2"),
        (P.L, r5 - C),
    ],
    grooves=[{"name": "ug", "x": x1, "w": P.tg, "d": DG, "side": "left"}],
)
front.thread("thr", THREAD, 0, lt)
front.keyway("kw", kx, P.kl, P.d5)
front.center_hole("chl", on="F.front.body", end="left", type="A", d=2.5)
front.center_hole("chr", on="F.front.body", end="right", type="A", d=2.5)

# 直径
front.dim.thread("d1", "F.front.thr", side="inside")
front.dim.dia("d2", (x1 + P.l2 / 2, r2), (x1 + P.l2 / 2, -r2), value=P.d2, tol="k6", side="inside")
front.dim.dia("d3", (x2 + P.l3 / 2, r3), (x2 + P.l3 / 2, -r3), value=P.d3, side="inside")
front.dim.dia("d4", (x3 + P.l4 / 2, r2), (x3 + P.l4 / 2, -r2), value=P.d2, tol="k6", side="inside")
xd = (kx + P.kl + P.L) / 2
front.dim.dia("d5", (xd, r5), (xd, -r5), value=P.d5, tol="k6", side="inside")
front.dim.groove("ug", "F.front.ug", dir=90, length=22)

# 轴向长度：下方链式（最右一段不注），总长另起一排
front.dim.linear("lt", (0, -r1), (lt, -r1), dir="h", value=lt, side="bottom")
front.dim.linear("l2", (x1, -r2), (x2, -r3), dir="h", value=P.l2, side="bottom")
front.dim.linear("l3", (x2, -r3), (x3, -r2), dir="h", value=P.l3, side="bottom")
front.dim.linear("l4", (x3, -r2), (x4, -r2), dir="h", value=P.l4, side="bottom")
front.dim.linear(
    "L", (0, -r1), (P.L, -r5), dir="h", value=P.L, role="overall", side="bottom", row=2
)
front.dim.linear(
    "ks",
    (x4, r5),
    (kx, r5),
    dir="h",
    value=P.ks,
    role="position",
    datum="E.front.body.e:start",
    side="top",
)
front.dim.linear("kl", (kx, r5), (kx + P.kl, r5), dir="h", value=P.kl, side="top")
front.dim.chamfer("c1", "E.front.body.ch1")
front.dim.chamfer("c2", "E.front.body.ch2")

# 移出断面 B-B：键槽
xm = kx + P.kl / 2
sec = d.removed_section("B", parent="front", through=[(xm, -r5 - 8), (xm, r5 + 8)], look="left")
sec.shaft_cut("s", P.d5, keyway="F.front.kw")
sec.dim.keyway("kb", "F.B.s", what="b")
sec.dim.keyway("kd", "F.B.s", what="depth")

# PMI：基准 A-B（两个 Ø20 轴承位），轴端径向圆跳动，粗糙度
front.datum("A", ref="D.d2")
front.datum("B", ref="D.d4")
front.gtol("run", "circular_runout", 0.02, datums=["A-B"], ref="E.front.body.e")
front.rough("j1", 0.8, ref="E.front.body.j1", process="磨")
front.rough("j2", 0.8, ref="E.front.body.j2", process="磨", at=0.85)
front.rough("e", 1.6, ref="E.front.body.e", process="磨")
d.rough_default(6.3)

d.notes.tech(["调质处理 217~255HBW。", "未注圆角 R0.5。"])
d.general_tol("m")
d.title(name="泵轴", drawing_no="LC-PS-01", material="45", designer="Liner-CAD")
