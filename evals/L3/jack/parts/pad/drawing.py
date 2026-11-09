from linercad import Drawing, Param

d = Drawing()
P = d.params(
    PD=Param(52, min=40, max=70, label="承压盘直径"),
    sd=Param(36, min=30, max=48, label="裙部外径"),
)
d.title(name="顶垫", drawing_no="LC-JK-04", material="45")
