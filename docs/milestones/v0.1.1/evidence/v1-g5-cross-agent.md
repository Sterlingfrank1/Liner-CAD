# V1 G5：独立 Agent 跨 Agent 验证与出图评审（证据）

卡 V1（issue #102，W4）· G5 硬合同 · 2026-11-23 · 由 supervisor 安排独立验证（dsh 全新子代理 + Codex 在干净 clone 上执行）；本文件由 w4-acceptance 维护，数字由 supervisor 核验后填入。

> 状态：**部分待填**。§1–§4、§6 为第一批已核验数据；磨头 PDF 任务（§2 任务 2）与出图评审（§5）数字第二批填入；CI 四项 run 在 PR 开出后填入。入库的小文件：`v1-g5-dsh-final-render-e3.png`、`v1-g5-dsh-check-e3.json`、`v1-g5-dsh-log.json`、`v1-g5-codex-report.json`。

## 1. 干净 clone 环境

- clone：`D:\Industry\Claude-Code\Liner-CAD-v1-clean`，HEAD **`865c9c1`**（D7，即 V1 文档 PR 之前的 main），2026-11-23 10:00Z。
- `uv sync --extra 3d`：绿。
- Skill 安装方式：只给 Agent 装好的 Skill（`lcad skill install`），不附加 harness 源码提示；Agent 为全新上下文（不给“预期答案”）。
- 图纸仓库都在 clone 之外的临时目录，产物不入库；复核确认没有图纸 commit 进入产品仓库。

## 2. 任务清单（issue #102：至少 2 个任务，其一参照用户磨头 PDF 画回转体零件）

| # | 任务 | 说明 | 结果 |
|---|---|---|---|
| 1 | 多轮修改任务 | dsh 路一：法兰变体 3 轮（init → 构建层变体 → 按检查器 candidates 修 → 修订层 dry-run + 真实 edit）；Codex 路：牛鼻立铣刀 fresh 首图 + conversation 修改轮 | 完成：dsh 3 轮 `e0→e3` 四提交、check 0/0；Codex 首图 386.5 s、修改轮 86.0 s、两轮 check 0/0；见 §3/§4 |
| 2 | 磨头 PDF 回转体零件 | 只参照用户提供的磨头参考图（`YH-0000-RJ-26041-AiN-A-磨头`，已渲染 PNG；PDF / PNG 不入库）新画一张回转体零件图，并用 `lcad check` 自检；含 dry-run 修改轮（v1-dsh-agent-2 全新子代理） | TBD-V1-G5-TASK2（第二批） |

## 3. 独立 Agent ①：dsh 全新子代理（法兰变体，多轮修改）

- 环境与命令：全新子代理，只读 lcad skill 文档；图纸仓库 `%TEMP%\v1dsh`；CLI 侧两轮 < 20 s，全程含看图约 30 min。
- 轮次：3 轮 —— `e0 init` → `e1` 构建层变体（检查器抓到 1 条 `place_nesting`）→ 按 finding 的 candidates 修 `e2` 归零 → 修订层 `--dry-run` 预览 + 真实 `e3`（凸台止口 h8、安装面粗糙度引线移到实体端面、新增止口对基准 A 圆跳动 0.04）；工作区干净。
- 每轮 `lcad check`：**0 error / 0 warning**（e3 原始输出见 `v1-g5-dsh-check-e3.json`）。
- dry-run 一致性：`--dry-run` 预览图与最终 `render` 的 SHA256 相同 = `FCA2B9DC6037D7DA462B7EAD1ADDA61501C2BF54ACCDDA72CD2922107940BA30`（两文件各 67,083 B，supervisor 复算）。
- 提交记录：`v1-g5-dsh-log.json`（e0 4ec44a1 / e1 29d1fbd / e2 2c2ef79 / e3 606afeb）。
- 发现的问题（如实记录，待 §5 评审结论定级）：
  1. 内置 flange 范例全剖端面线横穿 Φ30 通孔开口 —— v0.1.0 既有画法疑点，图像评审员独立判断中；
  2. PMI 元素 ID 无法从 `context` / 文档直接发现；
  3. `render --focus` 有 stderr 噪声；
  4. `--version` 报 0.1.0（本 V1 正在 bump 到 0.1.1，属既有版本号的预期差异）；
  5. 图框边偏挤。
- 渲染图：`v1-g5-dsh-final-render-e3.png`（本目录，67 KB）。

## 4. 独立 Agent ②：Codex（cross_agent conversation 模式，task=tool）

- 环境与命令：`evals/cross_agent.py` conversation 模式，`task=tool`（牛鼻立铣刀）；工作目录 `%TEMP%\v1-cross`；session `01a20737-c652-7981-9c8c-f60789d2bdec`；报告 `v1-g5-codex-report.json`。
- 轮次 / 每轮耗时 / 新处理 token / 模型步数：
  - 首图 fresh 轮：**386.5 s** / 78 步 / 新 token ≈ 2.99 M（input 1,523,347 + output 26,645；cache_read 1,442,048 不计）；check **0 error / 0 warning**。
  - 修改轮 conversation：**86.0 s** / 14 步（D8→10 联动 6 个参数：D1/R/L1/L2/d/L，title 图号同步）；check **0 error / 0 warning**。
  - 两轮 session 相同 → **约 4.5× 提速**；P conversation：`first_pass_rate = 1.0`、`mean_rounds = 0.0`、`mean_seconds = 236.2`、`mean_steps = 46.0`。
- 独立解决问题：本地没有样例 `./template/牛鼻铣刀.dxf` 时，按 A3 / GB 标准样式自建图面（尺寸参数表、标题栏、技术要求齐全）。
- 渲染图：报告 JSON 里 `png` 指向临时目录（`%TEMP%\v1-cross\codex\tool\drawing\.linercad\tmp\render.png`），不入库；评审用渲染由 supervisor 的评审代理读取。

## 5. 出图评审（是非题清单，与 v0.1.0 对比）

- 评审对象：TBD-V1-G5-DRAWINGS（dsh 路一 e3 渲染图 + Codex 牛鼻刀渲染图 + v0.1.0 对照图；V1 新出图，小文件入库 / 临时渲染不入库）。
- 评审方式：多模态逐张评审，是非题清单逐项答“是 / 否 / 不可判”，并给出理由；独立评审代理 `v1-image-review` 执行中。
- 是非题清单（每张图逐项）：
  1. 视图表达：三视图 / 剖视 / 局部放大关系正确，长对正、高平齐、宽相等；螺纹、中心孔、退刀槽等规定画法正确。
  2. 尺寸排布：尺寸线 / 尺寸界线 / 文字无交叉与压线，大小尺寸内外层次合理，数字方向正确（GB/T 4458.4）。
  3. 序号与明细栏：序号对齐、间距、顺序可读，明细栏合并与数量正确、长文字在格内（GB/T 4458.2）。
  4. PMI：公差 / 基准 / 形位公差 / 粗糙度框格与引线正确、不重叠，数值来自资源库并注明标准号。
  5. 标题栏 / 技术要求 / 图幅：字段填写完整、分区正确；技术要求与标准档一致。
  6. 整体观感：作为工程图可直接交付使用（人工评审 5 分制）。
- 评分与 v0.1.0 对比：TBD-V1-G5-REVIEW（v0.1.0 新范例与装配图多为 2–3 / 5；本次每张图的分数、问题清单与是否成立）
- 结论：TBD-V1-G5-REVIEW-CONCLUSION（可接受的缺口 / 必须修的回归；含 §3 五条问题的独立判断）

## 6. 干净 clone 全量回归（supervisor 复核，2026-11-23 10:00Z）

- clone HEAD `865c9c1`；`uv sync --extra 3d` 绿。
- pytest：**1515 passed / 1 skipped（786.7 s）**（V1 文档 PR 之前的 main；V1 另加 12 条版本 / 文档测试，合并态由 PR CI 覆盖）。
- ruff check：绿。
- `evals/run.py --baseline`：`regressions: []`，exit 0。
- `evals/mutate.py`：37 规则 / 39 变异 / **39 检出（1.0）** / 误报 **0** / errored 0 / unmutated 0。
- `evals/place_scores.py --eval40`：exit 0；flange 1.0（0/45）、pulley 0.9756（2/82）、gear_cover 1.0（0/82）、jack 1.0 / A.place 1.0、vise 0.9583（1/24）/ A.place 1.0。
- CI 四项（PR run）：TBD-V1-CI

## 7. 清理与产物

- viewer / lcad 进程扫描：全程零残留（supervisor 兜底已 kill 过 E7 遗留的 4 个 viewer）；临时目录与干净 clone 无图纸 commit 进入产品仓库（已核）。
- 入库产物：本文件 + 4 个小文件（渲染 PNG 67 KB、check JSON 1 KB、log JSON 0.9 KB、Codex 报告 JSON 3.5 KB）；样例 DXF、标准原文、用户磨头 PDF / 参照 PNG 不入库。
