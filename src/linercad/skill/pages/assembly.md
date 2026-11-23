# 装配图

需要 `linercad[3d]`。装配图目录引用若干零件目录，每个零件目录有 `model.py`（`model(**P)`）和可选的 `drawing.py`（读其中 `d.params(...)` 的缺省值、`d.title(name=, drawing_no=, material=)` 填明细栏；只读字面量，不执行）。

```python
from linercad import Drawing, Param

d = Drawing(kind="assembly", sheet="A3")
P = d.params(D=Param(20, min=10, max=30))
d.component("parts/base", params={"D": P.D})           # → A.base；参数共享：装配参数传给零件
d.component("parts/bush", params={"D": P.D}, at=(0, 0, 0), rot=(0, 0, 0))
d.component("parts/shaft", solid=True)                 # 实心件（轴、螺杆、键、销）纵剖时不剖
d.std_part("GB/T 5782", "M10×90", name="bolt", at=[(-40, 0, 30), (40, 0, 30)], material="Q235")  # 头在上
d.std_part("GB/T 6170", "M10", name="nut", at=[(-40, 0, -20), (40, 0, -20)], rot=(180, 0, 0))  # 在下方
front = d.view("front")
front.project(cut="full", hidden=False)                # 装配图一般不画虚线
d.view("top").project(hidden=False)
d.bom()                                                # 明细栏 T.bom（标题栏上方）+ 主视图序号 B.1 B.2 …
front.dim.linear("H", (-60, 0), (-60, 75), value=75, role="overall", side="left")   # 装配尺寸用普通 dim
d.title(name="滑动轴承", drawing_no="LC-A-01")
```

- `at` 是零件模型原点放到装配里的位置（mm），可给一组位置表示多件；`rot` 绕 X、Y、Z 转（度）。标准件局部坐标：轴线 +Z，支承面在 z = 0（螺栓头在 z ≥ 0、杆朝 −Z；螺母、垫圈在 z ≥ 0）。所以螺栓从上往下穿：`at` 放在上表面、不转；螺母拧在下方：`at` 放在下表面、`rot=(180, 0, 0)`。
- 明细栏的材料：零件取自 `d.title(material=)`；标准件用 `d.std_part(..., material="Q235")`，不给就空着。
- 标准件只有资源库里的：`GB/T 5782`（M6–M16）、`GB/T 6170`、`GB/T 97.1`、`GB/T 119.1`、`GB/T 68`、`GB/T 71`。`from linercad import res; res.std_part("GB/T 5782", "M10×90")` 查尺寸，数值带标准号；不在库里会列出候选。
- 剖面线：每个零件一组，相接触的零件方向或间距不同，同一零件在各视图相同（GB/T 4458.6）；接触面只画一条线。螺栓、螺母、垫圈、销和 `solid=True` 的零件纵剖不剖。
- 序号 `B.<组件名>`，编号 = **合并后的明细栏行号**：相同图号/相同标准件同规格同材料合并为一行并在「数量」列累计，因此同一行的多个组件共用同一序号（气球仍逐个组件各画一个，号码可重复）；`d["B.bush"].place(side="top")` 换到视图上方，`left/right/top/bottom` 都可以。
- **组件要在 `project()` 之前加**（在 drawing.py 里）；之后再加会报错。配合尺寸：`tol="H7/k6"`。
- 零件之间要贴合、不要互相穿透：螺纹按大径建模，孔与之等径。装配剖视里螺钉旋入螺孔用 `v.thread_mesh(...)` 画 GB/T 4459.1 啮合（旋合段按外螺纹；孔端面线到小径），剖面线用 `assembly.thread_hatch_loops(...)` 画到外螺纹牙顶；未被内核覆盖的外形仍由调用方画。
- 改零件的 `model.py` 或参数，重建装配即同步；零件目录和装配一起提交（放在图纸目录下的子目录里）。

## 序号排布（D3）

- `d.bom()` 的序号自动排布：**同一侧**序号沿同一**旋转方向单调递增**（行 / 列形态），并满足对齐、间距 ≥ δ（`[placement].balloon_clearance`，与 E5 A.place 同值）、引线**交叉 0**；引线尽量不压标注文字。
- `d["B.x"].place(side="top")` 等手写位置不参与自动换边（尊重手写）。
- 自动搜索只对 **2–12 个序号**（`BALLOON_PLAN_LIMIT = 12`）尝试；`n=1` 或 `n>12` 不尝试，或 2–12 时找不到无交叉方案，就退回「锚点排序 + 有界交换去交叉」的保守方案，并在 `resolved["order"] = "fallback"` 明示（正常为 `"side-monotonic"`），不静默。fallback 的交换有上界，不保证一般情况下的零交叉。
- 口径说明：issue 的「顺时针 / 逆时针全局连续」用直线引线在两个装配上穷举 2,030,000 个配置仍无零交叉解，本版按 lead 裁定落为上述「同侧旋转方向单调 + 对齐 + δ + 交叉 0」（GB/T 4458.2 行 / 列形态、标准措辞为「尽可能」）；严格全局连续留 v0.2。详见 `docs/milestones/v0.1.1/evidence/d3-balloon-sequences.md`。
