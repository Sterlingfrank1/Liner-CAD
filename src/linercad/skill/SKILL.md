---
name: linercad
description: 用 Liner-CAD（lcad）画和修改 2D 机械工程图（GB / ISO 制图标准，含公差、形位公差、粗糙度、规定画法、剖视断面）。新建图纸、按用户的话改尺寸/布局/公差/参数、撤销某一轮、出 PNG 自检时使用。
---

# Liner-CAD 工程图 Skill

Liner-CAD 是一个 2D 工程图 harness：你写 Python，它负责画法、布局、检查、DXF 输出和 git 版本。
**一张图 = 一个目录**：`drawing.py`（构建层：参数、视图、几何、基础标注）+ `drawing.actions.jsonl`（修订层：你的临时脚本自动记下的操作）。产物在 `.linercad/build/`（`drawing.dxf`、`model.json`），不入库，不要手改。

所有命令都在图纸目录里运行（或加 `-C <目录>`），输出**一个 JSON 对象**；`"ok": false` 时看 `error`。
找不到 `lcad` 就用 `python -m linercad`。

## 1. 工作循环（每一轮用户请求）

1. `lcad context` —— 看图幅、参数、视图、所有元素 ID 和问题列表。需要细节：`lcad context D.L E.front.body.3`。
2. 决定改哪一层：
   - **参数值、视图、几何结构** → 直接改 `drawing.py`（例如 `L=Param(200 ...)` 改成 240）。
   - **标注、布局、公差文字、加删注释** → 写临时脚本 `.linercad/tmp/<名字>.py`，定义 `apply(d)`。
   - 一轮里两者都改也可以：先改 drawing.py，再 `lcad edit`，它们会进同一个 commit。
3. 执行：
   - 临时脚本：`lcad edit .linercad/tmp/x.py -m "<用户原话>"`
   - 只改了 drawing.py：`lcad build -m "<用户原话>"`
4. 读输出：`ok`、`edit`（本轮编号 eN）、`changed`、`warnings`（`new: true` 是本轮新出现的问题）。有 warning 就改，再跑一轮。
5. 自检：`lcad render` → `.linercad/tmp/render.png`；局部：`lcad render --focus D.L` → `.linercad/tmp/render-D.L.png`（该元素画成红色）。输出 JSON 的 `png` 字段就是文件路径。用你的看图能力检查重叠、越界、表达是否合理。
6. 用户要撤销某一轮：`lcad undo e3 -m "<用户原话>"`。

失败时（退出码 1）**什么都没改**：日志不变、没有 commit。按 `error.message / candidates / hint / where` 改脚本重试。
不要自己 `git commit`、不要改 `.linercad/build/` 里的文件。每次成功的 build/edit/undo 自动 commit 一次，标题 `eN · 用户原话`。

### 用户在 Viewer 里选中、在试参数

用户可能开着 `lcad view`（浏览器里看图、点选、拖参数滑块）。
- 用户说“这个 / 我选中的 / @sel”，或贴来 `@D.d1（Φ25k6，主视图）` 这样的引用：`lcad context @sel` 给出选中元素的详情、邻近元素、来源行和一段可改写的脚本片段（`.linercad/selection.json` 的 `ids` 就是选中的 ID）。
- 用户在试的参数值在 `.linercad/snapshot.json` 的 `params`（只是预览，没写进 drawing.py）；用户要定下来时，改 drawing.py 里那个 `Param` 的默认值再 `lcad build -m`，或请用户点 Viewer 的[写回源码]。
- 你提交后 Viewer 会自动刷新，状态栏显示新的编号。

## 2. 临时脚本

```python
def apply(d):
    d["D.L"].place(side="top")          # 换侧
    d["D.d1"].tol = "k6"                # 改公差文字
    d["D.l2"].move(dy=-3)               # 微调：下方的尺寸往外（往下）挪 3 mm；dx/dy 是图纸方向，右/上为正
    d["N.tech.2"].suppress()            # 删除元素
    d.notes.tech("去除毛刺锐边。")        # 加一条技术要求
    front = d.view("front")
    front.dim.linear("l9", "E.front.body.3:start", "E.front.body.3:end", side="top")  # 加尺寸
```

- 脚本里的每个修改调用都会自动记进日志；查询到的元素记成具体 ID；`d.P.L` 这样的参数表达式记成表达式，改参数后重放仍然跟随。
- 参数在脚本里只读（`d.P.L` 可读，赋值会报错并告诉你改 drawing.py 的哪一行）。
- 脚本里读到的布局值（`.row` `.side`）是本轮修改之前的；本轮新建元素的布局值是 `None`。
- 参数表达式可以直接运算：`value=d.P.L - d.P.T`、`(d.P.Dh / 2, 0)`，日志里记成表达式。
- 脚本路径相对当前目录；`.linercad/tmp/` 由 `lcad init` 建好。`place(side=...)` 只改你给的字段，其余（如 `row`）保持原值。
- Windows 下用管道读 lcad 输出时设 `PYTHONUTF8=1`（输出是 UTF-8）。

## 3. drawing.py 速查

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
| `v.tapped_hole(name, at, "+x", "M8", depth, drill_depth=None)` | 非回转体上的螺孔（120° 钻尖） |
| `v.center_hole(name, on="F.front.body", end="left", type="A", d=2.5, keep=True)` | 中心孔代号 `GB/T 4459.5-A2.5/5.3` |
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

**资源库**：`from linercad import res`；`res.fit("H7", 30)`、`res.thread("M20x1.5")`、`res.key(32)`、`res.center_hole("A", 2.5)`、`res.spline("6x23x26x6")`、`res.general_tol("m", 45)`。数值都带标准号，不要自己编；退刀槽、越程槽尺寸资源库还没有，按设计给出。

## 4. 引用与查询

```python
d["D.L"]                                         # 按 ID；找不到会列出相近 ID
d.q.dims(view="front", role="position")          # 种类：views features edges lines circles arcs centers dims notes hatches sections cells all
d.q.lines(view="front").where(length=30, dir="h").near(120, 45).one()   # near 用该视图的模型坐标
```

`exactly(n)` / `one()` 不满足时报错并列出命中的元素和最近的候选。

**元素操作**：`el.place(**布局)`、`el.move(dx=, dy=)`、`el.set(**意图)` 或直接赋值（`el.tol = "h7"`、`el.text = "..."`）、`el.suppress()`、`d.accept(rule, id, "理由")`（有意为之的检查结果放行，参数用 `P.<名>`）。
逃生口：`d.raw("D.L").entities[0].dxf.color = 1`、`d.raw_add("LINE", start=(x, y), end=(x, y), layer="THIN")`（图纸坐标）。

## 5. 错误与检查

`error.code`：`not_found`（看 candidates）、`count_mismatch`、`invalid_arg`、`duplicate_id`、`param`、`script`（看 `where` / `trace`）、`stale`、`no_ops`、`dirty`、`undo`、`build`、`git`。

输出里 `errors` 是 error 级问题数，`warnings[]` 列出全部问题：`rule`、`pack`、`severity`（`error` 必须改；`warn` 改或 accept）、`id`、`message`、`std`（依据的标准号）、`violations`、`corridors`。`lcad check` 按规则包列出全部。

- drafting：`line_width` `text_height` `scale` `sheet` `conv_dim`（螺纹、花键、键槽、退刀槽缺代号或尺寸）`section_ref` `center_mark`（圆缺中心线）
- dimensioning：`duplicate` `closed_loop`（封闭尺寸链：删一个或 `reference=True`）`missing`（轴向台阶没全部定位）`param_cover`
- tolerancing：`gtol_syntax`（基准没定义）`datum_letter` `general_tol`（缺未注公差说明）`chain_limit` `dev_order`
- surface：`rough_syntax`（数值不在 GB/T 1031 系列）`rough_default`（缺通用符号）`rough_fit`（IT≤7 配合面没标粗糙度）
- layout：`overlap`（看 violations / corridors，换侧、换排、微调）`out_of_frame` `view_align` `stale_op`（`lcad undo <那一轮>` 或 accept）

## 6. 零件族

先判断零件族，再读对应卡片（视图方案、基准、标注要点、常见错误）：

| 零件族 | 卡片 | 范例 |
|---|---|---|
| 轴套类（轴、套筒、衬套、花键轴） | `lcad skill shaft` | `lcad init <目录> --from shaft` 等，见卡片 |
| 盘盖类（法兰、端盖、带轮、手轮） | `lcad skill disc` | `lcad init <目录> --from flange` 等，见卡片 |
| 叉架、支架 | 主、俯、左三视图；不可见孔用虚线加中心线；孔的定位尺寸 `role="position"` 给 `datum` | `--from bracket` |

被引用的几何都起名，日志里引用才稳定。`lcad init <目录>` 得到最小模板。
