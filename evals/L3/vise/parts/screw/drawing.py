from linercad import Drawing, Param

d = Drawing()
P = d.params(
    d=Param(16, min=12, max=20, label="螺纹大径"),
    x1=Param(172, min=160, max=200, label="右端位置"),
)
d.title(name="螺杆", drawing_no="LC-VS-04", material="45")
