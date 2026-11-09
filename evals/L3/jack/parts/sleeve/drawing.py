from linercad import Drawing, Param

d = Drawing()
P = d.params(
    Dn=Param(44, min=40, max=52, label="外径"),
    ID=Param(28, min=20, max=36, label="螺纹孔大径"),
    H=Param(70, min=60, max=90, label="座高"),
)
d.title(name="螺套", drawing_no="LC-JK-02", material="ZCuAl10Fe3")
