from linercad import Drawing, Param

d = Drawing()
P = d.params(
    D=Param(48, min=44, max=56, label="座孔径"),
    L=Param(120, min=110, max=140, label="座长"),
    H=Param(45, min=40, max=60, label="座高"),
)
d.title(name="轴承座", drawing_no="LC-BR-01", material="HT200")
