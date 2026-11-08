"""范例：隔套（轴套类）。主视图轴线水平、全剖；两端面平行，以左端面为基准 A。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="2:1")
P = d.params(
    L=Param(28, min=15, max=60, step=1, label="长度"),
    D=Param(42, min=34, max=60, step=1, label="外径", tol="h9", rule="D > d"),
    d=Param(30, min=20, max=45, step=1, label="内孔直径", tol="H9"),
)
C = 1.0  # 倒角
R, r = P.D / 2, P.d / 2

front = d.view("front")
front.turned(
    "sp",
    [(0, R - C, "c1"), (C, R, "od"), (P.L - C, R, "c2"), (P.L, R - C)],
    bore=[(0, r + C), (C, r), (P.L - C, r), (P.L, r + C)],
    cut="full",
)

front.dim.dia("D", (P.L, R - C), (P.L, -(R - C)), value=P.D, tol="h9", side="right", row=2)
front.dim.dia("d", (P.L, r), (P.L, -r), value=P.d, tol="H9", side="right", row=1)
front.dim.linear("L", (0, -R), (P.L, -R), dir="h", value=P.L, role="overall", side="bottom")
front.dim.chamfer("c1", "E.front.sp.c1")
front.dim.chamfer("c2", "E.front.sp.c2")
front.note("bch", "2×C1", anchor=(C / 2, r + C / 2))

front.datum("A", ref="E.front.sp.7")
front.gtol("par", "parallelism", 0.02, datums=["A"], ref="E.front.sp.10")
front.rough("f1", 1.6, ref="E.front.sp.7", at=0.95)
front.rough("f2", 1.6, ref="E.front.sp.10", at=0.95)
d.rough_default(6.3)

d.notes.tech(["去除毛刺锐边。"])
d.general_tol("m")
d.title(name="隔套", drawing_no="LC-SL-02", material="45", designer="Liner-CAD")
