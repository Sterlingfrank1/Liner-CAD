from linercad import Drawing, Param

d = Drawing()
P = d.params(D=Param(48, min=44, max=56, label="轴衬外径"))
d.title(name="油杯", drawing_no="LC-BR-05", material="Q235")
