# v0.1.2 动机基线：DSH 行星轮首图复盘（2026-11-23）

> 来源：DSH 会话「行星齿轮图纸生成测试」（session-7a206322，存档在 `C:\Users\XU\.dsh\sessions\--D-Industry-Claude-Code-Liner-CAD--\session-7a206322-f729-40da-9083-3a17a571b85d\`，多帧 zstd JSONL）与临时图纸仓库 `D:\Industry\Claude-Code\lcad-demo\planetary-gear\`（保留可查）。
> 目的：把只存在于该会话上下文中的复盘数据落盘，作为 V1 计时复跑的对照基线；数字为该会话 turn 3 对自身存档的统计（已抽查 commit 数、渲染文件时间戳相符）。

## 1. 原始请求（V1 复跑用同一句）

> 现在我想做一次测试，利用lcad，生成一个行星齿轮的图纸，尺寸合适即可。Viewer直接在dsh里打开，进行交互。

- 模型与档位：deepseek-v4.1-flash，reasoning effort high。
- 环境：v0.1.1 发布**前**（全局 lcad 当时为 0.1.0.dev0），DSH 未装 linercad skill，Agent 从 Liner-CAD 源码仓库探索起步。

## 2. 结果

- 终态 `lcad check`：**0 error / 0 warning**；e0→e11 共 12 个 commit，约 28 min。
- 图纸：A3、2:1，半剖主视图 + 端面视图；m=3 z=24 α=20°，内孔 Φ25H7，6×Φ8 EQS，基准 A + 跳动/垂直度，40Cr 调质（见仓库 `drawing.py`）。
- 参数表为 `d.raw_add` 手画 raw 图元，**不参与检查、不可点选** —— C3 `d.table` 的直接动机。
- 抛光式迭代实例：e9→e10→e11 连续三轮都在修"减重孔注释引线"一处。

## 3. 硬数据（首图交付轮）

| 指标 | 数值 |
|---|---|
| 总时长 | 2269.6 s = 37.8 min |
| 模型步数 | 148 步（27 步并行发多个工具） |
| 工具调用 | 174 次 |
| 模型生成时间 | 1984 s（87.4%） |
| 工具执行时间 | 283 s（12.5%） |
| 单步耗时 | 中位 11.1 s，p90 32.6 s，最长 58.9 s |
| lcad 命令 | 55 次，合计 235 s（build/render/check 中位 2.9 s） |
| 看图 read_image | 17 次 |
| 失败命令 | 26 次（约 6–8 次为自身失误，如 PowerShell 编码写坏文件） |

## 4. 时间阶段

| 阶段 | 步数 | 模型时间 | 发生了什么 |
|---|---|---|---|
| 0–5.7 min | 33 | 318 s | 读源码仓库 + 钻 DSH 内部（asar/插件/ego-browser）找 Viewer 打开方式，未碰 lcad |
| 5.7–11.9 min | 16 | 301 s | 读 SKILL/API/范例，init，写首图，第一次 build 成功 |
| 11.9–26.7 min | 60 | 846 s | **最大块**：11 次 build、14 次 render、17 次看图，标注一处处修 |
| 26.7–31.7 min | 18 | 193 s | 起 Viewer、ego-browser 截图尝试、选中链路验证 |
| 31.7–37.8 min | 21 | 327 s | 参数表、孔标注、技术要求等"收尾" |

首张 0 warning 约 22 min，定稿 26.7 min。

## 5. 根因 → v0.1.2 归因

| 根因 | 修复 | 落点 |
|---|---|---|
| 步数即时长（174 次工具 × ~11 s） | 压调用次数 | C2 `--png` + SKILL 硬规则 |
| 读仓库 / DSH 内部考古 | 全局 lcad + skill，禁读源码仓库 | C1 + SKILL 配方 |
| 一处处修、无批量 | 一次收齐全部 finding → 一个批量脚本 | SKILL 1.1 |
| 17 次看图 | 看 1 次/内层迭代 | SKILL 1.1 |
| 收尾阶段补参数表/技术要求 | 首图一次写全；参数表语义化 | SKILL 1.1 + C3 |
| Viewer 现场研究 | `LCAD_NO_VIEW=1` + `view --no-open` + 链接配方 | SKILL 1.1 |

历史对照：README 记录的 DSH 首图基线 713–1265 s（12–21 min）；本次 2269 s 为其 1.8–3.2 倍。

## 6. V1 复跑口径（建议写进 V1 验收）

- 同一请求原话、同复杂度、临时图纸仓库、相同模型与档位（deepseek-v4.1-flash / high）；
- 记录：模型步数（DSH session stats 同口径）、总耗时、lcad 子命令耗时、看图次数、失败命令数、是否读过源码仓库（应为 0）；
- 达标线：首图 ≤ 12 步 / ≤ 5 min，内层迭代 ≤ 6 步 / ≤ 2 min；0 error；warning 全修或带理由 accept 逐条列出；
- 未达标处置：改 SKILL 措辞后复跑一次；仍不达标 → 如实上报用户重定目标，不静默放宽。
