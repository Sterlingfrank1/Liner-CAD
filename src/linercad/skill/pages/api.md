# drawing.py 与临时脚本 API

## drawing.py 速查

```python
from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")     # sheet: A4(竖) A3 A2 A1 A0；std: "GB"|"ISO"；比例 "1:2" "2:1" …
# 可选：projection="third"（第三角，缺省第一角，标题栏投影符号随之）、overlay="<名>"（企业档，见下）
# 标题栏字段 d.title(...) 的键两档相同：name drawing_no material mass scale sheet company designer
#   checker approver process standardizer date revision stage doc_type；换 std= 即可出另一档
# 企业档：lcad template import 公司.dxf --name acme → templates/acme.toml（图层线宽/颜色、字高、箭头、标题栏块）
P = d.params(
    L=Param(200, min=120, max=400, step=1, label="总长"),
    d1=Param(25, min=10, max=60, label="轴颈直径", tol="k6"),
    d3=Param(36, label="轴身直径", rule="d3 > d1"),
)
front = d.view("front")      # 基本视图：front top bottom left right rear（第一角画法自动摆放、对齐）
```
**坐标**：每个视图用自己的**模型坐标**（mm，未缩放）。主视 (X, Z)、俯视 (X, Y)、左视 (−Y, Z)、右视 (Y, Z)、仰视 (X, −Y)，X 右、Y 向后、Z 向上。共享轴用同一组坐标，视图自动长对正、高平齐、宽相等。`d.near(x, y)` 用图纸坐标（mm，原点在图幅左下角）；`view.to_sheet(x, y)` / `view.to_local(x, y)` 互换。

**几何**（`role` = `thick` 粗实线 / `thin` / `hidden` 细虚线 / `center` / `phantom`，默认 thick）：

| 调用 | 说明 |
|---|---|
| `v.line(p1, p2, role=, name=)` / `v.polyline` / `v.polygon` / `v.rect((x, y), w, h)` | 特征 `F.<视图>.<名>`，边 `E.<视图>.<名>.<k>` |
| `v.circle(c, r)` / `v.arc(c, r, start, end)` | 角度制逆时针 |
| `v.turned(name, [(x, r, "名"?), ...], axis=0, bore=None, cut=None, half="top", holes=[], grooves=[])` | **回转体**（轴、套、盘、盖）：给上半外轮廓。`bore` 内孔轮廓；`cut="full"` 全剖、`"half"` 半剖（自动剖面区域、剖面线 `H.<v>.<name>`、孔后可见线）；`holes=[{"name","r","d","x0","x1","tip":True,"thread":"M8","depth":16}]` 轴向孔/螺孔；`grooves=[{"name","x","w","d","side":"left"}]` 退刀槽拼进轮廓；`hub_keyway=True` 剖视里的轮毂键槽。轮廓点第三项给名字（只用于外轮廓 profile；`bore` 点不能起名，内孔边用 `d.q.lines(...)` 选）→ 稳定边 `E.<v>.<name>.<名>`（下半 `<名>_lo`），PMI 引用它 |
| `v.centerline(p1, p2)` / `v.center_mark(c, r)` / `v.holes_on_circle(name, c, pcd, n, d, start=90)` | 中心线 / 十字中心线 / 均布孔 |
| `v.wavy(name, [p1, p2, ...])` | 局部剖、断裂的波浪线 |
| `v.hatch(name, loops=[...], outline=None)` | 剖面线；嵌套环是孤岛；`outline="thin"` = 重合断面 |

**规定画法**（数值查资源库，画法按 GB/T 4459；返回特征）：

| 调用 | 说明 |
|---|---|
| `v.thread(name, "M20x1.5", x0, x1, axis=0, kind="ext"/"int", cls=None)` | 轴向视图螺纹：外螺纹大径粗、小径细、终止线粗；内螺纹（`bore` 先画到小径）补大径细线和终止线 |
| `v.thread_end(name, c, "M20", kind=)` | 端视图：粗圆 + 约 3/4 细圆弧 |
| `v.thread_mesh(name, "M10", screw=(0, 50), hole=(20, 70), outer=12)` | 装配螺纹旋合剖视（GB/T 4459.1）：旋合段按外螺纹画（大径粗、小径细，不重复画内螺纹线），未旋合段按内螺纹画；孔端面线只画到螺纹小径。旋合长度 = screw / hole 区间交集，见 `assembly.thread_engagement`；剖面线边界用 `assembly.thread_hatch_loops`（到外螺纹牙顶） |
| `v.tapped_hole(name, at, "+x", "M8", depth, drill_depth=None)` | 非回转体上的螺孔（120° 钻尖） |
| `v.center_hole(name, on="F.front.body", end="left", type="A", d=2.5, keep=True, length=None)` | 中心孔代号 `GB/T 4459.5-A2.5/5.3`。`type` 可为 A / B / R / C：A / B / R 给导向孔直径 `d`（R 型的结果另给 `d2`、`l_min`、`r_max`、`r_min`），C 型 `d` 写螺纹（`6` 或 `"M6"`）并必须给 `length=` 螺纹长度，代号如 `CM6L10/10.5` |
| `v.keyway(name, x0, length, d)` | 轴上键槽（朝观察者，长圆形）；宽深查 GB/T 1095 |
| `sec.shaft_cut(name, d, keyway="F.front.kw")` | 在移出断面里画轴截面 + 键槽 + 剖面线 |
| `v.keyway_end(name, c, d, kind="hub")` | 端视图里的轮毂键槽 |
| `v.spline(name, "6x23x26x6", x0, x1)` / `v.spline_end(name, c, spec)` | 矩形花键 |

**视图**：

| 调用 | 说明 |
|---|---|
| `d.section("A", view="front", cut_in="left", through=[p1, p2, ...])` | 剖切符号；2 点全剖，直角折线阶梯剖，斜折线旋转剖 |
| `sec = d.removed_section("B", parent="front", through=[p1, p2], look="left")` | 移出断面 `V.B`。局部坐标：v 沿剖切线（同主视图的 y），u = 朝主视图观察者的深度 × `sec.intent["axes"]["depth"]` |
| `det = d.detail("I", parent="front", center=(x, y), r=5, scale="4:1")` | 局部放大 `V.I`：自动裁剪重画；可直接用主视图坐标在 `det` 上标尺寸 |
| `obl = d.oblique("C", parent="front", at=(x, y), look=-60, rotate=False)` | 斜视图：箭头 + 字母，几何你画 |

辅助视图自动找空位摆放；`V.B.place(at=(x, y))` 指定图纸位置，`move(dx=, dy=)` 微调。

**尺寸**（尺寸、引线注释、PMI **必须起名**）：

| 调用 | 说明 |
|---|---|
| `v.dim.linear(name, p1, p2, dir=None, value=, tol=, role="size", datum=, side=, row=, offset=, reference=False)` | 水平 `dir="h"` 量 Δx，竖直 `dir="v"` 量 Δy；`reference=True` 参考尺寸（加括号） |
| `v.dim.aligned(name, p1, p2, ...)` / `v.dim.angle(name, line1, line2)` | 对齐尺寸 / 角度（数字水平） |
| `v.dim.dia(name, p1, p2, ...)` / `v.dim.dia(name, circle=..., at=45, prefix="4×", suffix=" EQS")` / `v.dim.rad(name, circle=)` | 直径（非圆 / 圆视图）、半径 |
| `v.dim.chamfer(name, edge)` | 倒角：45° 注 `C1`，否则 `2×30°` |
| `v.dim.thread(name, feat)` / `v.dim.groove(name, groove, fmt="wd")` / `v.dim.hole(name, feat, n=4)` / `v.dim.spline(name, feat)` / `sec.dim.keyway(name, "F.B.s", what="b"/"depth")` | 规定画法的代号和必需尺寸 |
| `v.note(name, "text", anchor=, dir=, length=)` / `d.notes.tech([...])` / `d.title(name=, drawing_no=, material=, ...)` | 引线注释 / 技术要求 / 标题栏 |

- `value=P.L - P.l1` 让尺寸显示参数值并记录 `covers`；不给就显示几何实测值。`role="position"` 必须给 `datum=`。
- **公差**：`tol="k6"`（查 GB/T 1800 得偏差）、`"±0.1"`、`"+0.021/0"`；`tol_show="code"/"dev"/"both"` 三种注法；`envelope=True` 包容要求；`el.fit = "g6"` 同 `tol`。
- **布局字段**（不写就由引擎排）：`side` = `top/bottom/left/right/inside`；`row` = 第几排；`offset` 微调；圆视图 `at`（引出角度）；引线类 `dir`/`length`；PMI `at`（沿被测边的位置 0–1；被测要素是尺寸时 1 / 0 = 尺寸线两端）/`length`（引线长 mm，框格放在被测面外法向一侧）。写了的固定，没写的自动。

**PMI**（语义元素，字段分存，关联被测几何）：

```python
front.datum("A", ref="D.d1")                 # DT.A；ref 是尺寸 → 轴线基准，是边 → 表面基准
front.gtol("run", "circular_runout", 0.02, datums=["A-B"], ref="E.front.body.d3")   # G.run
front.gtol("cyl", "cylindricity", 0.005, ref="D.d1", zone=None, modifiers=[])
front.rough("j", 0.8, ref="E.front.body.d1", process="磨")   # R.j，Ra；removal="required/forbidden/any"
d.rough_default(6.3)                          # 标题栏附近的“通用符号 (√)”
d.general_tol("m")                            # 技术要求：未注尺寸公差按 GB/T 1804-m
d.chain("axial", closing="l5", increase=["D.L"], decrease=["D.l1", "D.l2"], require=(-0.2, 0.2))   # K.axial：极值法 / 均方根法
```

特征项目：`straightness flatness circularity cylindricity profile_line profile_surface parallelism perpendicularity angularity position concentricity symmetry circular_runout total_runout`。形状公差不带基准；方向、跳动、同轴、对称必须带基准。

**资源库**：`from linercad import res`；`res.fit("H7", 30)`、`res.thread("M20x1.5")`、`res.key(32)`、`res.center_hole("B", 2.5)`（A / B / R / C 型；R 型 `res.center_hole("R", 2.5)` 给 `d2` 等，C 型 `res.center_hole("C", "M6", length=10)` 的代号是 `CM6L10/10.5`，不给 `length` 时只有 `CM6`）、`res.spline("6x23x26x6")`、`res.general_tol("m", 45)`、`res.gtol("circular_runout")`（几何公差特征项目：类别、是否必须有基准、允许的被测要素、公差带形状、允许的修饰符与条款号，来自 GB/T 1182-2018；`res.gtol_rows()` 给表 1 的 19 项）。数值都带标准号，不要自己编。退刀槽和越程槽取资源库：`res.thread_undercut("M24x1.5")`（外螺纹槽宽 `g1_min`–`g2_max`、槽底 `dg` 与公差，`kind="int"` 为内螺纹）、`res.thread_runout("M24x1.5")`（收尾和肩距）、`res.grinding_groove(30)`（`options` 列出该直径可选的 b1 / b2 / h / r，`b1=` 选一档）。结果里 `verified` 为 False 的表只有一个来源，用了要在交付说明里提一句。

## 引用与查询

```python
d["D.L"]                                         # 按 ID；找不到会列出相近 ID
d.q.dims(view="front", role="position")          # 种类：views features edges lines circles arcs centers dims notes hatches sections cells all
d.q.lines(view="front").where(length=30, dir="h").near(120, 45).one()   # near 用该视图的模型坐标
```

`exactly(n)` / `one()` 不满足时报错并列出命中的元素和最近的候选。

**元素操作**：`el.place(**布局)`、`el.move(dx=, dy=)`、`el.set(**意图)` 或直接赋值（`el.tol = "h7"`、`el.text = "..."`）、`el.suppress()`、`d.accept(rule, id, "理由")`（有意为之的检查结果放行，参数用 `P.<名>`）。
逃生口：`d.raw("D.L").entities[0].dxf.color = 1`、`d.raw_add("LINE", start=(x, y), end=(x, y), layer="THIN")`（图纸坐标）。


## 用户模板：把一张画好的图沉淀成起步模板（H2）

用户（或你）把当前图纸存成**用户模板**后，换规格可以一条命令出图，不必重画：

```powershell
lcad -C <图纸目录> template save bull-nose --description "牛鼻刀 D/R 参数化"   # 前提：lcad check 0 error
lcad template list                                                          # 名称 / 描述 / 参数范围
lcad init <新目录> --from bull-nose --set D=6 R=0.5                           # 一步出图，参数已改好
```

- 存放位置：用户级目录，**不进图纸 git**；默认 Windows `%APPDATA%\linercad\templates`，其他系统 `$XDG_DATA_HOME/linercad/templates`（或 `~/.local/share/linercad/templates`），环境变量 `LCAD_TEMPLATES` 可覆盖。每个模板含 `drawing.py`、可选 `model.py` / `templates/` 企业档，以及记录名称、描述、参数范围、创建时间的 `template.json`。
- 只保存**构建层**：修订层 `drawing.actions.jsonl` 不随模板保存，存在时会提示；先把修订层改动并入 `drawing.py` 再 save。
- `--set 参数=值` 可一次给多个，只改 `Param` 的数字字面量默认值；找不到参数会直接失败、不建目录（`lcad check` 仍要过）。
- **匹配即从模板起步：** 用户的要求与已有用户模板（或内置范例，`lcad init --from <名>`）匹配时，先 `lcad template list` / `init --from` 起步，只改参数与少量标注，**不要从空白重画**；模板不匹配再走重画。


## 试改（dry-run，H1）

```powershell
lcad -C <图纸目录> edit .linercad/tmp/x.py --dry-run [-m "<用户原话>"]
```

走与真实 edit 相同的构建 / 脚本 / 检查 / 渲染流水线，返回 `{ok, dry_run:true, edit, commit:null, ops, changed, errors, warnings, dxf, model, preview}`：`dxf` / `model` 指向 `.linercad/tmp/dry-run-eN.*` 的试改产物，`preview` 是 PNG 预览。**不写** `drawing.actions.jsonl`、不改源文件、不提交；确认后去掉 `--dry-run` 真跑，changed / ops / warnings 与试改报告一致。失败时错误结构与 edit 相同（脚本异常、`stale`、`no_ops` 等）。

## DXF 导入（C1–C4）

- `lcad inspect x.dxf`：图层、实体统计、范围、导入映射和临时 PNG，并报告识别到的图框图元与标题栏（`frame` / `title`）。
- `lcad init <目录> --from-dxf x.dxf` 导入后照常编辑：`TEXT` / `MTEXT` 导成普通文字元素（保留位置/字高/旋转/对齐，MTEXT 保留换行），`HATCH` 保留（本仓语汇可表示的 ANSI31 / SOLID；不可表示图案按源 handle 报告），`DIMENSION` 保留为尺寸或降级为 note。
- 图框 / 标题栏：新图幅的模板图框保留，源图框 / 标题栏图层上的普通边**吸收**进模板图框语义，常规样例最终只有**一个**图框；标题栏块 INSERT 的模板文字与属性仍跳过（不导入）。已知例外：未命名 / 普通层不吸收、隐藏 / 冻结层不吸收、图框层上的 SPLINE / ELLIPSE 等 raw 仍按 raw 导入并可能否决单图框。

## 排布（D1 / D2）

- 圆形直径 / 半径的**放射引线**自动在 24 个候选方向（15° 档）里选优，避免与其他尺寸线及标注文字相交；公共圆心的汇聚尺寸按豁免规则处理。
- 线性 / **多层尺寸**按「小内大外」、文字内外、箭头外翻、行距与嵌套子项排序；不满意时用 `el.place(side=, row=)` 换侧 / 换排、`el.move(dx=, dy=)` 微调，或 `el.set(...)` 改意图。
- 布局 finding 的 `violations` / `corridors` 给出冲突对象与可动方向；`d.accept(rule, id, "理由")` 放行有意的检查结果。改完用 `lcad check` 看 E1 四字段，或用 Viewer 检查器/预览违规定位。
