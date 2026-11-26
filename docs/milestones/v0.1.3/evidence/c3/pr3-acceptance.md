# C3 验收报告（样式配置与标题栏 Logo）

- Issue：`#168`（`[v0.1.3/C3] 样式配置与标题栏 Logo`）
- 分支：`v013/style-logo`
- 提交范围：`16bd5c0..HEAD`（Commit 1 `9e8f429` R13；Commit 2 `5c5f163` R14；Commit 3 R15 + 文档与证据）

## 1. 需求逐项验收（R13–R15）

### R13：表格 / 单元格样式 `set()` API
- `Element.ALIASES` 与 `_resolve_aliases()` 支持别名映射，同时保留 `d.table("bad", ..., col_widths=[20])` 拒绝未知构造参数的行为：
  - `Cell.set(...)` 支持 `text_height`（别名 `font_size`）、`align`、`wrap`、`bold`。
  - `Table.set(...)` 支持 `col_widths`、`row_heights`、`text_height`（别名 `font_size`）、`align`、`wrap`、`bold`、`border_width`。
  - `d.table(..., border_width=None)` 支持直接设置表格外框线宽。
- 实测样本前后对照：
  - `T.title.material` 字高由 `3.5 mm` 调整为 `5.0 mm`，设置 `align="left"`、`bold=True`、文本 `"45"`。
  - `T.title.drawing_no` 设置 `align="right"`、文本 `"LC-C3-01"`。
  - `T.params` 外框线宽 `border_width=0.7 mm`，`T.params.2.2` 设置 `align="right"`、`bold=True`、文本 `"120"`。
- 渲染截图：[style-after.png](style-after.png)（目检确认 `45` 左对齐加粗、`LC-C3-01` 右对齐、`T.params` 外框加粗、`120` 右对齐加粗，格内均无文字溢出）。

### R14：GB 样式守护与标题栏格子溢出
- `rules.py` 新增 `title_style_gb` 与 `table_style_gb`（`severity="warn"`，`std="GB/T 10609.1-2008"`），纳入 `drafting` pack；同步更新 `src/linercad/std/{gb,iso}.toml`、`src/linercad/res/catalog.toml`、`evals/mutate.py` 与 `tests/test_metrics.py`。
- 实测 `title_style_gb`：当标题栏字段字高设为 `7.0 mm` 时触发 `title_style_gb` warning（`std="GB/T 10609.1-2008"`）。
- `checks.py` 将 `table_overflow` 扩展至标题栏单元格（通过 `_title_border_box` 取标题栏实际包围网格矩形框，且仅修改检查边界不改变 `cell_box`），在 40 份参考图（`640` 次 `table_overflow` 机会）下误报为 `0`。

### R15：标题栏 PNG Logo（`d.logo()`）
- 新增 `Drawing.logo()`（`@mutator("logo")`）、`Logo` 元素、`Image` 图元、SVG `<image data:image/png;base64,...>`、DXF `IMAGEDEF/IMAGE`、`render.py` `_Backend`（修复 `MatplotlibBackend` `AxesImage` 半像素偏移并关闭 PNG 渲染 `adjust_figure`）、`versions.py` 导出时自动复制关联图片至 `assets/` 并列入 `files`、以及 `logo_external_ref`（`severity="warn"`，`DESIGN §9.1`）。
- 渲染截图：[logo-render.png](logo-render.png)（`T.title.logo.company` 清晰绘制在 `T.title.company` 格内左对齐位置）。
- 四端导出位置精度实测（期望 bbox：`[366.0, 49.0, 390.0, 59.0]`）：

| 导出格式 | 实测 bbox `[x0, y0, x1, y1]` | 最大偏差 |
|---|---|---|
| DXF (`IMAGEDEF`/`IMAGE`) | `[366.0, 49.0, 390.0, 59.0]` | `0.0 mm` |
| SVG (`<image>`) | `[366.0, 49.0, 390.0, 59.0]` | `0.0 mm` |
| PNG (`render_png`) | `[366.1452, 49.1189, 389.9395, 58.9427]` | `0.1452 mm` |
| PDF (`render_pdf`) | `[365.9293, 48.9373, 389.9747, 58.928]` | `0.072 mm` |

- `lcad export` 打包实测：导出文件清单包含 `["drawing.dxf", "drawing.pdf", "assets/logo.png"]`，并产生预期的 `logo_external_ref` 警告。

## 2. 文档更新
- 更新 `src/linercad/skill/pages/api.md`（补充 `Cell.set()` / `Table.set()` 样式参数、别名与 `d.logo()` 用法）。
- 更新 `src/linercad/skill/pages/checks.md`（补充 `title_style_gb`、`table_style_gb` 与 `logo_external_ref` 条款说明）。

## 3. 已完成门禁证据
- `uv run ruff check`：`All checks passed!`
- `uv run ruff format --check`：`233 files already formatted`
- `uv run python evals/run.py --baseline evals/baseline.json --out .tmp/eval-report.json`：
  - `40/40 passed`（`geometry_pass_rate=1.0`，`completeness_pass_rate=1.0`，`expect.pass_rate=1.0`）
  - `G=1.0 (5109/0)`，`D=0.986906 (2902/38)`，`T=1.0 (403/0)`
  - `regressions: []`
- `uv run python evals/mutate.py --out .tmp/mutate-report.md`：
  - `规则数：41；变异数：45；检出：45；检出率：1.0；参考图误报：0；跳过用例：0；债务冻结精确：True`
  - 含 `table_overflow`（3/3, 100%, 0 FP）、`table_style_gb`（1/1, 100%, 0 FP）、`title_style_gb`（1/1, 100%, 0 FP）、`logo_external_ref`（1/1, 100%, 0 FP）。
- 全量 `uv run pytest -q` 在最终提交前统一执行，完整结果附于 PR 正文与后续进度记录。
