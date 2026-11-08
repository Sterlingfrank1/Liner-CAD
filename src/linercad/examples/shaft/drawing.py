"""范例：阶梯轴（轴套类）。主视图轴线水平；直径标在轴段上（inside）；
轴向长度链式标在下方并留最右一段不注（避免封闭尺寸链），总长另起一排。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(200, min=120, max=400, step=1, label="总长"),
    l1=Param(30, min=10, max=80, step=1, label="左轴颈长"),
    l2=Param(40, min=10, max=100, step=1, label="第二段长"),
    l3=Param(60, min=10, max=150, step=1, label="轴身长"),
    l4=Param(45, min=10, max=100, step=1, label="第四段长"),
    d1=Param(25, min=10, max=60, step=0.5, label="轴颈直径", tol="k6"),
    d2=Param(30, min=12, max=70, step=0.5, label="第二段直径"),
    d3=Param(36, min=14, max=80, step=0.5, label="轴身直径", rule="d3 > d2"),
    c=Param(1, min=0.5, max=3, step=0.5, label="倒角"),
)
x1, x2, x3, x4 = P.l1, P.l1 + P.l2, P.l1 + P.l2 + P.l3, P.l1 + P.l2 + P.l3 + P.l4
r1, r2, r3 = P.d1 / 2, P.d2 / 2, P.d3 / 2

front = d.view("front")
front.turned(
    "body",
    [
        (0, r1 - P.c),
        (P.c, r1, "j1"),
        (x1, r1),
        (x1, r2),
        (x2, r2),
        (x2, r3),
        (x3, r3),
        (x3, r2),
        (x4, r2),
        (x4, r1, "j2"),
        (P.L - P.c, r1),
        (P.L, r1 - P.c),
    ],
)

# 直径：标在各轴段中部
front.dim.dia("d1", (x1 / 2, r1), (x1 / 2, -r1), value=P.d1, tol="k6", side="inside")
front.dim.dia("d2", ((x1 + x2) / 2, r2), ((x1 + x2) / 2, -r2), value=P.d2, side="inside")
front.dim.dia("d3", ((x2 + x3) / 2, r3), ((x2 + x3) / 2, -r3), value=P.d3, side="inside")
front.dim.dia("d4", ((x3 + x4) / 2, r2), ((x3 + x4) / 2, -r2), value=P.d2, side="inside")
front.dim.dia(
    "d5", ((x4 + P.L) / 2, r1), ((x4 + P.L) / 2, -r1), value=P.d1, tol="k6", side="inside"
)

# 轴向长度：链式在下方（最右一段不注），总长另起一排
front.dim.linear("l1", (0, -r1), (x1, -r2), dir="h", value=P.l1, side="bottom")
front.dim.linear("l2", (x1, -r2), (x2, -r3), dir="h", value=P.l2, side="bottom")
front.dim.linear("l3", (x2, -r3), (x3, -r3), dir="h", value=P.l3, side="bottom")
front.dim.linear("l4", (x3, -r3), (x4, -r2), dir="h", value=P.l4, side="bottom")
front.dim.linear(
    "L", (0, -r1), (P.L, -r1), dir="h", value=P.L, role="overall", side="bottom", row=2
)

front.note("chamfer", "2×C1", anchor=(P.c / 2, r1 - P.c / 2))

front.rough("j1", 0.8, ref="E.front.body.j1")
front.rough("j2", 0.8, ref="E.front.body.j2")
d.rough_default(6.3)

d.notes.tech(["调质处理 220~250HBW。", "未注倒角 C1。"])
d.general_tol("m")
d.accept("missing", "F.front.body", "两端倒角由技术要求“未注倒角 C1”给出")
d.accept("param_cover", "P.c", "倒角写在技术要求里")
d.title(name="阶梯轴", drawing_no="LC-SH-01", material="45", designer="Liner-CAD")
