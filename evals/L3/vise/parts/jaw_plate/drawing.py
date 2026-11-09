from linercad import Drawing, Param

d = Drawing()
P = d.params(
    W=Param(72, min=70, max=90, label="钳身宽"),
    x0=Param(20, min=0, max=100, label="贴合钳口面位置"),
    side=Param(1, min=-1, max=1, step=2, label="板在钳口面的 +X(1) / -X(-1) 侧"),
)
d.title(name="钳口板", drawing_no="LC-VS-03", material="45")
