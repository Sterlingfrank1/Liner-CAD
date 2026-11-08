# M2 BRIEF：Viewer v0

> 写给 M2 里程碑会话。流程、门禁和**精简规则**见 `docs/ROADMAP.md`（§4.1–4.2 优先）；设计依据见 `DESIGN.md` §5（下文 § 均指它）；上一阶段见 `docs/milestones/M1/HANDOVER.md`（尤其 §7“给 M2 的说明”）。

## 1. 目标

做出 design for human & agent 的 Viewer（核心竞争力第 3 条）：人看图、点选、拖滑块；Agent 读 `selection.json` / `snapshot.json` / `@ID` 来改图。闭环是：**点选 → @ID → Agent 写临时脚本修改 → Viewer 自动刷新**；拖动参数滑块时实时重建，满意后写回源码。

Viewer 只是 harness 的一个窗口：不内嵌代码编辑器，不内置对话，不画图，不调 LLM。

## 2. 范围

| 模块 | 内容 | 依据 |
|---|---|---|
| 带 ID 的 SVG | 由内存中的 ezdxf 文档渲染 SVG，每个图元带 `data-id`（来自 XDATA 的元素 ID）；未命名几何也能被点中，并给出几何选择器表达式 | §5.1、§4.1 |
| 本地服务 + 静态页 | `lcad view [目录]`：很小的本地 Python 服务（尽量只用标准库）+ 一个静态页面（原生 JS，无框架、无构建步骤、可离线）。三栏：参数 / 画布 / 检查器，加状态栏 | §5.2 |
| 画布 | 平移、缩放；悬停高亮，点击选中整个元素，Ctrl 多选 | §5.2 |
| 检查器 | 意图 / 值 / 公差、引用关系、来源位置（链接到用户 IDE，如 `vscode://file/…:行`）、检查结果；[复制 @ID]，格式如 `@D.shaft_D（Φ30 g6，主视图）` | §5.2、§5.3 |
| Agent 桥 | `.linercad/selection.json`（选中 ID 或选择器）、`.linercad/snapshot.json`（当前版本、选择、问题列表、视口、滑块临时值）；`lcad context @sel` 可用 | §5.3 |
| 问题着色 | 红 = error，橙 = warn，accepted 另色；与 `lcad check` 结果一致 | §5.2、§4.5 |
| 自动刷新 | `drawing.py`、动作日志或 git HEAD 变化后自动重建并刷新画布；构建失败时保留上一版并显示错误（顺带修 M1 缺口：构建失败时 `lcad context` 不可用） | §5.2 |
| 状态栏 | `e7 · 2 个警告 · "用户原话"` | §5.2 |
| 参数滑块 | 由 `Param(min, max, step, unit, label, group)` 自动生成；拖动经防抖后在内存中重建（构建层 + 修订层）并刷新，不写文件不提交；违反 `rule` 时标红且不应用；失效的日志操作给出提示；临时值写进 `snapshot.json`；[写回源码] 改 `drawing.py` 中该 `Param` 的默认值、跑检查、提交一个 commit。典型零件拖动响应 < 0.5 s | §5.2、§6 |
| Skill | `SKILL.md` 增加一小节：用户说“这个 / @sel / 我选中的”时怎么读 selection / snapshot，怎么看到用户在试的参数值 | §7 |

**顺带（出图效果）：** M1 G5 实测中最弱的一项是形位公差框格、粗糙度引线在拥挤处与尺寸线 / 延伸线交叉（M1 render-review 第 1、6、11、12 条；pulley 主视图右侧 Φ28H7 / Φ60 / 基准 A 挤在一起）。在布局层修掉，并给每个案例留一个回归用例。另：ISO 档技术要求自动追加的“General tolerances ISO 2768-m”一条字号与前几条不一致（M1 `evidence/flange_iso.png`）。

**不做：** 版本列表与视觉 diff（M3）、编辑后高亮变化（之后）、直接拖动标注（之后）、多用户 / 远程访问、登录鉴权（只监听 127.0.0.1）。

## 3. 验收（G5）

1. **闭环实测：** 从干净 clone 安装，`lcad view` 打开一个范例；在浏览器里点选元素（M2 会话可用内置浏览器面板操作并截图）→ 生成 `selection.json` / 复制 `@ID` → 一个**独立 agent 只拿 `SKILL.md`** 和一句“把我选中的…改成…”，用 `lcad context @sel` 写临时脚本、`lcad edit` 提交 → Viewer 自动刷新出新版本，状态栏编号变化。两族各做至少 2 轮，记录进 `evidence/`。
2. **滑块：** 在轴套类、盘盖类范例上拖动参数，服务端“重建 + 渲染”耗时 p50 / max 记录在 evidence，典型零件 < 0.5 s；违反 `rule` 时不应用；写回源码只改该 `Param` 所在行，检查通过，恰好一个 commit。
3. **可点选覆盖：** 每个范例里，带 XDATA 的图元都有 `data-id`；随机抽取的未命名几何能给出可用的选择器表达式（有自动化测试）。
4. **着色一致：** Viewer 的问题着色与 `lcad check` 输出逐条一致（有自动化测试）。
5. **依赖：** 核心依赖仍以 ezdxf 为主，Viewer 不引入重型框架；前端无构建步骤。
6. **界面评审：** 各范例的 Viewer 截图（含选中、着色、滑块状态）由独立多模态 agent 对照 §5.2 评审，结论写进 HANDOVER；需要用户看的列进“待用户人工评审”。
7. CI 通过，HANDOVER 合并，tag `v0.1-m2` 已推送。

自动化测试测服务接口、SVG 与 `data-id` 映射、selection / snapshot 写入、内存重建、写回源码；浏览器里的交互用 G5 实测和截图证明，不为前端引入 Playwright 之类的重依赖。

## 4. 留给 SPEC 决定

1. SVG 怎么出：ezdxf drawing add-on 的 SVG 后端加 `data-id` 后处理，还是从模型直接写一个最小 SVG；图元到元素 ID 的映射方式。
2. 服务形态：标准库 `http.server` + 轮询还是 SSE；文件变化用 mtime 轮询（不加 watchdog 依赖）。
3. 内存重建怎么做到 < 0.5 s：哪些可缓存，怎么测。
4. 写回源码的规则：只改字面量默认值；默认值是表达式时拒绝并说明原因；commit 信息格式（例如 `e8 · 参数 d1=32（Viewer 写回）`）。
5. 未命名几何的选择器表达式格式（沿用 `d.q` 的写法）。
6. 分几组 PR。建议：带 ID 的 SVG + 服务 + 画布 / 选择 / 检查器 / 桥 → 着色 + 自动刷新 + 状态栏 → 滑块 + 写回 → 布局修复 → G5。

账户是 Pro 计划，周额度紧：按 ROADMAP §4.1 精简规则执行（前端这类简单卡片适合交给 Sonnet），额度用完按 §4.2 写进度笔记并以 `M2 BLOCKED — usage limit` 结束。

## 5. Goal 条件

> M2 done when: SPEC merged; all M2 PRs merged with CI green; from a clean clone `lcad view` serves an example and the loop works: click → selection.json/@ID → an independent agent using only SKILL.md edits via `lcad context @sel` + `lcad edit` → Viewer auto-refreshes (2+ rounds per family); sliders rebuild in memory under 0.5 s on example parts and write-back makes one commit; issue colours match `lcad check`; Viewer screenshots reviewed; HANDOVER merged; tag v0.1-m2 pushed.
