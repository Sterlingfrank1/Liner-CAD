# M2 HANDOVER：Viewer v0

> SPEC：`docs/milestones/M2/SPEC.md`；证据：`docs/milestones/M2/evidence/`。

## 1. 交付

| PR | 卡 | 内容 |
|---|---|---|
| #46 | SPEC | 详细设计（G1 独立评审一轮：3 个 blocker 与若干 should-fix 已处理）；参数覆盖的 contextvar 与 `build(dxf=)` 随此 PR 进了 main |
| #50 | V1 | `lcad view`：由布局图元直接写的带 `data-id` SVG、`d.q` 选择器（AST 白名单解释，从不 eval）、标准库服务（127.0.0.1、每次启动随机令牌、Host / Origin / JSON 校验、静态白名单、独占端口）、轮询自动刷新、selection.json / snapshot.json、`lcad context @sel`（构建失败时回退上一份 model.json）、问题着色、检查器（@ID 复制、IDE 链接）、状态栏、参数滑块内存预览、写回源码；SKILL 一小节。G4 独立评审一轮，2 个 should-fix 与 nit 已修 |
| #51 | V2 | PMI 引线穿越其它标注计为次要代价（有干净路径就走）；中英文混排技术要求统一字高度量（ISO 2768 一条） |
| #52 | V3 | G5 实测发现的两处：引线式尺寸 `place` 重放失败；`lcad edit` 认图纸目录相对路径 |
| 本 PR | V3 | 界面评审后的小改（公差可读、状态着色、选中光晕）；G5 证据与本交接 |

测试：干净 clone 848 个全部通过，ruff 通过，评测 30 / 30（几何对照 1.0）。无新增依赖，前端三个静态文件、无构建步骤。

## 2. 怎么验证

```bash
git clone https://github.com/Sterlingfrank1/Liner-CAD && cd Liner-CAD && uv sync
uv run lcad init /tmp/p --from flange
uv run lcad -C /tmp/p view                 # 打开 http://127.0.0.1:8765/ ：点选、拖滑块、[写回源码]
uv run lcad -C /tmp/p context @sel         # 另一个终端：Agent 读用户的选择
uv run pytest -q tests/test_viewer.py tests/test_layout_m2.py
```

## 3. 验收（BRIEF §3）与证据

| 项 | 结果 | 证据 |
|---|---|---|
| 1 闭环 | 干净 clone，内置浏览器真实点选 → selection.json / @ID → 独立 agent（只拿 `lcad skill` + 一句话）`context @sel` + `edit` / `build` → Viewer 自动刷新、状态栏编号变化。轴套 3 轮、盘盖 2 轮 + 1 次滑块写回；其中一轮暴露 harness 缺陷，已修（#52）后重做成功 | `evidence/g5-loop.md`、`shaft-r*.png`、`flange-r*.png` |
| 2 滑块 | 服务端重建 + 检查 + SVG：p50 32–103 ms，max 182 ms（四个范例各 30 次）；违反 rule 不应用、滑块标红并给出原因；写回只改该 `Param` 一行、检查通过、恰好一个 commit（`e3 · 参数 L=49（Viewer 写回）`） | `evidence/clean-clone.md`、`slider-timing.json`、`flange-slider-*.{png,jpg}`；`tests/test_viewer.py` |
| 3 可点选 | 每个范例 SVG 的 `data-id` 集合 = 有图元的元素集合；固定种子抽样的自动编号边，选择器解释后 `.one()` 得到同一元素 | `tests/test_viewer.py` |
| 4 着色一致 | Viewer 问题集合与 `lcad check` 逐条一致（含 error 级） | `tests/test_viewer.py` |
| 5 依赖 | `pyproject.toml` 依赖不变；页面为 html / js / css 三个静态文件 | — |
| 6 界面评审 | 独立多模态 agent 评分：布局 3、选中与着色 3、检查器 3、参数面板 4、状态栏 3、整体 3；指出的 10 条中，公差原样 JSON、状态无颜色、选中不显眼已改（`flange-after-ui-fixes.png`），其余列入 §5 | `evidence/ui-review.md` |
| 7 | CI 绿、本 HANDOVER、tag `v0.1-m2` | — |

## 4. 已知缺口

- 界面：初始视图不按内容放大；滑块无刻度、违规时仍显示行内[写回源码]（服务端会拒绝）；预览态只在状态栏标示，画布不区分；状态栏长原话被截断（悬停可看全文）。
- 布局：嵌套在外径尺寸内侧的内孔、以及范例脚本固定了 `at` 的 PMI，引线仍会穿过尺寸线（基线见 `tests/test_layout_m2.py`）；引线穿越不报检查。
- Skill：均布孔个数在 `holes_on_circle(n=)` 与尺寸前缀两处；`tol_show="both"` 的打印形式未写；没有“只预览不提交”的布局试探。
- 写回与另一个进程的 `lcad edit` 同时进行时，可能把对方刚写的日志行带进“参数”提交（窗口很窄，未加 git 级锁）。
- 内置浏览器面板截图偶发超时 / 裁切，证据截图用 `zoom` 全页捕获。

## 5. 偏离与决定

见 SPEC §6。另：SVG 不应用 `d.raw` 的颜色覆盖；预览走与 `lcad build` 相同的完整构建路径（实测足够快），以保证着色与 `lcad check` 一致。

## 6. 待用户人工评审

- Viewer 交互手感：点选容差、缩放平移、滑块防抖（`evidence/*.png`，最好亲自 `lcad view` 试一次）。
- 界面评审余下的 7 条（`evidence/ui-review.md`）是否需要在 M3 前处理。
- 局部服务的安全设计（令牌 + Host / Origin 校验 + 只绑 127.0.0.1）是否满足你的使用环境。

## 7. 给 M3 的说明

- 版本列表与视觉 diff 可直接复用 `svgout.svg()`：对两个版本各重建一次，按 `data-id` 对比意图与布局。
- `Viewer` 的构建锁与版本号机制可承载 `lcad diff` 的预览；3D 来源接入后，SVG 仍由同一份布局图元输出。
- 评测：`evals/run.py --drawings` 仍是批量指标入口；Viewer 的点选 → @sel 流程可作为跨 Agent 评测的一种输入方式。
