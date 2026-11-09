from linercad import Drawing, Param

d = Drawing()
P = d.params(
    d=Param(12, min=10, max=16, label="杆径"),
    L=Param(150, min=120, max=200, label="杆长"),
)
d.title(name="铰杠", drawing_no="LC-JK-05", material="Q235")
