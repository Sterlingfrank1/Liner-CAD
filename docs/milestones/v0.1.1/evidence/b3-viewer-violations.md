# B3 Viewer：违规元素画布标红 + 检查器四字段（证据）

卡 B3（issue #96，W3 核心卡）· 2026-11-21 · 依赖 E1（finding 的 clause / measured / expected / candidates）

## 1. 验收场景（lead 2026-11-21 裁定；随 main 演进重钉：D1、D2）

v0.1.0 review 第 3 条的复现写作「flange 把 dh 拖到违规值」，但 **E1 后的 dh 场景不可复现**：flange 的参数规则只挂在 Dh / d0 / L / pcd 上，dh 无规则；dh∈[6, 20] 内 `Dh < pcd − dh` 与 `pcd + dh < D` 恒成立，预览既不报 ParamError 也不产生任何 check finding（实测扫过 dh=6..20 全部 0.5 步长，并把其它参数推到极值核对规则语义）。lead 裁定改用真实可触发的预览违规。

**场景随 main 演进两次重钉**：B3 分支最初按 c20c8b7 的布局写「D=140 → overlap / G.pos」，D1（#117，放射状直径引线与布局）合入后 flange 的布局变了，D=140 不再产生 finding；按 main（ee5b1f6）实测重钉为 D=150 → `overlap / S.A`。D2（#84，多层尺寸避让）合入后布局再次变化，**当前 main 的触发值是 D=200**（`tests/test_viewer.py` 的 `PREVIEW_VIOLATION = {"D": 200}`）：

- **flange 把 D 拖到 200** → 预览产生 `overlap / S.A`（warn，E1 四字段齐全）→ 画布上 S.A（剖切符号 A）标红 → 拖回默认值 / 撤回预览后消失。
- dh 场景在 E1 后不可复现这件事，lead 记入台账，由 F1 的 docs PR 补偏离记录。
- 测试把触发值收在一个常量（`PREVIEW_VIOLATION = {"D": 200}` / `PREVIEW_VIOLATION_ID = "S.A"`），断言语义（违规 finding 四字段齐全、ID 是画布元素、撤回后消失）；以后 main 的布局再动只需改这一行。

## 2. 复现步骤（临时目录图纸仓库，产物不入库）

```powershell
uv run lcad init <临时目录>\flange --from flange
uv run lcad -C <临时目录>\flange view --port 0 --no-open   # 打开输出的 url
```

浏览器里：

1. 参数栏把「外径 D」滑到 **200**（预览态，画布左上角显示「预览中（未写回）」）。
2. 画布上剖切符号 S.A 变**红**（`g.st-violation`，`rgb(214, 39, 40)`）；检查器顶部「预览违规（1）」列出 `overlap S.A`，并**始终**显示条款 / 实测 / 要求 / 候选四个字段（空容器显示「无」，本例如候选为「无」）；点该行下面的 `S.A` 选中元素，元素详情里同样有这四个字段（见截图 1）。
3. 把 D 拖回 120（或点「撤回预览」/ 按 Esc）→ 红标与「预览违规」消失、画布恢复；此时 `snapshot.json` 的 `issues` 也回到空（见截图 2）。

截图（本目录，小图，同一缩放区域）：
- `b3-preview-violation.jpg`：**B3 合并时的历史截图（D=150）**，示意 S.A 标红 + 检查器四字段（选中态仍保持红色，CSS 让违规色优先于选中色）；当前 main 的触发值已改为 D=200，见上面的当前步骤。
- `b3-released.jpg`：拖回默认后，红标与预览违规消失、元素状态恢复为 ok。

## 3. 接口与文件字段

- `POST /api/preview` 成功时新增 `findings`：每条 finding 带 `rule / id / severity / message / clause / measured / expected / candidates / pack / std`；预览成功还带 `resolved`（finding id 不是可画元素时映射到的元素）、`unplaced`（没有可画目标的 finding）与 `element_issues`（选中目标元素时检查器用的数据）。
- 参数规则失败时返回 `affected`（covers 该参数的元素 ID），错误对象只用 ParamError 实有的 `message / values / hint / candidates`，不造 clause / measured / expected。
- `GET /api/state` 带 `preview` / `preview_seq` / `param_errors`：页面 reload 后客户端用 `preview_seq` 作拖动基线；失败预览的标红与面板保持到下一次用户动作。
- `GET /api/model` 的 `issues`（全局与每元素）、`resolved` / `unplaced` 带同样字段；页面 reload 且服务端预览仍在时，用 model 复原红色标记、检查器与预览参数值。
- `.linercad/snapshot.json` 的 `issues` 带同样字段（预览时是预览 build 的 findings，撤回后回到当前 build 的 findings）。下面是 B3 合并时（D=150）的实测示例，字段结构不随触发值变化（当前触发值见上面的 D=200 步骤）：

```json
{"rule": "overlap", "id": "S.A", "severity": "warn", "message": "S.A 的文字与 T.frame 重叠",
 "clause": "GB/T 4458.4-2003：尺寸线、尺寸数字不得与其他图线或文字相交",
 "measured": {"overlap": 7.686, "with": ["T.frame"]}, "expected": {"overlap": 0.0},
 "candidates": [], "pack": "layout", "std": "GB/T 4458.4-2003"}
```

## 4. 代码改动

- `src/linercad/viewer/__init__.py`：`FINDING_KEYS` / `_finding()`；`model()`、`_write_snapshot()`、`do_preview()` 输出 E1 字段；预览成功返回 `findings` / `resolved` / `unplaced` / `element_issues`；参数规则失败返回 `affected` 与 ParamError 原有字段；`state()` 暴露 `preview_seq` 与 `param_errors`；撤回预览先于 seq 判重并递增服务端 preview_seq（页面 reload 后旧的 seq 也能撤回、在途旧预览不能把红色写回），同时清空 snapshot.json 的 `param_errors`；`refresh()` 重建时同步清 `param_errors`。
- `viewer/viewer.js`：`applyFindings()` 消费 findings / element_issues → 每个元素的 issues + `previewIds`，保存并还原被预览覆盖的元素 `status`，即时重绘检查器；`colour()` 给违规元素加 `st-violation`（红，优先于选中 / hover 色）；检查器「预览违规」「未定位违规」面板与四字段（条款 / 实测 / 要求 / 候选，空容器显示「无」）、ParamError 面板（值 / 提示 / 候选）；拖动一开始就置 previewActive；轮询采用服务端 `preview_seq` 作基线；失败预览的标红与面板保持到下一次用户动作；页面 reload 且预览仍在时从 model 复原红色标记 / 检查器，并从 `/api/params` 的预览值复原 `S.values`（之后拖别的参数不会静默回退旧预览值）。
- `viewer/viewer.css`：`g.st-violation` 与选中 / hover 组合的红色规则。
- `tests/test_viewer.py`：G2 先失败（5 failed）再实现；新增 12 个测试（preview findings 四字段与 element_issues、model / snapshot 同步、撤回后清空、ParamError affected 且不造字段、view-level finding 映射且检查器可见、未定位参数 finding 进 unplaced 且四字段齐全、撤回后在途旧请求 superseded（含页面 reload 后旧 seq 撤回）、state 的 preview_seq / param_errors、refresh 清 param_errors、参数接口返回预览值、viewer.js / css 消费、HTTP 预览接口），并保留原有 issue 颜色与服务守卫测试。
- 未改 `commands.py` / `examples` / 布局 / check 规则。

## 5. 已知限制（记已知不修）

仓库没有 JS 测试运行器；`viewer.js` 的状态机（Esc / 撤回竞态 / reload 复原 / status 还原）由服务端 pytest（seq、param_errors、snapshot、params）+ ego-browser 现场证据承载，不为此引入浏览器测试框架。验收场景依赖当前布局坐标，已收进 `PREVIEW_VIOLATION` 常量并断言语义。

## 6. 验证

- `uv run pytest` 全量通过（数字见 PR 评论）。
- `uv run ruff check` / `uv run ruff format --check` 通过。
- `uv run python evals/run.py --baseline evals/baseline.json --out <临时目录>/report.json`：regressions 空，D 0.972252（2775, 77）与当前基线逐项一致。
- 截图来自 `ego-browser` 实际操作（滑块 set + input 事件、点选元素、滚轮缩放、撤回），临时目录 `%TEMP%\b3-evidence\flange-main`，不入库（本目录只留两张小 jpg）。
