"""L3 装配评测：滑动轴承（轴承座、轴承盖、上下轴衬、油杯 + GB/T 5782 螺栓、GB/T 6170 螺母）。

装配坐标：轴线沿 Y 过原点，剖分面 Z=0（盖在上、座在下），螺栓对称布置在 X=±42。
主视 (X, Z)：垂直于轴线的横向半剖（右半剖开、左半外形，螺栓在对称面上按不剖绘制）；
俯视 (X, Y)：外形；左视 (-Y, Z)：沿轴线（X=0）全剖。
"""

from linercad import Drawing, Param

d = Drawing(kind="assembly", sheet="A3", std="GB", scale="1:1")
P = d.params(D=Param(48, min=44, max=56, step=1, label="轴衬外径（座孔径）"))
D = P.D.value
BS = 42  # 螺栓中心到轴线
CAP_T = D / 2 + 8  # 盖高（剖分面以上）
SEAT_H = 45  # 座高（剖分面以下）
POCKET = SEAT_H - 14  # 螺母凹槽顶面深度

d.component("parts/seat", params={"D": P.D})
d.component("parts/cap", params={"D": P.D})
d.component("parts/bush_up", params={"D": P.D})
d.component("parts/bush_dn", params={"D": P.D})
d.component("parts/oilcup", params={"D": P.D})
d.std_part("GB/T 5782", "M10×75", name="bolt", at=[(-BS, 0, CAP_T), (BS, 0, CAP_T)])
d.std_part(
    "GB/T 6170", "M10", name="nut", at=[(-BS, 0, -POCKET), (BS, 0, -POCKET)], rot=(180, 0, 0)
)

# ---- 主视图 (X, Z)：半剖
front = d.view("front")
front.project(cut="half", hidden=False)
front.centerline((0, -SEAT_H - 4), (0, CAP_T + 18), name="axis")
front.center_mark((0, 0), D / 2, name="bore")
for s, tag in ((-1, "boltL"), (1, "boltR")):
    front.centerline((s * BS, -SEAT_H - 4), (s * BS, CAP_T + 10), name=tag)
front.dim.linear("L", (-85, -SEAT_H), (85, -SEAT_H), value=170, role="overall", side="bottom")
front.dim.linear(
    "H",
    (85, -SEAT_H),
    (9, CAP_T + 12),
    dir="v",
    value=SEAT_H + CAP_T + 12,
    role="overall",
    side="right",
)
seat_bore = next(e for e in d.q.arcs(view="front", r=D / 2) if e.mid[1] < 0)  # 座孔下半圆弧
front.dim.dia("fit", circle=seat_bore, value=P.D, suffix="H7/k6", at=-75)

# ---- 俯视图 (X, Y)：外形
top = d.view("top")
top.project(hidden=False)
top.centerline((0, -34), (0, 34), name="sym")
top.centerline((-92, 0), (92, 0), name="axis_y")
top.dim.linear(
    "mx", (-72, -22), (72, -22), value=144, role="position", datum="C.top.sym", side="bottom"
)

# ---- 左视图 (-Y, Z)：沿轴线全剖（X=0 对称面）
left = d.view("left")
left.project(cut="full", hidden=False)
left.centerline((-34, 0), (34, 0), name="axis")

d.bom()
d["B.bush_dn"].place(side="left")  # 下轴衬、座的引出点在下半部，从左侧引
d["B.seat"].place(side="left")
d.general_tol("m")
d.notes.tech(
    [
        "轴衬外圆与座孔、盖孔按 H7/k6 配合，装配后不得松动。",
        "螺栓对角交替拧紧，轴承盖与轴承座剖分面贴合。",
        "装配后轴衬内孔涂润滑脂，转动灵活无卡滞。",
    ]
)
d.title(name="滑动轴承", drawing_no="LC-BR-00", designer="Liner-CAD")
