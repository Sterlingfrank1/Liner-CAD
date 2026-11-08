"""轴承透盖（盘盖类）。主视图全剖：止口 f7 嵌入座孔，通孔内有矩形密封槽（毛毡圈），4 个
安装孔在上下两处被剖到；左视图是端面视图。基准 A 取止口轴线（它决定盖对座孔的定位）。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    D=Param(100, min=70, max=160, step=1, label="外径"),
    T=Param(12, min=8, max=20, step=1, label="盖板厚"),
    Ls=Param(22, min=14, max=40, step=1, label="总长（含止口）", rule="Ls > T + 4"),
    ds=Param(62, min=40, max=110, step=1, label="止口外径", tol="f7", rule="ds < pcd - 12"),
    d0=Param(36, min=16, max=60, step=1, label="孔径", tol="H9", rule="d0 + 2*hg < ds - 10"),
    g0=Param(4, min=2, max=10, step=0.5, label="槽距端面", rule="g0 + gw < Ls - 3"),
    gw=Param(5, min=3, max=10, step=0.5, label="槽宽"),
    hg=Param(4, min=2, max=8, step=0.5, label="槽深"),
    pcd=Param(80, min=60, max=140, step=1, label="安装孔中心圆直径", rule="pcd + dh + 6 < D"),
    dh=Param(9, min=6, max=14, step=0.5, label="安装孔径"),
)
R, rs, r0, Rb = P.D / 2, P.ds / 2, P.d0 / 2, P.pcd / 2
rg = r0 + P.hg

front = d.view("front")  # 全剖：x 沿轴线，x=0 是外端面
left = d.view("left")  # 端面视图

front.turned(
    "body",
    [(0, R, "rim"), (P.T, R), (P.T, rs, "spig"), (P.Ls - 1, rs, "ch"), (P.Ls, rs - 1)],
    bore=[
        (0, r0 + 1),
        (1, r0),
        (P.g0, r0),
        (P.g0, rg),
        (P.g0 + P.gw, rg),
        (P.g0 + P.gw, r0),
        (P.Ls, r0),
    ],
    cut="full",
    holes=[{"name": "bolt", "r": Rb, "d": P.dh, "x0": 0, "x1": P.T}],
)

left.circle((0, 0), R, name="outer")
left.circle((0, 0), r0, name="bore")
left.circle((0, 0), r0 + 1, name="bch")
left.holes_on_circle("bolt", (0, 0), pcd=P.pcd, n=4, d=P.dh, start=90)
left.center_mark((0, 0), R, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, -R), (0, R)])

# 尺寸
front.dim.dia("D", (0, R), (0, -R), value=P.D, side="left")
front.dim.dia("ds", (P.Ls - 1, rs), (P.Ls - 1, -rs), value=P.ds, tol="f7", side="right", row=2)
front.dim.dia("d0", (P.Ls, r0), (P.Ls, -r0), value=P.d0, tol="H9", side="right")
front.dim.linear("T", (0, -R), (P.T, -R), value=P.T, side="bottom")
front.dim.linear("Ls", (0, -R), (P.Ls, -rs), dir="h", value=P.Ls, side="bottom", row=3)
front.dim.linear("g0", (0, rg), (P.g0, rg), dir="h", value=P.g0, side="top")
front.dim.linear("gw", (P.g0, rg), (P.g0 + P.gw, rg), dir="h", value=P.gw, side="top", row=2)
front.dim.dia(
    "dg", (P.g0 + P.gw / 2, rg), (P.g0 + P.gw / 2, -rg), value=P.d0 + 2 * P.hg, side="inside"
)
front.dim.chamfer("ch", "E.front.body.ch")
left.dim.dia("bolt", circle="E.left.bolt.1", value=P.dh, prefix="4×", suffix=" EQS", at=120)
left.dim.dia("pcd", circle="C.left.bolt", value=P.pcd, at=-45)

# PMI：A = 止口轴线；孔对 A 同轴、端盖背面对 A 垂直、安装孔位置度
front.datum("A", ref="D.ds", at=1)
back = d.q.lines(view="front").where(dir="v").near(P.T, (rs + R) / 2, r=1).one()
back_lo = d.q.lines(view="front").where(dir="v").near(P.T, -(rs + R) / 2, r=1).one()
front.gtol("conc", "concentricity", 0.05, datums=["A"], zone="dia", ref="D.d0", at=0)
front.gtol("perp", "perpendicularity", 0.04, datums=["A"], ref=back.id, at=0.3, length=24)
left.gtol("pos", "position", 0.2, datums=["A"], zone="dia", ref="D.bolt", at=0, length=12)
front.rough("spig", 1.6, ref="E.front.body.spig")
front.rough("back", 3.2, ref=back_lo.id, at=0.3, length=20)
d.rough_default(12.5)

d.notes.tech(["铸件不得有砂眼、气孔、裂纹。", "未注倒角 C1。"])
d.general_tol("m")
d.title(name="轴承透盖", drawing_no="LC-BC-01", material="HT200", designer="Liner-CAD")
