# v0.1.3 进度笔记

- GitHub Milestone：`v0.1.3`（#6）
- 基线：`main`（v0.1.2）

| 卡号 | Issue | 分支 | PR | 状态 | 门禁结果 | Review 轮次 | 备注 |
|---|---|---|---|---|---|---|---|
| C1 | #164 | `v013/viewer` | #165 | 已合入 (`2ab7e4b`) | `pytest`: 1572 passed, 1 skipped；`ruff`: pass；`evals`: 40/40, regressions=[]; Playwright E2E: pass | 2 (R2 PASS) | R1 审查意见修复后 R2 通过并 squash 合入 |
| C1b | #166 | `v013/hint-bar` | #167 | 已合入 (`16bd5c0`) | `pytest` (`test_viewer.py`): 64 passed；`ruff`: pass；Playwright E2E: pass | 1 (R1 PASS) | 去掉 Viewer 底部 `#hint` 说明条；1 轮通过并 squash 合入 |
| C2 | — | `v013/templates` | — | 待开工 | — | — | 等 C3 合入后紧接着执行 |
| C3 | #168 | `v013/style-logo` | 待开 | R13–R15 与 R1 review 意见已修复，待 R2 复审 | `pytest`: 1578 passed, 1 skipped；`ruff`: pass；`evals`: 40/40, regressions=[]; `mutate`: 41 rules, 45/45 (1.0), 0 FP | 1 (待 R2) | R13 (`9e8f429`) + R14 (`5c5f163`) + R15 (`b8883d6`)；R1 6 条 minor 文档/清单项已修正 |
| R16 (PR-4) | — | `v013/release` | — | 未开工 | — | — | C1–C3 全部合入后收口 |
