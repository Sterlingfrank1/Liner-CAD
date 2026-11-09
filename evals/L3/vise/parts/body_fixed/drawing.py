from linercad import Drawing, Param

d = Drawing()
P = d.params(
    W=Param(72, min=70, max=90, label="钳身宽"),
    L=Param(150, min=140, max=180, label="导轨长"),
)
d.title(name="固定钳身", drawing_no="LC-VS-01", material="HT200")
