---
name: linercad
description: 用 Liner-CAD（lcad）画和修改 2D 机械工程图（GB 制图标准）。新建图纸、按用户的话改尺寸/布局/公差/参数、撤销某一轮、出 PNG 自检时使用。
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

d = Drawing(sheet="A3", std="GB", scale="1:1")     # sheet: A4(竖) / A3 / A2；比例 "1:2" "2:1" …
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
| `v.line(p1, p2, role=, name=)` | 一条边 |
| `v.polyline(pts, ...)` / `v.polygon(pts, ...)` / `v.rect((x, y), w, h, ...)` | 特征 `F.<视图>.<名>`，边 `E.<视图>.<名>.<k>` |
| `v.circle(c, r, ...)` / `v.arc(c, r, start, end, ...)` | 角度制逆时针 |
| `v.turned(name, [(x, r), ...], axis=0)` | **回转体**：给上半轮廓，自动镜像、补台阶/倒角竖线、画轴线 |
| `v.centerline(p1, p2, name=)` | 中心线（自动超出 3 mm，首末为长画） |
| `v.center_mark(c, r, name=)` | 圆的十字中心线 |
| `v.holes_on_circle(name, c, pcd, n, d, start=90)` | 均布孔 + 节圆 + 径向中心线 |

点可以写成 `(x, y)`（数字或参数表达式），也可以写**锚点** `"E.front.body.3:start"`（`start/end/mid/center`）。

**标注**（尺寸、引线注释、剖面线**必须起名**；第一个参数就是名字）：

| 调用 | 说明 |
|---|---|
| `v.dim.linear(name, p1, p2, dir=None, value=, tol=, role="size", datum=, side=, row=, offset=)` | 水平 `dir="h"` 量 Δx，竖直 `dir="v"` 量 Δy |
| `v.dim.dia(name, p1, p2, ...)` | 非圆视图上的直径（加 Φ） |
| `v.dim.dia(name, circle="E.left.hole.1", at=45, prefix="4×", suffix=" EQS")` | 圆视图上的直径；`circle` 也可以是节圆 `C.left.bolt` |
| `v.dim.rad(name, circle=<圆弧>)` | 半径（只用于圆弧，整圆标直径） |
| `v.note(name, "C1", anchor=, dir=, length=)` | 引线注释 |
| `d.notes.tech([...])` | 技术要求 `N.tech.<k>` |
| `d.title(name=, drawing_no=, material=, designer=, checker=, date=, mass=, company=)` | 标题栏 |
| `d.section("A", view="front", cut_in="left", through=[p1, p2])` | 全剖：剖切符号画在 `cut_in`，`A-A` 标在 `view` 上方 |
| `v.hatch(name, loops=[特征或ID, ...])` | 剖面线；嵌套环是孤岛 |

- `value=P.L - P.l1` 让尺寸显示参数值并记录 `covers`；不给就显示几何实测值。
- `role`：`size / position / overall`；**`position` 必须给 `datum=`**（基准元素 ID 或锚点）。
- `tol` 是文字：`"k6"` `"H7"` `"±0.1"`；`text=` 可整串替换显示文字。
- **布局字段**（不写就由引擎按制图习惯排）：`side` = `top/bottom/left/right/inside`；`row` = 第几排（1 起）；`offset` = 往外的微调 mm；圆视图用 `at`（引出角度，度，从 +x 逆时针，45 = 右上）；注释用 `dir`（同样的角度）/`length`。写了的固定，没写的自动；`place/move` 改过的从此固定。
- 剖视：剖面轮廓（闭合 polygon）和剖面线你自己画，剖切符号、箭头、字母、`A-A` 由 harness 画。

## 4. 引用与查询

```python
d["D.L"]                                         # 按 ID；找不到会列出相近 ID
d.q.dims(view="front", role="position")          # 种类：views features edges lines circles arcs centers dims notes hatches sections cells all
d.q.lines(view="front").where(length=30, dir="h").near(120, 45).one()   # near 用该视图的模型坐标
d.q.circles(view="left").where(r=6, tol=0.1).exactly(4)
```

`exactly(n)` / `one()` 不满足时报错并列出命中的元素和最近的候选。

**元素操作**：`el.place(**布局)`、`el.move(dx=, dy=)`、`el.set(**意图)` 或直接赋值（`el.tol = "h7"`、`el.text = "..."`、`el.role = "hidden"`）、`el.suppress()`（有别的元素引用它时会报错并列出依赖）、`d.accept(rule, id, "理由")`（有意为之的警告放行）。
逃生口（API 做不到时）：`d.raw("D.L").entities[0].dxf.color = 1`、`d.raw_add("LINE", start=(x, y), end=(x, y), layer="THIN")`（图纸坐标）。

## 5. 错误与警告

`error.code`：`not_found`（看 candidates）、`count_mismatch`、`invalid_arg`、`duplicate_id`、`param`、`script`（看 `where` / `trace`）、`stale`（本轮操作无法重放）、`no_ops`（脚本没改任何东西）、`dirty`（undo 前有未提交改动）、`undo`、`build`、`git`。

`warnings[].rule`：
- `overlap`：文字与图线或文字重叠。看 `violations`（与谁、重叠多少）和 `corridors`（四个方向还能挪多少），换侧 / 换排 / 微调。
- `out_of_frame`：越出图框或压到标题栏 → 换小比例或换大图幅，或调布局。
- `view_align`：视图之间的范围不一致（长对正 / 高平齐 / 宽相等）→ 检查各视图坐标。
- `stale_op`：日志里较早的某条操作失效（目标被删或改名）。处理：`lcad undo <那一轮>`，或重新做一次修改再撤销旧的，或 `d.accept("stale_op", id, "理由")`。

## 6. GB 表达要点（零件族）

- **轴套类**：轴线水平作主视图，用 `turned`。直径标在轴段上（`side="inside"`）；轴向长度链式标在下方，**留一段不注**（避免封闭尺寸链），总长另起一排（`row=2`）。倒角用引线注释 `C1`，或写进技术要求“未注倒角 C1”。
- **盘盖类**：主视图全剖（`section` + 闭合 polygon + `hatch`），剖切面过轴线和孔；端面视图画圆和均布孔，标 `n×Φd EQS` 和节圆直径 Φ。
- **叉架 / 支架**：主、俯、左三视图；不可见的孔用 `hidden` 虚线加中心线；孔的定位尺寸 `role="position"` 并给 `datum`。
- 被引用的几何都起名（`name=`），日志里引用才稳定。
- 新图从范例起步：`lcad init <目录> --from shaft|flange|bracket`，或 `lcad init <目录>` 得到最小模板。
