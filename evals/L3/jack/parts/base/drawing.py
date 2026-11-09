from linercad import Drawing, Param

d = Drawing()
P = d.params(
    Dn=Param(44, min=40, max=52, label="螺套孔径"),
    H=Param(70, min=60, max=90, label="座高"),
)
d.title(name="底座", drawing_no="LC-JK-01", material="HT200")
