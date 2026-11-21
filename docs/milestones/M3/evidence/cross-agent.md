# 跨 Agent 评测（BRIEF §3 第 6 项，SPEC §1.8）

日期 2026-11-09。运行器 `evals/cross_agent.py`，任务 `evals/cross/tasks.toml`（同一份需求文本给所有 Agent 与基线）。原始结果 `report-cross-agent.json`。

## 设置

- 工作目录在仓库外的临时目录；`lcad` 来自独立 venv（`linercad[3d]`）。每一轮都是一次新的非交互调用（像用户隔一段时间回来提下一个要求），首图 + 3 轮修改；每轮上限 20 分钟。
- **Claude**：`claude -p --model sonnet`，工作目录里只有 `lcad skill install --target claude` 装进去的 `.claude/skills/linercad/` 和需求文本，提示要求不读 linercad 源码。
- **DeepSeek Harness（dsh）**：本机 DeepSeek Harness 桌面版自带的 `dsh --profile headless`，模型 DeepSeek-V4.1-Flash、推理强度 high（运行器写一个 profile patch：`agent-default-model` = `deepseek-flash`，`reasoningEffort: high`；`--dsh-model` 可换）。工作目录里是 `lcad skill install --target codex` 写的 `AGENTS.md` 段落（dsh 与 Codex 一样读项目 `AGENTS.md`），权限 `workspace-write`、不询问。
- **基线**：同一个 `claude -p --model sonnet`，只许用 Python + ezdxf，要求原生 DIMENSION 实体；产物用 `lcad init --from-dxf` 导入后跑**同一套检查**。
- **Codex：未运行，按用户决定换成 dsh 与豆包。** 本机 `codex exec`（0.147.0）每次调用都被服务商拒绝 `403 Forbidden: 用户额度不足`（`codex-403.log`）。运行器保留 Codex 分支，充值后一条命令重跑：`python evals/cross_agent.py run --root <评测目录> --agent codex --task box`。
- **豆包工作（桌面版，云电脑、模型“自动-高”）：未运行。** 它没有命令行，只能用 computer use 驱动界面；本次 Claude Code 会话里没有 computer use 工具（用户已在设置里打开，新会话里仍没有）。运行器已备好：`prompt` 子命令输出每一轮的文本（云电脑里先 `pip install` 附带的 wheel，做完回传 `drawing.zip`；修改轮次在同一对话里继续，云电脑状态才保留），`record` 记录每轮用时，`score` 与其它 Agent 同样打分。

## 结果（每项 n = 1，只作参考）

| 任务 | 方式 | 4 轮成功 | 用时 s（首图 / 三轮修改） | 检查 error | warning | 语义元素 |
|---|---|---|---|---|---|---|
| 箱体（减速器箱盖） | Claude + skill | 4 / 4 | 94 / 58, 85, 54 | 0 | 0 | 13 尺寸、基准 A、垂直度、2 粗糙度，几何来自 3D 模型 |
| | dsh + skill | 4 / 4 ¹ | 1265 ¹ / 120, 990, 72 | 0 | 0 | 14 尺寸、基准 A、垂直度、2 粗糙度，几何来自 3D 模型 |
| | 基线 ezdxf | 4 / 4 | 472 / 29, 44, 16 | 0 | 4（封闭尺寸链、重复尺寸、缺未注公差说明、文字重叠） | 18 尺寸；形位公差、粗糙度是文字 |
| 叉架（托架） | Claude + skill | 4 / 4 | 123 / 36, 38, 25 | 0 | 1（剖切符号与视图重叠） | 16 尺寸、C–C 剖视（肋板不剖）、基准、垂直度、粗糙度 |
| | dsh + skill | 4 / 4 | 1005 / 83, 460, 31 | 0 | 0 | 16 尺寸、C–C 剖视（肋板不剖）、基准、垂直度、粗糙度 |
| | 基线 ezdxf | 4 / 4 | 366 / 25, 29, 24 | 0 | 4（两处封闭尺寸链、重复尺寸、缺未注公差说明） | 20 尺寸；PMI 是文字 |
| 装配（轴承座） | Claude + skill | 4 / 4 | 160 / 94, 60, 95 | 0 | 2（配合尺寸与序号重叠） | 5 组件、明细栏、5 序号、剖面线逐件、实心件不剖 |
| | dsh + skill | 4 / 4 | 713 / 40, 61, 358 | 0 | 0 | 5 组件、明细栏、5 序号；螺栓螺母是自建模型（见下） |
| | 基线 ezdxf | 4 / 4 | 156 / 34, 23, 28 | 0 | 1（缺未注公差说明） | 明细栏、序号是线和文字 |

¹ 箱体首图超过 20 分钟上限被运行器终止（`runs.json` 记 code −1）；终止前它已提交完整的图（e0–e5，检查 0 error 0 warning），后三轮在这张图上照常完成。

修改轮次的落实逐张看图核对：Claude 与 dsh 三个任务各 9 轮全部体现在图上，每轮至少一个 commit、标题是用户原话；基线 9 轮也都改到了 DXF 上（无版本记录）。

## 结论（如实）

- **出图观感三者相当。** 中等复杂度的这三张图，两种 Agent 用 skill、Sonnet 只用 ezdxf，都画出了合格的三视图、剖视、明细栏；单看渲染分不出明显高下。
- **harness 更好的地方**：检查全部通过、warning 更少（dsh 三张 0 warning；基线被查出封闭尺寸链与重复尺寸）；尺寸、基准、形位公差、粗糙度、组件、序号都是带 ID 的语义元素，可查询、可被 Viewer 点选和下一轮引用；每轮修改有带原话的 commit，可 `lcad diff` / `undo`。换一个模型（DeepSeek）只靠 `AGENTS.md` 也能用起来。
- **速度看 Agent**：Claude 首图比基线快得多（箱体 94 s 对 472 s，叉架 123 s 对 366 s；装配持平）；dsh 首图慢得多（713–1265 s），部分修改轮也长（加形位公差 990 s、改孔位 460 s）——它反复 render / check、用“试一下再撤销”的方式调布局。修改轮次两种 Agent 都比基线慢（基线只改一行常量重跑脚本）。
- **偏向**：箱体任务和范例 `gear_cover` 很像，Agent 直接从范例起步，这对 harness 有利。
- **评测中发现并修好的 harness 缺陷**：
  - 装配里同一标准件放在多个位置时，第二件在剖视中丢失（#66 修复并加回归测试）。
  - dsh：需求要求明细栏写全材料，`d.std_part` 没法给标准件写材料，它就把螺栓、螺母换成了自建模型（丢了标准件的规定尺寸）。现加 `d.std_part(..., material=)` 并加回归测试；skill 装配页的螺栓 / 螺母朝向示例原来写反了（螺栓 `rot=(180,0,0)`），它在日志里为此反复推敲，已改正并写明“螺栓从上穿不转、螺母在下 `rot=(180,0,0)`”。
  - dsh 在叉架、装配里没被要求就 `lcad export` 打了 `rev-A`：SKILL 路由表改为“用户要求发布时才用”。
- **未修、记为缺口**：没有“试改不提交”的方式，Agent 调布局时用 `edit` + `undo` 试错，历史里留下成对的“测试 / 撤销” commit（dsh 叉架 26 个 commit）。v0.2 可加 `lcad edit --dry-run`（只出 changed / findings / 渲染，不写日志不提交）。
- **导入器的不足**（影响基线导入后的样子，不影响上表的检查数）：TEXT 导入成带引线的注释、HATCH 被跳过、原图框被保留在新图幅里。
