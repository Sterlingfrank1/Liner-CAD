# v0.1.3 · AGY CLI 开工说明（Swarm：Supervisor + Worker + Reviewer）

> 这份文件是给 agy cli 的操作手册；需求/设计/拆卡的真相源是同目录三份文档。冲突时以文档为准。

## 0. 角色与模型

| 角色 | 模型 | 职责 |
|---|---|---|
| **Supervisor**（你） | Neon (xhigh) | 建卡、派活、验收、合并、写 HANDOVER；不写业务代码（冲突/小修除外） |
| **Worker** | Hydrogen (xhigh) | 一张卡一个会话，从分支开发到 PR |
| **Reviewer** | Hydrogen (xhigh) | 每个 PR 新开一个会话，只读评审，可多轮 |

## 1. 仓库与基线

- 仓库：`D:\Industry\Claude-Code\Liner-CAD`（Windows，`uv` 管理，UTF-8 + LF）。
- 门禁命令：`uv run pytest`、`uv run ruff check`；涉及检查/布局跑 `uv run python evals/run.py --baseline`。
- 基线：`main`（v0.1.2）；目标版本 `v0.1.3`。
- 必读：`docs/milestones/v0.1.3/{v0.1.3-REQ.md,v0.1.3-SPEC.md,v0.1.3-CARDS.md}`，以及仓库根 `CLAUDE.md`、`AGENTS.md`、`DESIGN.md` 相关章节。
- **这三份里程碑文档在开发期间只读**；要改先问用户。

## 2. Supervisor 先做的四件事

1. 读文档，确认 3 张卡的范围与你理解一致；有歧义先问用户，不猜。
2. 建 GitHub milestone `v0.1.3`（若不存在），建 3 张 issue：标题用 `[v0.1.3/Cx] <PR 名>`，正文用 CARDS 的"目标 / 范围 / 验收"三段，PR 里写 `Closes #N`。
3. 建进度笔记 `docs/milestones/v0.1.3/PROGRESS.md`：卡号、分支、PR 号、gate 结果、review 轮次、遗留项。
4. 起 **PR-1**（单独先做，见 §3）。

## 3. 顺序（不要三个同时开工）

```
W1：PR-1（唯一 Worker）           ← 改 cli.py / viewer/* 热文件
     合入、CI 绿、用户试用确认
W2：PR-2 与 PR-3 并行（两个 Worker）← 文件基本不重叠
```

- PR-1 合入前不要开 PR-2/PR-3 的分支，避免 cli.py 与 viewer 的 rebase 痛苦。
- PR-2 与 PR-3 同时进行时，各自 rebase 最新 main；合并顺序由你定，但每次合并后立刻在 main 重跑全量门禁。

## 4. 每张卡的硬顺序

1. **建卡**（issue，含验收清单）。
2. **派 Worker**：brief 必须带卡号、目标、范围/不做、SPEC 章节号、验收命令、分支名 `v013/<slug>`、停止条件。
3. **开发**：先写失败测试；小步提交；本地 `pytest` + `ruff` 全绿。
4. **自查**：跑本卡验收命令，产出证据（截图 / JSON 片段 / 命令输出），存到 PR 描述或 `docs/milestones/v0.1.3/evidence/<card>/`。
5. **开 PR**：标题 `[v0.1.3/Cx] <名>`；body 带验收勾选、证据、`Closes #N`、契约变更列表（新增 JSON 字段）。
6. **Code review**：**新开一个 agy 会话**（Hydrogen xhigh，只读），用 §6 的 reviewer brief。P0/P1 必须修完并复审，直到一轮 review 无 P0/P1。
7. **合并**：分支 rebase 最新 main → 重跑门禁 → squash 合并；合并后在 main 重跑 `pytest` + `ruff`（PR-1/PR-3 再跑 evals）。

## 5. 硬约束（违反即回退）

1. 不直推 `main`；不 `force-push`；不删别人的分支；不合并未过 review 的 PR。
2. 契约只增不改：CLI JSON、`selection.json`、`template.json` 现有字段语义不变，新增字段必须在 PR 里列出。
3. 不做 SPEC"明确不做"清单：sheet/drawing 双形态、`init --sheet`、参考 DXF/PDF 自动复刻、`--squash` 单文件、矢量 Logo。
4. 文档与代码同 PR：`SKILL.md`、`pages/viewer.md`、`pages/api.md`、`docs/ROADMAP.md` 看板。
5. `lcad` 不替用户 commit 图纸项目、不打 git tag；模板 `--tag` 只写 `template.json`。
6. 每 PR 必须绿：`pytest` + `ruff`；PR-1/PR-3 加 `evals/run.py --baseline`；CI 四项。
7. 遇到 SPEC 未写死的选择：**停下来问用户**，把问题、两个选项、推荐各一行写清楚。
8. 不要给 DSH 会话派活或等它——它只读监控。

## 6. Reviewer brief（原样发给新的 review 会话）

```text
你是 Liner-CAD v0.1.3 的独立代码评审者（只读，不改代码）。
仓库：D:\Industry\Claude-Code\Liner-CAD；PR #<N>；卡 C<x>。
先读：docs/milestones/v0.1.3/v0.1.3-SPEC.md 的对应章节、v0.1.3-CARDS.md 里该卡的"范围 / 验收"。
评审要点：
1) 改动是否只在卡内，有没有顺手改无关代码；
2) 契约是否只增不改（JSON/selection.json/template.json）；新增字段是否列出；
3) 验收清单是否每条都有自动化测试，或说明为何只能手工；
4) 边界：异常路径、空输入、Windows 路径、并发/端口、预览态与提交态；
5) 文档是否同 PR 更新；
6) 你可以在本地跑 uv run pytest / ruff check 验证，但不得修改任何文件；
7) 看 diff 用 `gh pr diff <N>`；需要读全文时用 `git worktree add ../rev-<N> <branch>` 另开工作区，**不要在主工作区切分支**（会把 Worker 的现场切走）。
输出 findings，按 P0（阻断）/ P1（必须修）/ P2（建议）分级，每条给 文件:行、问题、建议改法；
最后给结论：APPROVE 或 REQUEST CHANGES。不要评论纯风格偏好。
```

## 7. Worker brief 模板

```text
你是 v0.1.3 卡 C<x> 的开发者（Hydrogen xhigh）。
仓库：D:\Industry\Claude-Code\Liner-CAD；分支：v013/<slug>（从最新 main 切）。
读：docs/milestones/v0.1.3/v0.1.3-SPEC.md 的 §<章节>、v0.1.3-CARDS.md 的 C<x>。
范围：<一段话>；不做：<一句>。
要求：TDD（先失败测试）；小步提交；本地 pytest + ruff 全绿；<该卡的验收命令>。
完成标准：验收清单全勾 + 证据（截图/JSON）+ PR 描述写 Closes #<N> 与契约变更。
遇到 SPEC 未定：停下来问，不扩范围。
```

## 8. 收尾（PR-4）与发布归属

三卡合并且 main 全绿后，做一张收口 PR（不占功能卡名额）：

1. `pyproject.toml` 版本号 → `0.1.3`；
2. `docs/releases/v0.1.3.md`（做了什么、验证证据、已知缺口、升级说明）；
3. `docs/milestones/v0.1.3/HANDOVER.md`（交付、怎么验证、偏离）；
4. `docs/ROADMAP.md` 看板（状态更新，tag 列留空）；
5. 全局安装验证：`uv tool install --reinstall .` 后 `lcad --version` = 0.1.3。

合入后 STOP：**正式发布（`git tag` / `gh release create`）由 DSH 执行 `scripts/release.py 0.1.3`**，agy **不要**自己打 tag、建 Release，也不要推 tag。

## 9. 汇报节奏

- 每次回复不超过三行：`Cx / PR# / 测试结果 / review 结论`；卡住时给"问题 + 两个选项 + 推荐"。
- 每完成一个 gate，把证据路径写进 PROGRESS.md，不靠聊天记忆。
## 10. 与 agy orchestrator 模式的配合（推荐做法）

agy 1.5.17 有 `gemini-pro-orchestrator-neon`（Orchestrator）与 `gemini-4-hydrogen-xhigh` 等模型。建议**只把 orchestrator 用在开发轴**，评审与门禁不要交给它：

| 环节 | 用谁 |
|---|---|
| 规划 / 派活 / 汇总证据 | Orchestrator（Neon xhigh），一个阶段一个会话 |
| 写代码 | Worker：Hydrogen xhigh（在 brief 里写死，若 orchestrator 不能锁模型，就退回手动开 Worker 会话） |
| 代码评审 | **agy 后台新建的独立会话**，模型固定 `gemini-4-hydrogen-xhigh`，只读；一轮不够再来一轮，最多 3 轮 |
| 合并 / 关卡 | 你（或一个只读 Supervisor 会话）；orchestrator 不许合并 |

**分两次 orchestrator 运行，不要一次跑完三张卡**：

1. **Phase A**：会话只做 PR-1，交付 PR 后**停下来等用户试用确认**；
2. **Phase B**：新会话做 PR-2 + PR-3（可并行），每张卡结束同样停下等 review 结论。

理由：一次长会话会积累上下文、漂移范围；两段式天然对齐 W1/W2 门禁，也避免它自动连做三张卡。

**给 orchestrator 的额外约束（写进 kickoff 的启动语）**：

- 每完成一张卡的 PR 就 STOP，等用户/评审结论，不自动进入下一张；
- 不合并任何 PR、不打 tag、不改三份里程碑文档；
- 所有 Worker 一律 `hydrogen-xhigh`；评审会话由 agy 后台新建（命令见 §11），与开发会话分开；
- 子任务开始前先输出"卡号 + 分支 + 验收命令"一行，便于用户核对。

评审会话的固定命令（在独立 worktree 里跑，避免切走 Worker 现场）：

```powershell
git worktree add ..\rev-<PR号> origin/<分支>
agy --print --mode plan --model gemini-4-hydrogen-xhigh --effort xhigh "<§6 reviewer brief + PR 号>"
```

`--mode plan` 让评审会话不动文件；`--print` 拿到一次性结论。

如果 agy 的 orchestrator 无法锁定 executor 模型或无法在卡间停下，就**不要用它**，按 §7 手动开 Worker 会话——可控性优先于省事。
## 11. 启动提示词（直接粘贴到新的 agy 窗口）

```text
V0.1.3 开发：agy Orchestrator mode：Neon(xhigh) + Hydrogen(xhigh)；code review 由 agy 后台新建会话（Gemini 4 Hydrogen XHigh）。

你是 Liner-CAD v0.1.3 的执行 Agent，同时负责评审调度与验收。
工作目录 D:\Industry\Claude-Code\Liner-CAD（Windows / PowerShell / uv / gh 已登录 / 全局 lcad 0.1.2）。
本会话是 Orchestrator 模式（planner Gemini 4 Neon (XHigh)，executor Gemini 4 Hydrogen (XHigh)）。
不要改模型，不要在命令里传 --model 或 --effort（评审会话除外，见第 6 步）。

【第一步：只读，不改任何文件】
1) 读仓库根 AGENTS.md（行为纪律）与 CLAUDE.md（开发约定）。
2) 读 docs/milestones/v0.1.3/ 下的 v0.1.3-REQ.md、v0.1.3-SPEC.md、v0.1.3-CARDS.md、AGY-KICKOFF.md。
3) 读 DESIGN.md 相关章节、docs/ROADMAP.md §1/§6、docs/RELEASING.md（只读，用于最后的收口）。
4) 不要读 refs 下的 progress.md / status.json / 旧 milestone 全文；路径与版本以本提示词为准。

【第二步：开场自检，贴原始输出，然后停下】
执行并贴出：pwd、git status -sb、lcad --version、uv run pytest -q 的末行统计。
我说"开始"之前：不要写代码、不要建分支、不要开 issue。

【开工后：单卡闭环】
1) gh issue create：标题 [v0.1.3/Cx] <名>，正文含 目标 / 范围 / 不做 / 验收 / 依赖（取自 CARDS 对应 PR）。
2) git fetch origin && git switch -c v013/<card-slug> origin/main
3) RED：先写会失败的测试，uv run pytest <test> -q，贴失败输出。
4) GREEN：实现，uv run pytest -q 全绿。
5) 门禁：uv run ruff check；uv run ruff format --check；PR-1/PR-3 再跑 uv run python evals/run.py --baseline。
6) 评审（每卡最多 3 轮）：agy 后台新建只读会话，模型固定 Hydrogen XHigh：
   git worktree add ..\rev-<PR号> origin/<分支>
   agy --print --mode plan --model gemini-4-hydrogen-xhigh --effort xhigh "<§6 reviewer brief + PR 号>"
   输出问题清单（文件:行号 / 严重度 blocker|major|minor / 依据）+ 结论行 REVIEW PASS 或 REVIEW ISSUES: n。
   第 3 轮仍不过 → 停，报 CARD <id> BLOCKED — review escalation，复述 3 轮意见等仲裁。
7) gh pr create（body 写 Closes #<issue>，贴验收证据）→ CI 四项绿 → 合并前 rebase 最新 main → gh pr merge --squash。

【卡序】
PR-1 单独先做 → 合入并等我试用确认 → PR-2 与 PR-3 并行（各一个 Worker、各一个分支）→ PR-4 收口。
每完成一张卡的 PR 就 STOP，等我或评审结论，不自动进入下一张。

【收口】PR-4：版本号 0.1.3、docs/releases/v0.1.3.md、HANDOVER.md、ROADMAP 看板、全局安装验证。
合入后 STOP：正式发布（git tag / gh release create）由 DSH 执行 scripts/release.py 0.1.3，你不要打 tag、不要建 Release、不要推 tag。

【禁止】直推 main、force-push、删除他人分支、改三份里程碑文档（REQ/SPEC/CARDS）、合并未过评审的 PR、替用户的图纸项目 commit 或打 tag、给 DSH 会话派活。
遇到文档没写死的选择：停下来问，给"问题 + 两个选项 + 推荐"各一行，不自行扩范围。
```
