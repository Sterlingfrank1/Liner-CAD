# B7 整视图平移在版本对比中归并为一条（证据）

卡 B7（issue #100，W3，P2）· 分支 `m5/b7-layout-changed`（基于 main 61670c7）· 热点 `versions.py` + `viewer/`

## 复现

临时目录图纸仓库（flange，两个版本）：e1 把左视图整体右移 2 mm（`d.view("left").move(dx=2)`，提交「左视图右移 2mm」）。

- 改动前（origin/main 61670c7，`b7-view-move-before.jpg`）：`lcad diff e0 e1` 报 `layout_changed` **56 个元素**（两个视图的每条线、尺寸、PMI 各算一次），Viewer 对比横幅「位置改动 56」、检查器列出 56 个 ID，没有视图级摘要。
- 原因：layout 会自动居中整组视图（M0 SPEC 已知），移动一个视图后两个视图的元素各自整体平移，逐元素比较时全部进 layout_changed。

## 修复

`versions.compare` 按视图聚合 bbox 位移（snapshot 增加 `view`；视图元素 `V.<name>` 自身归入该视图）：

- 视图元素 `V.<name>` 的 **origin** 是平移锚点（bbox 只是内容并集，形状/尺寸变化不能当成视图平移）：origin 移动时，其位移就是视图平移，共享该位移的子元素从 `layout_changed` 移出，其余子元素（如 S.A）保留；没有 origin 锚点时要求 ≥2 个元素共享同一位移且严格多数，并列/恰好一半不报视图平移。
- 只有位移与该视图公共平移不同的元素（真正额外移动）才留在 `layout_changed`；单元素视图的移动不会误判为视图平移。
- 叠加 SVG 仍把被归并的元素标蓝（`df-chg`），画面上仍能看出整组视图移动；`lcad diff` 的 `counts.view_moves` 与 Viewer 对比横幅「视图平移 n」、检查器「视图平移（n）」（每行 `view 平移 (dx, dy) mm · n 个元素`）同步。
- 纯单视图平移的用例（单元测试）只报一条视图平移、`layout_changed` 为空。

## 改动后

同一用例（`b7-view-move-after.jpg`）：

```text
对比 e0 → e1：新增 0 · 删除 0 · 意图改动 0 · 位置改动 1 · 视图平移 2
位置改动（1）S.A
视图平移（2）front 平移 (-1, 0) mm · 36 个元素
              left  平移 ( 1, 0) mm · 19 个元素
```

说明：flange 的 layout 会自动居中，移动左视图 2 mm 后整组内容重新居中 → 前视图整体 -1 mm、左视图净 +1 mm，因此这里是**每个视图一条**的视图平移（issue 的「识别每个视图的公共平移」）；左侧视图相对前视图移动 2 mm。真正额外移动的只有 `S.A`（剖切符号的框因箭头宽度变化），与实现一致。

## 测试（G2 先失败 e0c2c82）

- `test_compare_merges_a_whole_view_translation`：合成快照里一个视图整体平移 → 恰好一条 view_move、layout_changed 为空；其中一个元素额外移动 → view_move 保留、该元素留在 layout_changed。
- `test_compare_keeps_a_lone_moved_element_as_layout_change`：单元素视图移动不误判。
- `test_diff_reports_view_moves_for_the_real_drawing`：真实 flange 移动左视图 2 mm → view_moves front(-1,0)/left(1,0)、`layout_changed` 只剩 `S.A`、`counts.view_moves` 一致、叠加 SVG 中被归并元素仍是 `df-chg`。
- `test_viewer_compare_panel_shows_merged_view_moves`：Viewer 对比面板读取 `view_moves` 并显示「视图平移」。

## 验证

- `uv run pytest`：全量见 PR 评论。
- `uv run ruff check` / `uv run ruff format --check`：见 PR 评论。
- `uv run python evals/run.py --baseline evals/baseline.json`：见 PR 评论（本卡不动规则/布局，D 应保持 0.965724（2830, 97））。
- 截图来自 `ego-browser` 实际操作（临时目录 f2 图纸仓库；改动前截图在 origin/main 61670c7 worktree 上拍）。D1/D2 都合并后 B 卡截图按 PLAN §2 会统一重拍一次作 V1 证据。
