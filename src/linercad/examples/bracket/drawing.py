"""范例：L 形支架（叉架类的简单形式）。主、俯、左三视图，长对正、高平齐、宽相等；
孔在不反映圆的视图里用细虚线和点画线表达。
模型轴：X 向右（长），Y 向后（宽），Z 向上（高）。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    A=Param(80, min=40, max=160, step=1, label="长"),
    B=Param(50, min=30, max=100, step=1, label="宽"),
    H=Param(60, min=30, max=120, step=1, label="高"),
    t=Param(10, min=5, max=20, step=1, label="板厚"),
    hb=Param(40, min=15, max=100, step=1, label="立板孔中心高", rule="hb < H"),
    D=Param(20, min=6, max=40, step=1, label="立板孔径"),
    e=Param(15, min=8, max=40, step=1, label="底板孔边距"),
    yb=Param(20, min=8, max=40, step=1, label="底板孔前后位置"),
    d=Param(10, min=5, max=20, step=0.5, label="底板孔径"),
)
A, B, H, t = P.A, P.B, P.H, P.t
xb1, xb2 = P.e, A - P.e  # 底板两孔 x
yf = B - t  # 立板前面的 Y

# ---- 主视图 (X, Z)
front = d.view("front")
front.rect((0, 0), A, H, name="outline")
front.line((0, t), (A, t), name="base_top")
front.circle((A / 2, P.hb), P.D / 2, name="hole")
front.center_mark((A / 2, P.hb), P.D / 2, name="hole")
for k, x in ((1, xb1), (2, xb2)):
    front.line((x - P.d / 2, 0), (x - P.d / 2, t), role="hidden", name=f"bh{k}_a")
    front.line((x + P.d / 2, 0), (x + P.d / 2, t), role="hidden", name=f"bh{k}_b")
    front.centerline((x, 0), (x, t), name=f"bh{k}")

# ---- 俯视图 (X, Y)：立板在后（靠近主视图一侧）
top = d.view("top")
top.rect((0, 0), A, B, name="outline")
top.line((0, yf), (A, yf), name="wall_front")
for k, x in ((1, xb1), (2, xb2)):
    top.circle((x, P.yb), P.d / 2, name=f"bh{k}")
    top.center_mark((x, P.yb), P.d / 2, name=f"bh{k}")
top.line((A / 2 - P.D / 2, yf), (A / 2 - P.D / 2, B), role="hidden", name="vh_a")
top.line((A / 2 + P.D / 2, yf), (A / 2 + P.D / 2, B), role="hidden", name="vh_b")
top.centerline((A / 2, yf), (A / 2, B), name="vh")

# ---- 左视图 (-Y, Z)：L 形
left = d.view("left")
left.polygon([(-B, 0), (0, 0), (0, t), (-yf, t), (-yf, H), (-B, H)], name="outline")
left.line((-B, P.hb - P.D / 2), (-yf, P.hb - P.D / 2), role="hidden", name="vh_a")
left.line((-B, P.hb + P.D / 2), (-yf, P.hb + P.D / 2), role="hidden", name="vh_b")
left.centerline((-B, P.hb), (-yf, P.hb), name="vh")
left.line((-P.yb - P.d / 2, 0), (-P.yb - P.d / 2, t), role="hidden", name="bh_a")
left.line((-P.yb + P.d / 2, 0), (-P.yb + P.d / 2, t), role="hidden", name="bh_b")
left.centerline((-P.yb, 0), (-P.yb, t), name="bh")

# ---- 尺寸
front.dim.linear("A", (0, 0), (A, 0), value=A, role="overall", side="bottom")
front.dim.linear("H", (0, 0), (0, H), value=H, role="overall", side="left")
front.dim.linear(
    "hb", (A, 0), (A, P.hb), value=P.hb, role="position", datum="E.front.outline.1", side="right"
)
front.dim.dia("D", circle="E.front.hole.1", value=P.D, tol="H8")
front.dim.linear(
    "xh",
    (0, H),
    (A / 2, P.hb),
    dir="h",
    value=A / 2,
    role="position",
    datum="E.front.outline.4",
    side="top",
)
top.dim.linear("B", (A, 0), (A, B), value=B, role="overall", side="right")
top.dim.linear(
    "pitch",
    (xb1, P.yb),
    (xb2, P.yb),
    value=xb2 - xb1,
    role="position",
    datum="E.top.bh1.1:center",
    side="bottom",
)
top.dim.linear(
    "e", (0, P.yb), (xb1, P.yb), value=P.e, role="position", datum="E.top.outline.4", side="bottom"
)
top.dim.linear(
    "yb", (xb1, 0), (xb1, P.yb), value=P.yb, role="position", datum="E.top.outline.1", side="left"
)
top.dim.dia("dh", circle="E.top.bh1.1", value=P.d, prefix="2×")
left.dim.linear("t", (0, 0), (0, t), value=t, side="right")
left.dim.linear("tw", (-B, H), (-yf, H), value=t, side="top")

d.general_tol("m")
d.notes.tech(["去除毛刺锐边。"])
d.title(name="支架", drawing_no="LC-BR-01", material="Q235", designer="Liner-CAD")
