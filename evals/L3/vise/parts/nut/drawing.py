from linercad import Drawing, Param

d = Drawing()
P = d.params(
    x0=Param(76, min=50, max=100, label="左端位置"),
    bore=Param(16, min=12, max=20, label="螺纹大径"),
)
d.title(name="方块螺母", drawing_no="LC-VS-05", material="ZCuAl10Fe3")
