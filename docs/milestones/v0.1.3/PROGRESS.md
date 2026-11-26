# v0.1.3 进度笔记

- GitHub Milestone：`v0.1.3`（#6）
- 基线：`main`（v0.1.2）

| 卡号 | Issue | 分支 | PR | 状态 | 门禁结果 | Review 轮次 | 备注 |
|---|---|---|---|---|---|---|---|
| C1 | #164 | `v013/viewer` | #165 | 已合入 (`2ab7e4b`) | `pytest`: 1572 passed, 1 skipped；`ruff`: pass；`evals`: 40/40, regressions=[]; Playwright E2E: pass | 2 (R2 PASS) | R1 审查意见修复后 R2 通过并 squash 合入 |
| C1b | #166 | `v013/hint-bar` | #167 | 已合入 (`16bd5c0`) | `pytest` (`test_viewer.py`): 64 passed；`ruff`: pass；Playwright E2E: pass | 1 (R1 PASS) | 去掉 Viewer 底部 `#hint` 说明条；1 轮通过并 squash 合入 |
| C2 | #170 | `v013/templates` | 待开 | R9–R12 与 R1 review 3 项 minor 已修正，待 R2 复审 | `pytest`: 1590 passed, 1 skipped；`ruff`: pass | 1 (待 R2) | R9–R12 已落盘；R1 修正 `_template_section` trust、`logo.png` git 跟踪与图纸子目录护栏 |
| C3 | #168 | `v013/style-logo` | #169 | 已合入 (`19e6785`) | `pytest`: 1578 passed, 1 skipped；`ruff`: pass；`evals`: 40/40, regressions=[]; `mutate`: 41 rules, 45/45 (1.0), 0 FP | 2 (R2 PASS) | R13–R15；R2 通过后 4 项 CI 全绿并 squash 合入 |
| R16 (PR-4) | — | `v013/release` | — | 未开工 | — | — | C1–C3 全部合入后收口 |
