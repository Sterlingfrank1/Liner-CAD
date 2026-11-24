# v0.1.2 计划：一次请求 = 一次达标交付

2026-11-24 · 来源：DSH 现场复盘（首次出图 **37.8 min / 148 模型步 / 174 次工具调用**，其中 lcad 命令仅 235 s）· 目标：把“Agent 自己反复抛光”改成“一次写全 + 批量修到达标”，并让任意目录直接 `lcad`。

## 1. 目标

1. **装一次，直接用**：全局 `lcad`（0.1.1 起）+ DSH skill 一次安装；之后在任意图纸目录直接 `lcad ...`，不 `uv run`，不读 Liner-CAD 源码仓库。
2. **一次调用拿到“改 + 查 + 图”**：`build` / `edit` 加 `--png`，一个事务返回全部 findings 与 PNG；**不新增 `review` 命令**，`check` / `render` 保持独立。
3. **首图一次写全**：视图、尺寸、PMI、技术要求、参数表、标题栏、未注公差都在第一次 build 前写进 `drawing.py`；参数表升级为语义表格（`d.table`），可查询、可点选、可检查。
4. **可度量的体验**：首次出图 ≤ 12 模型步 / ≤ 5 min；后续每轮（人点选或对话反馈）≤ 6 步 / ≤ 2 min；每轮修改必须是批量脚本，不设迭代次数上限，达标才交付。

## 2. 非目标

- 不做 `lcad review` 新命令：它只是 build/edit + check + render 的包装，会增加概念；用 `--png` 合并。
- 不做 DSH `open_url` 插件：Viewer 用 `lcad view --no-open` + 回复里的链接，人在 DSH 右侧边栏点开。
- 不改自动布局算法（layout.py 的求解策略）；`d.table` 只做排版与检查，不做全局求解。
- 不做参数表之外的通用复杂表格（合并单元格、跨页等）v1 不做。

## 3. 决策记录（已与用户确认）

1. **“1 轮”= 一次用户请求到达标**；轮内可以有很多次内层批量迭代，**不设上限**。约束是：每次修改必须批量、必须先收齐全部 finding 再规划。
2. **warning 修复，或 `d.accept(rule, id, "理由")` 并逐条列出理由，算达标**；不静默、不因为“看着差不多”就停。
3. **不做与达标无关的自行抛光**；但达标所需修复必须做完。
4. **脚本只属于 `edit`**；`--png` 是 `edit`/`build` 的输出选项，不是新层、不是新命令。
5. **首图不设“收尾阶段”**；参数表、技术要求、标注、标题栏全部进第一次 build。

## 4. 卡片

| ID | 优先 | 目标 | 依赖 | 热点 | 核心 | Goal 条件 | 估时 |
|---|---|---|---|---|---|---|---|
| C1 | P0 | DSH skill 安装：`lcad skill install --target dsh` 写到 `%USERPROFILE%\.agents\skills\linercad\SKILL.md`，幂等更新；帮助 / README 写清全局安装（`uv tool install`） | — | commands.py、cli.py、tests/test_skill.py、README.md | 否 | 任意 cwd 执行后文件存在、内容与打包 SKILL.md 一致（首行 `name: linercad`）；重复执行不产生第二份、能覆盖更新；`lcad --help` 的 `skill` 条目列出 dsh；测试用临时 HOME，不碰真实用户目录；pytest、ruff、CI 四项绿；PR squash 合并 | 0.5d |
| C2 | P0 | `lcad build --png` / `lcad edit --png`：成功事务后在同一调用内渲染，JSON 增加 `png`；不新增命令；失败不渲染 | — | commands.py、cli.py、render.py、tests | 否 | `build --png` 与 `edit x.py --png` 的 JSON 含 `png` 且文件存在、尺寸正确；不带 `--png` 行为与现在完全一致；失败路径无 `png`、仍回滚；动作日志 / commit / 事务语义不变；成功、失败、无标志三组测试；CLI help 同步（SKILL 示例由 lead 更新）；CI 绿；PR 合并 | 0.5d |
| C3 | P0 | `d.table(...)` 语义表格（参数表）：单元格 `T.<name>.<r>.<c>`，可查询、可点选、进检查；默认标题栏上方，`at=` 可覆盖；列宽、行高、换行；v1 不做合并单元格 | — | annotate.py、layout.py、rules.py、model.py（query）、viewer/、tests | 是 | 一张 5×4 参数表零件图 `lcad check` 0 error；`d.q.cells(table="…")` 能取到单元格；表格越界、文字出格能被 check 抓到并给 candidates；参数滑块变化后表格内容更新；Viewer 能点选单元格；每个场景留回归用例；评测 40/40、几何 1.0 不退化；pytest、ruff、CI 绿；PR 合并（skill/pages/api.md 由 lead 同步） | 2d |
| V1 | P0 | 计时复跑：用 C1 + C2 + 新 skill 在**临时图纸仓库**重画行星轮（或同复杂度），验证“不读源码仓库、直接 lcad、批量修到达标” | C1、C2、Skill playbook | docs/milestones/v0.1.2/evidence/ | 否 | 首次出图 ≤ 12 模型步、≤ 5 min；一次迭代 ≤ 6 步、≤ 2 min；0 error；warning 全部修复或带理由 accept 并逐条列出；记录步数 / 耗时 / lcad 子命令；cwd 是图纸仓库、无 Liner-CAD 源码读取；证据（JSON + 小截图）入库；独立复核通过 | 0.5d |
| R1 | P1 | 版本与安装：0.1.2 版本号、发布说明、`uv tool install` 后任意目录 `lcad --version` 验证 | C1、C2、C3、V1 | pyproject.toml、docs/releases/v0.1.2.md、README.md | 否 | `uv tool install --force <repo>` 后 `lcad --version` = 0.1.2（在 `%TEMP%` 验证）；发布说明列 C1–C3 与 V1 数字；README 快速开始改成“全局 lcad + skill”；CI 绿；tag `v0.1.2` | 0.5d |

## 5. 顺序与依赖

```
C1 → C2 → V1 → R1
C3 可并行（热点 annotate/layout/rules/viewer，不与 C1/C2 冲突）
```

- C1、C2 是 V1 的前置；V1 用新流程跑通后才发版。
- C3 只动表格相关文件；V1 先用现有 raw 参数表跑，不阻塞。
- R1 必须等 V1 的数字进证据后再打 tag。

## 6. Skill 变更（lead 直接维护，不走卡片）

已改 `src/linercad/skill/SKILL.md`：

- 新增 **1.1 交付轮与内层迭代**：一次请求 = 1 轮；内层迭代不限次数；每次修改必须批量、先收齐 finding 再规划；达标定义；首图一次写全；不自行抛光。
- 工作循环改为 `build --png` / `edit --png`（当前版本无 `--png` 时同回合紧跟 `render`，C2 合并后删掉这句 fallback）。
- 增加 Viewer 配方：`LCAD_NO_VIEW=1` 出图；`lcad view --no-open` 起后台 Viewer；URL 给用户，DSH 侧边栏点开；`lcad context "@sel"` 读选中。
- 明确“在图纸目录直接用 `lcad`，不读 Liner-CAD 源码仓库，不 `uv run`”。

已同步到本机 `C:\Users\XU\.agents\skills\linercad\SKILL.md`（DSH 当前会话已能加载 `linercad` skill）。

## 7. 验收与质量门禁

- 每张卡：先写失败测试（G2）；`uv run pytest`、`uv run ruff check`、`uv run ruff format --check` 全绿；CI 四项（lint、ubuntu 3.11、windows 3.13、3d）；新代码有测试；修复留回归；不为过关削弱检查。
- 评测：40/40 零 error、几何 / 完整性 1.0 不退化；C3 后基线不退化。
- V1 证据：`docs/milestones/v0.1.2/evidence/` 放步数 / 耗时 JSON、最终渲染图（小）、accept 清单。
- 不产生图纸仓库 commit 到本开发仓库（V1 在临时目录进行）。

## 8. 已知边界

- `--png` 会让 build/edit 多 1–2 s 渲染；不带标志不增加。
- `d.table` 默认位置需要避让标题栏、技术要求、明细栏；v1 只保证“标题栏上方 + at 覆盖”，复杂版式用 `at`。
- 全局 `lcad` 是发布快照；开发期改了源码要重新 `uv tool install --force` 才生效。
- DSH 的 skill 在会话启动时加载；安装后新会话生效（本次会话已手动刷新，属例外）。
