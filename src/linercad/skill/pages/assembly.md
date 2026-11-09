# 装配图

需要 `linercad[3d]`。装配图目录引用若干零件目录，每个零件目录有 `model.py`（`model(**P)`）和可选的 `drawing.py`（读其中 `d.params(...)` 的缺省值、`d.title(name=, drawing_no=, material=)` 填明细栏；只读字面量，不执行）。

```python
from linercad import Drawing, Param

d = Drawing(kind="assembly", sheet="A3")
P = d.params(D=Param(20, min=10, max=30))
d.component("parts/base", params={"D": P.D})           # → A.base；参数共享：装配参数传给零件
d.component("parts/bush", params={"D": P.D}, at=(0, 0, 0), rot=(0, 0, 0))
d.component("parts/shaft", solid=True)                 # 实心件（轴、螺杆、键、销）纵剖时不剖
d.std_part("GB/T 5782", "M10×90", name="bolt", at=[(-40, 0, 30), (40, 0, 30)], rot=(180, 0, 0))
d.std_part("GB/T 6170", "M10", name="nut", at=[(-40, 0, -20), (40, 0, -20)])
front = d.view("front")
front.project(cut="full", hidden=False)                # 装配图一般不画虚线
d.view("top").project(hidden=False)
d.bom()                                                # 明细栏 T.bom（标题栏上方）+ 主视图序号 B.1 B.2 …
front.dim.linear("H", (-60, 0), (-60, 75), value=75, role="overall", side="left")   # 装配尺寸用普通 dim
d.title(name="滑动轴承", drawing_no="LC-A-01")
```

- `at` 是零件模型原点放到装配里的位置（mm），可给一组位置表示多件；`rot` 绕 X、Y、Z 转（度）。标准件局部坐标：轴线 +Z，支承面在 z = 0（螺栓头在 z ≥ 0、杆朝 −Z；螺母、垫圈在 z ≥ 0）。
- 标准件只有资源库里的：`GB/T 5782`（M6–M16）、`GB/T 6170`、`GB/T 97.1`、`GB/T 119.1`、`GB/T 68`、`GB/T 71`。`from linercad import res; res.std_part("GB/T 5782", "M10×90")` 查尺寸，数值带标准号；不在库里会列出候选。
- 剖面线：每个零件一组，相接触的零件方向或间距不同，同一零件在各视图相同（GB/T 4458.6）；接触面只画一条线。螺栓、螺母、垫圈、销和 `solid=True` 的零件纵剖不剖。
- 序号 `B.<组件名>`，编号 = 明细栏行号（组件加入的顺序）；`d["B.bush"].place(side="top")` 换到视图上方，`left/right/top/bottom` 都可以。
- **组件要在 `project()` 之前加**（在 drawing.py 里）；之后再加会报错。配合尺寸：`tol="H7/k6"`。
- 零件之间要贴合、不要互相穿透：螺纹按大径建模，孔与之等径。
- 改零件的 `model.py` 或参数，重建装配即同步；零件目录和装配一起提交（放在图纸目录下的子目录里）。
