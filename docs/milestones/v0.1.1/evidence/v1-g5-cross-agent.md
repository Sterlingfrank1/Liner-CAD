# V1 G5：独立 Agent 跨 Agent 验证与出图评审（证据）

卡 V1（issue #102，W4）· G5 硬合同 · 2026-11-23 · 由 supervisor 安排独立验证（dsh 全新子代理 + Codex 在干净 clone 上执行）；本文件由 w4-acceptance 维护，数字由 supervisor 核验后填入。

> 状态：**待填（TBD-V1-G5）**。方法、环境与检查清单先落档；agent 用到的干净 clone 与命令、每轮耗时 / token / check 结果、出图评审是非题清单与 v0.1.0 对比，由 supervisor 核验后替换本节占位。

## 1. 干净 clone 环境

- clone：TBD-V1-G5-CLONE（目录 / commit / 日期）
- `uv sync --extra 3d`：TBD-V1-G5-SYNC（exit code / Python / build123d 版本）
- Skill 安装方式：只给 Agent 装好的 Skill（`lcad skill install`），不附加 harness 源码提示；Agent 为全新上下文（不给预期答案）。
- 图纸仓库都在 clone 之外的临时目录，产物不入库。

## 2. 独立 Agent ①：dsh 全新子代理（多轮修改）

- 任务与场景：TBD-V1-G5-DSH-TASKS
- 轮次 / 每轮耗时 / 新处理 token / 模型步数 / lcad 子命令：TBD-V1-G5-DSH-ROUNDS
- 每轮 `lcad check`：TBD-V1-G5-DSH-CHECK（error / warning）
- 失败与恢复记录（如有）：TBD-V1-G5-DSH-NOTES

## 3. 独立 Agent ②：Codex（多轮修改）

- Codex 版本与命令：TBD-V1-G5-CODEX-ENV
- 任务与场景：TBD-V1-G5-CODEX-TASKS
- 轮次 / 每轮耗时 / 新处理 token / 模型步数：TBD-V1-G5-CODEX-ROUNDS
- 每轮 `lcad check`：TBD-V1-G5-CODEX-CHECK
- 失败与恢复记录：TBD-V1-G5-CODEX-NOTES

## 4. 出图评审（是非题清单，与 v0.1.0 对比）

- 评审对象：TBD-V1-G5-DRAWINGS（V1 新出图 + v0.1.0 对照图）
- 评审方式：多模态逐张评审，是非题清单（视图表达 / 尺寸排布 / 序号与明细栏 / 螺纹与局部放大 / 标题栏与技术要求的正确性）。
- 评分与 v0.1.0 对比：TBD-V1-G5-REVIEW（v0.1.0 新范例与装配图多为 2–3 / 5；本次每张图的分数、问题清单与是否成立）。
- 结论：TBD-V1-G5-REVIEW-CONCLUSION（可接受的缺口 / 必须修的回归）。

## 5. 干净 clone 全量回归（supervisor 复核）

- pytest：TBD-V1-CLEAN-CLONE-TESTS
- ruff check / ruff format --check：TBD-V1-CLEAN-CLONE-RUFF
- `evals/run.py --baseline`：TBD-V1-CLEAN-CLONE-BASELINE
- `evals/mutate.py` / `evals/place_scores.py --eval40`：TBD-V1-CLEAN-CLONE-EVALS
- CI 四项（PR run）：TBD-V1-CI

## 6. 清理与产物

- 验收页签 / 后台 Viewer / 临时进程清理：TBD-V1-G5-CLEANUP（要求：无残留 `linercad.viewer` / 浏览器页签；临时图纸仓库删除）。
- 入库产物：本文件（数字与结论），以及必要的少量渲染图 / 截图（小文件，不含样例 DXF、标准原文与用户 PDF）。
