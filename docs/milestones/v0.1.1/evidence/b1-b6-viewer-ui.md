# B1–B6 Viewer 小改（合批 PR 证据）

卡片：B1 #94、B2 #95、B4 #97、B5 #98、B6 #99（W3，P2，非核心卡；PLAN §4 允许合一个 PR）。
分支 `m5/b1-b6-ui`（基于 main 681780e）。改动只涉及 `viewer/`。

环境：临时目录图纸仓库（flange，4 个版本，其中一条提交原话很长），`lcad view` + `ego-browser` 实际操作。
「改动前」截图来自 origin/main 681780e 的 worktree（旧代码、同一图纸仓库）；「改动后」截图来自本分支。

## B1 滑块显示 min / max 与刻度（issue #94）

- **复现**（`b1-slider-before.jpg`）：参数行只有名称、当前值和滑轨，没有可调范围与刻度（v0.1.0-review #1）。
- **修复**（`b1-slider-after.jpg`）：`/api/params` 每个参数多返回 `range: {min, max}`（Param 自带 min/max；缺省取默认值的 0.5–1.5 倍，默认值 0 时取 ±1）；滑块两端显示 min / max 数值，滑轨上按 5 等分画刻度。前端仍兼容没有 `range` 的旧接口。
- **测试**：`test_b1_params_api_reports_slider_ranges`（有 min/max 与缺省回退两种参数）、`test_b1_slider_scale_rendered`（JS / CSS 结构）。

## B2 检查器空态给用法与图纸摘要（issue #95）

- **复现**（`b2-inspector-before.jpg`）：未选中元素时只有一行「点选图上的元素（Ctrl 多选）」。
- **修复**（`b2-inspector-after.jpg`）：空态给出用法（单击点选、Ctrl 多选、选中后复制 @ID 粘给 Agent）和图纸摘要（元素数 / 错误 / 警告，错误红色、警告橙色）；摘要来自 `/api/model` 新增的 `summary: {elements, errors, warnings}`，预览时随预览 findings 变化。
- **测试**：`test_b2_model_summary_counts`（与 model 元素数 / issues 一致，预览后 warning 增加）、`test_b2_inspector_empty_state_shows_usage_and_summary`（JS 结构）。

## B4 预览态在画布上标示「预览（未写回）」（issue #97）

- **复现**（`b4-preview-before.jpg`）：M3 已有蓝边框和角标「预览中 · 未写回源码」，但拖动/松手没有阶段提示，松手后也没有提交入口提示（v0.1.0-review #4 的“看不出预览态”只剩文案与提示缺口）。
- **修复**（`b4-preview-after.jpg`）：角标改为「预览（未写回）」；拖动中显示「· 拖动中…」，松手预览稳定后显示「· 点「写回源码」提交」，与参数行的写回按钮呼应；蓝边框沿用 `#canvas-wrap.is-preview`。
- **测试**：`test_b4_state_switches_with_the_preview`（`/api/state.preview` 随预览/撤回切换）、`test_b4_preview_marking_text_exists`（角标文案两态）。

## B5 状态栏可读性（issue #98）

- **复现**（`b5-status-before.jpg`）：状态栏 12 px，错误/警告计数与 edit id 混在一行字符串里、不着色；长提交原话被单行裁掉且无法展开。
- **修复**（`b5-status-after.jpg`、`b5-status-expanded.jpg`）：字号 13 px、对比度提高；`/api/state` 新增 `message`，前端拆成 edit id / 错误数 / 警告数 / 原话四段，计数按 0（绿）/ warn（橙）/ error（红）着色；原话单行省略，点击在状态栏上方展开完整原话（`#st-full`）。
- **测试**：`test_b5_state_exposes_status_bar_parts`（计数、message；构造 error 与 warning 两种图纸）、`test_b5_status_bar_rendering`（HTML / JS / CSS 结构）。

## B6 版本列表在刷新时保持展开（issue #99）

- **复现**（`b6-versions-before.jpg`）：手动关闭「版本」列表后刷新页面，它按 HTML 默认重新展开；参数面板滚动位置也回到顶部（v0.1.0-review #6；M3 的 DOM 结构下轮询刷新本身已不折叠，本卡补的是用户状态持久化）。
- **修复**（`b6-versions-closed-after.jpg`、`b6-versions-scrolled-after.jpg`）：展开状态与参数面板滚动位置用 sessionStorage 持久化；`reload()` 前后保存/恢复，页面重载后面板内容渲染完再重试应用滚动位置。实测：关闭后刷新仍关闭；打开 + 滚动到底部后刷新，展开与滚动位置都保持。
- **测试**：`test_b6_versions_open_state_and_scroll_are_preserved`（JS 持久化结构）。

## 已知限制

仓库没有 JS 测试运行器；前端状态（B6 展开/滚动持久化、B4 角标两态、B2 空态渲染）由服务端接口测试 + ego-browser 现场证据承载，不为此引入浏览器测试框架（与 B3 相同）。

## 验证

- `uv run pytest`：见 PR 评论（合批 PR 新增 9 个测试）。
- `uv run ruff check` / `uv run ruff format --check`：见 PR 评论。
- `uv run python evals/run.py --baseline evals/baseline.json`：见 PR 评论（UI 卡不动规则/布局，预期无回归）。
