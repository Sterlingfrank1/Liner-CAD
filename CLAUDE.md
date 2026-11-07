# Liner-CAD 项目指令

Liner-CAD v0.1：通用 2D 工程图 **Harness 层**（包 `linercad`，命令行 `lcad`），供任意 Coding Agent 调用。它本身不是 Agent。

## 先读

| 文件 | 用途 |
|---|---|
| `DESIGN.md` | 设计真相源（v1.0）。实现与它冲突时以它为准；确需偏离，写进当前里程碑 SPEC 的“偏离记录”并说明理由 |
| `DRAFTING-COVERAGE.md` | 制图专业度、覆盖矩阵、评测集、公开资源 |
| `docs/ROADMAP.md` | 里程碑看板、开发流程、质量门禁、交接记录 |
| `docs/milestones/Mx/` | 当前里程碑的 BRIEF → SPEC → HANDOVER |
| `AGENT.md` | 开发素养（参考） |

## 不能忘的五条

1. **临时脚本层是核心。** Agent 现写 Python、现跑、即弃，效果沉淀为动作日志。API 是给模型写代码用的：命名直白、可组合；失败时给出元素 ID、原因、数值和候选，让模型改脚本重试。
2. **工程专业性。** 规定画法做成内核工具，标准数值来自资源库并注明标准号，不编造；评测集用于验证和内化：发现问题 → 修到对应的层（工具 / 卡片 / 资源 / 检查）→ 留一个回归用例。
3. **Viewer：design for human & agent。** 人看图、点选、拖滑块；Agent 读 `selection.json` / `snapshot.json` / `@ID`。
4. **git 与版本管理。** 只管源；一次成功的修改 = 一个 commit。
5. **Harness 定位。** 简洁、通用、design for agent；内部不调 LLM，不做意图分类和路由，不绑定某一类工件。v0.1 侧重技术架构和 harness 层的完整实现，同时要有不错的出图效果。

## 开发约定

- 环境：`uv` 管理；核心依赖保持最少（ezdxf 为主）。3D（build123d）只作可选依赖 `linercad[3d]` 和开发期工具。
- TDD：先写失败的测试，再实现。开 PR 前 `uv run pytest` 和 `uv run ruff check` 必须全绿。
- 分支 `mN/<card-slug>`，一张卡片一个 PR，squash 合并。main 只经 PR 改动，不 force-push。
- 测试和验收在临时目录里建图纸仓库，**不得**在本开发仓库里产生图纸 commit。
- 渲染图、DXF 等产物不入库；golden 基准和验收证据例外，且保持小。
- 开发机是 Windows：路径用 `pathlib`，文本统一 UTF-8 + LF。
