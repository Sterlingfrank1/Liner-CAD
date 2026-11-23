# Liner-CAD

**v0.1.1**（[v0.1.0 发布说明](docs/releases/v0.1.0.md)） · 通用 2D 工程图 Harness 层：包名 `linercad`，命令行 `lcad`。

Liner-CAD 本身不是 Agent。推理、理解需求、写代码交给宿主 Coding Agent（Claude Code / Codex / OpenCode / WorkBuddy …）；Harness 提供语义化图纸模型、脚本运行时、制图与制造约束检查、交互 Viewer 和基于 git 的版本管理。

**跨 Agent 定位（初步结论）：** 出图观感与同一模型裸写 ezdxf 相当，优势在检查、语义元素与版本。**首图速度取决于 Agent**：Claude 首图多数任务明显快于基线（箱体 94 s 对 472 s、叉架 123 s 对 366 s，装配 160 s 对 156 s 基本持平 / 略慢）；DeepSeek Harness 首图 713–1265 s，慢于基线；修改轮次两种 Agent 都比基线慢。依据 #70（每格 n=1；箱体任务与范例 `gear_cover` 相近，对 harness 有利；基线只覆盖单一模型），v0.1.1 复测改用 DeepSeek Harness + Codex。

| 文档 | 内容 |
|---|---|
| [DESIGN.md](DESIGN.md) | 设计（v1.0），唯一的设计真相源 |
| [DRAFTING-COVERAGE.md](DRAFTING-COVERAGE.md) | 机械制图专业度、覆盖矩阵、评测集 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 里程碑、开发流程、质量门禁、交接记录 |
| [AGENT.md](AGENT.md) | 开发素养（参考） |

## v0.1.1 新增

- **试改不提交：** `lcad edit .linercad/tmp/x.py --dry-run` 返回变化元素、finding 与预览（PNG + DXF），HEAD、动作日志、源文件都不变；确认后去掉 `--dry-run` 真跑，报告一致。
- **用户参数化模板：** `lcad template save <名> --description …` 把当前图纸沉淀成模板；`lcad template list` 看清单；`lcad init <目录> --from <模板名> --set D=6 R=0.5` 一步出图（已有模板能匹配时先从模板起步，不重画）。
- **Viewer 自动打开与选择同步：** 首次 `build` / `edit` 成功后自动在后台起 Viewer 并开一次浏览器，已在运行只刷新；`--no-view` / `LCAD_NO_VIEW` / CI 默认关，空闲自退。选中后「复制引用」（Ctrl+Alt+C）得到一行 `@ID`，粘给任意 Agent；也可直接说「选中的 / 这个」，Agent 用 `lcad context "@sel"` 读取，选择过期会如实报告。
- **DXF 导入改进：** TEXT / MTEXT 导成普通文字元素，HATCH 保留（ANSI31 / SOLID；不可表示图案按 handle 报告），尺寸保留或降级 note；**识别到的**源图框 / 标题栏层上的普通边**吸收**进新图幅模板语义（常规样例只留一个图框）；未命名 / 普通层不吸收，隐藏 / 冻结层不吸收，图框层上的 SPLINE / ELLIPSE 等 raw 仍按 raw 导入（可能否决单图框）——均为已知局限。`lcad inspect` 报告识别到的图框 / 标题栏。
- **排布改进：** 圆形尺寸的放射引线自动在 24 个方向（15° 档）里选优；线性 / 多层尺寸按小内大外、文字内外、箭头外翻排序；装配序号在 2–12 个时自动搜索「同侧沿旋转方向单调 + 对齐 + 间距 ≥ δ + 引线交叉 0」，超出规模或找不到无交叉方案时退回保守排布并在 `resolved["order"] = "fallback"` 明示（严格全局连续留 v0.2）。

## 快速开始

```bash
git clone https://github.com/Sterlingfrank1/Liner-CAD && cd Liner-CAD
uv sync                     # 需要 3D 来源 / 装配图：uv sync --extra 3d
uv run lcad init /tmp/shaft --from shaft && uv run lcad -C /tmp/shaft render
uv run lcad -C /tmp/shaft view   # 本地 Viewer（首次 build 也会自动打开）
uv run lcad -C /tmp/shaft template list        # 用户模板清单
uv run lcad skill install --target claude --dir <Agent 工作目录>   # 也可 codex / opencode / generic
```

**Viewer 适用范围：** `lcad view` 面向本机单用户。它只监听 127.0.0.1，写回等接口靠每次启动随机的令牌和 Host / Origin 校验，防的是浏览器里的其他网页；令牌随首页下发，所以不防同一台机器上的其他用户或进程。共享主机上不要开，也不要把端口暴露给他人。

之后由你的 Coding Agent 按装好的 Skill 用 `lcad context` / `lcad edit` 改图；每轮修改是一个以用户原话为标题的 commit。
