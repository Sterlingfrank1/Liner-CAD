"""齿轮坯（盘盖类）。对称零件：主视图半剖（上半剖开：孔、孔内键槽、减轻孔；下半保持外形），
左视图是端面视图，孔带键槽缺口（keyway_end）、6 个减轻孔均布（holes_on_circle）。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    da=Param(126, min=80, max=200, step=1, label="齿顶圆直径", tol="h11"),
    B=Param(30, min=15, max=60, step=1, label="齿宽"),
    L=Param(45, min=20, max=80, step=1, label="总长（含轮毂）", rule="L > B"),
    Dh=Param(60, min=40, max=100, step=1, label="轮毂外径", rule="Dh < pcd - dl"),
    d0=Param(32, min=22, max=38, step=1, label="孔径", tol="H7", rule="d0 < Dh - 14"),
    pcd=Param(92, min=70, max=160, step=1, label="减轻孔中心圆直径", rule="pcd + dl < da - 14"),
    dl=Param(16, min=8, max=30, step=1, label="减轻孔直径"),
)
R, Rh, r0, Rb = P.da / 2, P.Dh / 2, P.d0 / 2, P.pcd / 2

front = d.view("front")  # 半剖：x 沿轴线，上半剖开
left = d.view("left")  # 端面视图（看齿轮坯的盘面一侧）

front.turned(
    "body",
    [(0, R - 1.5, "ch0"), (1.5, R, "rim"), (P.B - 1.5, R, "ch1"), (P.B, R - 1.5), (P.B, Rh, "hubf"), (P.L, Rh, "hub")],
    bore=[(0, r0), (P.L, r0)],
    cut="half",
    half="top",
    hub_keyway=True,
    holes=[{"name": "lh", "r": Rb, "d": P.dl, "x0": 0, "x1": P.B}],
)

left.circle((0, 0), R, name="outer")
left.circle((0, 0), R - 1.5, name="chamfer")
left.keyway_end("kw", (0, 0), 32, kind="hub")
left.holes_on_circle("lh", (0, 0), pcd=P.pcd, n=6, d=P.dl, start=90)
left.center_mark((0, 0), R, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, -R), (0, R)])

# 尺寸
front.dim.dia("da", (1.5, R), (1.5, -R), value=P.da, tol="h11", side="left")
front.dim.dia("Dh", (P.L, Rh), (P.L, -Rh), value=P.Dh, side="right", row=2)
front.dim.dia("d0", (P.L, r0), (P.L, -r0), value=P.d0, tol="H7", side="right")
front.dim.linear("B", (0, -R), (P.B, -R + 1.5), dir="h", value=P.B, side="bottom")
front.dim.linear("L", (0, -R), (P.L, -Rh), dir="h", value=P.L, side="bottom", row=2)
front.dim.chamfer("ch", "E.front.body.ch0")
front.dim.chamfer("ch2", "E.front.body.ch1")
left.dim.dia("lh", circle="E.left.lh.1", value=P.dl, prefix="6×", suffix=" EQS", at=60)
left.dim.dia("pcd", circle="C.left.lh", value=P.pcd)
left.dim.keyway("kb", "F.left.kw", what="b", side="inside")
left.dim.keyway("kd", "F.left.kw", what="depth")

# PMI：A = 孔轴线；齿顶圆径向跳动、端面（定位面）轴向跳动；孔、端面、齿顶圆粗糙度
front.datum("A", ref="D.d0", at=0)
front.gtol("run", "circular_runout", 0.03, datums=["A"], ref="E.front.body.rim_lo")
front.rough("bore", 1.6, ref="D.d0", at=1)
front.rough("rim", 3.2, ref="E.front.body.rim")
d.rough_default(6.3)
d.accept("conv_dim", "F.left.kw", "键槽宽 D.kb、深 D.kd 已标（dim.keyway 的尺寸没有关联到端视图键槽特征）")

d.notes.tech(["正火处理 170~217HBW。", "未注倒角 C1.5。", "齿坯各面不得有裂纹、夹渣。"])
d.general_tol("m")
d.title(name="齿轮坯", drawing_no="LC-GB-01", material="45", designer="Liner-CAD")
