# M2 SPEC：Viewer v0

> 依据 `BRIEF.md`、`DESIGN.md` §5–§6、M1 `HANDOVER.md` §7。精简规则见 ROADMAP §4.1。只写决定、接口、验收映射和卡片。

## 1. 决定（BRIEF §4）

| # | 问题 | 决定 |
|---|---|---|
| 1 | SVG 怎么出 | **直接由布局结果写最小 SVG**（`linercad/svgout.py`）：每个元素一个 `<g data-id="…" data-kind="…">`，内含它的图元（line / circle / arc path / polyline / polygon / text；剖面线用 SVG `<pattern>` 填充）。图元与 DXF 实体一一对应（同一份 `_prims`，DXF 写出用的也是它），所以 `data-id` = XDATA 元素 ID，`data-k` = 子图元序号。不走 ezdxf drawing add-on：慢且要后处理找回 ID |
| 2 | 服务形态 | 标准库 `ThreadingHTTPServer`，只绑 `127.0.0.1`；页面每 1 s 轮询 `/api/state`（版本号 + 状态行）；服务在轮询时比较 `drawing.py`、`drawing.actions.jsonl`、`.git/HEAD` 及其指向的 ref 的 mtime，变了就重建。不用 SSE、不用 watchdog |
| 3 | < 0.5 s 重建 | 实测（本机）完整重建 + 检查 + SVG：shaft 70 ms、pulley 50 ms、end_cover 45 ms，不需要缓存。预览走与 `lcad build` **同一条**构建路径（含 DXF 文档，`raw` 覆盖与失效操作一致），只是不写文件、不提交；参数覆盖由 contextvar 注入 `Drawing.params`，`validate` 照常报 `rule` / 越界。服务端计时随响应返回（`timing_ms`），测试断言 < 2 s（CI 宽松），evidence 记 p50 / max |
| 4 | 写回源码 | 源文件有未提交改动时拒绝（`dirty`）；先用该值做一次内存构建（校验 rule / 范围）；再用 `ast` 找 `name=Param(<字面量>, …)` 的第一个位置参数（含负号字面量），按列号替换（整数写 `32`，小数写 `repr`）；只改这一处；默认值是表达式、跨行或找不到唯一一处时拒绝并说明原因。随后 `lcad build` 事务提交一个 commit：`eN · 参数 d1=32（Viewer 写回）`；任何失败都恢复原文件 |
| 5 | 未命名几何的选择器 | 每条边本来就有 ID，`selection.json` 以 `ids` 为准（`lcad context @sel` 读它）；选择器是给人和 Agent 读的辅助文本，**从不 eval**（测试用 AST 白名单解释器验证）。格式沿用 `d.q`：`d.q.lines(view="front").where(length=30, dir="h").near(120, 45).one()`（`near` 用视图模型坐标；圆、圆弧用 `circles` / `arcs` + `r=`）。命名元素直接用 ID；自动编号的边（`E.<v>.<k>`、`E.<v>.<特征>.<k>`）同时给 ID 和选择器 |
| 6 | PR 分组 | ① Viewer：SVG + 服务 + 页面 + 选择 / 检查器 / 桥 + 着色 + 自动刷新 + 状态栏 + 滑块 / 写回（核心：Viewer 桥，评审一轮，重点看安全与写回路径）；② 布局修复（M1 遗留）；③ G5 + HANDOVER |

## 2. 接口

**CLI**：`lcad view [-C 目录] [--port 8765] [--no-open]` → 打印 `{"ok": true, "url": "http://127.0.0.1:8765/"}` 后阻塞服务。`lcad context @sel`：展开为 `selection.json` 里的 ID / 选择器，输出详情、邻近元素、来源位置和一段可粘进临时脚本的代码。构建失败时 `lcad context` 退回上一份 `model.json` 并标 `stale: true`（M1 缺口）。

**安全**：只绑 127.0.0.1；静态文件固定白名单；POST 只收 `application/json`，校验 `Host` 为 `127.0.0.1:<端口>` / `localhost:<端口>`、`Origin`（若有）同源，并要求页面内嵌的每次启动随机令牌头 `X-LCAD-Token`。所有构建、写回共用一把锁（`redirect_stdout` 非线程安全）。首个构建失败时 `/svg` 返回 503，页面只显示错误；之后失败保留上一版。文件变化以 `(mtime_ns, size)` + `git rev-parse HEAD` 判断，构建失败的同一版本再重试一次（防止读到写了一半的文件）。selection / snapshot 原子写（临时文件 + replace，Windows 上遇占用重试）；`/api/view` 由页面防抖。写回或外部提交后预览值清空。

**HTTP**（JSON，除 `/` 和 `/svg`）：

| 路由 | 说明 |
|---|---|
| `GET /` | 静态页（`linercad/viewer/index.html` + `viewer.js` + `viewer.css`，无构建步骤） |
| `GET /api/state` | `{version, edit, status, errors, warnings, build_error}`；version 变了页面才取 SVG |
| `GET /svg` | 当前（或预览）SVG |
| `GET /api/model` | 元素摘要：id、kind、label（`Φ30g6`）、view、intent 要点、refs、src、status、issues、selector |
| `GET /api/params` | 参数：name value default min max step unit label group rule |
| `POST /api/select` | `{ids, selectors}` → 写 `.linercad/selection.json`，更新 snapshot |
| `POST /api/preview` | `{values: {d1: 32}}` → 内存重建；违反 rule / 越界 → `{ok:false, error}`；成功返回 `{ok, timing_ms, stale_ops, version}`，SVG 用 `/svg?preview=1` 取 |
| `POST /api/writeback` | `{name, value}` → 改 drawing.py + 提交，返回 lcad 的 JSON |
| `POST /api/view` | `{viewport}` → 写进 snapshot |

**文件**：
```jsonc
// .linercad/selection.json
{"version": "e7", "ids": ["D.d1"], "items": [{"id": "D.d1", "kind": "dim", "label": "Φ25k6", "view": "front",
  "ref": "@D.d1（Φ25k6，主视图）", "selector": null}], "time": "…"}
// .linercad/snapshot.json
{"version": "e7", "commit": "a1b2c3d", "selection": [...], "issues": [{"rule","id","severity","message"}],
 "viewport": [x0, y0, x1, y1], "params": {"d1": 32}, "param_errors": {}, "stale_ops": []}
```

**页面**：三栏（参数 / 画布 / 检查器）+ 状态栏 `e7 · 2 个警告 · "用户原话"`。画布：滚轮缩放、拖动平移、悬停高亮、单击选中整个元素、Ctrl 多选、Esc 清空。着色：`error` 红、`warn` 橙、`accepted` 灰蓝，与 `lcad check` 同源（同一次 `checks.run`）。检查器：意图 / 值 / 公差、引用、来源（`vscode://file/<绝对路径>:<行>` 链接）、检查结果、[复制 @ID]。滑块：拖动防抖 250 ms 后 `/api/preview`（后到的请求覆盖前面未完成的）；失败标红；预览导致失效的日志操作在参数面板下方列出；[写回源码]。

**`lcad context` 回退**：构建失败时返回 `{ok: true, stale: true, build_error, items: [{element}]}`，元素取自上一份 `model.json`，不含邻近元素与代码片段。

**Skill**：`SKILL.md` 增一小节：用户说“这个 / @sel / 我选中的”→ `lcad context @sel`；用户在试的参数值看 `.linercad/snapshot.json` 的 `params`。

## 3. 布局修复（M1 遗留）

- 形位公差框格、粗糙度、基准的引线候选：冲突检测把**引线本身**（不只是框格 / 符号）与已有尺寸线、延伸线、引线的相交计入；候选增加反向与更长引线，先取无冲突者。回归：M1 render-review 第 1、6、11、12 条各一个最小用例（pulley 主视图右侧作综合用例：零 overlap，且引线不穿尺寸线）。
- ISO 档“General tolerances ISO 2768-m”字号与其它技术要求一致（宽字符估算），回归用例。

## 4. 验收 → 测试 / 演示

| BRIEF §3 | 证据 |
|---|---|
| 1 闭环 | G5：干净 clone，`lcad view` 打开轴套、盘盖范例，内置浏览器点选 → selection.json / 复制 @ID → 独立 agent（只给 SKILL.md + 一句话）`lcad context @sel` + `lcad edit` → 页面自动刷新、状态栏编号变化；两族各 ≥ 2 轮，截图与记录进 `evidence/` |
| 2 滑块 | `tests/test_viewer.py`：预览不写文件不提交、违反 rule 返回错误、写回只改一行且恰好一个 commit；G5 记录 p50 / max |
| 3 可点选 | `tests/test_viewer.py`：每个范例 SVG 的 `data-id` 集合 = 有图元的元素集合；固定种子抽 20 条自动编号边，选择器经 AST 白名单解释后 `.one()` 得到同一元素 |
| 4 着色一致 | `tests/test_viewer.py`：`/api/model` 的问题集合与 `commands.check` 逐条一致 |
| 5 依赖 | 不加依赖（`pyproject.toml` 的 dependencies 不变）；前端为三个静态文件 |
| 6 界面评审 | G5：独立多模态 agent 评审截图，写进 HANDOVER |
| 7 | CI、HANDOVER、tag |

## 5. 卡片

| 卡 | 内容 | Goal |
|---|---|---|
| V1 | SVG 输出、选择器、服务、页面、桥、着色、刷新、状态栏、`context @sel`、滑块、写回、SKILL 小节 | `tests/test_viewer.py` 覆盖 §4 第 2–5 项且全绿；`lcad view` 能在浏览器里完成点选、着色、刷新、滑块和写回 |
| V2 | 布局修复 + ISO 字号 | M1 评审第 1、6、11、12 条各有回归用例且零 overlap；评测集仍 30/30 |
| V3 | G5 + HANDOVER | BRIEF §3 全部有证据；HANDOVER 合并，tag 推送 |

## 6. 偏离记录

| 偏离 | 理由 |
|---|---|
| DESIGN §5.1 写“由内存中的 ezdxf 文档渲染 SVG”；M2 由同一份布局图元直接写 SVG | 与 DXF 实体一一对应，ID 映射天然准确；比 drawing add-on 快一个数量级，满足 < 0.5 s |
| SVG 线宽、线型取自标准档 `[lines]` / `[linetypes]`；不应用 `d.raw` 的颜色覆盖 | 只为点选与预览；DXF 仍是成果 |
| 浏览器交互不做自动化测试 | BRIEF §3 允许：用 G5 实测与截图证明，不引入 Playwright |
