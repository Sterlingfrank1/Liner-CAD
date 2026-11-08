"""范例：端盖（盘盖类）。主视图过轴线和上方螺孔全剖：止口外圆 h8、阶梯孔 H7、内螺纹（剖视
里小径粗、大径细）；左视图是带螺孔的端面，螺孔用 thread_end 画端视图规定画法，3×M8 均布在
节圆上。基准 A 是孔轴线，止口跳动、背面垂直度、螺孔位置度，配合面标粗糙度。"""

import math

from linercad import Drawing, Param, res

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    D=Param(110, min=80, max=160, step=1, label="外径"),
    T=Param(16, min=10, max=30, step=1, label="盖板厚"),
    Ls=Param(24, min=18, max=45, step=1, label="总长（含止口）", rule="Ls > T + 4"),
    ds=Param(70, min=45, max=110, step=1, label="止口外径", tol="h8", rule="ds < pcd - 8"),
    d0=Param(40, min=20, max=60, step=1, label="孔径", tol="H7", rule="d0 < dc"),
    lb=Param(18, min=8, max=40, step=1, label="孔深（小孔段）", rule="lb < Ls - 3"),
    dc=Param(52, min=26, max=80, step=1, label="沉孔径", rule="dc < ds - 4"),
    pcd=Param(85, min=60, max=140, step=1, label="螺孔中心圆直径", rule="pcd + 10 < D"),
)
R, rs, r0, rc, Rb = P.D / 2, P.ds / 2, P.d0 / 2, P.dc / 2, P.pcd / 2
M8 = res.thread("M8")  # 螺孔 M8（粗牙），螺纹深 10，钻孔深 12.5
TD, DD = 10, 12.5

front = d.view("front")  # 全剖：x 沿轴线，x=0 是带螺孔的外端面
left = d.view("left")  # 端面视图

front.turned(
    "body",
    [(0, R, "rim"), (P.T, R), (P.T, rs, "spig"), (P.Ls - 1, rs, "ch"), (P.Ls, rs - 1)],
    bore=[(0, r0), (P.lb, r0), (P.lb, rc), (P.Ls, rc)],
    cut="full",
    holes=[
        {
            "name": "tap",
            "r": Rb,
            "d": M8["d1"],
            "x0": 0,
            "x1": DD,
            "tip": True,
            "thread": "M8",
            "depth": TD,
            "at": "top",
        }
    ],
)

left.circle((0, 0), R, name="outer")
left.circle((0, 0), r0, name="bore")
left.circle((0, 0), Rb, role="center", name="pcd")
for k in range(3):  # 3×M8 均布，第一个在正上方（落在剖切面上）
    a = math.radians(90 + 120 * k)
    left.thread_end(f"t{k + 1}", (Rb * math.cos(a), Rb * math.sin(a)), "M8", kind="int")
    left.center_mark((Rb * math.cos(a), Rb * math.sin(a)), 6, name=f"c{k + 1}")
left.center_mark((0, 0), R, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, -R), (0, R)])

# 尺寸
front.dim.linear("td", (0, R), (TD, R), value=TD, side="top")  # 螺纹深
front.dim.linear("dd", (0, R), (DD, R), value=DD, side="top", row=2)  # 钻孔深
front.dim.linear("T", (0, -R), (P.T, -R), value=P.T, side="bottom")
front.dim.linear("lb", (0, -R), (P.lb, -rc), dir="h", value=P.lb, side="bottom", row=2)
front.dim.linear("Ls", (0, -R), (P.Ls, -rs), dir="h", value=P.Ls, side="bottom", row=3)
front.dim.dia("D", (0, R), (0, -R), value=P.D, side="left")
front.dim.dia("ds", (P.Ls - 1, rs), (P.Ls - 1, -rs), value=P.ds, tol="h8", side="right", row=3)
front.dim.dia("dc", (P.Ls, rc), (P.Ls, -rc), value=P.dc, side="right", row=2)
front.dim.dia("d0", (P.lb, r0), (P.lb, -r0), value=P.d0, tol="H7", side="right")
front.dim.chamfer("ch", "E.front.body.ch")
left.dim.hole("tap", "F.left.t1", n=3)
left.dim.dia("pcd", circle="E.left.pcd.1", value=P.pcd)

# PMI：A = 孔轴线；止口对 A 跳动、背面对 A 垂直、螺孔位置度；粗糙度
front.datum("A", ref="D.d0", at=0)
back = d.q.lines(view="front").where(dir="v").near(P.T, (rs + R) / 2, r=1).one()
front.gtol("run", "circular_runout", 0.03, datums=["A"], ref="E.front.body.spig")
front.gtol("perp", "perpendicularity", 0.03, datums=["A"], ref=back.id)
left.gtol("pos", "position", 0.2, datums=["A"], zone="dia", ref="D.tap")
front.rough("bore", 1.6, ref="D.d0")
front.rough("spig", 3.2, ref="E.front.body.spig")
front.rough("back", 3.2, ref=back.id)
d.rough_default(12.5)
d.accept("conv_dim", "F.left.t2", "均布螺孔 t1–t3 共用一个代号标注 3×M8-6H")
d.accept("conv_dim", "F.left.t3", "均布螺孔 t1–t3 共用一个代号标注 3×M8-6H")

d.notes.tech(["铸件不得有砂眼、气孔、裂纹。", "未注倒角 C1。"])
d.general_tol("m")
d.title(name="端盖", drawing_no="LC-EC-01", material="HT200", designer="Liner-CAD")
