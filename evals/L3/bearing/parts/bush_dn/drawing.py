from linercad import Drawing, Param

d = Drawing()
P = d.params(
    D=Param(48, min=44, max=56, label="外径"),
    d=Param(40, min=30, max=50, label="内径"),
)
d.title(name="下轴衬", drawing_no="LC-BR-04", material="ZCuSn5Pb5Zn5")
