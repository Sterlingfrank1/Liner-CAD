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
3. 执行（修改 + 检查 + 出图放在同一次调用）：
   - 临时脚本：`lcad edit .linercad/tmp/x.py --png -m "<用户原话>"`；只改 drawing.py：`lcad build --png -m "<用户原话>"`。
   - `--png` 在同一个事务里顺带渲染，JSON 多一个 `png` 路径；修改、动作日志、commit 与不带 `--png` 时完全一致。
   - `--dry-run` 仍可用于试改（不写日志、不改源文件、不提交，返回预览），但正常交付轮直接 `--png`。
4. 读输出：`ok`、`edit`（本轮编号 eN）、`changed`、`errors`、`warnings`（全部 finding）、`png`。**一次收齐全部问题**，不要边看边逐条改。
5. 看图：看 `png` 一次；`lcad render --focus D.L` 只用于定位某个元素。用你的看图能力检查重叠、越界、表达是否合理。
6. 撤销某一轮：`lcad undo e3 -m "<用户原话>"`。历史：`lcad log`；两版对比：`lcad diff e2 e5`。

失败时（退出码 1）**什么都没改**：日志不变、没有 commit。按 `error.message / candidates / hint / where` 改脚本重试。
不要自己 `git commit`、不要改 `.linercad/build/`。每次成功的 build / edit / undo 自动 commit 一次，标题 `eN · 用户原话`。

## 1.1 交付轮与内层迭代（硬规则）

- **交付轮**：一次用户请求 = 1 个交付轮；达标才交付。
- **内层迭代**：收齐全部 finding → 先思考规划 → 写**一个**批量脚本（或一次改完 `drawing.py`）→ `edit --png` / `build --png` → 看一次图；未达标再来一次。**不设迭代次数上限**。
- 硬约束只有三条：每次修改必须**批量**（一个脚本装下本轮全部修复，不逐条改）；写之前必须**先收集全部 finding 并规划**；**达标才停**，不因为“看着差不多”就交付。
- **达标定义**：`errors` = 0；`warnings` 全部修复，或 `d.accept(rule, id, "理由")` 并在交付说明里逐条列出理由；图面完整（视图、尺寸、PMI、技术要求、参数表、标题栏、未注公差）。
- **首图一次写全**：视图方案、尺寸、公差、形位公差、粗糙度、技术要求、参数表、标题栏、未注公差全部在第一次 build 前写进 `drawing.py`；不要留“收尾阶段”。
- **零试探起步**：只读 `lcad skill api` 与当前零件族对应的**那 1 张**卡片，禁止遍读无关零件族、禁止在图纸目录建临时参考目录、禁止翻 `.linercad/build/drawing.dxf` 或在首图前跑试探脚本。需画参数表时优先用 `d.table(name, rows, headers=..., title=...)`（默认右对齐叠放在标题栏 / 技术要求上方；需要手写位置 `at=(x, y)` 时从 `d.template["frame"]` 与 `d.template["title_block"]`（`origin`/`size`）计算；GB 档 A3 默认图框 `[25, 5, 415, 292]`、标题栏 `[235, 5, 415, 61]` 仅作默认示例，非默认图幅或 ISO 档勿照抄）；手工附加图元用 `d.raw_add("LINE", ...)` / `d.raw_add("TEXT", ...)`，图层 `THICK`/`THIN`/`TEXT`。
- **不重复调用**：`build --png` / `edit --png` 已返回全部 `errors` 与 `warnings`，内层迭代不重复跑 `lcad check`（仅交付前核验一次）；每轮用**一次**写全 `drawing.py` 或**一个**批量脚本完成修改，不拆成多次零散修改。
- **不自行抛光**：不做用户没要求、也不属于达标必需的改动；但达标所需的修复必须做完。
- **Viewer**：交付轮 `lcad build --png --ensure-viewer` / `lcad edit ... --png --ensure-viewer`（静默起后台守护进程、不弹系统浏览器，且**覆盖** `LCAD_NO_VIEW` / `CI`），并在回复中附上返回的 `viewer.url`；显式抑制用 `--no-viewer` / `--no-view`。用户点选后用 `lcad context "@sel"` 读取；手动 `lcad view --no-open` 仅作备用。
- **工作目录**：在图纸目录里直接 `lcad ...`，不要读 Liner-CAD 源码仓库，也不要 `uv run`（除非本机没有全局 `lcad`）。

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
| 想沉淀一张图成可复用模板，或按已有用户模板 / 内置范例出图（匹配即从模板起步） | `lcad skill api` 的「用户模板」 |
| 用户开着 Viewer、说“这个 / 我选中的 / @sel”、在拖参数滑块；或首次 build/edit 自动打开了 Viewer（`--ensure-viewer` / `--no-viewer`） | `lcad skill viewer` |
| 有 3D 模型（`model.py` / STEP），或要由模型投影出视图、剖视 | `lcad skill 3d` |
| 画装配图（组件、标准件、序号、明细栏） | `lcad skill assembly` |
| 读懂 `error.code`、检查规则包（drafting / dimensioning / tolerancing / surface / layout） | `lcad skill checks` |
| 别人的 DXF：`lcad inspect x.dxf` 看内容并报告识别到的图框 / 标题栏；`lcad init <目录> --from-dxf x.dxf` 导入后照常编辑——TEXT / MTEXT 成普通文字、HATCH 保留、源图框 / 标题栏吸收进模板语义（只留一个图框） | — |
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
