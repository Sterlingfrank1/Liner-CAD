# V1 G5：独立 Agent 跨 Agent 验证与出图评审（证据）

卡 V1（issue #102，W4）· G5 硬合同 · 2026-11-23 · 由 supervisor 安排独立验证（dsh 全新子代理 + Codex 在干净 clone 上执行）；本文件由 w4-acceptance 维护，数字由 supervisor 核验后填入。

> 状态：**已填**（CI 四项在 PR 上运行，结果见 GitHub Actions）。入库的小文件：`v1-g5-dsh-final-render-e3.png`、`v1-g5-dsh-check-e3.json`、`v1-g5-dsh-log.json`、`v1-g5-codex-report.json`、`v1-g5-mo-tou-final-render.png`、`v1-g5-mo-tou-compare-stack.png`。

## 1. 干净 clone 环境

- clone：`D:\Industry\Claude-Code\Liner-CAD-v1-clean`，HEAD **`865c9c1`**（D7，即 V1 文档 PR 之前的 main），2026-11-23 10:00Z。
- `uv sync --extra 3d`：绿。
- Skill 安装方式：只给 Agent 装好的 Skill（`lcad skill install`），不附加 harness 源码提示；Agent 为全新上下文（不给“预期答案”）。
- 图纸仓库都在 clone 之外的临时目录，产物不入库；复核确认没有图纸 commit 进入产品仓库。

## 2. 任务清单（issue #102：至少 2 个任务，其一参照用户磨头 PDF 画回转体零件）

| # | 任务 | 说明 | 结果 |
|---|---|---|---|
| 1 | 多轮修改任务 | dsh 路一：法兰变体 3 轮（init → 构建层变体 → 按检查器 candidates 修 → 修订层 dry-run + 真实 edit）；Codex 路：牛鼻立铣刀 fresh 首图 + conversation 修改轮 | 完成：dsh 3 轮 `e0→e3` 四提交（e1 变体被检查器抓 1 条 place_nesting、e2 归零，**e3 最终 check 0/0**）；Codex 首图 386.5 s、修改轮 86.0 s、两轮 check 0/0；见 §3/§4 |
| 2 | 磨头 PDF 回转体零件 | 只参照用户提供的磨头参考图（`YH-0000-RJ-26041-AiN-A-磨头`，已渲染 PNG；PDF / PNG 不入库）新画一张回转体零件图，并用 `lcad check` 自检；含 dry-run 修改轮（v1-dsh-agent-2 全新子代理） | 完成：两轮 `e0→e2`、check 0/0、dry-run 5 ops 与真实提交一致；见 §3b |

## 3. 独立 Agent ①：dsh 全新子代理（法兰变体，多轮修改）

- 环境与命令：全新子代理，只读 lcad skill 文档；图纸仓库 `%TEMP%\v1dsh`；CLI 侧两轮 < 20 s，全程含看图约 30 min。
- 轮次：3 轮 —— `e0 init` → `e1` 构建层变体（检查器抓到 1 条 `place_nesting`）→ 按 finding 的 candidates 修 `e2` 归零 → 修订层 `--dry-run` 预览 + 真实 `e3`（凸台止口 h8、安装面粗糙度引线移到实体端面、新增止口对基准 A 圆跳动 0.04）；工作区干净。
- `lcad check`：e1 变体按设计被检查器抓到 **1 条 `place_nesting`**（非回归，用来验证 finding → candidates → 修复闭环），e2 归零；**e3 最终 0 error / 0 warning**（原始输出见 `v1-g5-dsh-check-e3.json`）。
- dry-run 一致性：`--dry-run` 预览图与最终 `render` 的 SHA256 相同 = `FCA2B9DC6037D7DA462B7EAD1ADDA61501C2BF54ACCDDA72CD2922107940BA30`（两文件各 67,083 B，supervisor 复算）。
- 提交记录：`v1-g5-dsh-log.json`（e0 4ec44a1 / e1 29d1fbd / e2 2c2ef79 / e3 606afeb）。
- 发现的问题（§5 评审结论已定级）：① 内置 flange 范例全剖端面线横穿 Φ30 通孔开口（v0.1.0 既有，评审证实 → issue #145）；② PMI 元素 ID 无法从 `context` / 文档直接发现（#147）；③ `render --focus` 有 stderr 噪声（#147）；④ `--version` 报 0.1.0（本 V1 已 bump 到 0.1.1）；⑤ 图框边偏挤（#147）。

## 3b. 独立 Agent ①b：dsh 全新子代理（磨头参考图 → 回转体零件）

- 环境：v1-dsh-agent-2，全新上下文，只参照磨头参考图（像素判读图幅 A3 横 / 2:1 / 第三角投影）；图纸仓库 `%TEMP%\v1accept\drawing`（`e0→e2` 干净）；CLI 侧 2 轮各约 2 s。
- 轮次：
  - `e1` 首图：Ø16×20 磨头 + Ø14 柄 + 端面 Ø12 深 3 沉孔 + 2×2.5 端槽 + 基准 A + 平行度 0.04 A + 7 条技术要求。
  - `e2` 修改轮：`--dry-run` **5 ops 与真实提交一致**（补 Ra1.6 / Ra3.2 / 通用符号、去重复技术要求、尺寸线移位）。
- 每轮 `lcad check`：**0 error / 0 warning**。
- 几何自检：渲染实测总长 69.9 / 磨头 20.0 / Ø16.1 / 柄 Ø14.0（题目 2:1 比例下与设计值一致）。
- 参照图自身缺陷（agent 如实指出，非实现问题）：柄径标注与描画不一致（标注 Ø14 / 描图 Ø12）；平面度违规带基准；无粗糙度标注。磨料纹理只能以 45° 剖面线近似（`v.hatch` 无纹理图案接口，见 #147）。
- 渲染 / 对比图：`v1-g5-mo-tou-final-render.png`（1018×720，49 KB）、`v1-g5-mo-tou-compare-stack.png`（1400×1999，参照 vs 渲染上下叠放，354 KB）；DXF / 样例 PDF / 参照 PNG 不入库。

## 4. 独立 Agent ②：Codex（cross_agent conversation 模式，task=tool）

- 环境与命令：`evals/cross_agent.py` conversation 模式，`task=tool`（牛鼻立铣刀）；工作目录 `%TEMP%\v1-cross`；session `01a20737-c652-7981-9c8c-f60789d2bdec`；报告 `v1-g5-codex-report.json`。
- 轮次 / 每轮耗时 / 新处理 token / 模型步数：
  - 首图 fresh 轮：**386.5 s** / 78 步 / 新 token **1,549,992**（input 1,523,347 + output 26,645；cache_read 1,442,048 不计，报告里的 `tokens_total` 2,992,040 含 cache_read，不作新 token 口径）；check **0 error / 0 warning**。
  - 修改轮 conversation：**86.0 s** / 14 步（D8→10 联动 6 个参数：D1/R/L1/L2/d/L，title 图号同步）；check **0 error / 0 warning**。
  - 两轮 session 相同 → **约 4.5× 提速**；P conversation：`first_pass_rate = 1.0`、`mean_rounds = 0.0`、`mean_seconds = 236.2`、`mean_steps = 46.0`。
- 独立解决问题：本地没有样例 `./template/牛鼻铣刀.dxf` 时，按 A3 / GB 标准样式自建图面（尺寸参数表、标题栏、技术要求齐全）。

## 5. 出图评审（是非题清单，与 v0.1.0 对比）

- 评审对象：dsh 路一 `e3` 渲染图（`v1-g5-dsh-final-render-e3.png`）+ v0.1.0 对照；独立评审代理 `v1-image-review` 逐像素评审。
- 评审方式：多模态逐张评审，是非题清单逐项答“是 / 否 / 不可判”并给理由。
- 评分（5 分制）：① 视图方案 / 剖视 **4**；② 标注 **3**；③ 标题栏 / 技术要求 **4**；④ 整体可读 **4**；⑤ 画法 **3**。总评 **PASS WITH NOTES**：可作 V1 出图能力验收；两处必须修已开 issue、记 v0.2，不阻塞本版。
- 证实 / 新开 issue：
  - **#145**：通孔开口封口疑点**证实为真**（两版渲染均在，v0.1.0 既有）——全剖端面粗实线整段横穿 Φ30 通孔开口，通孔被读成盲孔，与左视图 Φ30 圆自相矛盾；修复属引擎改动，记 v0.2。
  - **#146**：形位公差符号渲染不可辨（圆跳动只剩单斜线、箭头端缺失）；记 v0.2。
  - **#147**：V1 发现汇总（`v.hatch` 无图案 / 纹理接口等 7 条 + 正面确认；另含 dim.groove fmt、技术要求去重、el.move 语义、dim.dia 45° 引出、环形 hatch loops、render 无 DPI 等）。
- e3 vs e2 改进确认：Ra 引线贴面、补 h8、无回退。
- B 级意见（记录，不阻塞）：Φ105 引线穿中心、Ra1.6 引线共线、EQS / GB 混用、Ra 注位与 GB/T 131 常见图示相反。

## 6. 干净 clone 全量回归（supervisor 复核，2026-11-23 10:00Z）

- clone HEAD `865c9c1`；`uv sync --extra 3d` 绿。
- pytest：**1515 passed / 1 skipped（786.7 s）**（V1 文档 PR 之前的 main；V1 另加版本 / 文档测试，合并态由 PR CI 覆盖）。
- ruff check：绿。
- `evals/run.py --baseline`：`regressions: []`，exit 0。
- `evals/mutate.py`：37 规则 / 39 变异 / **39 检出（1.0）** / 误报 **0** / errored 0 / unmutated 0。
- `evals/place_scores.py --eval40`：exit 0；flange 1.0（0/45）、pulley 0.9756（2/82）、gear_cover 1.0（0/82）、jack 1.0 / A.place 1.0、vise 0.9583（1/24）/ A.place 1.0。
- CI 四项（PR run）：见 PR 的 GitHub Actions（lint / test ubuntu 3.11 / test windows 3.13 / test-3d）。

## 7. 清理与产物

- viewer / lcad 进程扫描：全程零残留（supervisor 兜底已 kill 过 E7 遗留的 4 个 viewer）；干净 clone 遗留的 `report.json` 已清（非验证产生）。
- 临时目录与干净 clone 无图纸 commit 进入产品仓库（已核）；临时图纸仓库删除。
- 入库产物：本文件 + 6 个小文件（两份渲染 PNG 共 403 KB、check JSON 1 KB、log JSON 0.9 KB、Codex 报告 JSON 3.5 KB，均为小验收证据）；样例 DXF、标准原文、用户磨头 PDF / 参照 PNG 不入库。
