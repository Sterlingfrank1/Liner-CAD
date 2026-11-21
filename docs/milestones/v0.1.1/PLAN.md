# v0.1.1 计划

2026-11-14 · supervisor 会话“Liner-CAD v0.1.1开发”（Opus 5.5 / xhigh，只规划、派活、核验、验收；用户 2026-11-14 将 effort 由 high 调为 xhigh）· GitHub milestone `v0.1.1`（#5）· 卡片 issue #73–#102、#104–#108

> **2026-11-20 更新**（续跑 2026-11-14 被中断的 supervisor 计划更新回合）：H1（#104，`lcad edit --dry-run`）入卡片表并入 W3 顺序；2026-11-13 用户试用后的“三项”（commit 49d8759：首次出图自动打开 Viewer、选择同步到对话、迭代提速）拆为 H2（#105）、H3（#106）、H4（#107）、E7（#108）并入；U1 / U2 / U3 / U5 按用户 2026-11-14 六条决定收口。

> **2026-11-21 更新**（用户指示）：v0.1.1 的跨 Agent 验证改用 DeepSeek Harness（dsh）与 Codex，豆包工作不再使用；E7、F1、V1 的口径按二者更新（见偏离记录 7）。PR #69（GB/T 3 / GB/T 6403.5 / B 型中心孔）已按 A1 + A3 核对并 squash 合并，A1、A3 随之关闭（见偏离记录 8）。

## 1. 目标

把 `docs/releases/v0.1.0.md` 的已知缺口与 `docs/releases/v0.1.0-review.md` 的全部“v0.1.1 候选”做完（用户 2026-11-14 决策），守住 `CLAUDE.md` 的四个核心竞争力与 harness 定位，不堵 v0.2（STEP AP242 语义 PMI）。头号优先是出图质量与尺寸排布（D），配套先把评测变成可比较、可信的数字（E1、E5、E2）。

## 2. 覆盖矩阵

逐条对照 `v0.1.0.md`“已知缺口”“待用户人工评审”、`v0.1.0-review.md` 与 M1–M3 HANDOVER 的遗留。

| 来源 | 项 | 归属 | 状态 |
|---|---|---|---|
| 已知缺口·出图 | 放射状直径引线避让 | D1 | v0.1.1 |
| 已知缺口·出图 | 多层尺寸避让（含 M1 遗留：pulley 右侧形位公差 / 粗糙度引线交叉） | D2 | v0.1.1 |
| 已知缺口·出图 | 序号对齐与最小间距 | D3 | v0.1.1 |
| 已知缺口·出图 | 明细栏合并相同零件（M3：文字不换行） | D5 | v0.1.1 |
| 已知缺口·出图 | 装配螺纹啮合画法 | D6 | v0.1.1 |
| 已知缺口·出图 | 3D / 装配视图局部放大 | D7 | v0.1.1 |
| 已知缺口·3D | 投影边按位置编号，diff 乱 | D4 | v0.1.1 |
| 已知缺口·3D | 阶梯剖、旋转剖、移出断面（3D 来源） | **v0.2（用户 2026-11-14 确认 U1）** | review 未提及；现可用 2D 画法补 |
| 已知缺口·DXF 导入 | TEXT 成带引线注释、HATCH 被跳过 | C2、C3 | v0.1.1 |
| 已知缺口·DXF 导入 | 验收只用 ezdxf 样例 → 用户第三方样例 | C1 | v0.1.1 |
| review·DXF | 原图框保留在新图幅里 | C4 | v0.1.1 |
| 已知缺口·跨 Agent | Codex 未运行 | 已关闭（#70 dsh）；v0.1.1 复测改为 dsh + Codex | — |
| review·跨 Agent | 措辞收紧为“首图速度取决于 Agent” | F1 | v0.1.1 |
| 已知缺口·资源库 | 缺 GB/T 3、6403.5、B 型中心孔 | PR #69 + A1、A3 | v0.1.1 |
| 用户 2026-11-14 | GB/T 145 R 型、C 型中心孔 | A2 | v0.1.1 |
| 用户 2026-11-14 | GB/T 1182 / 17851 / 17852 → 基准字母核对与 gtol 数据 | A4 → E4 | v0.1.1 |
| 待评审·出图质量 | 尺寸布局为第一优先 | D 流 + E5 | v0.1.1 |
| 待评审·标题栏 / 投影符号 | 接受并标注；原文对照 | v0.2（用户已定） | — |
| 待评审·资源库来源 | 基准字母（GB 已关闭）、键槽深度（已关闭） | 已关闭 | — |
| review 遗留 | GB/T 1095 松联结 H9/D10、36×20 以上行、(d−t1)/(d+t2) 符号约定 | v0.2（用户已定，资料到位可提前） | — |
| review 遗留 | ISO 5459 原文（ISO 档基准字母 `verified=false`） | v0.2（用户已定） | — |
| 待评审·Viewer | 交互手感 | 已通过 | — |
| 待评审·Viewer | 界面 6 项 | B1–B6 | v0.1.1 |
| M3 HANDOVER | `layout_changed` 在整视图移动时过长 | B7 | v0.1.1 |
| 待评审·Viewer | 本地服务安全：本机单用户已写进文档；令牌加固 | v0.2（用户已定） | — |
| review·Viewer × 指标 | 画布标红消费 finding 元素 ID，检查器显示 clause / measured / expected / candidates | B3（依赖 E1） | v0.1.1 |
| 待评审·第三方 DXF | 用户样例已到位（4 DXF + 3 PDF） | C1–C4；磨头 PDF 用于 V1 | v0.1.1 |
| 用户 2026-11-10 | 评测指标方案 §8 六步 | E1、E2、E3、E4、E5、E6 | v0.1.1 |
| 用户 2026-11-13 试用 | 首次出图自动打开 Viewer（后台常驻、空闲自退） | H3（#106） | v0.1.1 |
| 用户 2026-11-13 试用 | Viewer 选择同步到对话（点选复制引用 + 自然语言指代；B2 钩子 2026-11-21 转 v0.2） | H4（#107） | v0.1.1 |
| 用户 2026-11-13 试用 | 迭代提速：`lcad template save` 沉淀参数化模板 | H2（#105） | v0.1.1 |
| 用户 2026-11-13 试用 | 迭代提速：`lcad edit --dry-run` 试改不提交 | H1（#104） | v0.1.1 |
| 用户 2026-11-13 试用 | 迭代速度并入评测指标（P 过程，两种口径） | E7（#108） | v0.1.1 |
| M3 HANDOVER | 没有“试改不提交”（`lcad edit --dry-run`） | **v0.2 候选（待用户确认 U2）** | v0.1.0.md 未列 |
| 已知缺口·出图 | 新范例与装配图出图评审 2–3 分 | D 流；V1 出图评审对比 v0.1.0 | v0.1.1 |

**Viewer 结论：** 已覆盖。界面 6 项 → B1–B6，`layout_changed` → B7，安全加固 → v0.2。依赖：B3 依赖 E1 的 finding 字段；D 流改变布局后，Viewer 截图证据以合并后的 main 为准（B 卡的截图在 D1、D2 合并后重拍一次，作为 V1 证据）。

## 3. 工作流与顺序

同时运行的开发会话不超过 3 个（W1–W3）；W4 先握手后空闲，等全部卡片合并再做 V1。各流内按顺序做，一张卡片一个 PR；热点文件只在一个流里写。supervisor 可按进度把未开工的卡片在流之间重排（只用 `send_message`）。

```
W1 指标 + 导入 : E1 → E5 → E2 → C1 → C2 → C3 → C4 → E6 → E3 → E4 → E7
W2 布局       : D1 (合并等 E5) → D2 → D3 → D5 → D4 → D6 → D7
W3 数据 + Viewer: A1+A3(合并 #69) → A2 → A4 → B3(等 E1) → B1/B2/B4/B5/B6 → B7 → H3 → H4 → H2 → H1(默认等 D2 合并，可提前) → F1
W4 验收       : V1（全部卡片合并后）
跨流依赖: E1 → B3；E5 → D1 合并；A4 → E4；B2 → H4（复制引用合并做）；D2 → H1（默认）；C4、D3、E1、H1 → F1
```

热点归属：`rules.py` / `checks.py` / `evals/run.py` / `importdxf.py` → W1；`layout.py` / `annotate.py` / `pmi_layout.py` / `assembly.py` / `views.py` / `source3d.py` / `hlr.py` → W2；`res/` / `viewer/` / `versions.py` / `skill/` → W3。跨流必须动对方热点时，先通知 supervisor 排期。

**PR #69 的归宿（A5）：** 在 `m4/res-gaps` 上继续做 A1、A3，核对完成后合并。理由：#69 的数据多为单一谱系，用户已给 2008 原文，先核对再合并，main 上不留待核对的数据；A2 是新功能，单独一个 PR。

## 4. 卡片

执行档位一律 Sonnet 5.5（`claude-sonnet-5-5`）+ effort `xhigh`。“核心”= 合并前一轮独立评审。完整卡片见 issue。

| ID | issue | 流 | 优先 | 目标 | 依赖 | 文件热点 | 核心 | Goal 条件 |
|---|---|---|---|---|---|---|---|---|
| E1 | #73 | W1 | P0 | finding 补 clause / measured / expected / candidates，规则报告机会数；评测出分族分数向量与基线 | — | rules.py、checks.py、evals/run.py | 是 | 现有全部规则的 finding 都带 clause / measured / expected / candidates 且报告机会数；`evals/run.py` 输出分族向量；evals/baseline.json 入库；--baseline 遇退化非零退出（有测试）；评测 40/40 零 error、几何与完整性对照 1.0 不变；一轮独立评审意见已处理；pytest、ruff（含 format）、CI 四项绿；PR 已 squash 合并。 |
| E5 | #74 | W1 | P0 | D.place / A.place 排布指标（交叉、间距、嵌套、文字方向、重叠） | E1 | 新指标模块（不改 layout.py）、evals/run.py |  | D.place 与 A.place 各子规则有条款、机会数、正反例测试；评测 40 例出排布分数并更新 baseline.json（PR 写明新增项）；给出 flange、pulley、gear_cover、jack、vise 当前排布分数作为 D 流的起点；不改 layout.py；pytest、ruff、CI 绿；PR 已合并。 |
| E2 | #75 | W1 | P1 | 规则目录 catalog.toml + 变异框架：每条规则的检出率与误报率 | E1、E5 | 规则目录、evals 变异脚本、rules.py（只读或小改） | 是 | catalog.toml 覆盖现有全部规则与 D.place 子规则；每条 done 规则有变异算子，检出率 1.0、参考图误报 0（做不到的列为已知问题并开 issue，不削弱规则）；评测输出检出率 / 误报率；一轮独立评审已处理；pytest、ruff、CI 绿；PR 已合并。 |
| C1 | #76 | W1 | P2 | DXF 导入评测方法与指标（用户样例，样例不入库） | E1 | evals/dxf_import.py（新）、tests 用 ezdxf 自造夹具 |  | evals/dxf_import.py 对样例目录输出上述指标的 JSON；4 个样例 DXF 的基线数字写进 docs/milestones/v0.1.1/evidence/dxf-import.md（只放数字和小的衍生图，不放原图）；测试用自造夹具覆盖各指标；pytest、ruff、CI 绿；PR 已合并。 |
| C2 | #77 | W1 | P2 | DXF 导入：TEXT / MTEXT 导成普通文字元素 | C1 | importdxf.py |  | 导入后文字为普通文字元素（无引线），位置 / 字高 / 旋转与原图一致（容差 0.01 mm）；C1 指标中文字保留率较基线提升并记录；改一段导入文字后重建成功；pytest、ruff、CI 绿；PR 已合并。 |
| C3 | #78 | W1 | P2 | DXF 导入：HATCH 导入为剖面线元素 | C2 | importdxf.py |  | 样例中的 HATCH 在导入后保留（C1 填充保留率记录在证据里）；不能表示的情况有明确报告；自造夹具测试覆盖实体填充与图案填充；pytest、ruff、CI 绿；PR 已合并。 |
| C4 | #79 | W1 | P2 | DXF 导入：原图框 / 标题栏不再叠进新图幅 | C3 | importdxf.py、commands.py | 是 | 4 个样例导入后只有一个图框；`lcad inspect` 报告识别到的图框 / 标题栏；改一轮能成；C1 全部指标较基线不退化并写入证据；一轮独立评审（覆盖 C2–C4）已处理；pytest、ruff、CI 绿；PR 已合并。 |
| E6 | #80 | W1 | P2 | 仅 DXF 模式的指标：只靠渲染图元判的规则，用于任意来源图纸 | E5、C4 | 指标模块、evals |  | 对任意 DXF 输出仅 DXF 模式的分数向量（可判规则列表写明）；对 4 个样例 DXF 和 M3 基线图各出一份数字进证据；自造夹具的正反例测试；pytest、ruff、CI 绿；PR 已合并。 |
| E3 | #81 | W1 | P2 | expect.py 约束语义与几何签名匹配；L2 的 20 例写 expect | E2 | linercad 的 expect 模块、evals/L2/*/expect.py |  | L2 的 20 例各有十来行的 expect.py，对参考图全部通过；变异（删一个必需尺寸、改配合）能被抓到；分数进向量、baseline 更新并说明；pytest、ruff、CI 绿；PR 已合并。 |
| E4 | #82 | W1 | P2 | T.syntax / T.target / T.hier：按 GB/T 1182 数据判形位公差 | A4、E2 | rules.py（形位公差部分）、规则目录 |  | 三条规则读 res/gtol.toml、带条款、有正反例与变异算子（检出 1.0、误报 0）；评测报告 GB/T 1182 条款覆盖率；baseline 不退化；pytest、ruff、CI 绿；PR 已合并。 |
| E7 | #108 | W1 | P2 | 迭代速度指标（P 过程）：run_demo.py 并入 evals/cross_agent.py，区分两种口径 | E1 | evals/cross_agent.py |  | 评测输出每轮耗时 / 新处理 token / 模型步数 / lcad 子命令统计；区分“每轮新开调用”与“同一对话连续修改”两种口径；4 个试用场景（dsh + Codex）各出一份数字进证据；自造夹具测试；pytest、ruff、CI 绿；PR 已合并。 |
| D1 | #83 | W2 | P0 | 放射状直径 / 半径引线的候选生成与代价函数 | E5 | layout.py、annotate.py | 是 | flange、end_cover、pulley、gear_cover、bearing_support 的圆视图直径 / 半径引线：E5 中与之相关的可避免交叉为 0，D 族排布分数提升并附前后渲染图；确定性测试（同输入同输出、固定元素不动）；每个修好的情形留回归用例；评测 40/40、几何 1.0、baseline 不退化；一轮独立评审已处理；CI 绿；PR 已合并。 |
| D2 | #84 | W2 | P0 | 多层尺寸避让：排序外推、小内大外、文字内外与箭头外翻、PMI 引线 | D1 | layout.py、pmi_layout.py | 是 | 评测集与范例的 D.place 交叉、间距、嵌套子项较 D1 后的基线明显改善（PR 给出数字）且无回退；pulley 右侧拥挤处无交叉；前后渲染图进证据；确定性与固定元素测试；每个修复留回归用例；40/40、几何 1.0、baseline 不退化；一轮独立评审已处理；CI 绿；PR 已合并。 |
| D3 | #85 | W2 | P1 | 装配序号：对齐、最小间距、顺序、引线不交叉 | D2 | assembly.py、layout.py |  | jack、vise、bearing 三个装配：A.place 序号引线交叉 0、间距 ≥ δ、对齐与顺序子项通过；前后渲染图进证据；回归用例；L3 评测通过、baseline 不退化；CI 绿；PR 已合并。 |
| D5 | #86 | W2 | P1 | 明细栏合并相同零件，文字换行 | D3 | assembly.py |  | 装配评测中相同零件合并为一行、数量正确、序号一一对应；长文字在格内换行不出格；回归用例；L3 通过、baseline 不退化；CI 绿；PR 已合并。 |
| D4 | #87 | W2 | P2 | 3D 投影边按拓扑稳定命名 | D5 | source3d.py、hlr.py |  | gear_cover 改一个尺寸参数后，`lcad diff` 只报实际变化的边（测试断言集合）；同一模型重复投影 ID 不变；旧 ID 引用给出候选；评测 40/40、几何 1.0 不变；CI 绿；PR 已合并。 |
| D6 | #88 | W2 | P2 | 装配螺纹啮合画法（GB/T 4459.1） | D5 | features.py、assembly.py |  | 一个含螺钉旋入螺孔的装配用例按 GB/T 4459.1 出图，在渲染图元上断言啮合段画法；回归用例；L3 通过、baseline 不退化；渲染图进证据；CI 绿；PR 已合并。 |
| D7 | #89 | W2 | P2 | 3D 投影视图与装配视图的局部放大 | D6 | views.py、source3d.py |  | gear_cover 与一个装配视图各出一处局部放大，几何对照对放大区域通过；标注与比例正确；回归用例；评测不退化；渲染图进证据；CI 绿；PR 已合并。 |
| A1 | #90 | W3 | P1 | GB/T 6403.5-2008 逐表核对砂轮越程槽，并合并 PR #69（含 A3） | — | res/grinding_grooves.toml（分支 m4/res-gaps） |  | grinding_grooves.toml 回转面及端面表与 2008 原文逐格一致（逐格比对表作测试 fixture）；[meta] 写来源、读取日期、核对方式、未录入的表；verified 如实；受影响的范例与测试同步；A3 完成后 #69 CI 绿并 squash 合并。 |
| A3 | #91 | W3 | P1 | ISO 2540 附录 A（B 型中心孔）独立核对 | — | res/center_holes.toml [meta]（分支 m4/res-gaps） |  | center_holes.toml 的 B 型 [meta] 写明独立来源及谱系，数值逐格一致或分歧已解决并有测试；或明确记录“未找到独立来源”并登记待用户项、verified=false；不编造数值。 |
| A2 | #92 | W3 | P1 | GB/T 145 R 型、C 型中心孔 | A1 | res/center_holes.toml、res/__init__.py、features.py、skill/pages/api.md |  | R、C 型数据有来源与核对记录，逐格对照测试通过；features 能画 R / C 型并给出代号；临时目录现写一张带 R 型中心孔的轴，`lcad check` 0 error；pytest、ruff、CI 绿；PR 已合并。 |
| A4 | #93 | W3 | P1 | GB/T 1182-2018 / 17851-2010 / 17852-2018 抽取 → res/gtol.toml，核对基准字母 | — | res/gtol.toml（新）、res/datum.toml、res/__init__.py |  | res/gtol.toml 每行带条款号且有读取接口与测试；datum.toml 核对结论写进 [meta]；条文草稿入 docs/milestones/v0.1.1/evidence/gtol-clauses.md；未读到的部分如实记录；pytest、ruff、CI 绿；PR 已合并。 |
| B1 | #94 | W3 | P2 | Viewer：滑块显示 min / max 与刻度 | — | viewer/ |  | 复现截图与修复后截图进证据；参数接口返回范围并有测试；滑块两端显示数值；pytest、ruff、CI 绿；PR 已合并（可与 B2、B4、B5、B6 合一个 PR）。 |
| B2 | #95 | W3 | P2 | Viewer：检查器空态给用法与图纸摘要 | — | viewer/ |  | 复现与修复截图进证据；摘要数据有测试；pytest、ruff、CI 绿；PR 已合并。 |
| B3 | #96 | W3 | P1 | Viewer：违规元素在画布标红，检查器显示 clause / measured / expected / candidates | E1 | viewer/、预览接口 | 是 | flange 把 dh 拖到违规值时画布上对应元素标红、松手 / 撤回后消失；检查器显示 clause / measured / expected / candidates；snapshot.json 同字段；接口测试 + 现场截图进证据；一轮独立评审已处理；pytest、ruff、CI 绿；PR 已合并。 |
| B4 | #97 | W3 | P2 | Viewer：预览态在画布上标示“预览（未写回）” | — | viewer/ |  | 复现与修复截图进证据；状态切换有测试（接口或前端状态）；pytest、ruff、CI 绿；PR 已合并。 |
| B5 | #98 | W3 | P2 | Viewer：状态栏可读性（字号、原话展开、警告数着色） | — | viewer/ |  | 复现与修复截图进证据；着色逻辑有测试；pytest、ruff、CI 绿；PR 已合并。 |
| B6 | #99 | W3 | P2 | Viewer：版本列表在轮询刷新时保持展开 | — | viewer/ |  | 复现与修复截图进证据；回归用例；pytest、ruff、CI 绿；PR 已合并。 |
| B7 | #100 | W3 | P2 | 版本对比：整视图移动时 layout_changed 归并为一条 | — | versions.py、viewer/ |  | 整视图平移的用例里 `lcad diff` 与 Viewer 对比只报一条视图平移、layout_changed 只含真正额外移动的元素（测试断言）；截图进证据；pytest、ruff、CI 绿；PR 已合并。 |
| H3 | #106 | W3 | P1 | 首次出图自动打开 Viewer（后台常驻、空闲自退、--no-view / CI 默认关） | — | viewer/、commands.py、.linercad/ 状态（git 不跟踪） |  | 图纸目录第一次 build / edit 成功后自动起后台 Viewer 并开一次浏览器（JSON 带 viewer: {url, opened}，打不开时输出可用地址）；已在运行只刷新不开新标签；空闲超时自退、无遗留进程；CI 与 --no-view 默认关；Claude Code 与 dsh 各出一张图现场验收；pytest、ruff、CI 绿；PR 已合并。 |
| H4 | #107 | W3 | P1 | Viewer 选择同步到对话：点选复制引用 + 自然语言指代（所有 Agent；B2 钩子转 v0.2） | B2（复制引用合并做） | viewer/、skill/（指代读取走 `lcad context @sel` / selection.json） | 是 | 两条路径都要过：① 多选 3 元素 → 复制引用粘进 dsh 一轮改对；② 不复制、直接打字“把选中的直径改成 k6” → Agent 先读当前选择再改对；无选择 / 选择过期时 Agent 如实报告、不猜测；skill 写明指代规则；现场截图进证据；一轮独立评审已处理；pytest、ruff、CI 绿；PR 已合并。 |
| H2 | #105 | W3 | P2 | `lcad template save/list`：用户沉淀参数化模板，`init --from` 一步出图 | — | commands.py、模板清单与存放、skill/pages/api.md |  | `save`（前提 check 0 error）后 `lcad init <目录> --from <名> --set …` 一步出图；清单含名称 / 描述 / 参数范围；`template list` 与 skill 列出用户模板并写“匹配即从模板起步”规则；修订层存在时提示；牛鼻刀基线（首次 vs 换规格）出数进证据；pytest、ruff、CI 绿；PR 已合并。 |
| H1 | #104 | W3 | P2 | `lcad edit --dry-run`：试改不提交 | D2（默认） | txn.py；cli.py、commands.py 只加开关 | 是 | 临时目录图纸仓库里 `lcad edit --dry-run` 后 HEAD、git status、动作日志、源文件均不变（测试断言）；输出含变化元素、finding、预览路径；随后同一脚本真实 edit 的结果与 dry-run 报告一致；失败路径与 edit 同结构；一轮独立评审已处理；pytest、ruff、CI 绿；PR 已合并。 |
| F1 | #101 | W3 | P3 | 文档：跨 Agent 措辞收紧；Skill 与 README 同步 v0.1.1 变更 | E1、C4、D3、H1 | README、skill/、docs/ |  | README 与 Skill 中跨 Agent 表述与 #70 证据及 v0.1.1 复测（dsh + Codex）一致；Skill 覆盖本版新接口（逐项列在 PR 里）；`lcad skill install` 后的文件与源一致的测试通过；CI 绿；PR 已合并。 |
| V1 | #102 | W4 | P0 | v0.1.1 版本验收（G5）：干净 clone、独立 Agent 多轮修改与出图评审、版本号与发布说明 | 全部卡片 | pyproject、版本号、docs/releases/v0.1.1.md、docs/milestones/v0.1.1/HANDOVER.md |  | 干净 clone 全量测试、ruff、评测 40/40 零 error、几何 / 完整性 1.0、baseline 不退化；独立 Agent（dsh 与 Codex）多轮修改与出图评审记录进证据；版本号 0.1.1、docs/releases/v0.1.1.md 与 HANDOVER 合并；CI 四项绿；PR 已合并。 |

## 5. 质量标准

1. **每张卡：** 先提交会失败的测试（G2）；`uv run pytest`、`uv run ruff check`、`uv run ruff format --check` 全绿；CI 四项（lint、test ubuntu 3.11、test windows 3.13、test-3d）绿；新代码有测试；每个缺陷修复留回归用例；**不为过关削弱检查或测试**。
2. **评测护栏：** 评测 40/40 零 error、几何 / 完整性对照 1.0 不退化。E1 合并后 `evals/baseline.json` 为基线向量，之后每个 PR 跑 `evals/run.py --baseline`，任一族下降或 error 增加即不合并；新增指标进基线须在 PR 里写明是“新增”。
3. **出图 / 布局卡：** 附前后对比渲染图（`docs/milestones/v0.1.1/evidence/`，小）和 D.place / A.place 数字；守 DESIGN §4.6（确定性、写了的固定、不做全局求解、排不好就报冲突）。
4. **数据卡：** `[meta]` 写来源、读取日期、核对方式、未读到的部分；单一谱系标 `verified = false`；不编造数值；标准原文、样例 DXF / PDF 不入库，只入数值、条款号、陈述摘要。
5. **Viewer 卡：** 复现截图 → 修复 → 回归用例 + 修复后截图（Browser 面板），进证据。
6. **仓库卫生：** 测试和验收在临时目录建图纸仓库，不在开发仓库产生图纸 commit；渲染图、DXF 不入库（golden 与小的验收证据例外）。
7. **独立评审：** 核心卡（E1、E2、C4〔覆盖 C2–C4〕、D1、D2、B3）合并前一轮：子代理、新上下文、只给卡片 + diff + DESIGN 相关节，同样 Sonnet xhigh；只看正确性与对 DESIGN 的偏离。
8. **核验不信自述：** supervisor 对每个合并的 PR 看 diff、CI 与测试输出；布局与指标卡抽跑评测；必要时干净 clone 复现。
9. **版本验收（V1 + G6）：** 干净 clone（`uv sync --extra 3d`）全量测试、ruff、评测与基线对比；只拿 Skill 的独立 Agent 多轮修改 + 出图评审（ROADMAP §4.1“不省的”）；supervisor 在干净 clone 复核（G6）；然后 tag `v0.1.1` 与 GitHub Release。

**版本 Goal：** 覆盖矩阵中 v0.1.1 各项全部关闭（做完，或经用户同意转 v0.2）；第 5 节全部满足；干净 clone 复核通过；`v0.1.1` tag 与 GitHub Release 已建。

## 6. 派活与续跑

- 用户在本会话回复“开始”后，一个回合内开出 W1–W4（`fresh`、`claude-sonnet-5-5`、各自 worktree），首回合只核对模型后等待；supervisor 把每个会话的 effort 设为 `xhigh` 并用 `get_session` 核对，再 `send_message` 发第一张卡。之后只用 `send_message` 推进。
- 开发会话：基于 `origin/main`；CI 绿后自己 `gh pr merge --squash`（auto-merge 已禁用）；进度写仓库外 `D:\Industry\Claude-Code\Liner-CAD-refs\v0.1.1-supervisor\progress\<流>.md`；最后一条消息以 `CARD <id> DONE — PR #n merged` 或 `CARD <id> BLOCKED — <原因>`（额度用尽写 `BLOCKED — usage limit`）开头。
- 续跑：状态文件 `Liner-CAD-refs\v0.1.1-supervisor\status.json` + `progress.md`；会话内看门狗（额度 ≥ 90% 时定在 `resetsAt` + 10 分钟，否则 ≤ 3 小时心跳）；桌面计划任务 `liner-cad-watchdog-backstop` 每 6 小时兜底。见 `docs/ROADMAP.md` §4.2。

## 7. 待用户确认（不阻塞）

| # | 事项 | 结论 |
|---|---|---|
| U1 | 3D 来源的阶梯剖、旋转剖、移出断面（v0.1.0 已知缺口，review 未提及） | **已确认转 v0.2**（用户 2026-11-14：通过） |
| U2 | `lcad edit --dry-run`（M3：Agent 用 edit + undo 试错，历史留成对 commit） | **已确认放入 v0.1.1**（用户 2026-11-14）：卡片 H1（#104），默认排 D2 之后，评测显示轮次多可提前 |
| U3 | 磨头只有 PDF | **已关闭**（用户 2026-11-14：仅作测试 / V1 出图参照，不再索要 DXF） |
| U4 | ISO 2540 附录 A 原文 | 先由 A3 找独立来源；找不到再请用户提供 |
| U5 | 指标落地顺序：E5（D.place）提前到 E1 之后；核心卡也用 Sonnet xhigh | **已确认**（用户 2026-11-14 未提异议；见偏离记录 1、2） |

2026-11-20 增补：按用户指示，2026-11-13 试用“三项”（commit 49d8759）并入计划，拆为 H2（#105）、H3（#106）、H4（#107）、E7（#108）；dry-run 即 H1（#104）。方案与验收见 `docs/releases/v0.1.0-review.md` “Viewer 自动打开、选择同步到对话、迭代速度”一节。

## 8. 风险

- **额度：** Pro 计划，周额度起始 37%。并发 ≤ 3；撞额度靠状态文件与看门狗续跑；必要时把 P2 卡转 v0.2 前先问用户。
- **布局改动牵动全局：** 以评测基线、确定性测试和固定元素测试做护栏；D1、D2 独立评审。
- **D4 改投影边 ID：** 已有图纸仓库的动作日志可能引用旧 ID；要求失败时给 not_found + 候选，并写进发布说明。
- **标准 PDF 为图片：** 本机缺 poppler，先转图片再多模态读；读不到的如实记录，不补编。
- **样例许可：** 用户样例与标准原文不入库，证据只放数字与小的自身输出。
- **Viewer 常驻进程（H3）：** 端口 / pid 记 `.linercad/`（git 不跟踪）、空闲超时自退、CI 与 `--no-view` 默认关；常驻后暴露时间变长的风险随卡评估（令牌加固仍在 v0.2）。

## 9. 偏离记录

1. **E5 提前到 E1 之后**（方案 §8 原为第 5 步）：D 流是头号优先，需要 D.place 作尺子；E2 紧随其后，仍在 D 流大部分卡片之前完成。
2. **核心卡也用 Sonnet 5.5 xhigh**（ROADMAP §4 原定核心卡用 Opus）：用户 2026-11-14 决策，开发只允许 Sonnet 5.5 xhigh；以独立评审与 supervisor 核验补足。
3. **v0.1.1 不另写 BRIEF / SPEC**：本 PLAN 加卡片 issue 即 BRIEF + SPEC；G1 由用户在本会话审计划（回复“开始”）代替独立评审；设计细节在各卡 PR 里写明。
4. **`lcad edit --dry-run` 转入 v0.1.1**（原 U2 建议 v0.2）：用户 2026-11-14 决定；卡片 H1（#104），默认排 D2 之后，D 流评测显示 Agent 调布局轮次多可提前。
5. **“三项”并入 v0.1.1**（首次出图自动打开 Viewer、选择同步到对话、迭代提速）：用户 2026-11-13 试用后定方向（commit 49d8759），2026-11-20 指示吸收进 PLAN 与 ROADMAP；拆为 H2（#105）、H3（#106）、H4（#107）、E7（#108）。
6. **supervisor effort high → xhigh**：用户 2026-11-14 直接调整（BRIEF.md 步骤 0 已同步接受两档；开发会话仍一律 Sonnet 5.5 xhigh）。
7. **跨 Agent 验证改用 dsh + Codex**（2026-11-21 用户指示）：v0.1.1 涉及跨 Agent 效果的地方（E7 的场景、F1 的措辞依据、V1 的独立 Agent 验收）以 DeepSeek Harness 与 Codex 为准；豆包工作不再使用。
8. **A1、A3 随 PR #69 核对关闭**（2026-11-21）：GB/T 6403.5-2008 表 1 与原文逐格对上，`res/grinding_grooves.toml` 改 `verified = true`，逐格表作测试 fixture；B 型中心孔的 D1 / l2 对 ISO 2540:2016 表 1 与几何复核，D2 / l_min 仍单一谱系，保持 `verified = false` 并把待用户项写进 [meta]。
9. **B2（Claude Code 提示钩子）转 v0.2，B1 细化**（2026-11-21 用户决定）：开发主平台已切至 DeepSeek Harness，钩子只对 Claude Code 宿主有意义，回到该宿主时再启用；H4（#107）收敛为两条路径——点选 / 多选后复制引用一行粘贴进任何 Agent；自然语言指代（用户直接说“修改什么…”，Agent 经 `lcad context @sel` / `selection.json` 知道针对与相关的修改对象，选择过期时如实报告、不猜测）。详见 `v0.1.0-review.md` 同名一节。
10. **每张卡都评审，不分档**（2026-11-21 用户决定，取代 §5.7「核心卡合并前一轮」）：每张卡合并前经 Codex 评审（BRIEF-DSH §3：`codex exec`，本机默认 deepseek-v4.1-flash / max；最多 3 轮，第 3 轮仍不过升级 lead 仲裁，禁止拉锯烧额度）；核心卡（E1、E2、C4、D1、D2、B3、H4、H1）另加一道 glm-5.3-flash（max）短命子代理第二道评审，与 Codex 形成跨模型交叉。
11. **不做 Code Simplifier**（2026-11-21 用户决定）：不设独立的代码简化轮；以「代码只写当前验收需要的」在编写时把住（ROADMAP §4.1 精简规则）。
12. **开发档位与会话机制改由 DSH 团队章程承担**（2026-11-21）：v0.1.1 开发自本日起在 DeepSeek Harness 下进行，成员一律 deepseek-v4.1-flash（1017）+ max，取代 §4「执行档位一律 Sonnet 5.5 xhigh」与 §6 的 Claude Code 会话机制；单卡闭环、评审纪律、额度续跑见仓库外 `Liner-CAD-refs\v0.1.1-supervisor\BRIEF-DSH.md` 与 `KICKOFF-DSH-TEAM.md`；某卡评审反复不过时由 lead 开 deepseek-v4-pro（max）一次性替身接卡（升级路径）。
