"""范例：V 带轮（盘盖类，腹板式）。主视图全剖：轮缘上两个 V 槽（槽角、槽距、槽深由尺寸给出）、
腹板两侧凹进（用 turned 的 holes 表示环形凹槽）、轮毂孔 H7 带键槽（hub_keyway）；左视图是
端面视图，轮毂孔画成带键槽缺口的圆（keyway_end）。"""

import math

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    da=Param(120, min=80, max=250, step=1, label="带轮外径"),
    di=Param(84, min=60, max=200, step=1, label="轮缘内径", rule="di < da - 2*hg - 8"),
    Dh=Param(60, min=34, max=100, step=1, label="轮毂外径", rule="Dh < di - 10"),
    d0=Param(28, min=16, max=60, step=1, label="孔径", tol="H7", rule="d0 < Dh - 12"),
    e=Param(18, min=12, max=30, step=0.5, label="槽距", rule="e > bg + 2"),
    f=Param(11, min=8, max=20, step=0.5, label="第一槽对称面至端面", rule="f > bg / 2 + 2"),
    bg=Param(11, min=8, max=17, step=0.5, label="槽口宽"),
    hg=Param(11, min=8, max=16, step=0.5, label="槽深"),
    ang=Param(34, min=32, max=40, step=1, label="槽角"),
    tw=Param(10, min=6, max=20, step=1, label="腹板厚", rule="tw < 2*f + e - 12"),
)
Ro, Ri, Rh, r0 = P.da / 2, P.di / 2, P.Dh / 2, P.d0 / 2
B = 2 * P.f + P.e  # 轮缘宽（2 槽）
w, hg = P.bg / 2, P.hg
wb = w - hg * math.tan(math.radians(P.ang / 2))  # 槽底半宽
c1, c2 = P.f, P.f + P.e
xa, xb = (B - P.tw) / 2, (B + P.tw) / 2  # 腹板两面
Rm = (Rh + Ri) / 2

front = d.view("front")  # 全剖：x 沿轴线
left = d.view("left")  # 端面视图

front.turned(
    "body",
    [
        (0, Ro - 1, "ch0"),
        (1, Ro, "land0"),
        (c1 - w, Ro, "g1a"),
        (c1 - wb, Ro - hg, "g1bot"),
        (c1 + wb, Ro - hg, "g1b"),
        (c1 + w, Ro, "land1"),
        (c2 - w, Ro, "g2a"),
        (c2 - wb, Ro - hg, "g2bot"),
        (c2 + wb, Ro - hg, "g2b"),
        (c2 + w, Ro, "land2"),
        (B - 1, Ro, "ch1"),
        (B, Ro - 1),
    ],
    bore=[(0, r0), (B, r0)],
    cut="full",
    hub_keyway=True,
    holes=[
        {"name": "rl", "r": Rm, "d": Ri - Rh, "x0": 0, "x1": xa},
        {"name": "rr", "r": Rm, "d": Ri - Rh, "x0": xb, "x1": B},
    ],
)

left.circle((0, 0), Ro, name="outer")
left.circle((0, 0), Ro - 1, name="chamfer")
left.circle((0, 0), Ri, name="rim")
left.circle((0, 0), Rh, name="hub")
left.keyway_end("kw", (0, 0), 28, kind="hub")
left.center_mark((0, 0), Ro, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, -Ro), (0, Ro)])
for k in ("rl_1", "rl_2", "rr_3", "rr_4"):  # 环形凹槽不是圆孔，不要孔的中心线
    d[f"C.front.body_{k}"].suppress()

# 尺寸：直径左（外径、轮缘内径）、右（孔、轮毂）；轴向 f、e 链式在上方，B 为参考尺寸
front.dim.dia("da", (1, Ro), (1, -Ro), value=P.da, side="left")
front.dim.dia("di", (0, Ri), (0, -Ri), value=P.di, side="left", row=2)
front.dim.dia("d0", (B, r0), (B, -r0), value=P.d0, tol="H7", side="right")
front.dim.dia("Dh", (B, Rh), (B, -Rh), value=P.Dh, side="right", row=2)
front.dim.linear("f", (0, Ro), (c1, Ro - hg), dir="h", value=P.f, side="top")
front.dim.linear("e", (c1, Ro - hg), (c2, Ro - hg), dir="h", value=P.e, side="top")
front.dim.linear("B", (0, Ro), (B, Ro), dir="h", value=B, side="top", row=2, reference=True)
front.dim.linear("bg", (c2 - w, -Ro), (c2 + w, -Ro), value=P.bg, side="bottom")
front.dim.linear("hg", (c2 + w, Ro), (c2 + wb, Ro - hg), dir="v", value=P.hg, side="right")
front.dim.angle("ang", "E.front.body.g1a_lo", "E.front.body.g1b_lo", value=P.ang)
front.dim.linear("tw", (xa, Rm), (xb, Rm), dir="h", value=P.tw, side="inside")
front.dim.chamfer("ch", "E.front.body.ch0")
left.dim.keyway("kb", "F.left.kw", what="b", side="inside")
left.dim.keyway("kd", "F.left.kw", what="depth")

# PMI：A = 孔轴线；轮缘外圆对 A 跳动；孔和槽侧面（工作面）粗糙度
front.datum("A", ref="D.d0", at=0)
front.gtol("run", "circular_runout", 0.05, datums=["A"], ref="E.front.body.land1_lo")
front.rough("bore", 1.6, ref="D.d0", at=1)
front.rough("flank", 3.2, ref="E.front.body.g2b")
d.rough_default(12.5)
d.accept("missing", "F.front.body", "V 槽轮廓由槽口宽 bg、槽深 hg、槽角 ang、槽距 e、f 确定")
d.accept(
    "conv_dim",
    "F.left.kw",
    "键槽宽 D.kb、深 D.kd 已标（dim.keyway 的尺寸没有关联到端视图键槽特征）",
)

d.notes.tech(["铸件时效处理。", "铸件不得有砂眼、气孔、裂纹。", "未注倒角 C1。"])
d.general_tol("m")
d.title(name="V 带轮", drawing_no="LC-PU-01", material="HT200", designer="Liner-CAD")
