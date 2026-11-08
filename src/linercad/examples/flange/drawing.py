"""范例：法兰盘（盘盖类）。主视图全剖（剖切面过轴线和上下两个螺栓孔），
左视图为端面视图，标剖切符号、均布孔和节圆直径。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    D=Param(120, min=80, max=200, step=1, label="外径"),
    Dh=Param(60, min=30, max=120, step=1, label="凸台外径", rule="Dh < pcd - dh"),
    d0=Param(30, min=10, max=60, step=0.5, label="中心孔径", tol="H7", rule="d0 < Dh"),
    T=Param(15, min=8, max=40, step=1, label="盘厚"),
    L=Param(40, min=20, max=80, step=1, label="总长", rule="L > T"),
    pcd=Param(90, min=50, max=180, step=1, label="螺栓孔中心圆直径", rule="pcd + dh < D"),
    dh=Param(12, min=6, max=20, step=0.5, label="螺栓孔径"),
)
R, Rh, r0, Rb, rb = P.D / 2, P.Dh / 2, P.d0 / 2, P.pcd / 2, P.dh / 2

front = d.view("front")  # 全剖：x 沿轴线
left = d.view("left")  # 端面视图

for s, nm in ((1, "up"), (-1, "dn")):
    inner = front.polygon(
        [
            (0, s * r0),
            (P.L, s * r0),
            (P.L, s * Rh),
            (P.T, s * Rh),
            (P.T, s * (Rb - rb)),
            (0, s * (Rb - rb)),
        ],
        name=f"{nm}_in",
    )
    outer = front.polygon(
        [(0, s * (Rb + rb)), (P.T, s * (Rb + rb)), (P.T, s * R), (0, s * R)], name=f"{nm}_out"
    )
    front.hatch(nm, loops=[inner, outer])
    front.centerline((0, s * Rb), (P.T, s * Rb), name=f"hole_{nm}")
front.centerline((0, 0), (P.L, 0), name="axis")

left.circle((0, 0), R, name="outer")
left.circle((0, 0), Rh, name="boss")
left.circle((0, 0), r0, name="bore")
left.holes_on_circle("bolt", (0, 0), pcd=P.pcd, n=4, d=P.dh, start=90)
left.center_mark((0, 0), R, name="axis")

d.section("A", view="front", cut_in="left", through=[(0, -R), (0, R)])

front.dim.linear("T", (0, R), (P.T, R), value=P.T, side="top")
front.dim.linear("L", (0, -R), (P.L, -Rh), dir="h", value=P.L, side="bottom")
front.dim.dia("D", (0, R), (0, -R), value=P.D, side="left")
front.dim.dia("Dh", (P.L, Rh), (P.L, -Rh), value=P.Dh, side="right")
front.dim.dia("d0", (P.L, r0), (P.L, -r0), value=P.d0, tol="H7", side="right")
left.dim.dia("holes", circle="E.left.bolt.1", prefix="4×", suffix=" EQS")
left.dim.dia("pcd", circle="C.left.bolt")

d.notes.tech(["未注倒角 C1。", "铸件不得有砂眼、裂纹等缺陷。", "未注尺寸公差按 GB/T 1804-m。"])
d.title(name="法兰盘", drawing_no="LC-FL-01", material="HT200", designer="Liner-CAD")
