# B3 Viewer：违规元素画布标红 + 检查器四字段（证据）

卡 B3（issue #96，W3 核心卡）· 2026-11-21 · 依赖 E1（finding 的 clause / measured / expected / candidates）

## 1. 验收场景（lead 2026-11-21 裁定）

v0.1.0 review 第 3 条的复现写作「flange 把 dh 拖到违规值」，但 **当前 main（含 E1）的 dh 场景不可复现**：flange 的参数规则只挂在 Dh / d0 / L / pcd 上，dh 无规则；在 dh∈[6, 20] 内 `Dh < pcd − dh`（60 < 70…84）与 `pcd + dh < D`（96…110 < 120）恒成立，预览既不报 ParamError 也不产生任何 check finding（实测扫过 dh=6..20 全部 0.5 步长，并把其它参数推到极值核对过规则语义）。lead 裁定改用**真实可触发的预览违规**：

- **flange 把 D 拖到 140** → 预览产生 `overlap / G.pos`（warn，E1 四字段齐全）→ 画布上 G.pos 标红 → 拖回默认值 / 撤回预览后消失。
- dh 场景在 E1 后不可复现这件事，lead 记入台账，由 F1 的 docs PR 补偏离记录；V1 重拍 B 卡截图时与 D1 / D2 一起复核（PLAN §2 的截图重拍约定）。

## 2. 复现步骤（临时目录图纸仓库，产物不入库）

```powershell
uv run lcad init <临时目录>\flange --from flange
uv run lcad -C <临时目录>\flange view --port 0 --no-open   # 打开输出的 url
```

浏览器里：

1. 参数栏把「外径 D」滑到 **140**（预览态，画布左上角显示「预览中（未写回）」）。
2. 画布上左视图的 G.pos 形位公差框格变**红**（`g.st-violation`，`rgb(214, 39, 40)`）；检查器顶部「预览违规（1）」列出 `overlap G.pos`，并**始终**显示条款 / 实测 / 要求 / 候选四个字段（空容器显示「无」，本例如候选为「无」）；点该行下面的 `G.pos` 可选中元素，元素详情里同样有这四个字段（见截图 1）。
3. 把 D 拖回 120（或点「撤回预览」）→ 红框与「预览违规」消失、画布恢复；此时 `snapshot.json` 的 `issues` 也回到空（见截图 2）。

截图（本目录，小图）：
- `b3-preview-violation.jpg`：D=140 预览，G.pos 红框 + 检查器四字段（选中态仍保持红色，CSS 让违规色优先于选中色）。
- `b3-released.jpg`：拖回默认后，红框与预览违规消失。

## 3. 接口与文件字段

- `POST /api/preview` 成功时新增 `findings`：每条 finding 带 `rule / id / severity / message / clause / measured / expected / candidates / pack / std`；参数规则失败时返回 `affected`（covers 该参数的元素 ID），错误对象只用 ParamError 实有的 `message / values / hint / candidates`，不造 clause / measured / expected。
- `GET /api/model` 的 `issues`（全局）与每个元素的 `issues` 带同样字段；页面 reload 且服务端预览仍在时，用 model 的 issues 复原红色标记与检查器。
- `.linercad/snapshot.json` 的 `issues` 带同样字段（预览时是预览 build 的 findings，撤回后回到当前 build 的 findings）。实测预览 D=140 时：

```json
{"rule": "overlap", "id": "G.pos", "severity": "warn", "message": "G.pos 的文字与 D.pcd 重叠",
 "clause": "GB/T 4458.4-2003：尺寸线、尺寸数字不得与其他图线或文字相交",
 "measured": {"overlap": 2.536, "with": ["D.pcd"]}, "expected": {"overlap": 0.0},
 "candidates": [], "pack": "layout", "std": "GB/T 4458.4-2003"}
```

## 4. 代码改动

- `src/linercad/viewer/__init__.py`：`FINDING_KEYS` / `_finding()`；`model()`、`_write_snapshot()`、`do_preview()` 输出 E1 字段；预览成功返回 `findings` 与 `resolved`（finding id 本身不是可画元素时映射到的元素，如 `V.top` → 该视图的元素）；参数规则失败返回 `affected` 与 ParamError 原有字段（次要路径，不改 E1 字段语义）；撤回预览同时清空 snapshot.json 的 `param_errors`。
- `viewer/viewer.js`：`applyFindings()` 消费 preview 的 findings → 每个元素的 issues + `previewIds`；`colour()` 给违规元素加 `st-violation`（红色，优先于选中 / hover 色）；检查器新增「预览违规」面板与四字段（条款 / 实测 / 要求 / 候选，空容器显示「无」）、ParamError 面板（值 / 提示 / 候选）；页面 reload 且预览仍在时从 model 复原（含 `resolved`）；预览结束 / Esc / 撤回预览清空并重绘。
- `viewer/viewer.css`：`g.st-violation` 与选中 / hover 组合的红色规则。
- `tests/test_viewer.py`：G2 先失败（5 failed）再实现；新增 7 个测试（preview findings 四字段、model / snapshot 同步、撤回后清空、ParamError affected 且不造字段、view-level finding 映射到视图元素、viewer.js / css 消费、HTTP 预览接口），并保留原有 issue 颜色与服务守卫测试。
- 未改 `commands.py` / `examples/` / check 规则。

## 5. 验证

- `uv run pytest` 全量通过（最终数字见 PR）。
- `uv run ruff check` / `uv run ruff format --check` 通过。
- `uv run python evals/run.py --baseline evals/baseline.json --out <临时目录>/report.json`：regressions 空（A4/E1 后的基线，最终数字见 PR）。
- 截图来自 `ego-browser` 实际操作（滑块 set + input 事件、点选元素、撤回），临时目录 `%TEMP%\b3-evidence\flange`，不入库（本目录只留两张小 jpg）。
