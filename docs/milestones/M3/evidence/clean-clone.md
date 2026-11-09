# G5：干净 clone 实测（2026-11-09）

main `6ac8d59`（#66 合并后），新 clone，`uv sync --extra 3d`：

- `uv run pytest -q` → **946 passed**（8 min 39 s）；`uv run ruff check` → All checks passed。
- `uv run python evals/run.py` → 40 / 40 例构建，零 error 率 1.0，几何对照 1.0，完整性对照 1.0（L1 + L2 shaft / disc / fork / box）。

## DXF 导入闭环（`tests/data/dxf/sample_part.dxf`，ezdxf 生成、带原生 DIMENSION）

| 步 | 命令 | 结果 |
|---|---|---|
| e0 | `lcad init g5dxf --from-dxf sample_part.dxf` | ok，errors 0；8 个尺寸、2 注释、2 个 raw 曲线 |
| e1 | `lcad edit a.py -m "…"`：`D.dim_1` 加 `±0.1`、`d.general_tol("m")` | ok，errors 0，changed `D.dim_1`、`N.tech.e1_1` |
| — | `lcad edit b.py`：`D.dim_2.place(side="top")` | 拒绝、什么都没改：“D.dim_2 是竖直尺寸，side 不能是 'top'” |
| e2 | `lcad export --to g5out --formats dxf,pdf` | ok，tag `rev-A`，drawing.dxf + drawing.pdf |
| e3 | 改成 `side="left"` 并填标题栏后重跑 | ok，errors 0，changed `D.dim_2`、`T.title.name`、`T.title.drawing_no` |
| — | `lcad log` / `lcad diff e1 e3` | 4 条历史；diff：意图改动 3（图号、名称、修订 A）、布局改动 3，叠加 SVG |

Viewer：`lcad view` 打开同一目录，版本列表选 e1、e3 进入叠加对比，右栏列出改动（`viewer-version-compare.jpg`）。
