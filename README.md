# Liner-CAD

**v0.1.0**（[发布说明](docs/releases/v0.1.0.md)） · 通用 2D 工程图 Harness 层：包名 `linercad`，命令行 `lcad`。

Liner-CAD 本身不是 Agent。推理、理解需求、写代码交给宿主 Coding Agent（Claude Code / Codex / OpenCode / WorkBuddy …）；Harness 提供语义化图纸模型、脚本运行时、制图与制造约束检查、交互 Viewer 和基于 git 的版本管理。

| 文档 | 内容 |
|---|---|
| [DESIGN.md](DESIGN.md) | 设计（v1.0），唯一的设计真相源 |
| [DRAFTING-COVERAGE.md](DRAFTING-COVERAGE.md) | 机械制图专业度、覆盖矩阵、评测集 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 里程碑、开发流程、质量门禁、交接记录 |
| [AGENT.md](AGENT.md) | 开发素养（参考） |

## 快速开始

```bash
git clone https://github.com/Sterlingfrank1/Liner-CAD && cd Liner-CAD
uv sync                     # 需要 3D 来源 / 装配图：uv sync --extra 3d
uv run lcad init /tmp/shaft --from shaft && uv run lcad -C /tmp/shaft render
uv run lcad view /tmp/shaft # 本地 Viewer
uv run lcad skill install --target claude --dir <Agent 工作目录>   # 也可 codex / opencode / generic
```

之后由你的 Coding Agent 按装好的 Skill 用 `lcad context` / `lcad edit` 改图；每轮修改是一个以用户原话为标题的 commit。
