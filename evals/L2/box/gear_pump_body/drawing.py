"""齿轮油泵泵体（箱体类 L2，3D 来源）：主视图看前端面（8 字形齿轮腔、6 个螺栓孔，反映形状特征），
俯视图沿 z = 0 全剖看进出油口，左视图看油口端面。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)。"""

import math

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(96, min=84, max=120, step=2, label="泵体长"),
    W=Param(30, min=24, max=40, step=1, label="泵体厚"),
    H=Param(64, min=56, max=80, step=2, label="泵体高"),
    cx=Param(14, min=12, max=18, step=0.5, label="齿轮腔中心距之半", rule="cx < Rc"),
    Rc=Param(17, min=14, max=22, step=0.5, label="齿轮腔半径", tol="H8"),
    dp=Param(14, min=10, max=18, step=1, label="油口孔径", rule="dp < dq"),
    dq=Param(22, min=16, max=28, step=1, label="油口沉孔径"),
    cb=Param(6, min=4, max=10, step=1, label="沉孔深"),
    dh=Param(7, min=5, max=10, step=0.5, label="螺栓孔径"),
    bx=Param(36, min=30, max=42, step=1, label="螺栓孔 x 向位置"),
    bz=Param(24, min=18, max=28, step=1, label="螺栓孔 z 向位置"),
    mz=Param(26, min=20, max=29, step=1, label="中间螺栓孔 z 向位置"),
)
L, W, H, cx, Rc, dp, dq, cb = P.L, P.W, P.H, P.cx, P.Rc, P.dp, P.dq, P.cb
d.model("model.py")


def rim(view, cx_, cy_, r, deg):
    """投影出的圆边（跨接缝或被相贯截断时是圆弧）：取过圆周上 deg 方向那一点的边。"""
    a = math.radians(deg)
    pt = (cx_ + r * math.cos(a), cy_ + r * math.sin(a))
    return d.q.edges(view=view).where(r=r).near(*pt, r=0.3).one()


# ---- 主视图 (X, Z)：前端面，8 字形齿轮腔贯通
front = d.view("front")
front.project(hidden=False)
front.centerline((-L / 2 - 5, 0), (L / 2 + 5, 0), name="sym_h")
front.centerline((0, -H / 2 - 5), (0, H / 2 + 5), name="sym_v")
for s in (-1, 1):
    front.centerline((s * cx, -Rc - 4), (s * cx, Rc + 4), name=f"gear{s}")
front.dim.linear("L", (-L / 2, -H / 2), (L / 2, -H / 2), value=L, role="overall", side="bottom")
front.dim.linear(
    "H", (L / 2, -H / 2), (L / 2, H / 2), dir="v", value=H, role="overall", side="right"
)
front.dim.linear(
    "c2", (-cx, 0), (cx, 0), value=2 * cx, role="position", datum="C.front.sym_v", side="top"
)
front.dim.dia(
    "Rc2",
    circle=rim("front", cx.value, 0, Rc.value, 20),
    value=2 * Rc,
    tol="H8",
    prefix="2×",
    at=20,
)
front.dim.linear(
    "px",
    (-P.bx, P.bz),
    (P.bx, P.bz),
    value=2 * P.bx,
    role="position",
    datum="C.front.sym_v",
    side="top",
    row=2,
)
front.dim.linear(
    "pz",
    (P.bx, -P.bz),
    (P.bx, P.bz),
    dir="v",
    value=2 * P.bz,
    role="position",
    datum="C.front.sym_h",
    side="right",
)
front.dim.linear(
    "pm",
    (0, -P.mz),
    (0, P.mz),
    dir="v",
    value=2 * P.mz,
    role="position",
    datum="C.front.sym_h",
    side="left",
)
holes = d.q.circles(view="front", r=P.dh.value / 2)
front.dim.dia(
    "dh",
    circle=holes.near(P.bx.value, P.bz.value, r=P.dh.value).one(),
    value=P.dh,
    prefix="6×",
    at=45,
)
front.rough("cav", 1.6, ref="D.Rc2", at=0)
for k, (x, z) in enumerate(
    [(sx * P.bx, sz * P.bz) for sx in (-1, 1) for sz in (-1, 1)] + [(0, -P.mz), (0, P.mz)], 1
):
    front.center_mark(
        (x.value if hasattr(x, "value") else x, z.value if hasattr(z, "value") else z),
        P.dh / 2,
        name=f"bolt{k}",
    )

# ---- 俯视图 (X, Y)：沿 z = 0 全剖（过两齿轮轴线），看进出油口
top = d.view("top")
top.project(cut="full", hidden=False)
top.centerline((-L / 2 - 5, 0), (L / 2 + 5, 0), name="port_axis")
top.dim.linear("W", (L / 2, -W / 2), (L / 2, W / 2), dir="v", value=W, role="overall", side="right")
top.dim.linear("cb", (L / 2 - cb, W / 2), (L / 2, W / 2), value=cb, side="top")
top.dim.linear(
    "wall", (cx + Rc, W / 2), (L / 2 - cb, W / 2), value=L / 2 - cb - cx - Rc, side="top", row=2
)

# ---- 左视图 (-Y, Z)：油口端面
left = d.view("left")
left.project(hidden=False)
left.centerline((-W / 2 - 5, 0), (W / 2 + 5, 0), name="axis_h")
left.centerline((0, -dq / 2 - 5), (0, dq / 2 + 5), name="axis_v")
left.center_mark((0, 0), dq / 2, name="port")
left.dim.dia("dq", circle=d.q.circles(view="left", r=dq.value / 2).one(), value=dq, at=45)
left.dim.dia("dp", circle=d.q.circles(view="left", r=dp.value / 2).one(), value=dp, at=225)

d.rough_default(12.5)
d.general_tol("m")
d.notes.tech(["未注铸造圆角 R2~R3。", "铸件不得有砂眼、气孔、裂纹。", "两齿轮腔轴线平行度 0.02。"])
d.title(name="齿轮油泵泵体", drawing_no="LC-GP-01", material="HT200", designer="Liner-CAD")
