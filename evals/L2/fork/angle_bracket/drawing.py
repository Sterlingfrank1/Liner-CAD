"""斜撑托架（叉架类）：底板两个 Φ10 孔，后缘接一块 45° 斜板，斜板上有长方窗口。斜板在主、俯视图里
都是缩小变形的，窗口的真形和尺寸用斜视图 B（垂直于斜板前表面看）表达；左视图是斜板的实形断面轮廓，
标斜板厚度、斜面长和倾斜角。基准 A 是底板底面，斜板前表面对 A 的倾斜度。
模型轴：X 向右，Y 向后，Z 向上。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)；斜板绕 X 轴上斜 45°。"""

import math

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(80, min=60, max=120, step=1, label="底板长", rule="L > wp + 2 * 6"),
    W=Param(60, min=40, max=90, step=1, label="底板宽", rule="W > 2 * yh + dh"),
    t0=Param(10, min=6, max=16, step=1, label="底板厚"),
    xh=Param(26, min=15, max=50, step=1, label="孔距的一半", rule="xh + dh / 2 < L / 2 - 4"),
    yh=Param(15, min=10, max=30, step=1, label="孔距底板前缘"),
    dh=Param(10, min=6, max=14, step=0.5, label="底板孔径"),
    wp=Param(56, min=30, max=100, step=1, label="斜板宽"),
    tp=Param(10, min=6, max=16, step=1, label="斜板厚"),
    Ls=Param(44, min=30, max=70, step=1, label="斜板沿斜面长（背面）", rule="Ls > w0 + wl + 6"),
    ww=Param(26, min=10, max=40, step=1, label="窗口宽", rule="ww < wp - 12"),
    wl=Param(16, min=8, max=30, step=1, label="窗口沿斜面长"),
    w0=Param(14, min=6, max=30, step=1, label="窗口起点（背面，自底板上表面）"),
)
L, W, t0, xh, dh, wp, tp, Ls = P.L, P.W, P.t0, P.xh, P.dh, P.wp, P.tp, P.Ls
ww, wl, w0 = P.ww, P.wl, P.w0
c = s = math.sqrt(0.5)  # 斜板倾角 45°，向后（+Y）上斜
yb = W / 2  # 底板后缘；斜板背面从 (yb, t0) 起
yf = yb - 2 * tp * c  # 斜板前表面与底板上表面的交线
Bt = (yb + Ls * c, t0 + Ls * s)  # 背面上端角点 (y, z)
Ft = (Bt[0] - tp * c, Bt[1] + tp * c)  # 前表面上端角点


def back(k):  # 背面上沿斜面 k 处 (y, z)
    return (yb + k * c, t0 + k * s)


def face(k):  # 前表面上同一处
    return (yb + k * c - tp * c, t0 + k * s + tp * c)


# ---- 主视图 (X, Z)
front = d.view("front")
front.move(dx=30, dy=-18)
front.rect((-L / 2, 0), L, t0, name="base")
front.line((-wp / 2, t0), (-wp / 2, Ft[1]), name="pl")
front.line((wp / 2, t0), (wp / 2, Ft[1]), name="pr")
front.line((-wp / 2, Ft[1]), (wp / 2, Ft[1]), name="top")
zf1, zb2, zf2 = face(w0)[1], back(w0 + wl)[1], face(w0 + wl)[1]  # 窗口的三条可见横线
front.line((-ww / 2, zf1), (ww / 2, zf1), name="w1")
front.line((-ww / 2, zb2), (ww / 2, zb2), name="w2")
front.line((-ww / 2, zf2), (ww / 2, zf2), name="w3")
front.line((-ww / 2, zf1), (-ww / 2, zf2), name="wl")
front.line((ww / 2, zf1), (ww / 2, zf2), name="wr")
for sg in (-1, 1):  # 底板孔（虚线）
    for dx in (-dh / 2, dh / 2):
        front.line((sg * xh + dx, 0), (sg * xh + dx, t0), role="hidden", name=f"h{sg}{int(dx)}")
    front.centerline((sg * xh, -3), (sg * xh, t0 + 3), name=f"h{sg}")
front.centerline((0, -3), (0, Ft[1] + 5), name="sym")

# ---- 俯视图 (X, Y)
top = d.view("top")
top.polyline(
    [(-wp / 2, yb), (-L / 2, yb), (-L / 2, -yb), (L / 2, -yb), (L / 2, yb), (wp / 2, yb)],
    name="base",
)
top.line((-wp / 2, yf), (wp / 2, yf), name="foot")
top.line((-wp / 2, yf), (-wp / 2, Ft[0]), name="pl")
top.line((wp / 2, yf), (wp / 2, Ft[0]), name="pr")
top.line((-wp / 2, Ft[0]), (wp / 2, Ft[0]), name="ft")
top.line((-wp / 2, Ft[0]), (-wp / 2, Bt[0]), name="el")
top.line((wp / 2, Ft[0]), (wp / 2, Bt[0]), name="er")
top.line((-wp / 2, Bt[0]), (wp / 2, Bt[0]), name="bt")
yw1, yw2, yw3 = face(w0)[0], back(w0)[0], face(w0 + wl)[0]  # 窗口的三条可见横线
top.line((-ww / 2, yw1), (ww / 2, yw1), name="w1")
top.line((-ww / 2, yw2), (ww / 2, yw2), name="w2")
top.line((-ww / 2, yw3), (ww / 2, yw3), name="w3")
top.line((-ww / 2, yw1), (-ww / 2, yw3), name="wl")
top.line((ww / 2, yw1), (ww / 2, yw3), name="wr")
for k, sx in enumerate((-xh, xh), 1):
    top.circle((sx, -yb + P.yh), dh / 2, name=f"h{k}")
    top.center_mark((sx, -yb + P.yh), dh / 2, name=f"h{k}")
top.centerline((0, -yb - 4), (0, Bt[0] + 4), name="sym")

# ---- 左视图 (-Y, Z)：斜板的实形断面轮廓（u = -y）
left = d.view("left")
uf, ub = -yf, -yb
left.line((yb, 0), (-yb, 0), name="bottom")
left.line((-yb, 0), (-yb, t0), name="side_f")
left.line((-yb, t0), (yb, t0), name="base_top")
left.line((yb, 0), (yb, t0), name="side_b")
left.line((ub, t0), (-Bt[0], Bt[1]), name="back")
left.line((-Bt[0], Bt[1]), (-Ft[0], Ft[1]), name="end")
left.line((uf, t0), (-Ft[0], Ft[1]), name="face")
left.line((ub, t0), (ub - 14, t0), role="thin", name="ext")  # 倾角的延长线
for k, dy in enumerate((-dh / 2, dh / 2), 1):  # 底板孔（虚线）
    u = -(-yb + P.yh) + dy
    left.line((u, 0), (u, t0), role="hidden", name=f"h{k}")
left.centerline((-(-yb + P.yh), -3), (-(-yb + P.yh), t0 + 3), name="h")

# ---- 斜视图 B：垂直于斜板前表面看（箭头在左视图里），v 沿斜面向上、从与底板的交线算起
fm = face(Ls / 2)  # 前表面中点 (y, z)，在左视图里 u = -y
obl = d.oblique("B", parent="left", at=(-fm[0], fm[1]), look=-135, rotate=False)
obl.rect((-wp / 2, 0), wp, Ls + tp, name="face")
obl.rect((-ww / 2, w0 + tp), ww, wl, name="win")
obl.centerline((0, -4), (0, Ls + tp + 4), name="sym")

# ---- 尺寸：主视图
front.dim.linear("L", (-L / 2, 0), (L / 2, 0), value=L, role="overall", side="bottom")
front.dim.linear("t0", (-L / 2, 0), (-L / 2, t0), dir="v", value=t0, side="left")
front.dim.linear("wp", (-wp / 2, Ft[1]), (wp / 2, Ft[1]), dir="h", value=wp, side="top")
front.dim.linear(
    "Hs", (L / 2, 0), (wp / 2, Ft[1]), dir="v", value=round(Ft[1], 1), reference=True, side="right"
)

# ---- 尺寸：俯视图
top.dim.dia("dh", circle="E.top.h1.1", value=dh, prefix="2×")
top.dim.linear(
    "px",
    (-xh, -yb + P.yh),
    (xh, -yb + P.yh),
    dir="h",
    value=2 * xh,
    role="position",
    datum="C.top.sym",
    side="bottom",
)
top.dim.linear(
    "yh",
    (-xh, -yb),
    (-xh, -yb + P.yh),
    dir="v",
    value=P.yh,
    role="position",
    datum="E.top.base.3",
    side="left",
)

# ---- 尺寸：左视图
left.dim.linear("W", (yb, 0), (-yb, 0), dir="h", value=W, role="overall", side="bottom")
left.dim.aligned("Ls", (ub, t0), (-Bt[0], Bt[1]), value=Ls, side="left")
left.dim.aligned("tp", (-Bt[0], Bt[1]), (-Ft[0], Ft[1]), value=tp, side="top")
left.dim.angle("alpha", "E.left.ext.1", "E.left.back.1")

# ---- 尺寸：斜视图 B（真形）
obl.dim.linear(
    "ww", (-ww / 2, w0 + tp + wl), (ww / 2, w0 + tp + wl), dir="h", value=ww, side="top", row=1
)
obl.dim.linear("wl", (ww / 2, w0 + tp), (ww / 2, w0 + tp + wl), dir="v", value=wl, side="right")
obl.dim.linear(
    "w0",
    (wp / 2, 0),
    (ww / 2, w0 + tp),
    dir="v",
    value=w0 + tp,
    role="position",
    datum="E.B.face.1",
    side="right",
    row=2,
)

# ---- PMI：A = 底板底面；斜板前表面对 A 的倾斜度
left.datum("A", ref="E.left.bottom.1", at=0.15)
# 引出端默认朝远离视图中心的一侧（这里是板的背面），用 move 拉到前表面外侧的空白处
left.gtol("ang", "angularity", 0.1, datums=["A"], ref="E.left.face.1", at=0.35, length=6).move(
    dx=34, dy=30
)
left.rough("face", 3.2, ref="E.left.face.1", at=0.75, length=6).move(dx=30, dy=24)
left.rough("bottom", 6.3, ref="E.left.bottom.1", at=0.9)
d.rough_default(12.5)

d.notes.tech(["铸件不得有砂眼、气孔、裂纹。", "未注铸造圆角 R3~R5。", "时效处理。"])
d.general_tol("m")
d.title(name="斜撑托架", drawing_no="LC-AB-01", material="HT200", designer="Liner-CAD")
