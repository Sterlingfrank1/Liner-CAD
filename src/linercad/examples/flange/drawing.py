"""范例：法兰盘（盘盖类）。主视图用 turned(cut="full") 全剖（剖切面过轴线和上下两个螺栓孔），
左视图为端面视图；孔轴线为基准 A，端面垂直度、外圆跳动、螺栓孔位置度，配合孔 H7 + 粗糙度。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    D=Param(120, min=80, max=200, step=1, label="外径"),
    Dh=Param(60, min=30, max=120, step=1, label="凸台外径", rule="Dh < pcd - dh"),
    d0=Param(30, min=10, max=60, step=0.5, label="中心孔径", tol="H7", rule="d0 < Dh"),
    T=Param(15, min=8, max=40, step=1, label="盘厚"),
    L=Param(40, min=20, max=80, step=1, label="总长", rule="L > T"),
    pcd=Param(90, min=50, max=180, step=1, label="螺栓孔中心圆直径", rule="pcd + dh < D"),
    dh=Param(12, min=6, max=20, step=0.5, label="螺栓孔径"),
)
R, Rh, r0, Rb = P.D / 2, P.Dh / 2, P.d0 / 2, P.pcd / 2

front = d.view("front")  # 全剖：x 沿轴线
left = d.view("left")  # 端面视图

front.turned(
    "body",
    [(0, R, "rim"), (P.T, R), (P.T, Rh, "hub"), (P.L - 1, Rh, "ch"), (P.L, Rh - 1)],
    bore=[(0, r0), (P.L - 1, r0), (P.L, r0 + 1)],
    cut="full",
    holes=[{"name": "bolt", "r": Rb, "d": P.dh, "x0": 0, "x1": P.T}],
)
left.circle((0, 0), R, name="outer")
left.circle((0, 0), r0, name="bore")
left.holes_on_circle("bolt", (0, 0), pcd=P.pcd, n=4, d=P.dh, start=90)
left.center_mark((0, 0), R, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, -R), (0, R)])

front.dim.linear("T", (0, -R), (P.T, -R), value=P.T, side="bottom")
front.dim.linear("L", (0, -R), (P.L, -Rh), dir="h", value=P.L, side="bottom", row=2)
front.dim.dia("D", (0, R), (0, -R), value=P.D, side="left")
front.dim.dia("Dh", (P.L - 1, Rh), (P.L - 1, -Rh), value=P.Dh, side="right")
front.dim.dia("d0", (P.L - 1, r0), (P.L - 1, -r0), value=P.d0, tol="H7", side="right")
front.dim.chamfer("ch", "E.front.body.ch")
left.dim.dia("holes", circle="E.left.bolt.1", value=P.dh, prefix="4×", suffix=" EQS", at=120)
left.dim.dia("pcd", circle="C.left.bolt", value=P.pcd)

# PMI：孔轴线为基准 A；端面对 A 垂直、外圆对 A 跳动、螺栓孔位置度
front.datum("A", ref="D.d0", at=0)
face = d.q.lines(view="front").where(dir="v", length=P.D).near(0, 0, r=1).one()
front.gtol("perp", "perpendicularity", 0.03, datums=["A"], ref=face.id)
front.gtol("run", "circular_runout", 0.05, datums=["A"], ref="E.front.body.rim")
left.gtol("pos", "position", 0.1, datums=["A"], zone="dia", ref="D.holes", at=0, length=12)
front.rough("bore", 1.6, ref="D.d0")
front.rough("face", 3.2, ref=face.id)
d.rough_default(12.5)

d.notes.tech(["铸件时效处理。", "铸件不得有砂眼、裂纹等缺陷。", "未注倒角 C1。"])
d.general_tol("m")
d.title(name="法兰盘", drawing_no="LC-FL-01", material="HT200", designer="Liner-CAD")
