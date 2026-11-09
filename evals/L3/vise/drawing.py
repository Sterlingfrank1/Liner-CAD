"""L3 装配评测：机用虎钳（简化）。固定钳身、活动钳身、钳口板 ×2、螺杆、方块螺母
+ GB/T 97.1 垫圈、GB/T 119.1 圆柱销、GB/T 68 沉头螺钉 ×4。

装配坐标：螺杆轴线沿 X（高度 Z=30），固定钳口在左（X=0..20），Y=0 为对称面，底面 Z=0。
主视 (X, Z)：沿前后对称面全剖（螺杆、销、螺钉在剖切面上按不剖绘制）；俯视 (X, Y)：外形。
"""

from linercad import Drawing, Param

d = Drawing(kind="assembly", sheet="A3", std="GB", scale="1:1")
P = d.params(W=Param(72, min=70, max=90, step=2, label="钳身宽"))

d.component("parts/body_fixed", params={"W": P.W})
d.component("parts/body_mov", params={"W": P.W})
d.component("parts/jaw_plate", name="plate_fixed", params={"W": P.W, "x0": 20, "side": 1})
d.component("parts/jaw_plate", name="plate_mov", params={"W": P.W, "x0": 60, "side": -1})
d.component("parts/screw", solid=True)
d.component("parts/nut")
d.std_part("GB/T 97.1", "16", name="washer", at=(150, 0, 30), rot=(0, 90, 0))
d.std_part("GB/T 119.1", "6m6×30", name="pin", at=(156, 0, 15))
d.std_part("GB/T 68", "M6×16", name="csk_fixed", at=[(24, 0, 26), (24, 0, 42)], rot=(0, 90, 0))
d.std_part("GB/T 68", "M6×16", name="csk_mov", at=[(56, 0, 26), (56, 0, 42)], rot=(0, -90, 0))

# ---- 主视图 (X, Z)：全剖
front = d.view("front")
front.project(cut="full", hidden=False)
front.centerline((34, 30), (178, 30), name="axis")
front.dim.linear("L", (0, 0), (172, 0), value=172, role="overall", side="bottom")
front.dim.linear("H", (0, 0), (0, 50), dir="v", value=50, role="overall", side="left")
front.dim.linear("fit", (76, 42), (96, 42), value=20, suffix="H8/f7", side="top")

# ---- 俯视图 (X, Y)：外形
top = d.view("top")
top.project(hidden=False)
top.centerline((-4, 0), (178, 0), name="axis")
top.dim.linear("W", (0, -36), (0, 36), dir="v", value=P.W, role="overall", side="left")

d.bom()
d.general_tol("m")
d.notes.tech(
    [
        "装配后活动钳身在导轨上移动灵活，无卡滞。",
        "螺杆与方块螺母的螺纹配合处涂润滑脂。",
        "钳口板的沉头螺钉拧紧后，头部不得高出钳口板表面。",
    ]
)
d.title(name="机用虎钳", drawing_no="LC-VS-00", designer="Liner-CAD")
