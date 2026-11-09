"""连杆（叉架类）：大头、小头两个带孔的凸台，杆身是两圆的外公切线围成的平板（圆弧连接：切线与圆相切，
定形尺寸是两圆直径，定位尺寸是中心距），平板正面有一条加强筋。主视图表达外形，俯视图表达各段厚度，
杆身断面用移出断面 B-B（T 形）。基准 A 是大头孔轴线，小头孔轴线对 A 的平行度。
模型轴：X 向右，Y 向后，Z 向上。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)；孔轴线沿 Y。"""

import math

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(100, min=70, max=160, step=1, label="中心距", rule="L > D1 / 2 + D2 / 2 + 10"),
    D1=Param(44, min=30, max=70, step=1, label="大头外径", rule="D1 > d1 + 8"),
    D2=Param(28, min=20, max=50, step=1, label="小头外径", rule="D2 > d2 + 8"),
    d1=Param(24, min=12, max=40, step=1, label="大头孔径", tol="H7"),
    d2=Param(12, min=6, max=24, step=1, label="小头孔径", tol="H7"),
    b1=Param(24, min=14, max=40, step=1, label="大头长"),
    b2=Param(18, min=10, max=32, step=1, label="小头长"),
    tw=Param(8, min=5, max=14, step=1, label="杆身厚", rule="tw < b2"),
    rw=Param(6, min=4, max=10, step=1, label="加强筋宽"),
    rh=Param(3, min=2, max=6, step=1, label="加强筋高", rule="tw / 2 + rh < b2 / 2"),
)
L, R1, R2 = P.L, P.D1 / 2, P.D2 / 2
r1, r2, b1, b2, tw, rw, rh = P.d1 / 2, P.d2 / 2, P.b1, P.b2, P.tw, P.rw, P.rh
nx = (R1 - R2) / L  # 外公切线的法向 (nx, ny)
ny = math.sqrt(1 - nx**2)
t1 = (R1 * nx, R1 * ny)  # 切点：大头圆 / 小头圆（上侧，下侧对称）
t2 = (L + R2 * nx, R2 * ny)
xa = math.sqrt(R1**2 - (rw / 2) ** 2)  # 加强筋两端：与大头 / 小头圆的交点
xb = L - math.sqrt(R2**2 - (rw / 2) ** 2)
xm = 0.6 * L  # 移出断面的位置（杆身中部偏小头，避开中心距尺寸的数字）
zm = (R1 - nx * xm) / ny  # 该处杆身半宽
yr = tw / 2 + rh  # 加强筋前表面（-Y 侧）

# ---- 主视图 (X, Z)：孔轴线垂直于图面
front = d.view("front")
front.move(dx=12, dy=-10)
front.circle((0, 0), R1, name="boss1")
front.circle((0, 0), r1, name="bore1")
front.circle((L, 0), R2, name="boss2")
front.circle((L, 0), r2, name="bore2")
front.line(t1, t2, name="web_t")
front.line((t1[0], -t1[1]), (t2[0], -t2[1]), name="web_b")
front.line((xa, rw / 2), (xb, rw / 2), name="rib_t")
front.line((xa, -rw / 2), (xb, -rw / 2), name="rib_b")
front.center_mark((0, 0), R1, name="c1")
front.center_mark((L, 0), R2, name="c2")
front.centerline((-R1 - 5, 0), (L + R2 + 5, 0), name="axis")

# ---- 俯视图 (X, Y)
top = d.view("top")
top.line((-R1, -b1 / 2), (-R1, b1 / 2), name="b1_l")
top.line((-R1, b1 / 2), (R1, b1 / 2), name="b1_b")
top.line((-R1, -b1 / 2), (R1, -b1 / 2), name="b1_f")
top.line((R1, b1 / 2), (R1, tw / 2), name="b1_rb")
top.line((R1, -b1 / 2), (R1, -yr), name="b1_rf")
top.line((t1[0], tw / 2), (t2[0], tw / 2), name="web_b")
top.line((t1[0], -tw / 2), (t2[0], -tw / 2), name="web_f")
top.line((xa, -tw / 2), (xa, -yr), name="rib_a")
top.line((xa, -yr), (xb, -yr), name="rib_f")
top.line((xb, -tw / 2), (xb, -yr), name="rib_b")
top.line((L - R2, b2 / 2), (L - R2, tw / 2), name="b2_lb")
top.line((L - R2, -b2 / 2), (L - R2, -yr), name="b2_lf")
top.line((L - R2, b2 / 2), (L + R2, b2 / 2), name="b2_b")
top.line((L - R2, -b2 / 2), (L + R2, -b2 / 2), name="b2_f")
top.line((L + R2, -b2 / 2), (L + R2, b2 / 2), name="b2_r")
for k, (x, r) in enumerate(((0, r1), (L, r2)), 1):  # 孔（虚线）
    top.line(
        (x - r, -(b1 if k == 1 else b2) / 2),
        (x - r, (b1 if k == 1 else b2) / 2),
        role="hidden",
        name=f"h{k}_l",
    )
    top.line(
        (x + r, -(b1 if k == 1 else b2) / 2),
        (x + r, (b1 if k == 1 else b2) / 2),
        role="hidden",
        name=f"h{k}_r",
    )
top.centerline((0, -b1 / 2 - 4), (0, b1 / 2 + 4), name="c1")
top.centerline((L, -b2 / 2 - 4), (L, b2 / 2 + 4), name="c2")

# ---- 左视图 (-Y, Z)：只剩大头外形，其余在它后面（虚线）
left = d.view("left")
left.polygon([(-b1 / 2, -R1), (b1 / 2, -R1), (b1 / 2, R1), (-b1 / 2, R1)], name="boss1")
left.line((-b1 / 2, r1), (b1 / 2, r1), role="hidden", name="bore1_t")
left.line((-b1 / 2, -r1), (b1 / 2, -r1), role="hidden", name="bore1_b")
left.polygon(
    [(-b2 / 2, -R2), (b2 / 2, -R2), (b2 / 2, R2), (-b2 / 2, R2)], role="hidden", name="boss2"
)
left.line((-b2 / 2, r2), (b2 / 2, r2), role="hidden", name="bore2_t")
left.line((-b2 / 2, -r2), (b2 / 2, -r2), role="hidden", name="bore2_b")
left.centerline((-b1 / 2 - 5, 0), (b1 / 2 + 5, 0), name="axis")

# ---- 移出断面 B-B：杆身中部的 T 形断面（筋在 -Y 侧，u = +y，所以筋在左）
sec = d.removed_section("B", parent="front", through=[(xm, -zm - 6), (xm, zm + 6)], look="left")
sec.polygon(
    [
        (-yr, -rw / 2),
        (-tw / 2, -rw / 2),
        (-tw / 2, -zm),
        (tw / 2, -zm),
        (tw / 2, zm),
        (-tw / 2, zm),
        (-tw / 2, rw / 2),
        (-yr, rw / 2),
    ],
    name="web",
)
sec.hatch("b", loops=["F.B.web"])

# ---- 尺寸：主视图
front.dim.dia("D1", circle="E.front.boss1.1", value=P.D1, at=100)
front.dim.dia("D2", circle="E.front.boss2.1", value=P.D2, at=60)
front.dim.dia("d1", circle="E.front.bore1.1", value=P.d1, tol="H7", at=-50)
front.dim.dia("d2", circle="E.front.bore2.1", value=P.d2, tol="H7", at=-50)
front.dim.linear(
    "L",
    (0, -R1),
    (L, -R2),
    dir="h",
    value=L,
    role="position",
    datum="E.front.bore1.1:center",
    side="bottom",
)
front.dim.linear(
    "Lt",
    (-R1, -R1),
    (L + R2, -R2),
    dir="h",
    value=L + R1 + R2,
    role="overall",
    side="bottom",
    row=2,
)

# ---- 尺寸：俯视图、断面
top.dim.linear("b1", (-R1, -b1 / 2), (-R1, b1 / 2), dir="v", value=b1, side="left")
top.dim.linear("b2", (L + R2, -b2 / 2), (L + R2, b2 / 2), dir="v", value=b2, side="right")
sec.dim.linear("tw", (-tw / 2, zm), (tw / 2, zm), dir="h", value=tw, side="top")
sec.dim.linear("rw", (-yr, -rw / 2), (-yr, rw / 2), dir="v", value=rw, side="left")
sec.dim.linear(
    "zw", (tw / 2, -zm), (tw / 2, zm), dir="v", value=round(2 * zm, 1), reference=True, side="right"
)
sec.dim.linear("rh", (-yr, -rw / 2), (-tw / 2, -rw / 2), dir="h", value=rh, side="bottom")

# ---- 剖切符号 B-B 由移出断面生成；PMI
front.datum("A", ref="D.d1", at=0)
front.gtol("par", "parallelism", 0.05, datums=["A"], zone="dia", ref="D.d2", at=1)
front.rough("bore1", 1.6, ref="D.d1")
front.rough("bore2", 1.6, ref="D.d2")
top.rough("end", 3.2, ref="E.top.b1_f.1", at=0.3, length=10)
d.rough_default(12.5)

d.notes.tech(["铸件不得有砂眼、气孔、裂纹。", "未注铸造圆角 R3~R5。", "时效处理。"])
d.general_tol("m")
d.title(name="连杆", drawing_no="LC-LK-01", material="HT200", designer="Liner-CAD")
