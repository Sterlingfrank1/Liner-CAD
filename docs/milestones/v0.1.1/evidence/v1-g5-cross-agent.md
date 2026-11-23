# V1 G5：独立 Agent 跨 Agent 验证与出图评审（证据）

卡 V1（issue #102，W4）· G5 硬合同 · 2026-11-23 · 由 supervisor 安排独立验证（dsh 全新子代理 + Codex 在干净 clone 上执行）；本文件由 w4-acceptance 维护，数字由 supervisor 核验后填入。

> 状态：**待填（TBD-V1-G5）**。方法、环境、任务与检查清单先落档；实际记录与数字由 supervisor 核验后替换本节占位。

## 1. 干净 clone 环境

- clone：TBD-V1-G5-CLONE（目录 / commit / 日期）
- `uv sync --extra 3d`：TBD-V1-G5-SYNC（exit code / Python / build123d 版本）
- Skill 安装方式：只给 Agent 装好的 Skill（`lcad skill install`），不附加 harness 源码提示；Agent 为全新上下文（不给“预期答案”）。
- 图纸仓库都在 clone 之外的临时目录，产物不入库。

## 2. 任务清单（issue #102：至少 2 个任务，其一参照用户磨头 PDF 画回转体零件）

| # | 任务 | 说明 | 结果 |
|---|---|---|---|
| 1 | 多轮修改任务 | 从范例起步，按自然语言要求连续修改 ≥2 轮（每轮一个 commit；用 `lcad context` / `edit` / `check`） | TBD-V1-G5-TASK1 |
| 2 | 磨头 PDF 回转体零件 | 只参照用户提供的磨头 PDF（PDF 不入库）新画一张回转体零件图；用 `lcad check` 自检 | TBD-V1-G5-TASK2 |

## 3. 独立 Agent ①：dsh 全新子代理（多轮修改）

- 环境与命令：TBD-V1-G5-DSH-ENV
- 轮次 / 每轮耗时 / 新处理 token / 模型步数 / lcad 子命令：TBD-V1-G5-DSH-ROUNDS
- 每轮 `lcad check`：TBD-V1-G5-DSH-CHECK（error / warning）
- 失败与恢复记录（如有）：TBD-V1-G5-DSH-NOTES

## 4. 独立 Agent ②：Codex（多轮修改）

- Codex 版本与命令：TBD-V1-G5-CODEX-ENV
- 轮次 / 每轮耗时 / 新处理 token / 模型步数：TBD-V1-G5-CODEX-ROUNDS
- 每轮 `lcad check`：TBD-V1-G5-CODEX-CHECK
- 失败与恢复记录：TBD-V1-G5-CODEX-NOTES

## 5. 出图评审（是非题清单，与 v0.1.0 对比）

- 评审对象：TBD-V1-G5-DRAWINGS（V1 新出图 + v0.1.0 对照图；渲染图保持小文件，样例 / PDF / 标准原文不入库）
- 评审方式：多模态逐张评审，是非题清单逐项答“是 / 否 / 不可判”，并给出理由。
- 是非题清单（每张图逐项）：
  1. 视图表达：三视图 / 剖视 / 局部放大关系正确，长对正、高平齐、宽相等；螺纹、中心孔、退刀槽等规定画法正确。
  2. 尺寸排布：尺寸线 / 尺寸界线 / 文字无交叉与压线，大小尺寸内外层次合理，数字方向正确（GB/T 4458.4）。
  3. 序号与明细栏：序号对齐、间距、顺序可读，明细栏合并与数量正确、长文字在格内（GB/T 4458.2）。
  4. PMI：公差 / 基准 / 形位公差 / 粗糙度框格与引线正确、不重叠，数值来自资源库并注明标准号。
  5. 标题栏 / 技术要求 / 图幅：字段填写完整、分区正确；技术要求与标准档一致。
  6. 整体观感：作为工程图可直接交付使用（人工评审 5 分制）。
- 评分与 v0.1.0 对比：TBD-V1-G5-REVIEW（v0.1.0 新范例与装配图多为 2–3 / 5；本次每张图的分数、问题清单与是否成立）
- 结论：TBD-V1-G5-REVIEW-CONCLUSION（可接受的缺口 / 必须修的回归）

## 6. 干净 clone 全量回归（supervisor 复核）

- pytest：TBD-V1-CLEAN-CLONE-TESTS
- ruff check / ruff format --check：TBD-V1-CLEAN-CLONE-RUFF
- `evals/run.py --baseline`：TBD-V1-CLEAN-CLONE-BASELINE
- `evals/mutate.py` / `evals/place_scores.py --eval40`：TBD-V1-CLEAN-CLONE-EVALS
- CI 四项（PR run）：TBD-V1-CI

## 7. 清理与产物

- 验收页签 / 后台 Viewer / 临时进程清理：TBD-V1-G5-CLEANUP（要求：无残留 `linercad.viewer` 与 lcad 进程；验收页签关闭；临时图纸仓库删除）
- 入库产物：本文件（数字与结论），以及必要的少量渲染图 / 截图（小文件；不含样例 DXF、标准原文与用户 PDF）。
