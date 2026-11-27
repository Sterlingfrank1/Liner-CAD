# v0.1.3 交接文档（HANDOVER）

- 里程碑：`v0.1.3`（GitHub Milestone `#6`）
- 收口版本：`0.1.3`（基线 `v0.1.2`，`74d4b84`）
- 依据文档：[v0.1.3-REQ.md](v0.1.3-REQ.md) · [v0.1.3-SPEC.md](v0.1.3-SPEC.md) · [v0.1.3-CARDS.md](v0.1.3-CARDS.md) · [发布说明](../../releases/v0.1.3.md)

## 1. 交付

1. **Viewer 全量闭环与界面清理（PR-1 + C1b，R1–R8）**：
   - `lcad build` / `lcad edit` 支持 `--ensure-viewer`（覆盖 `LCAD_NO_VIEW` 与 `CI`）及 `--no-viewer`，`lcad view` 默认端口被占自动回退空闲端口（显式 `--port` 被占报 `viewer_bind`）。
   - 左右面板支持拖拽调宽（`localStorage` 持久化）、双击复位、一键折叠及 `<=1100` / `<=820` 两档窄屏适配；去除底部 `#hint` 条；检查器改为「已选中 N 个元素」。
   - 画布支持左键两态框选（L→R 蓝实线全包含 / R→L 绿虚线相交）、右/中键/`Space` 平移与右键菜单抑制；`Viewer.select` 默认上限 50，`lcad context "@sel"` 超 10 条返回摘要（保留 `items: []`）。
   - 标题栏全部 16 个字段格生成 `cell_box` 与 SVG 命中矩形；`GET /api/download?fmt=dxf|pdf|png[&preview=1]` 无副作用导出产物，带内部外部图片时 DXF 打 `.zip`。
2. **项目级模板与保存前自检（PR-2，R9–R12）**：
   - `src/linercad/project.py` 实现 `linercad.project.toml` 标记与优先级解析（`--project` > `LCAD_PROJECT_ROOT` > 向上找 marker 并在祖先 `.git` 查完后停 > `cwd.parent` / `cwd`），严禁在图纸目录内创建标记或模板目录；查找按 **项目 > 用户 > 范例**。
   - `lcad template save` 支持 `--scope` / `--project` / `--tag`（仅写 `template.json`），按语义规则固化 `baseline.actions.jsonl` 并校验越界图片；`init --from` 合并 `e0` 并校验 `model_hash`，拒绝 `lcad undo e0`。
   - `probe_template()` 在隔离副本对有界非空参数做 min/max 探测（上限 16 次，支持 `--force-probe-fail` / `--no-probe`），并在列表与初始化输出提供 `trust` 提示。
3. **样式配置与标题栏 PNG Logo（PR-3，R13–R15）**：
   - `Cell.set()` / `Table.set()` 支持 `text_height`（`font_size`）、`align`、`wrap`、`bold`、`cols`（`col_widths`）、`row_height`、`border_width` 并在 DXF/SVG/PNG/PDF 保持同步。
   - 新增 `title_style_gb`（`GB/T 10609.1-2008`）、`table_style_gb`（`GB/T 14691-1993`）及标题栏 `table_overflow`；`d.logo()` 实现 PNG Logo 标题栏嵌入、四端输出与 `logo_external_ref` 警告。
4. **收口与发布准备（PR-4，R16）**：
   - `pyproject.toml` 与 `uv.lock` 升至 `0.1.3`，补齐 `docs/releases/v0.1.3.md`、`HANDOVER.md`、`docs/ROADMAP.md`、`README.md`、`PROGRESS.md` 与 `tests/test_release_v013.py`，完成全量回归与 `%TEMP%` 全局 `lcad --version` == `0.1.3` 安装验证（`scripts/release.py 0.1.3 --dry-run` 与 `0.1.3` 待 PR-4 合入且 `main` CI 全绿后执行）。

## 2. 怎么验证

仓库内全套门禁与基准：

```bash
uv lock
uv sync --extra 3d
uv run ruff check
uv run ruff format --check
uv run pytest -q
uv run python evals/run.py --baseline evals/baseline.json --out .tmp/eval-report.json
uv run python evals/mutate.py --out .tmp/mutate-report.md
```

全局安装与任意目录 CLI 验证：

```powershell
uv tool install --force --reinstall --no-cache --with build123d .
cd $env:TEMP
lcad --version
```

发布预检与正式打 tag / Release（`main` 合入且 CI 四项全绿后执行）：

```powershell
uv run python scripts/release.py 0.1.3 --dry-run
uv run python scripts/release.py 0.1.3
gh release view v0.1.3
```

## 3. 5 卡清单与去向

| 卡号 | Issue | PR | 内容与结论 | 状态 |
|---|---|---|---|---|
| C1 | #164 | #165 | Viewer 全量（R1–R8）：2 轮评审通过（R2 PASS），CI 4/4 绿；`1572 passed, 1 skipped`、`evals` 40/40、Playwright E2E 通过 | 已合入 (`2ab7e4b`) |
| C1b | #166 | #167 | 去掉 Viewer 底部 `#hint` 说明条：1 轮评审通过（R1 PASS），CI 4/4 绿；`test_viewer.py` `64 passed`、Playwright E2E 通过 | 已合入 (`16bd5c0`) |
| C3 | #168 | #169 | 样式配置与标题栏 Logo（R13–R15）：2 轮评审通过（R2 PASS），CI 4/4 绿；`1578 passed, 1 skipped`、`evals` 40/40、`mutate.py` 41 rules, 45/45 (1.0), 0 FP | 已合入 (`19e6785`) |
| C2 | #170 | #171 | 项目级模板与保存前自检（R9–R12）：3 轮评审通过（R3 PASS），CI 4/4 绿；`1590 passed, 1 skipped`、`test_project_templates.py` 5 passed | 已合入 (`2b95720`) |
| R16 | #172 | 本 PR | 版本 `0.1.3` 收口：发布说明、`HANDOVER.md`、`ROADMAP.md`、`README.md`、`tests/test_release_v013.py` 与全局安装验证 | 收口中 |

## 4. 验收与证据

- **PR-1 Viewer 全量实测与截图**：[pr1-acceptance.md](evidence/c1/pr1-acceptance.md) · [marquee-window.png](evidence/c1/marquee-window.png) · [marquee-crossing.png](evidence/c1/marquee-crossing.png) · [title-cell-picked.png](evidence/c1/title-cell-picked.png)
- **PR-2 项目级模板与自检实测**：[pr2-acceptance.md](evidence/c2/pr2-acceptance.md)
- **PR-3 样式配置与 Logo 实测与截图**：[pr3-acceptance.md](evidence/c3/pr3-acceptance.md) · [style-after.png](evidence/c3/style-after.png) · [logo-render.png](evidence/c3/logo-render.png)
- **评测与变异汇总（PR-3 / PR-4 基线）**：
  - `evals/run.py --baseline`：`40/40 passed`（`G=1.0`，`D=0.986906`，`T=1.0`，`regressions: []`）。
  - `evals/mutate.py`：`41` 条规则 / `45` 个变异，`45` 检出（`1.0`），参考图误报 `0`，`debt_freeze_exact=True`（涵盖 `table_overflow` 3/3、`table_style_gb` 1/1、`title_style_gb` 1/1、`logo_external_ref` 1/1）。

## 5. 偏离记录

1. **新增跟进卡 C1b（`#166` / `#167`）**：PR-1 合入后用户试用确认底部 `#hint` 说明条多余；曾讨论标题栏非字段格按几何线段切格并经用户明确收敛为仅移除 `#hint`，独立建卡一轮评审通过合并。
2. **并行卡片合入顺序与 3 轮评审**：PR-3（`#168`/`#169`）与 PR-2（`#170`/`#171`）基于 PR-1/C1b 并行推进，PR-3 先于 PR-2 通过 2 轮评审合入；PR-2 在第 2 轮修正目录查找跳过图纸自身 `.git` 后通过第 3 轮只读评审并合入。
3. **发布执行分工变更（`#163`，`4354aab`）**：由早期「DSH 执行发布」更新为 `PR-4` 合入且 `main` CI 全绿后由 `agy` 执行 `scripts/release.py 0.1.3`（DSH 事后核对 tag 与 Release）。

## 6. 遗留事项与 v0.2 建议

- **v0.1.3 需求明确延期项（见 `v0.1.3-REQ.md` §4）**：基线修订层 codegen 成单文件 `drawing.py`（B 方案推迟至 `v0.1.4`+）；参考 DXF/PDF 自动模板逆向；矢量 Logo；表格/标题栏非字段静态格或边框线逐段 ID 化。
- **既有 v0.2 跟踪事项**：继续推进 `#145`（全剖端面线贯通通孔）、`#146`（形位公差符号渲染）、`#147`（V1 发现汇总）以及 STEP/PMI、尺寸与序号布局深耕。
