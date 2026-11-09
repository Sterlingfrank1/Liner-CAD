from linercad import Drawing, Param

d = Drawing()
P = d.params(
    D=Param(48, min=44, max=56, label="盖孔径"),
    L=Param(120, min=110, max=140, label="盖长"),
)
d.title(name="轴承盖", drawing_no="LC-BR-02", material="HT200")
