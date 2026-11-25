# v0.1.2 HANDOVER

2026-11-25 · 版本 `0.1.2` · 计划 [PLAN](PLAN.md) · 证据 [evidence/](evidence/) · 发布说明 [docs/releases/v0.1.2.md](../../releases/v0.1.2.md)

v0.1.2 完成“一次请求 = 一次达标交付”闭环改造：DSH 全局 Skill 安装（C1）、`build --png` / `edit --png` 单事务出图与查验（C2）、`d.table` 语义参数表（C3）、无源码读取的计时复跑验证（V1），以及 0.1.2 发版收口（R1）。**版本 tag `v0.1.2` 与 GitHub Release 不在本 PR 内创建**，由用户在 `main` 复核后按 `docs/RELEASING.md` 执行 `uv run python scripts/release.py 0.1.2`。

## 1. 交付

- `pyproject.toml` 与 `uv.lock` 升级至 **`0.1.2`**（CI 使用 `uv sync --locked`）。
- 发布说明 `docs/releases/v0.1.2.md` 与本交接文档 `docs/milestones/v0.1.2/HANDOVER.md`，同步更新 `docs/ROADMAP.md` §1 / §5 与 `README.md`。
- 核心功能与证据：C1（#151 / PR #152）、C2（#153 / PR #154）、V1（#155 / PR #157 + `evidence/v1-planetary-rerun.*`）、C3（#158 / PR #159）、R1（#160 / 本 PR）。

## 2. 怎么验证

在干净仓库或隔离目录执行：

```bash
uv sync --extra 3d

uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run python evals/run.py --baseline evals/baseline.json
uv run python evals/mutate.py
```

全局安装与任意目录 Smoke 验证（在 `%TEMP%` 执行，不留提交进开发仓库）：

```powershell
uv tool install --force .
Push-Location $env:TEMP; lcad --version; Pop-Location   # 应输出 0.1.2
lcad skill install --target dsh
```

## 3. 5 卡清单与去向

| 卡 | issue | PR | 分支 / 合并 SHA | 内容与去向 |
|---|---|---|---|---|
| C1 | #151 | #152 | `m1/c1-skill-dsh` (`ee9c1ca`) | `lcad skill install --target dsh` 全局写 `~/.agents/skills/linercad/SKILL.md`、幂等覆盖、帮助/文档更新。已合并。 |
| C2 | #153 | #154 | `m1/c2-build-edit-png` (`303cca5`) | `lcad build --png` / `lcad edit --png` 成功事务直接输出 PNG（失败不写并回滚），CLI 帮助同步。已合并。 |
| V1 | #155 | #157 | `m1/v1-planetary-rerun` (`237decd`) | 行星齿轮隔离目录复跑证据（`evidence/v1-planetary-rerun.{json,md}`, `evidence/v1-planetary-r2-render.png`）、SKILL/API 修订、PLAN §9 偏离 17、v0.1.3 摩擦点 `#156`。已合并。 |
| C3 | #158 | #159 | `m1/c3-semantic-table` (`d295267`) | `d.table(...)` 与 1-based `T.<name>.<r>.<c>`、查询、布局避让、`table_overflow` 规则与变异（`DESIGN §4.2`）、SVG/Viewer 点选与参数预览、`T.title.*` `table="title"` 统一。已合并。 |
| R1 | #160 | 本 PR | `m1/r1-release-0.1.2` | 版本 `0.1.2`、发布说明、`HANDOVER.md`、ROADMAP/README 同步、`tests/test_release_v012.py` 与 `%TEMP%` 全局安装实测。 |

## 4. 验收与证据

| 项 | 结果 | 证据 |
|---|---|---|
| C3 合并态回归与门禁（`main@d295267`） | `uv run pytest -q`：**1551 passed, 1 skipped**；`ruff check` & `ruff format --check` 全绿；`evals/run.py --baseline`：40/40、`regressions: []`（G 1.0 `4469/0`、D 0.986906 `2902/38`、T 1.0 `403/0`；G 新增 `table_overflow` `0/0`）；`evals/mutate.py`：38 规则 / 41 变异 / **41 检出（1.0）** / 误报 **0** / `known_debt.exact = True` | PR #159、CI 4/4（lint / ubuntu 3.11 / windows 3.13 / test-3d） |
| R1 全量回归与全局 CLI（issue #160 / 本 PR 本地实测） | `uv run pytest -q`：**1556 passed, 1 skipped**（含 `tests/test_release_v012.py`）；`ruff check` & `ruff format --check`（231 文件）全绿；`evals/run.py --baseline`：40/40、`regressions: []`；`evals/mutate.py`：38 规则 / 41 变异 / 检出 **1.0** / 0 误报 / `known_debt.exact = True`；`uv tool install --force --reinstall --no-cache --with build123d` 后于 `%TEMP%` 执行 `lcad --version` 输出 `{"ok": true, "version": "0.1.2"}`，`lcad skill install --target dsh` 写入 `~/.agents/skills/linercad/SKILL.md` | `tests/test_release_v012.py`、`%TEMP%` CLI 实测 |
| V1 计时复跑（跨 harness 对照，仅方向性参考） | DSH 基线：`2269.6 s (37.8 min)` / `148` 步 / `174` tool calls；Run 2（`agy`）：**`623.0 s`（`10.38 min`）/ `41` tool calls（`35` turns）**、看图 `4` 次、失败 `7` 次、源码读取 **`0` 次**、终态 `0/0`（含 1 accept），分阶段 `18–19 / 7 / 7 / 4` 步、`286–295 / 151 / 96 / 33` s；Run 1：`728.0 s / 75 tool calls`、0 源码读取、终态 `0/0` | `evidence/v1-planetary-rerun.md`、`evidence/v1-planetary-rerun.json`、`evidence/v1-planetary-r2-render.png` |
| 每卡 Codex 独立评审 | C1（R1 PASS）、C2（R2 PASS）、V1（R4 PASS）、C3（R5 合流终审 `REVIEW PASS`, `findings: []`）、R1（本 PR 经 Codex 评审后合并） | `v0.1.2-supervisor/status.json` |

## 5. 偏离记录

- **偏离 17（PLAN §9）**：V1 原始阶段门槛（首次 `≤ 12 步 / ≤ 5 min`，后续迭代 `≤ 6 步 / ≤ 2 min`）由 **DSH + `deepseek-v4.1-flash`** 标定；本次复跑在 **`agy`** 下按工具调用计步（`18–19 / 7 / 7` 步与 `286–295 / 151 / 96` s）。经 2026-11-24 用户裁定，以过程行为合同（0 源码读取、首图写全、批量修改、4 次看图、终态 0 error / 0 warning）判 V1 通过，原始实测数字完整留存于 [PLAN.md §9](PLAN.md#9-偏离记录) 与 `evidence/v1-planetary-rerun.*`，不作改写。

## 6. 遗留事项与 v0.1.3 建议

- **#156（[v0.1.3 汇总 issue](https://github.com/Sterlingfrank1/Liner-CAD/issues/156)）**：
  1. `lcad skill --help` 返回 `usage: unrecognized arguments: --help`（exit code 2）；
  2. `d["G.cyl_bore"].set(target=...)` 需在 `message`/`hint` 明确列出可写属性与只读约束；
  3. `d.q.lines().near(...)` 多命中时在 `message`/`candidates` 按距离列出候选元素。
- **V1 同 harness 校准**：在 DSH + `deepseek-v4.1-flash` 环境下重新标定/复测 `v0.1.2` 流程并校准阶段数字门槛。
- **用户发版操作**：R1 PR 合并入 `main` 且 CI 四项全绿后，由用户在 `main` 执行 `uv run python scripts/release.py 0.1.2 --dry-run` 核对无误后执行 `uv run python scripts/release.py 0.1.2` 打 `v0.1.2` annotated tag 并发布 GitHub Release。
