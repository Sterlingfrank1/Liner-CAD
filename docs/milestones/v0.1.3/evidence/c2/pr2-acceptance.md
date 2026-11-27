# C2 验收报告（项目级模板与保存前自检）

- Issue：`#170`（`[v0.1.3/C2] 项目级模板与保存前自检`）
- 分支：`v013/templates`
- 提交范围：`19e6785..HEAD`（Commit 1 `699475a` R9；Commit 2 `d26eeae` R10；Commit 3 `0dc2fcc` R11；Commit 4 R12 + 文档与证据）

## 1. 需求逐项验收（R9–R12）

### R9：项目根标记、解析顺序、优先级与列表契约
- 新增 `src/linercad/project.py`：实现 `linercad.project.toml` 标记读写与优先级解析（`--project` > `LCAD_PROJECT_ROOT` > 向上找 marker 并在遇到祖先 `.git` 查完后停止 > `cwd.parent` / `cwd` 兜底）；严守不在图纸目录内建标记或目录、不以无标记磁盘根目录为项目根。
- 默认行为：显式 `--scope project` 或 `--project` 允许创建项目标记（且仅在 `--dry-run` 之外、校验与边界自检全部通过后写入）；缺省 `--scope` 与 `--project` 仅复用已有项目标记，找不到时回退用户目录 `LCAD_TEMPLATES`（避免意外写盘）。
- `--tag` 仅写入 `template.json`，不触发用户项目内 `git commit` / `git tag`；模板包及 `template list` 中不存在 `kind` 字段；`init --from` 查找优先级严格为 **项目 > 用户 > 内置范例**。
- 实测保存目录结构（含 marker、语义基线与 Logo 资源）：
  ```text
  linercad.project.toml
  lcad-templates/flange-std/assets/logo.png
  lcad-templates/flange-std/baseline.actions.jsonl
  lcad-templates/flange-std/drawing.py
  lcad-templates/flange-std/template.json
  ```
- 实测 `linercad.project.toml`：
  ```toml
  version = 1
  name = "raptor-proj"
  created = "2026-11-26T21:39:23+00:00"
  [templates]
  dir = "lcad-templates"
  ```

### R10：语义基线固化、`model_hash` 校验与实例化重放
- `usertemplates.py` 新增 `is_semantic_op()` / `filter_baseline_ops()` / `model_hash()` / `probe_template()`：
  - 保留 `accept` / `general_tol` / `rough_default` 及 `D.` / `N.` / `G.` / `R.` / `DT.` / `T.` / `A.` / `B.` / `K.` / `V.` 前缀操作（统一改写 `edit="e0"`），写入 `baseline.actions.jsonl`；丢弃非语义前缀并记录 `baseline_stats` 与前 5 条示例。
  - 通过 `dxfout.external_images()` 将图纸目录内 Logo 图片复制到模板包并写入 `assets/`；若图片指向图纸目录之外则在保存阶段拒绝并给出路径。
- 实测 `template.json`（schema=2，含 `model_hash` 与 `probe`，`source.dir` 为绝对源码目录）：
  ```json
  {
    "schema": 2,
    "name": "flange-std",
    "tag": "r1",
    "description": "带Logo和基线的法兰模板",
    "files": ["drawing.py", "assets/logo.png", "baseline.actions.jsonl"],
    "model_hash": "sha256:214ab9b74bc610c5f8ace83e42f1b8da0da2ab74eaa966a30f9021e185eab732",
    "probe": {"builds": 6, "failed": [], "stale_semantic": [], "skipped": []}
  }
  ```
- 实测 `lcad log` 与撤销守卫：
  - 带 tag（`--tag r1`）：`e0` 提交消息为 `init --from flange-std@r1`（对应 git subject `e0 · init --from flange-std@r1`）。
  - 无 tag：`e0` 提交消息为 `init --from flange-notag`（不留尾随 `@`）。
  - `lcad undo e0` 拒绝（`ok: false`，消息 `e0（init）不能撤销`）；后续 `e1` 修改后执行 `lcad undo e1` 成功（`ok: true`），且 `drawing.actions.jsonl` 中源自基线的 `D.L` 位置修订完整保留。
- 实测 `--set` 三组参数（`80/40/8`、`150/90/14`、`190/110/20`）实例化与 `lcad check`：
  - 3 组实例 `init` `errors` 与 `lcad check` `errors` 全部为 `0`（`baseline_warnings = 0`）。

### R11：保存前参数边界自检
- `probe_template()` 在隔离临时副本中材料化基线日志后，对每个非空且 `min != max` 参数依次构建 `min` / `max`（上限 16 次，超限记入 `skipped`）；普通 `warn` 与 `E.*` 失效不报错，`Param.rule` 违反、构建异常、`errors > 0` 或语义 op 失效记入 `failed` / `stale_semantic` 并拒绝保存（`--force-probe-fail` / `--no-probe` 可按需覆盖）。
- 实测 `flange-std`（3 个有界参数 `L`/`H`/`W`）触发 `builds=6, failed=[], stale_semantic=[], skipped=[]`；内置 `shaft` 因耦合 `Param.rule` 触发默认探测失败并回滚，`--force-probe-fail` 与 `--no-probe` 行为与单测一致。

### R12：来源信任提示与文档
- `trust_info()` 区分 `local` / `builtin` / `external`；当模板来源于项目根之外或源码目录缺失时，在 `template list` 与 `init --from` 输出中附带 `trust="external"` 与 `trust_warning="模板含可执行 drawing.py，确认后再用"`（实测与 `ext-tpl` 输出完全一致）。
- 已更新 `src/linercad/skill/SKILL.md`（保持 `<= 120` 行）、`src/linercad/skill/pages/api.md`、`src/linercad/commands.py`（`_template_section`）与 `src/linercad/cli.py`（`COMMANDS`），并通过 `tests/test_skill.py` 与 `tests/test_docs.py`。

## 2. 门禁结果
- `uv run ruff check`：`All checks passed!`
- `uv run ruff format --check`：`236 files already formatted`
- `uv run pytest -q`：`1590 passed, 1 skipped`（0 失败，包含 `test_project_templates.py`、`test_template_replay.py`、`test_templates.py`、`test_skill.py`、`test_docs.py` 与全套回归）
