from linercad import Drawing, Param

d = Drawing()
P = d.params(
    d=Param(28, min=20, max=36, label="螺纹大径"),
    zh=Param(108, min=90, max=130, label="头部下端高度"),
)
d.title(name="螺杆", drawing_no="LC-JK-03", material="45")
