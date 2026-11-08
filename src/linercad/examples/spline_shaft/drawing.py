"""范例：花键轴（轴套类）。主视图轴线水平，左端矩形花键 6×23×26×6（轻系列）；左视图为花键端面视图。
两个 Ø30k6 轴颈为基准 A-B，花键外圆给径向圆跳动；直径标在轴段上，轴向长度链式标在下方。"""

from linercad import Drawing, Param, res

SPLINE = "6x23x26x6"

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(120, min=90, max=200, step=1, label="总长"),
    l1=Param(36, min=20, max=60, step=1, label="花键段长"),
    l2=Param(30, min=20, max=60, step=1, label="左轴颈长"),
    l3=Param(10, min=6, max=20, step=1, label="轴肩长"),
    d2=Param(30, min=26, max=40, step=1, label="轴颈直径", tol="k6"),
    d3=Param(38, min=30, max=50, step=1, label="轴肩直径", rule="d3 > d2"),
)
C = 1.5  # 右端倒角
rs = res.spline(SPLINE)["D"] / 2  # 花键大径
x1 = P.l1
x2 = x1 + P.l2
x3 = x2 + P.l3
r2, r3 = P.d2 / 2, P.d3 / 2

front = d.view("front")
left = d.view("left")  # 花键端面视图

front.turned(
    "body",
    [
        (0, rs, "spl"),
        (x1, rs),
        (x1, r2, "j1"),
        (x2, r2),
        (x2, r3, "sh"),
        (x3, r3),
        (x3, r2, "j2"),
        (P.L - C, r2, "ch"),
        (P.L, r2 - C),
    ],
)
front.spline("sp", SPLINE, 0, x1)
front.center_hole("chl", on="F.front.body", end="left", type="A", d=2.5)
front.center_hole("chr", on="F.front.body", end="right", type="A", d=3.15)

left.spline_end("spe", (0, 0), SPLINE)
left.circle((0, 0), r2, name="j")
left.circle((0, 0), r3, name="sh")
left.center_mark((0, 0), r3, name="axis")

# 花键代号（轴向视图、端面视图各一）
front.dim.spline("sd", "F.front.sp")
left.dim.spline("sde", "F.left.spe")

# 直径
front.dim.dia("d2", (x1 + P.l2 / 2, r2), (x1 + P.l2 / 2, -r2), value=P.d2, tol="k6", side="inside")
front.dim.dia("d3", (x2 + P.l3 / 2, r3), (x2 + P.l3 / 2, -r3), value=P.d3, side="inside")
xm = (x3 + P.L) / 2
front.dim.dia("d5", (xm, r2), (xm, -r2), value=P.d2, tol="k6", side="inside")
# 轴向长度：下方链式（最右一段不注），总长另起一排
front.dim.linear("l1", (0, -rs), (x1, -r2), dir="h", value=P.l1, side="bottom")
front.dim.linear("l2", (x1, -r2), (x2, -r3), dir="h", value=P.l2, side="bottom")
front.dim.linear("l3", (x2, -r3), (x3, -r2), dir="h", value=P.l3, side="bottom")
front.dim.linear(
    "L", (0, -rs), (P.L, -r2), dir="h", value=P.L, role="overall", side="bottom", row=2
)
front.dim.chamfer("c", "E.front.body.ch")

# PMI：基准 A-B（两轴颈），花键外圆径向圆跳动，粗糙度
front.datum("A", ref="D.d2")
front.datum("B", ref="D.d5")
front.gtol("run", "circular_runout", 0.03, datums=["A-B"], ref="E.front.body.spl")
front.rough("j1", 0.8, ref="E.front.body.j1", process="磨")
front.rough("j2", 0.8, ref="E.front.body.j2", process="磨")
d.rough_default(6.3)

d.notes.tech(["调质处理 28~32HRC，花键齿部高频淬火 48~53HRC。", "去除毛刺锐边。"])
d.general_tol("m")
d.title(name="花键轴", drawing_no="LC-SP-01", material="40Cr", designer="Liner-CAD")
