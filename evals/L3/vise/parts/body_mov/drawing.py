from linercad import Drawing, Param

d = Drawing()
P = d.params(
    W=Param(72, min=70, max=90, label="钳身宽"),
    x0=Param(60, min=40, max=90, label="钳口面位置"),
)
d.title(name="活动钳身", drawing_no="LC-VS-02", material="HT200")
