"""范例：带肩衬套（轴套类）。主视图轴线水平、半剖（上半剖开、下半外形）；外径 r6 过盈压入座孔，
内孔 H7 配轴，同轴度和肩面垂直度以内孔轴线为基准 A。肩径在左，外径和内孔在右，长度在下方。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="2:1")
P = d.params(
    L=Param(45, min=30, max=80, step=1, label="总长"),
    lf=Param(6, min=4, max=12, step=1, label="肩厚", rule="lf < L"),
    Df=Param(50, min=44, max=70, step=1, label="肩外径", rule="Df > D"),
    D=Param(40, min=34, max=60, step=1, label="外径", tol="r6", rule="D > d"),
    d=Param(32, min=20, max=50, step=1, label="内孔直径", tol="H7"),
)
C = 1.0  # 倒角
R, Rf, r = P.D / 2, P.Df / 2, P.d / 2

front = d.view("front")
front.turned(
    "cv",
    [
        (0, Rf, "fl"),
        (P.lf, Rf, "fs"),
        (P.lf, R, "od"),
        (P.L - C, R, "ch"),
        (P.L, R - C),
    ],
    bore=[(0, r + C), (C, r), (P.L - C, r), (P.L, r + C)],
    cut="half",
)

# 直径
front.dim.dia("Df", (0, Rf), (0, -Rf), value=P.Df, side="left")
front.dim.dia("d", (P.L - C, r), (P.L - C, -r), value=P.d, tol="H7", side="right", row=1)
front.dim.dia("D", (P.L - C, R), (P.L - C, -R), value=P.D, tol="r6", side="right", row=2)
# 长度：肩厚 + 总长；倒角
front.dim.linear("lf", (0, -Rf), (P.lf, -Rf), dir="h", value=P.lf, side="bottom")
front.dim.linear("L", (0, -Rf), (P.L, -R), dir="h", value=P.L, role="overall", side="bottom", row=2)
front.dim.chamfer("c", "E.front.cv.ch")
front.note("bch", "2×C1", anchor=(C / 2, r + C / 2))

# PMI：内孔轴线为基准 A
front.datum("A", ref="D.d")
front.gtol("coax", "concentricity", 0.03, datums=["A"], zone="dia", ref="D.D")
front.gtol("perp", "perpendicularity", 0.02, datums=["A"], ref="E.front.cv.7")
front.rough("bore", 0.8, ref="E.front.cv.2", process="铰")
front.rough("od", 1.6, ref="E.front.cv.od", process="磨")
d.rough_default(6.3)

d.notes.tech(["压入座孔后精加工内孔。", "去除毛刺锐边。"])
d.general_tol("m")
d.title(name="带肩衬套", drawing_no="LC-SL-01", material="ZCuSn10P1", designer="Liner-CAD")
