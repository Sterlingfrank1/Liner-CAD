# v0.1.1 HANDOVER

2026-11-23 · 版本 `0.1.1` · 计划 [PLAN](PLAN.md) · 证据 [evidence/](evidence/) · 发布说明 [docs/releases/v0.1.1.md](../../releases/v0.1.1.md)

v0.1.1 把 v0.1.0 的已知缺口与人工评审项收口：评测指标体系（E1–E7）、DXF 导入（C1–C4）、出图与排布（D1–D7）、资源库数据（A1–A4）、Viewer 界面与迭代提速（B1–B7、H1–H4）、文档（F1），最后做版本验收（V1）。tag `v0.1.1` 与 GitHub Release 由 supervisor 复核后在 main 上按 `docs/RELEASING.md` 打（`scripts/release.py`），不在本 PR 内。

## 1. 交付

- `pyproject.toml` 版本 0.1.1（`uv.lock` 同步；CI 使用 `uv sync --locked`）。
- 发布说明 `docs/releases/v0.1.1.md`；本交接。
- G5 独立 Agent（dsh + Codex）多轮修改与出图评审：`evidence/v1-g5-cross-agent.md`。
- 在册 32 张开发卡（§3 表中除 V1 外）全部合并；另有 A1/A3 随 PR #69 提前关闭；逐卡去向见 §3。

## 2. 怎么验证

干净 clone，按顺序：

```bash
git clone https://github.com/Sterlingfrank1/Liner-CAD && cd Liner-CAD
uv sync --extra 3d

uv run pytest -q                                   # 全量（含 3D extra 的 3D / 装配测试）
uv run ruff check
uv run ruff format --check

uv run python evals/run.py --baseline evals/baseline.json   # 40 例分族向量对基线，退化即非零退出
uv run python evals/mutate.py                      # 37 规则 / 39 变异检出与误报
uv run python evals/place_scores.py --eval40       # 五范例 D.place / A.place
uv run python evals/expect_mutation.py             # L2 20 例 expect 变异（可选，写文件）
```

现场 Smoke（临时目录，产物不入库）：

```powershell
uv run lcad init $env:TEMP\flange --from flange; uv run lcad -C $env:TEMP\flange build --no-view
uv run lcad -C $env:TEMP\flange check
uv run lcad -C $env:TEMP\flange render
uv run lcad -C $env:TEMP\flange view --no-open
uv run lcad -C $env:TEMP\flange template list
```

DXF 样例评测的两把尺（样例是用户提供的外部文件，不入库；路径按本机 refs 填）：

```bash
uv run python evals/dxf_import.py "<sample 目录>" --out report.json
uv run python evals/dxf_only.py --sample-dir "<sample 目录>" --m3 tests/data/dxf/sample_part.dxf --out report.md
```

## 3. 33 卡清单与去向

| 卡 | issue | PR | 流 | 内容与去向 |
|---|---|---|---|---|
| E1 | #73 | #115 | W1 | finding 补 clause / measured / expected / candidates 与机会数；评测分族向量 + baseline 门禁。已合并。 |
| E5 | #74 | #119 | W1 | D.place / A.place 排布指标（11 条子规则）。已合并；数字见 `evidence/placement-scores.md`。 |
| E2 | #75 | #121 | W1 | catalog.toml 规则目录 + 变异框架 + place_leader_cross。已合并；`evidence/mutation-report.md`。 |
| E3 | #81 | #138 | W1 | `linercad/expect.py` + L2 20 例 expect。已合并；`evidence/expect-scores.md`。 |
| E4 | #82 | #140 | W1 | T.syntax / T.target / T.hier 读 `res/gtol.toml`；GB/T 1182 表 1 覆盖 19/19。已合并；`evidence/gtol-coverage.md`。 |
| E6 | #80 | #135 | W1 | 仅 DXF 模式指标（5 条可判规则 + 不可判表）。已合并；`evidence/dxf-only-metrics.md`。 |
| E7 | #108 | #143 | W1 | 迭代速度 P 指标（fresh / conversation 两口径）。已合并；dsh conversation 402 缺测，见 §6；`evidence/e7-iteration-metrics.md`。 |
| C1 | #76 | #123 | W1 | DXF 导入评测指标 + 4 样例基线。已合并；`evidence/dxf-import.md`。 |
| C2 | #77 | #125 | W1 | TEXT / MTEXT → 普通文字元素（as_text 0/67 → 67/67）。已合并。 |
| C3 | #78 | #128 | W1 | HATCH → 剖面线元素（4/4）。已合并。 |
| C4 | #79 | #132 | W1 | 源图框 / 标题栏吸收，single_frame_ok 1.0（偏离记录 15）。已合并。 |
| D1 | #83 | #117 | W2 | 放射引线 24 方向候选与代价函数（偏离记录 14）。已合并；`evidence/d1-radial-leaders.md`。 |
| D2 | #84 | #127 | W2 | 多层尺寸避让；D 族 0.965724 → 0.986572（97→38 违规）。已合并；`evidence/d2-multi-layer.md`。 |
| D3 | #85 | #136 | W2 | 装配序号顺序 / 对齐 / 间距 / 交叉；L3 A.place 1.0（0/116）（偏离记录 16）。已合并；`evidence/d3-balloon-sequences.md`。 |
| D5 | #86 | #139 | W2 | 明细栏合并相同零件 + 长文字换行；vise 10→8 行。已合并；`evidence/d5-parts-list.md`。 |
| D4 | #87 | #141 | W2 | 3D 投影边拓扑稳定命名；假 diff 19→0。已合并；`evidence/d4-topo-stable-edges.md`。 |
| D6 | #88 | #142 | W2 | 装配螺纹啮合画法（GB/T 4459.1 通行画法；条款号 pending）。已合并；`evidence/d6-thread-meshing.md`。 |
| D7 | #89 | #144 | W2 | 3D / 装配视图局部放大 + 源语义回溯。已合并；`evidence/d7-detail-views.md`。 |
| A2 | #92 | #116 | W3 | GB/T 145 R / C 型中心孔数据、画法与代号。已合并；`[meta].pending` 保留待核项。 |
| A4 | #93 | #118 | W3 | GB/T 1182 / 17851 / 17852 抽取 → `res/gtol.toml` + 基准字母核对。已合并；`evidence/gtol-clauses.md`。 |
| B1 | #94 | #122 | W3 | 滑块 min / max 与刻度。已合并；`evidence/b1-b6-viewer-ui.md`。 |
| B2 | #95 | #122 | W3 | 检查器空态用法 + 图纸摘要。已合并（H4 的 Claude Code 提示钩子拆分项按用户决定转 v0.2，见 PLAN 偏离 9）。 |
| B3 | #96 | #120 | W3 | 画布违规标红 + 检查器 E1 四字段（偏离记录 13）。已合并；`evidence/b3-viewer-violations.md`。 |
| B4 | #97 | #122 | W3 | 预览态画布标示“预览（未写回）”。已合并。 |
| B5 | #98 | #122 | W3 | 状态栏可读性（字号 / 展开原话 / 计数着色）。已合并。 |
| B6 | #99 | #122 | W3 | 版本列表展开 / 滚动持久化。已合并。 |
| B7 | #100 | #124 | W3 | 整视图平移归并为视图对比一条（56 → 0 layout_changed）。已合并；`evidence/b7-view-moves.md`。 |
| H1 | #104 | #134 | W3 | `lcad edit --dry-run`（四项不变 + dry/real 一致 + 失败同构）。已合并；3 条 minor 见 §6。 |
| H2 | #105 | #133 | W3 | `lcad template save / list` + `init --from --set`；牛鼻刀 5.92 s → 2.21 s。已合并；`evidence/h2-template-save.md`。 |
| H3 | #106 | #126 | W3 | 首次出图自动打开 Viewer（后台、复用、空闲自退、开关）。已合并；`evidence/h3-auto-viewer.md`。 |
| H4 | #107 | #129 | W3 | 选择同步到对话（复制引用 + 自然语言指代 + 选择过期如实报告）。已合并；`evidence/h4-selection-sync.md`。 |
| F1 | #101 | #137 | W3 | README 跨 Agent 措辞收紧、Skill 同步 v0.1.1、PLAN 偏离 13–16 入 SPEC。已合并。 |
| V1 | #102 | 本 PR | W4 | 版本 0.1.1 + 发布说明 + 本 HANDOVER + G5 证据。 |

- 另有 **A1 #90 / A3 #91**：2026-11-21 随 PR #69 核对后 squash 合并、issue 已关闭（见 PLAN 偏离 8），不计入上表 33 张在册卡。
- 上表 33 行 = milestone v0.1.1 在册卡片（A1/A3 关闭后）。在册 32 张开发卡已合并；A1/A3 另随 PR #69 关闭；V1 为本 PR。

## 4. 验收（G5）与证据

| 项 | 结果 | 证据 |
|---|---|---|
| 干净 clone（`uv sync --extra 3d`）全量回归 | clone HEAD `865c9c1`（V1 文档 PR 之前，2026-11-23）：pytest **1515 passed / 1 skipped（786.7 s）**；ruff check 绿；`--baseline` `regressions: []` exit 0；mutation 39/39 检出、误报 0；place_scores 见下行。V1 的 12 条版本 / 文档测试由 PR CI 覆盖。 | 本文件与发布说明“质量与证据”；`evidence/v1-g5-cross-agent.md` §6 |
| 评测 40 / 40、零 error、几何 / 完整性 1.0、baseline 不退化 | 是：40/40、geometry 35 例 1.0、completeness 5 例 1.0、expect 20/20（198 checks）、`regressions: []` | `evals/baseline.json`、E1 证据 |
| 规则变异 | 37 规则 / 39 变异 / **39 检出（100%）** / 误报 0 / known-debt 38 条精确冻结 | `evidence/mutation-report.md` |
| 排布分数 | flange 1.0（0/45）、pulley 0.9756（2/82）、gear_cover 1.0（0/82）、jack 1.0 / A 1.0（0/30 / 0/25）、vise 0.9583（1/24）/ A 1.0（0/59）；E5 起点见 placement-scores | 最终值：`evidence/d2-multi-layer.md`、`evidence/d5-parts-list.md`；E5 起点：`evidence/placement-scores.md`；`evals/place_scores.py --eval40` |
| DXF 导入 4 样例 | entity 256/325、text 67/67、hatch 4/4、single_frame_ok 4/4、inspect 4/4、edit_round 4/4 | `evidence/dxf-import.md` |
| 仅 DXF 模式 | G 1.0（0/296）、D 0.97619（1/42）、T/A/P 不可判明示 | `evidence/dxf-only-metrics.md` |
| 迭代速度 | fresh 4 场景均值 487.4 s / 108,462 token / 82.5 步；Codex 首图 523.8 s → 修改轮 114.2 s（约 4.6×） | `evidence/e7-iteration-metrics.md` |
| 独立 Agent（dsh + Codex）多轮修改与出图评审 | 第一批：dsh 路一 3 轮（法兰变体 e0→e3、check 0/0、dry-run 预览与最终渲染 SHA256 一致）+ Codex 路 fresh 386.5 s → conversation 86.0 s（约 4.5×、两轮 0/0）。第二批：磨头 PDF 回转体任务 + 多模态是非题清单与 v0.1.0 对比（TBD-V1-G5） | `evidence/v1-g5-cross-agent.md` |
| CI 四项（lint / ubuntu 3.11 / windows 3.13 / test-3d） | TBD-V1-CI（本 PR 的 run） | GitHub Actions |
| 版本号 / 发布说明 / HANDOVER | 0.1.1；两份文档随本 PR 合并 | 本文件、`docs/releases/v0.1.1.md` |

## 5. 偏离记录（PLAN §9 第 13–16 条指针）

F1 已把四条偏离写进 [PLAN §9](PLAN.md)（#137），原文不在此重复，只给指针与证据：

| # | 卡 / issue | 内容 | 证据 |
|---|---|---|---|
| 偏离 13 | B3 / #96 | B3 验收场景随布局演进两次重钉：v0.1.0-review 的“flange dh 拖到违规值”在 E1 后不可复现，改真实可触发场景；D1 后 D=150、D2 后 D=200（`PREVIEW_VIOLATION` 常量）。 | `evidence/b3-viewer-violations.md`（含历史截图标注） |
| 偏离 14 | D1 / #83 | D1 证据机制措辞更正：E5 的 place_dim_cross 也判引线型尺寸线；D1 修的是尺寸界线与中心线交叉（不在 E5 计量内），E5 数字不变是设计使然、不是退化。 | `evidence/d1-radial-leaders.md` |
| 偏离 15 | C4 / #79 | C4 图框策略与 issue 措辞相反：保留新图幅模板图框、把源图框 / 标题栏层普通几何吸收进模板语义；4 样例 single_frame_ok 0.0 → 1.0，局限（未命名层不吸收等）如实记录。 | `evidence/dxf-import.md` |
| 偏离 16 | D3 / #85 | D3 序号顺序口径：issue 的“顺 / 逆时针连续”用直线引线在 vise / bearing 上穷举 2,030,000 个配置 / 94 s 零交叉解，lead 裁定落为“同侧沿旋转方向单调 + 对齐 + 间距 ≥ δ + 交叉 0”（GB/T 4458.2 行 / 列形态）；严格全局连续留 v0.2。 | `evidence/d3-balloon-sequences.md` + `evidence/d3-order-search.py` |

其余偏离（1–12）见 PLAN §9，本版不改。

## 6. 遗留事项与已知缺口

- **折线 / 绕行引线（v0.2）：** D3 的严格全局序号连续需要新的引线形式或改组件锚点，超出本版热点与标准口径，留 v0.2 候选；本版用同侧单调口径（偏离 16）。
- **GB/T 4249-2018 原文：** 未读，`res/catalog.toml` 的 `gtol_hier` 条款状态 `pending`；`res/gtol.toml` 为 `verified = false`（单谱系 PDF 多模态读）。T.hier 的判定依据与未读清单见 `evidence/gtol-clauses.md`。
- **DEEPSEEK_API_KEY 余额：** E7 的 dsh conversation 口径返回 `QUOTA 402 Insufficient Balance`，该格缺测、未伪造；充值后按 `evals/cross_agent.py run --agent dsh --mode conversation` 一条命令补测（细节见 E7 证据 §4）。
- **ci.yml 的 3D job 装配测试清单：** `test-3d` 目前只跑 `tests/test_hlr.py` + `tests/test_evals.py`；装配 / 3D 集成测试（`test_assembly.py`、`test_views_detail3d.py`、`test_source3d_stable.py` 等）未纳入，改 `ci.yml` 需要带 workflow scope 的 token（本版 workflow scope 不可用）。补偿：非 3D 单元测试 `test_bom_merge_unit.py` / `test_bom_wrap.py` / `test_source3d_naming_unit.py` / `test_detail_semantics.py` 已进普通 job。
- **数据待核（`verified = false` 与 `pending`）：** `res/center_holes.toml` 的 C 型 M24 t = 8.0 与锥面几何不符（两来源均如此，照录）、B 型 D2 / l_min 单一谱系、R/C 型 ISO 2541 / DIN 332-2 原文未读；`res/gtol.toml` 未读条款见 `[meta].unread`。需要时请用户提供原文。
- **其他 v0.2 项：** 标题栏 GB/T 10609.1 图 2 与 GB/T 14692 投影符号原文对照；GB/T 1095-2003 松联结 H9/D10、36×20 以上行、(d−t1)/(d+t2) 符号约定；ISO 5459 原文；Viewer 令牌加固（共享主机）；大样本评测验证跨 Agent 定位；STEP AP242 语义 PMI。
- **本版已知 minor：** D4 拓扑键依赖 OCC 遍历序（增删特征换 ID，旧 ID 有候选）；C4 只识别白名单图框 / 标题栏层；B 系列前端无 JS 测试运行器（服务端接口 + 浏览器证据）；H1 三条 minor（预览按 edit_id 命名的覆盖语义、OSError 报错形状、断言强度）；E6 30+ 条 intent 依赖规则“不可判”明示；D6 GB/T 4459.1 条款号 `pending`；D2 残余 38 条 known-debt（写死布局 / 缺中心线，见发布说明“已知缺口”）。

## 7. 评测基线与门禁运行方式

- `evals/baseline.json`：40 例（L1 20 + L2 20）的分族向量基线；字段 `families`（G / D / T / A 的 score / opportunities / violations）+ `errors` / `zero_error_rate` / `geometry_pass_rate` / `completeness_pass_rate` / `expect`。`uv run python evals/run.py --baseline evals/baseline.json` 对比当前树；任一族分数下降、机会数减少或 error 增加 → 非零退出。**新增指标进基线必须在 PR 写明是“新增”**（本版 E3 / E4 / E5 均按此说明）。
- `evals/known-debt.json`：E5 排布规则在参考图上的已知违规签名（38 条 / 12 图）精确冻结；变异框架把已知债务算真阳性，新增债务即红。
- `evals/mutate.py`：37 条规则 / 39 个变异，输出检出率、误报率、跳过与 known-debt 精确性；`--mutation` 对算子崩溃 / 无基座 fail-closed。
- `evals/place_scores.py --eval40`：五范例的 D.place / A.place 分数（不是 baseline 的一部分，只做 D 流尺子与回归观察）。
- `evals/expect_mutation.py`：L2 20 例 expect 的变异检出（43/43）。
- `evals/gtol_coverage.py`：GB/T 1182 表 1 行覆盖与 clause 状态。
- `evals/dxf_import.py` / `evals/dxf_only.py`：两把 DXF 尺（导入器产物 vs 任意 DXF 图元），样例目录外部传入、不入库。
- E7 的 P 指标独立于绘图向量（`cross_agent.py` 输出 report），不进 `baseline.json`；两种口径命令见 `evidence/e7-iteration-metrics.md`。
- 更新基线：`uv run python evals/run.py --save-baseline evals/baseline.json`（会拒绝不干净工作树 / 部分运行）；更新后在 PR 正文说明新增项。

## 8. 待用户人工评审

- **出图质量（V1 重评）：** G5 出图评审数字见 `evidence/v1-g5-cross-agent.md`（与 v0.1.0 的 2–3 / 5 对比）；是否接受当前尺寸 / 序号布局水平、是否把剩余布局项作为 v0.2 第一优先。
- **跨 Agent 定位：** 出图观感与裸 ezdxf 相当、优势在检查 / 语义 / 版本、首图速度取决于 Agent；v0.1.1 复测用 dsh + Codex（每格 n 小，仍属初步结论）。是否接受该定位。
- **数据来源：** `res/gtol.toml` 与 `res/center_holes.toml` 的 `verified = false` 项与 `pending` 清单是否接受现状，或提供标准原文。
- **D6 画法：** 旋合段按外螺纹、内螺纹剖面线画到大径（牙底），评审建议画到小径未采纳并写明依据；请确认。
- **CI 3D job：** 是否授权用带 workflow scope 的 token 把装配 / 3D 集成测试加入 `test-3d`。
- **标题栏 / 投影符号、Viewer 界面余项、本地服务安全**：仍按 v0.2 清单跟踪，是否需要提前。

## 9. 给下一步（v0.2）

- **STEP AP242 语义 PMI：** 尺寸 / 公差 / 基准 / 形位公差 / 粗糙度已保持语义字段（`res/gtol.toml` 的 clause / 被测要素 / 公差带），`src3d` / `src3d_refs` 与 D4 的拓扑命名是映射到模型拓扑的入口。
- **布局：** 剩余 38 条 known-debt 集中在写死 `inside` 的尺寸线与缺中心线的测量点；折线 / 绕行引线、序号严格全局连续是候选方向。入口仍是 `layout.py` 候选生成 + 代价函数（DESIGN §4.6）。
- **评测：** `baseline.json` + `known-debt.json` + 变异框架使新增规则可直接量化；大样本评测（v0.1.1 每格 n 小）用同一门禁。
- **数据：** 按 `[meta].pending` 逐项补原文核对；GB/T 1095 / ISO 5459 / GB/T 10609.1 / GB/T 14692 原文到位后可提前做。
