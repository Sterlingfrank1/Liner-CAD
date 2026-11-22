---
name: linercad
description: 用 Liner-CAD（lcad）画和修改 2D 机械工程图（GB / ISO 制图标准，含公差、形位公差、粗糙度、规定画法、剖视断面、由 3D 模型投影、装配图）。新建图纸、按用户的话改尺寸/布局/公差/参数、撤销某一轮、导入 DXF、出 PNG 自检时使用。
---

# Liner-CAD 工程图 Skill

Liner-CAD 是一个 2D 工程图 harness：你写 Python，它负责画法、布局、检查、DXF 输出和 git 版本。
**一张图 = 一个目录**：`drawing.py`（构建层：参数、视图、几何、基础标注）+ `drawing.actions.jsonl`（修订层：你的临时脚本自动记下的操作）+ 可选的 `model.py` / 零件子目录（3D 来源）。产物在 `.linercad/build/`，不入库，不要手改。

所有命令都在图纸目录里运行（或加 `-C <目录>`），输出**一个 JSON 对象**；`"ok": false` 时看 `error`。
找不到 `lcad` 就用 `python -m linercad`。Windows 下用管道读输出时设 `PYTHONUTF8=1`。

## 1. 工作循环（每一轮用户请求）

1. `lcad context` —— 看图幅、参数、视图、所有元素 ID 和问题列表。细节：`lcad context D.L E.front.body.3`。
   用户说「这个 / 那个 / 我选中的 / 当前对象」而消息里没有 `@ID` 时，先 `lcad context "@sel"`（PowerShell 要加引号）读当前选中再动手；返回 `selection_stale`（无选择 / 版本落后 / 超时）时如实说「当前没有有效选中」，不要猜。
2. 决定改哪一层：
   - **参数值、视图、几何结构** → 直接改 `drawing.py`。
   - **标注、布局、公差文字、加删注释** → 写临时脚本 `.linercad/tmp/<名字>.py`，定义 `apply(d)`。
   - 一轮里两者都改也可以：先改 drawing.py，再 `lcad edit`，它们进同一个 commit。
3. 执行：临时脚本 `lcad edit .linercad/tmp/x.py -m "<用户原话>"`；只改了 drawing.py：`lcad build -m "<用户原话>"`。
4. 读输出：`ok`、`edit`（本轮编号 eN）、`changed`、`errors`、`warnings`（`new: true` 是本轮新出现的）。有问题就改，再跑一轮。
5. 自检：`lcad render` → `.linercad/tmp/render.png`；`lcad render --focus D.L` 把该元素画成红色。用你的看图能力检查重叠、越界、表达是否合理。
6. 撤销某一轮：`lcad undo e3 -m "<用户原话>"`。历史：`lcad log`；两版对比：`lcad diff e2 e5`。

失败时（退出码 1）**什么都没改**：日志不变、没有 commit。按 `error.message / candidates / hint / where` 改脚本重试。
不要自己 `git commit`、不要改 `.linercad/build/`。每次成功的 build / edit / undo 自动 commit 一次，标题 `eN · 用户原话`。

## 2. 临时脚本

```python
def apply(d):
    d["D.L"].place(side="top")          # 换侧
    d["D.d1"].tol = "k6"                # 改公差文字
    d["D.l2"].move(dy=-3)               # 微调；dx/dy 是图纸方向，右/上为正
    d["N.tech.2"].suppress()            # 删除元素
    d.notes.tech("去除毛刺锐边。")        # 加一条技术要求
    front = d.view("front")
    front.dim.linear("l9", "E.front.body.3:start", "E.front.body.3:end", side="top")  # 加尺寸（必须起名）
```

- 每个修改调用自动记进日志；查询到的元素记成具体 ID；`d.P.L` 这样的参数表达式记成表达式，改参数后重放仍然跟随。
- 参数在脚本里只读（`d.P.L` 可读；改值去改 drawing.py）。脚本里读到的布局值是本轮修改之前的。
- 被引用的几何都起名，日志里引用才稳定。

## 3. 按需再读（`lcad skill <页>`）

| 什么时候 | 读 |
|---|---|
| 写 / 改 drawing.py：几何、规定画法（螺纹、键槽、中心孔、花键）、视图（剖视、断面、局部放大）、尺寸与公差、形位公差、粗糙度、查询与元素操作、资源库 | `lcad skill api` |
| 用户开着 Viewer、说“这个 / 我选中的 / @sel”、在拖参数滑块 | `lcad skill viewer` |
| 有 3D 模型（`model.py` / STEP），或要由模型投影出视图、剖视 | `lcad skill 3d` |
| 画装配图（组件、标准件、序号、明细栏） | `lcad skill assembly` |
| 读懂 `error.code`、检查规则包（drafting / dimensioning / tolerancing / surface / layout） | `lcad skill checks` |
| 别人的 DXF：`lcad inspect x.dxf` 看内容；`lcad init <目录> --from-dxf x.dxf` 导入后照常编辑 | — |
| 用户要求发布 / 出版时才用：`lcad export --to <目录> --formats dxf,pdf`（打 tag `rev-A`…） | — |

## 4. 零件族

先判断零件族，再读对应卡片（视图方案、基准、标注要点、常见错误）：

| 零件族 | 卡片 | 范例 |
|---|---|---|
| 轴套类（轴、套筒、衬套、花键轴） | `lcad skill shaft` | `lcad init <目录> --from shaft` 等，见卡片 |
| 盘盖类（法兰、端盖、带轮、手轮） | `lcad skill disc` | `--from flange` 等，见卡片 |
| 叉架类（支架、拨叉、连杆） | `lcad skill fork` | `--from shift_fork` / `bearing_support` / `bracket` |
| 箱体类（箱体、箱盖、泵体、阀体） | `lcad skill box` | `--from gear_cover` / `pump_body`（3D 来源） |

`lcad init <目录>` 得到最小模板。
