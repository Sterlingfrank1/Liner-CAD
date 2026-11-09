"""范例：拨叉（叉架类）。主视图按工作位置、孔轴线垂直于图面，表达套筒、臂和叉口的外形；俯视图沿
孔轴线全剖（B-B，过臂和叉口槽的对称面），左视图补厚度关系；臂的断面用移出断面 C-C。
基准 A 是孔轴线，叉口槽对 A 的对称度、套筒端面对 A 的垂直度；孔 Φ22H7 和槽 24H12 标粗糙度。
模型轴：X 向右，Y 向后，Z 向上。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)；孔轴线是 Y 轴。"""

import math

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    D=Param(40, min=30, max=60, step=1, label="套筒外径", rule="D > d + 10"),
    d=Param(22, min=12, max=32, step=1, label="孔径", tol="H7"),
    Lh=Param(36, min=24, max=60, step=1, label="套筒长"),
    tw=Param(12, min=8, max=20, step=1, label="臂厚", rule="tw < tj"),
    wa=Param(28, min=16, max=36, step=1, label="臂宽", rule="wa < hj"),
    xj=Param(62, min=50, max=80, step=1, label="叉口起点距孔轴线", rule="xj > D / 2 + 20"),
    L=Param(100, min=80, max=130, step=1, label="孔轴线到叉口端面", rule="L > xs"),
    tj=Param(24, min=16, max=36, step=1, label="叉口厚"),
    hj=Param(44, min=32, max=60, step=1, label="叉口高", rule="hj > ws + 8"),
    ws=Param(24, min=12, max=32, step=1, label="槽宽", tol="H12"),
    xs=Param(88, min=70, max=120, step=1, label="槽底圆心距孔轴线", rule="xs > xj + ws / 2"),
)
R, r, Lh, tw, wa, xj, L = P.D / 2, P.d / 2, P.Lh, P.tw, P.wa, P.xj, P.L
tj, hj, ws, xs = P.tj, P.hj, P.ws, P.xs
rs = ws / 2  # 槽底半圆半径
xa = math.sqrt(R**2 - (wa / 2) ** 2)  # 臂的上下边与套筒外圆的交点
xm = (xj + R) / 2 + 4  # 移出断面 C-C 的位置（臂中部）

# ---- 主视图 (X, Z)：孔轴线垂直于图面
front = d.view("front")
front.move(dx=40, dy=-22)
front.circle((0, 0), R, name="hub")
front.circle((0, 0), r, name="bore")
front.line((xa, wa / 2), (xj, wa / 2), name="arm_t")
front.line((xa, -wa / 2), (xj, -wa / 2), name="arm_b")
front.line((xj, -hj / 2), (xj, hj / 2), name="jaw_l")
front.line((xj, hj / 2), (L, hj / 2), name="jaw_t")
front.line((xj, -hj / 2), (L, -hj / 2), name="jaw_b")
front.line((L, hj / 2), (L, rs), name="end_t")
front.line((L, -hj / 2), (L, -rs), name="end_b")
front.line((xs, rs), (L, rs), name="slot_t")
front.line((xs, -rs), (L, -rs), name="slot_b")
front.arc((xs, 0), rs, 90, 270, name="slot")
front.center_mark((0, 0), R, name="axis")
front.centerline((R + 4, 0), (xs, 0), name="sym")  # 到槽底圆心为止，给槽宽尺寸留位置
front.centerline((xs, -hj / 2 - 4), (xs, hj / 2 + 4), name="slot_c")

# ---- 俯视图 (X, Y)：沿孔轴线全剖 B-B（z = 0，过臂和槽的对称面）
top = d.view("top")
top.polygon(
    [
        (r, -Lh / 2),
        (R, -Lh / 2),
        (R, -tw / 2),
        (xj, -tw / 2),
        (xj, -tj / 2),
        (xs - rs, -tj / 2),
        (xs - rs, tj / 2),
        (xj, tj / 2),
        (xj, tw / 2),
        (R, tw / 2),
        (R, Lh / 2),
        (r, Lh / 2),
    ],
    name="cut_r",
)
top.polygon([(-R, -Lh / 2), (-r, -Lh / 2), (-r, Lh / 2), (-R, Lh / 2)], name="cut_l")
top.line((-r, Lh / 2), (r, Lh / 2), name="bore_t")  # 孔口下半圆在剖视图里投影成直线
top.line((-r, -Lh / 2), (r, -Lh / 2), name="bore_b")
top.line((xs - rs, tj / 2), (L, tj / 2), name="prong_t")  # 剖切面以下的叉口（可见）
top.line((xs - rs, -tj / 2), (L, -tj / 2), name="prong_b")
top.line((L, -tj / 2), (L, tj / 2), name="prong_e")
top.hatch("b", loops=["F.top.cut_r", "F.top.cut_l"])
top.centerline((0, -Lh / 2 - 6), (0, Lh / 2 + 6), name="axis")
top.centerline((-R - 6, 0), (L + 6, 0), name="sym")

# ---- 左视图 (-Y, Z)：套筒挡住了臂和槽，只剩叉口上下凸出的部分
left = d.view("left")
left.polygon([(-Lh / 2, -R), (Lh / 2, -R), (Lh / 2, R), (-Lh / 2, R)], name="hub")
left.polyline([(-tj / 2, R), (-tj / 2, hj / 2), (tj / 2, hj / 2), (tj / 2, R)], name="jaw_t")
left.polyline([(-tj / 2, -R), (-tj / 2, -hj / 2), (tj / 2, -hj / 2), (tj / 2, -R)], name="jaw_b")
left.line((-Lh / 2, r), (Lh / 2, r), role="hidden", name="bore_t")
left.line((-Lh / 2, -r), (Lh / 2, -r), role="hidden", name="bore_b")
left.line((-tj / 2, rs), (tj / 2, rs), role="hidden", name="slot_t")
left.line((-tj / 2, -rs), (tj / 2, -rs), role="hidden", name="slot_b")
left.centerline((-Lh / 2 - 6, 0), (Lh / 2 + 6, 0), name="axis")

# ---- 移出断面 C-C：臂（矩形）
sec = d.removed_section(
    "C", parent="front", through=[(xm, -wa / 2 - 4), (xm, wa / 2 + 4)], look="left"
)
sec.rect((-tw / 2, -wa / 2), tw, wa, name="arm")
sec.hatch("c", loops=["F.C.arm"])

# ---- 尺寸：主视图
front.dim.dia("D", circle="E.front.hub.1", value=P.D, at=135)
front.dim.dia("d", circle="E.front.bore.1", value=P.d, tol="H7", at=45)
front.dim.linear("hj", (L, -hj / 2), (L, hj / 2), dir="v", value=hj, side="right")
xw = L - 3
front.dim.linear("ws", (xw, -rs), (xw, rs), dir="v", value=ws, tol="H12", side="inside")
front.dim.linear(
    "xs",
    (0, -R),
    (xs, -hj / 2),
    dir="h",
    value=xs,
    role="position",
    datum="E.front.bore.1:center",
    side="bottom",
    row=2,
)
front.dim.linear("L", (0, -R), (L, -hj / 2), dir="h", value=L, role="overall", side="bottom", row=3)
front.dim.linear("lj", (xj, -hj / 2), (L, -hj / 2), dir="h", value=L - xj, side="bottom", row=1)

# ---- 尺寸：俯视图、左视图、断面
top.dim.linear("Lh", (-R, -Lh / 2), (-R, Lh / 2), dir="v", value=Lh, side="left")
top.dim.linear("tj", (L, -tj / 2), (L, tj / 2), dir="v", value=tj, side="right")
sec.dim.linear("tw", (-tw / 2, -wa / 2), (tw / 2, -wa / 2), dir="h", value=tw, side="bottom")
sec.dim.linear("wa", (tw / 2, -wa / 2), (tw / 2, wa / 2), dir="v", value=wa, side="right")

# ---- 剖切符号
d.section("B", view="top", cut_in="front", through=[(-R - 10, 0), (L + 10, 0)])

# ---- PMI：基准 A = 孔轴线
front.datum("A", ref="D.d")
front.gtol("sym", "symmetry", 0.1, datums=["A"], ref="D.ws")
front.rough("bore", 1.6, ref="D.d")
front.rough("slot", 3.2, ref="E.front.slot_t.1", at=0.3, length=10)
d.rough_default(12.5)

d.notes.tech(["铸件不得有砂眼、气孔、裂纹。", "未注铸造圆角 R3~R5。", "时效处理。"])
d.general_tol("m")
d.title(name="拨叉", drawing_no="LC-SF-01", material="HT200", designer="Liner-CAD")
