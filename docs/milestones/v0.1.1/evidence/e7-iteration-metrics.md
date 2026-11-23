# E7 迭代速度（P 过程）证据

卡片 issue #108 · 流 W1 · 分支 m5/e7-iteration-metrics · 基线 cf1f959。
入库 P 工件：docs/milestones/v0.1.1/evidence/e7-cross-report.json（由 import-demo 生成，含 4 个 fresh 场景与 P 字段）。
数据源：把仓库外的 run_demo.py 驱动/事件解析并入 evals/cross_agent.py（import-demo 可回放其 events.jsonl + metrics.json）；现场 Codex 用 cross_agent.py 直接跑；dsh 使用 H2 已有 4 场景结果与本机 headless 复跑（配额见第 4 节）。

## 1. 口径

| 口径 | 实现 | 说明 |
|---|---|---|
| fresh（每轮新开调用） | 每轮一个新 CLI 进程/新 session | 上一轮上下文不保留，最坏情况 |
| conversation（同一对话连续修改） | 首轮后带 session id resume：codex exec resume、dsh --session-id、claude --resume | 同一 session 连续修改 |

每轮记录：seconds（进程墙钟）、usage input/output（新处理 token = input + output，cache_read 不计）、steps（模型步）、tools/lcad 子命令计数、lcad check errors/warnings。
P 聚合（cross_agent score / import-demo 的 P 字段）：first_pass_rate（首轮 check 0 error 的比例）、mean_rounds（到 0 error 的轮数）、mean_seconds、mean_new_tokens、mean_steps，按 mode 分列。
这些字段是 Agent 侧口径；H2 的 5.92s/2.21s 是 lcad 进程侧，不能直接相加比较。

## 2. run_demo 4 个试用场景（fresh 首轮，H2 现场实测，来源：D:\Industry\Claude-Code\lcad-demo\results，2026-11-22 前跑）

命令：uv run python evals/cross_agent.py import-demo --results D:\Industry\Claude-Code\lcad-demo\results --out docs/milestones/v0.1.1/evidence/e7-cross-report.json（入库的 P 报告工件即该命令产物）

| 场景 | 首轮耗时 s | 新 token（in+out） | 步数 | check |
|---|---:|---:|---:|---|
| claude × 牛鼻刀 tool | 100.1 | 5,141 | 25 | 0 error |
| claude × 电机 motor | 274.2 | 23,214 | 39 | 0 error |
| dsh × 牛鼻刀 tool | 675.3 | 177,401 | 124 | 0 error |
| dsh × 电机 motor | 900.0 | 228,094 | 142 | 0 error |
| **P / fresh 均值** | **487.4** | **108,462** | **82.5** | first_pass_rate **1.0** / mean_rounds **0.0** |

对照 H2：lcad 侧首次出图 5.92s、模板换规格 2.21s（本机 lcad 进程口径）；Agent 侧首轮均值 487s，说明迭代慢落在模型轮次/探索，不在 lcad 命令本身（与 issue #108 的试用结论一致）。

## 3. 两口径命令（可直接复跑）

    # fresh：每轮新 session
    uv run python evals/cross_agent.py run --root R --agent codex --task box --rounds 1 --mode fresh
    # conversation：同一 session 连续修改
    uv run python evals/cross_agent.py run --root R --agent codex --task box --rounds 1 --mode conversation
    # 回放 run_demo 结果
    uv run python evals/cross_agent.py import-demo --results D:\Industry\Claude-Code\lcad-demo\results --out report.json

## 4. 现场复跑状态（不伪造）

- Codex：cross_agent 现场 run tool（fresh 首轮 + conversation 修改轮）结果见第 6 节；命令与事件流已跑通。
- 裁定（lead 2026-11-22）：dsh conversation 数据格标「402 配额阻塞、待充值后补测」，不伪造；同日 w3/lead 同机同 key，换人跑仍是 402。
- dsh conversation：本机 headless resume 正常启动（session 能 resume），但 DEEPSEEK_API_KEY 返回 `QUOTA 402 Insufficient Balance`（request_id 44ddaba6-13ee-49bb-bde5-1661d5448b6f），修改轮无法出数；已报用户充值，充值后一行命令可补测。dsh fresh 首轮四场景亲眼数据见第 2 节。

## 5. 测试与框架

- tests/test_cross_agent.py 11 tests：claude/dsh/codex 事件解析（token/步/工具/lcad 子命令）、fresh vs conversation 命令构造（dsh --session-id / codex resume / claude --resume）、P first_pass/mean_rounds 两 mode、import-demo 回放。
- G2：test commit 6a0ed71；实现 commit 7dfd88b。
- baseline：P 按 E1 设计不在绘图向量内（evals/baseline.json 的 families 不含 P）；cross_agent 的 P 报告独立产出，写 PR 说明，无绘图 baseline 变动（--baseline 仍空）。

## 6. Codex 现场（cross_agent run，2026-11-22 本机）

任务 tool（牛鼻刀模板，workdir %TEMP%\e7-cross 外的 e7-codex），首轮 fresh + 第 1 轮 conversation：

| 口径 | 轮 | 耗时 s | 新 token（in+out） | cache read | 步数 | shell 工具 | lcad check |
|---|---|---:|---:|---:|---:|---:|---|
| fresh | 0 首图 | 523.8 | 3,882,262 | 3,709,440 | 119 | 40 | 0 error / 0 warning |
| conversation | 1 改 D=10 | 114.2 | 5,129,887 | 4,820,672 | 26 | 8 | 0 error / 0 warning |

同一 session（thread 01a206d2-…）连续修改：耗时从 523.8s 降到 114.2s（约 4.6×），步数 119→26；首图与修改轮都 0 error。Codex 现场只跑了 tool（fresh 首图 + resume 修改轮）与 motor（fresh 首图）；另两个 Codex 场景未跑（时间预算），dsh 见第 4 节。conversation 的修改轮无 round 0，P 中记为 incremental，不能当成完整 conversation 口径。

任务 motor（电机外形图，fresh 首轮）：

| 口径 | 轮 | 耗时 s | 新 token（in+out） | cache read | 步数 | shell 工具 | lcad check |
|---|---|---:|---:|---:|---:|---:|---|
| fresh | 0 首图 | 301.5 | 1,973,440 | 1,881,856 | 81 | 28 | 0 error / 1 warning |

Codex 两种口径的 P（本机现场，来自 e7-codex root 的 runs，未写进入库的 e7-cross-report.json）：fresh tool+motor 2 场景 mean_seconds **412.6**、mean_new_tokens 2,927,851、mean_steps 100、first_pass_rate 1.0、mean_rounds 0.0；conversation 只有修改轮（round 1，无 round 0），按实现归入 **incremental**，不计算 first_pass_rate/mean_rounds：本轮 114.2s、5,129,887 新 token、26 步；comparison 只作增量口径。

## 7. P 族数据

- fresh（入库 e7-cross-report.json 为 H2 四场景回放；Codex tool/motor 为 e7-codex root 现场 runs，另表）first_pass_rate、mean_rounds、mean_seconds、mean_new_tokens、mean_steps 见 cross_agent report 的 P 字段；本卡 P fresh 数据来自 §2/§6；conversation 只有 Codex tool 的修改轮增量（incremental），无完整 conversation 首轮数据，dsh conversation 402 缺测。
- P 不在 evals/baseline.json 的绘图向量内（E1 设计：families 为 G/D/T/A，P 为过程规则）；cross_agent 的 P 报告独立产出。本卡未改绘图 baseline，--baseline 仍空。


