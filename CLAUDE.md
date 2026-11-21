# Liner-CAD 项目指令

Liner-CAD v0.1：通用 2D 工程图 **Harness 层**（包 `linercad`，命令行 `lcad`），供任意 Coding Agent 调用。它本身不是 Agent。

## 先读

| 文件 | 用途 |
|---|---|
| `DESIGN.md` | 设计真相源（v1.0）。实现与它冲突时以它为准；确需偏离，写进当前里程碑 SPEC 的“偏离记录”并说明理由 |
| `DRAFTING-COVERAGE.md` | 制图专业度、覆盖矩阵、评测集、公开资源 |
| `docs/ROADMAP.md` | 里程碑看板、开发流程、质量门禁、交接记录 |
| `docs/VISUAL-VERIFICATION.md` | 看图验证契约：页幅像素、可读性下限、字体缺字、已知盲区（图只管观感，数值走 ID） |
| `docs/milestones/Mx/` | 当前里程碑的 BRIEF → SPEC → HANDOVER |
| `AGENT.md` | 开发素养（参考） |

## 核心竞争力（设计取舍都向这四点看齐）

1. **专业度的 harness 强化，以及图纸与制造信息的索引和表征。** 依托公共资源库、评测集和标准规范，在特征、零件、视图、装配各个层级强化 harness：规定画法做成内核工具；标准数值来自资源库并注明标准号，不编造；评测发现的问题修到对应的层（工具 / 卡片 / 资源 / 检查），并留一个回归用例。尺寸、公差、基准、形位公差、粗糙度、工艺等信息是带 ID、可索引、可查询的语义元素，不只是画出来的文字。
2. **临时脚本层与 coding。** Agent 现写 Python、现跑、即弃，效果沉淀为动作日志。API 是给模型写代码用的：命名直白、可组合；失败时给出元素 ID、原因、数值和候选，让模型改脚本重试。
3. **Viewer 人机交互，用于图纸交互和迭代。** design for human & agent：人看图、点选、拖滑块；Agent 读 `selection.json` / `snapshot.json` / `@ID`。
4. **定位在 harness 层。** 简洁、通用、design for agent；内部不调 LLM，不做意图分类和路由，不绑定某一类工件。

另外要守住：git 只管源，一次成功的修改 = 一个 commit。v0.1 侧重技术架构和 harness 层的完整实现，同时要有不错的出图效果。

**v0.2 方向（v0.1 不做，但设计不能堵死，见 `docs/ROADMAP.md` §6）：** 更深入地内化资源库、用大量零件图纸评测，强化图形效果和标注专业度；输出 STEP 以表达 PMI。

## 开发约定

- 环境：`uv` 管理；核心依赖保持最少（ezdxf 为主）。3D（build123d）只作可选依赖 `linercad[3d]` 和开发期工具。
- TDD：先写失败的测试，再实现。开 PR 前 `uv run pytest` 和 `uv run ruff check` 必须全绿。
- 分支 `mN/<card-slug>`，一张卡片一个 PR，squash 合并。main 只经 PR 改动，不 force-push。
- 测试和验收在临时目录里建图纸仓库，**不得**在本开发仓库里产生图纸 commit。
- 渲染图、DXF 等产物不入库；golden 基准和验收证据例外，且保持小。
- 开发机是 Windows：路径用 `pathlib`，文本统一 UTF-8 + LF。
