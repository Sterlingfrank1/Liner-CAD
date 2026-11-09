"""范例：齿轮箱盖（箱体类，3D 来源）。几何全部由 model.py 投影：主视全剖、俯视外形、左视局部剖；
尺寸、技术要求、形位公差照常标在投影出的边上。
模型轴：X 向右（长），Y 向后（宽），Z 向上（高）。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(150, min=140, max=240, step=2, label="底板长", rule="L >= A + 2 * e + dh"),
    W=Param(110, min=90, max=160, step=2, label="底板宽", rule="W >= B + 2 * e + dh"),
    t=Param(10, min=6, max=16, step=1, label="底板厚"),
    A=Param(110, min=80, max=180, step=2, label="箱长"),
    B=Param(70, min=60, max=120, step=2, label="箱宽"),
    H=Param(55, min=40, max=100, step=1, label="箱高"),
    s=Param(5, min=4, max=10, step=0.5, label="壁厚"),
    D=Param(46, min=36, max=70, step=1, label="凸台直径", rule="D < B"),
    h=Param(12, min=8, max=30, step=1, label="凸台高"),
    d=Param(28, min=16, max=45, step=1, label="轴承孔径", rule="d < D - 10"),
    dh=Param(11, min=7, max=14, step=0.5, label="底板孔径"),
    e=Param(10, min=8, max=20, step=1, label="孔边距"),
)
L, W, t, A, B, H, s, D, h = P.L, P.W, P.t, P.A, P.B, P.H, P.s, P.D, P.h
d.model("model.py")

# ---- 主视图 (X, Z)：沿前后对称面全剖
front = d.view("front")
front.project(cut="full")
front.move(dx=12)
front.centerline((0, H - s - 5), (0, H + h + 5), name="axis")
front.dim.linear("L", (-L / 2, 0), (L / 2, 0), value=L, role="overall", side="bottom")
front.dim.linear(
    "Htot", (L / 2, 0), (D / 2, H + h), dir="v", value=H + h, role="overall", side="right"
)
front.dim.linear("H", (-A / 2, 0), (-A / 2, H), value=H, side="left")
front.dim.linear("t", (-L / 2, 0), (-L / 2, t), value=t, side="left")
front.dim.linear("s", (A / 2 - s, H / 2), (A / 2, H / 2), value=s, side="top")
front.dim.dia("D", (-D / 2, H + h), (D / 2, H + h), value=D, side="top")
front.dim.dia("d", (-P.d / 2, H + h), (P.d / 2, H + h), value=P.d, tol="H7", side="top", row=2)
front.rough("bore", 1.6, ref="D.d")

# ---- 俯视图 (X, Y)：外形
top = d.view("top")
top.project(hidden=False)
top.centerline((0, -W / 2 - 5), (0, W / 2 + 5), name="sym_x")
top.centerline((-L / 2 - 5, 0), (L / 2 + 5, 0), name="sym_y")
top.dim.linear("W", (L / 2, -W / 2), (L / 2, W / 2), value=W, role="overall", side="right")
top.dim.linear("A", (-A / 2, -B / 2), (A / 2, -B / 2), value=A, side="bottom")
top.dim.linear("B", (-A / 2, -B / 2), (-A / 2, B / 2), value=B, side="left")
top.dim.linear(
    "px",
    (-L / 2 + P.e, W / 2 - P.e),
    (L / 2 - P.e, W / 2 - P.e),
    value=L - 2 * P.e,
    role="position",
    datum="C.top.sym_x",
    side="top",
)
top.dim.linear(
    "py",
    (L / 2 - P.e, -W / 2 + P.e),
    (L / 2 - P.e, W / 2 - P.e),
    value=W - 2 * P.e,
    role="position",
    datum="C.top.sym_y",
    side="right",
    row=2,
)
for k, (x, y) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), 1):
    top.center_mark((x * (L / 2 - P.e), y * (W / 2 - P.e)), P.dh / 2, name=f"hole{k}")
top.center_mark((0, 0), D / 2, name="boss")
top.dim.dia("dh", circle=d.q.circles(view="top", r=P.dh.value / 2).first(), value=P.dh, prefix="4×")

# ---- 左视图 (-Y, Z)：外形 + 虚线
left = d.view("left")
left.project()
left.centerline((0, H - s - 5), (0, H + h + 5), name="axis")

d.rough_default(12.5)
d.general_tol("m")
d.notes.tech(["未注铸造圆角 R3~R5。", "铸件不得有砂眼、裂纹。", "时效处理。"])
d.title(name="齿轮箱盖", drawing_no="LC-GC-01", material="HT200", designer="Liner-CAD")
