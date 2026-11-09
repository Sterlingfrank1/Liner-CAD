"""L3 装配评测：千斤顶（底座、螺套、螺杆、顶垫、铰杠 + GB/T 71 紧定螺钉）。

装配坐标：轴线沿 Z 过原点，底面 Z=0；铰杠沿 X 穿过螺杆头部横孔（Z=117）。
主视 (X, Z)：沿前后对称面全剖（螺杆、铰杠按不剖绘制）；左视 (-Y, Z)：外形。
"""

from linercad import Drawing, Param

d = Drawing(kind="assembly", sheet="A3", std="GB", scale="1:1.5")
P = d.params(Dn=Param(44, min=40, max=52, step=1, label="螺套外径（底座孔径）"))
SZ = 136  # 紧定螺钉轴线高度
SKIRT = 18  # 顶垫裙部半径

d.component("parts/base", params={"Dn": P.Dn})
d.component("parts/sleeve", params={"Dn": P.Dn})
d.component("parts/screw", solid=True)
d.component("parts/pad")
d.component("parts/bar", solid=True)
d.std_part("GB/T 71", "M8×12", name="set_screw", at=(SKIRT, 0, SZ), rot=(0, 90, 0))

# ---- 主视图 (X, Z)：全剖
front = d.view("front")
front.project(cut="full", hidden=False)
front.centerline((0, 0), (0, 158), name="axis")
front.dim.linear(
    "fit", (-22, 14), (22, 14), value=P.Dn, prefix="Φ", suffix="H7/n6", side="bottom", row=1
)
front.dim.dia("Db", (-50, 0), (50, 0), value=100, side="bottom", row=2)
front.dim.linear("Lb", (-83, 117), (83, 117), value=166, role="overall", side="bottom", row=3)

# ---- 左视图 (-Y, Z)：外形
left = d.view("left")
left.project(hidden=False)
left.centerline((0, 0), (0, 158), name="axis")
left.dim.linear("H", (50, 0), (26, 156), dir="v", value=156, role="overall", side="right")

d.bom()
d.general_tol("m")
d.notes.tech(
    [
        "螺套压入底座后，用螺钉防转。",
        "螺杆与螺套的螺纹配合处涂润滑脂，旋转灵活。",
        "铰杠两端球面光滑，不得有毛刺。",
    ]
)
d.title(name="千斤顶", drawing_no="LC-JK-00", designer="Liner-CAD")
