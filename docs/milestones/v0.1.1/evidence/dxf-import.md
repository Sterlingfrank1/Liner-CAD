# DXF 导入评测（C1 / issue #76）

2026-11-21 · 流 W1 · 脚本 evals/dxf_import.py · 样例原图不入库（本文件只放数字）。

复现：uv run python evals/dxf_import.py "<sample 目录>" --out report.json

## 指标口径（脚本按此输出 JSON；每条读数都由实际导入结果推导）

| 指标 | 含义 | 当前实现下的已知边界 |
|---|---|---|
| entity_retention | 按 DXF 实体类型统计：源实体中有多少变成模型元素 | HATCH / INSERT / POINT / ATTRIB 等导入器跳过的类型恒为 0；退化实体（零长线等）不计 |
| layer_retention | 有内容的源图层、其内容能否真的进入模型（按导入器逐实体行为判定，含尺寸缺 defpoint/零长、raw 写回验证、退化 edge）；一次分组，不重扫 | dimensions / notes 不携带图层 meta，names_preserved 只反映 edges（C2 可提升） |
| dimension_retention | DIMENSION 作为尺寸保留、降级 note、无法导入（skipped）三种去向 | 与被测几何对不上时降级为 note，属现状 |
| text_retention | TEXT / MTEXT 作为**普通文字元素**保留（as_text，按内容多重集匹配）与作为 leader note（as_note）；两者不相交消费；尺寸降级 note 单列 dims_fallback_notes，不计入文字 | C2 起 as_text 67/67，as_note 为现状读数；C2 引入普通文字后 as_text 才有提升 |
| hatch_retention | HATCH 作为 hatch 保留的比例（按源 dxf handle 归属，retained ≤ source） | C3 起 hatch 4/4 |
| frame_title | sheet available/fits；标题/图框 INSERT（handle 匹配 retained）；图框层几何 frame_edges（handle 匹配）；标题属性字段（全部顶层 ATTRIB + INSERT 属性，handle 匹配 retained）；标题文字（modelspace 标题层文字 + **标题块模板 TEXT**，分母含 4×16 模板文字）；最终图纸的 frame 元素数 model_frames 与 single_frame_ok | INSERT / ATTRIB 当前 skipped（retained 0）；图框层几何作为普通 edges 导入（保留 16/16，single_frame_ok=false），C4 要在读数上做"只剩一个图框" |
| inspect | 同一文件跑 lcad inspect CLI，并比对 maps_to 与 scan 分类、sheet 与 guess_sheet；PNG 渲染失败（png_error）判为失败 | — |
| edit_round | 端到端：init --from-dxf → 按尺寸侧向移一个尺寸 → 改一段文字 → edit/build；从 edit 输出 ops 验证 move + set 都发生 | 失败时 JSON 带 error / edit_code / build_ok |

## 口径修正前 / 后（C2/C3/C4 的起点 = 修正后）

第 3 轮评审发现 8 处尺子缺陷，修正后重跑同样 4 个样例。修正涉及：标题文字分母（含标题块模板文字 64 条）、
标题 INSERT/ATTRIB 改按 dxf handle 匹配、图框层几何单列并统计最终图纸 frame 元素、hatch 按源 handle 且设上界、
尺寸退化/raw 写回预测、as_text/as_note 不交叠并排除尺寸 fallback note、inspect PNG 失败判失败、图层分组一次扫描。

| 指标 | 修正前 | 修正后（起点） |
|---|---|---|
| 标题文字 source / as_text / as_note / note_rate | 仅 modelspace 标题层文字（4 样例 = 0） | **64（4×16 标题块模板 TEXT）/ 0 / 0 / 0.0** |
| 标题 INSERT / ATTRIB retained | kinds 兜底可虚高（无 handle 也计） | **handle 匹配：0 / 0**（无假计数） |
| 图框读数 | 仅 frame_edges 16/16 | **frame_edges 16/16 + model_frames 4（每图 1）+ single_frame_ok_rate 0.0** |
| hatch rate | 元素数可得 >1.0 | **按源 handle 归属，0.0（retained ≤ source）** |
| 尺寸 skipped | 只按 defpoint 存在性 | **零长/缺 defpoint 真实判 skipped；样例 skipped 0** |
| text as_text/as_note | 可能同一文字双计 | **不相交；dims_fallback_notes 单列（样例 1 条）** |
| inspect | 只看退出码/ok | **png_ok + maps_match + sheet_match 全判** |
| 其余（entities/dims/layer/inspect/edit） | — | 与修正前一致（见下表） |

## 4 个样例 DXF 的基线（修正后，本机 2026-11-21；sha 前 12 位）

样例不入库。4 个文件为平铣刀/牛鼻铣刀/球头铣刀/钻头铣刀（PCCAD 风格：标题栏 = INSERT + 标题块模板 TEXT +
顶层 ATTRIB，填充 = HATCH，文字 = MTEXT）。磨头只有 PDF，按 issue 不做 DXF 评测。

| 文件 | sha12 | bytes | 实体 源/保留 | entity rate | dims（保尺寸/降级/跳过） | text as_text/as_note | hatch | layer（内容/进入模型·names） | 图框 INSERT / 图框边 / model_frames / single_ok | 标题文字 source/as_text/as_note | 标题属性字段 / retained | sheet | inspect | edit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 平头铣刀.dxf | ceb03019b2c8 | 118533 | 114/61 | 0.5351 | 6/6 · 0 · 0 | 0 / 16 | 0/1 | 7/5 · 4 | 1 / 4 / 1 / false | 16 / 0 / 0 | 49 / 0 | A3 1:1 fits | ok·png·匹配 | 通过（dy） |
| 牛鼻铣刀.dxf | 0ee2981ad1f0 | 95520 | 74/68 | 0.9189 | 7/7 · 0 · 0 | 0 / 19 | 0/1 | 7/6 · 4 | 1 / 4 / 1 / false | 16 / 0 / 0 | 3 / 0 | A3 1:1 fits | ok·png·匹配 | 通过（dy） |
| 球头铣刀.dxf | bab1f472030d | 92729 | 68/61 | 0.8971 | 5/6 · 1 · 0 | 0 / 16 | 0/1 | 7/5 · 4 | 1 / 4 / 1 / false | 16 / 0 / 0 | 4 / 0 | A3 1:1 fits | ok·png·匹配 | 通过（dx，right） |
| 钻头铣刀.dxf | 353b4f2f7bbd | 93820 | 69/62 | 0.8986 | 7/7 · 0 · 0 | 0 / 16 | 0/1 | 7/5 · 4 | 1 / 4 / 1 / false | 16 / 0 / 0 | 4 / 0 | A3 1:1 fits | ok·png·匹配 | 通过（dy） |
| **合计** | — | 400602 | **325/252** | **0.7754** | **25/26 · 1 · 0（0.9615）** | **0/67（主 0.0，note 1.0）** | **0/4** | **21/28（0.75）· names 16** | **4 / 16 / 4 / 0.0** | **64 / 0 / 0** | **60 / 0** | **4/4 fits** | **4/4 ok·png·匹配** | **4/4** |

按类型（合计）：LINE 156/156、MTEXT 67/67、DIMENSION 26/26（25 保持为尺寸）、ARC 3/3（均 1.0）；
ATTRIB 0/60、HATCH 0/4、INSERT 0/9（导入器当前跳过，是现状读数不是目标值）。

补充：layer not_imported 为「5剖面线层」（只含 HATCH）与「6文字层」（只含 ATTRIB）；
标题文字分母是标题块模板文字（不进入 modelspace，导入器跳过 INSERT）→ as_text=0、as_note=0，C2 把模板文字变普通文字后
应上升；图框层几何 4 条/文件作为普通 edges 导入（frame_edges 16/16），最终图纸另有模板 frame（model_frames 1），
故 single_frame_ok=false —— 这就是 C4"只剩一个图框"要改善的读数。


## C2 后（TEXT / MTEXT 导成普通文字元素）：C1 指标变化

C2 把 modelspace 的 TEXT / MTEXT 从 leader note 改为普通文字元素（kind=text，无引线，保留位置/字高/旋转/对齐/样式，
MTEXT 保留换行）。C1 尺子的读数变化（同一 4 样例、同一命令）：

| 指标 | C1 基线（C2 前） | C2 后 | 说明 |
|---|---|---|---|
| text as_text | 0 / 67（rate 0.0） | **67 / 67（rate 1.0）** | 目标②达成：文字保留率显著上升 |
| text as_note | 67 / 67（note_rate 1.0） | **0 / 67（note_rate 0.0）** | 不再借用 leader note |
| layer names_preserved | 16 | **21** | 普通文字元素也带源图层 dxf 元数据 |
| dims as_note（尺寸降级） | 1 | 1 | 未变，仍单列 dims_fallback_notes |
| 标题块模板文字 as_text | 0 / 64 | **0 / 64** | 边界：C2 只覆盖 modelspace 的 TEXT/MTEXT；标题块内部模板文字仍随 INSERT 跳过，留 C4 |
| entities / dims / hatch / 图框 / sheet / inspect / edit | 见上表 | **逐项不变** | edit_round 现在可直接改导入文字（4/4，3 个样例改的是 T.txt_1） |

4 样例合计：text as_text 67/67；layer names 21；其余（entities 252/325、dims 25/26+1 note、hatch 0/4、
图框 4 INSERT/16 边/model_frames 4/single_ok 0.0、sheet 4/4 fits、inspect 4/4 ok·png·匹配、edit_round 4/4）与 C1 基线一致。


## C3 后（HATCH 导入为剖面线元素）：C1 指标变化

importdxf 现在把 HATCH 分类为 hatches 桶并导入为剖面线元素（kind=hatch）：
- 图案填充：只映射本仓剖面线语汇可表示的图案（ANSI31）与 SOLID；pattern / angle / scale 写入意图并在 build 回写时原样保留（pattern_name/pattern_angle/pattern_scale 与源一致），不再被 std 45°/spacing 变换改写；其它预定义图案（如 ANSI37）按不可表示报告。
- 实体填充：solid=True；layout/dxfout/svgout 按实体填充处理（dxfout set_solid_fill）。
- 边界：多边形路径（含 bulge 圆弧）与 edge 路径的 LINE/ARC 逐段展平；弧采样按 sagitta ≤ 0.01mm 自适应（半径 20 与 1000 均满足），闭合/首尾连接按 0.01mm 校验，面积为零/开口/缺口路径按路径丢弃并报告；多个路径 → 多个 loop（islands 保留），源 hatch_style 保留（非 normal 时报告近似为 even-odd）。
- 不能表示：渐变填充、无可映射图案（如 ANSI37）、非预定义图案类型、ELLIPSE/SPLINE 边界、开口/零面积/空路径——按源 dxf handle + 图层 + 原因记录，不静默；部分路径不可表示但其余边界有效时，整张 hatch 保留并把路径明细写进 counts.hatch_warnings 与 intent.dropped_paths。

| 指标 | C2 后（C3 前） | C3 后 | 说明 |
|---|---|---|---|
| hatch_retention | 0/4（0.0） | **4/4（1.0）** | 4 个样例 HATCH 均保留 |
| entity HATCH 保留 | 0/4 | **4/4（1.0）** | entities 总保留 252/325 → **256/325（0.7877）** |
| layer content retention | 21/28（0.75） | **25/28（0.8929）** | 剖面线层不再是 skipped |
| layer names_preserved | 21 | **25** | 剖面线元素带源图层 dxf 元数据 |
| 其余（dims/text/图框/sheet/inspect/edit） | — | **逐项不变** | edit_round 4/4 |

### 不能表示 / 部分丢失的报告（样例实测）

- 4 个样例的 HATCH 都是 ANSI31、scale 0.5、angle 0（预定义图案）：整张 hatch 保留。
- 每个样例另有 3 条**退化边界路径**（1 条空路径、1 条零面积回首路径等），按路径丢弃并报告：
  counts.hatch_warnings 列出 {handle, layer, reason: "path 1/3/5: degenerate boundary"}；元素 intent.dropped_paths 保留同样明细；
  有效边界（2 个四边形）仍导入为 loops，不因此整张丢失。
- 渐变填充：整张 HATCH skipped（counts.hatch_skipped + skipped["HATCH(gradient)"]）；非预定义图案类型、ELLIPSE/SPLINE 边界同理（测试夹具覆盖 gradient 与 partial path）。


## C4 后（源图框/标题栏并入模板语义）：只有一个图框

策略：导入时识别源图框语义——图框/标题栏图层（解码后含「图框」「标题栏」「TITLE」「FRAME」等）上的普通几何（边/raw）不再创建为 E 元素，而是**吸收进新图幅的模板图框语义**（模板 frame 仍只 1 个）；标题栏块 INSERT 与其 ATTRIB 仍按边界跳过（不导入模板文字/属性）。`lcad inspect` 新增 `frame` / `title` 报告（识别到的图框图层与实体统计、将吸收的数量、标题栏块名）。

| 指标 | C3 后 | C4 后 | 说明 |
|---|---|---|---|
| single_frame_ok_rate | 0.0 | **1.0** | 4/4 文件只剩 1 个模板图框 |
| model_frames | 4 | 4 | 每图 1 个（模板） |
| frame_edges retained / absorbed | 16 / — | **0 / 16** | 源图框边不再作为第二条图框叠入 |
| entities | 256/325（0.7877） | **256/325（0.7877）** | 吸收的 16 条边按「转入模板语义」计 retained，不退化 |
| layer content / names | 25/28、25 | **25/28、25** | 图框层名称按吸收层保留在报告 |
| text / hatch / dims / title / sheet / inspect / edit | 67/67、4/4、25/26+1、0/64、4/4、4/4、4/4 | **逐项不变** | — |

说明：C1 尺子把「吸收进模板图框语义」的源图框实体显式记为 `frame_edges_absorbed`（entity/layer 读数同时保留 retained），因此「C1 指标不退化」不是靠丢弃分母，而是把 C4 的语义转换单独记账；标题块模板文字/ATTRIB 仍是 0/64、0/60 的既知边界（C4 不改标题栏语义）。

## 口径用途（C2 / C3 / C4 的尺子）

- C2（普通文字 / 标题栏 / 图层）：以 text_retention.as_text、frame_title.title_texts_as_text、title_attrib_retained、
  layer_retention.names_preserved 为提升目标；修正后的起点均在上表（当前 as_text=0、模板文字 0、ATTRIB retained 0）。
- C3（HATCH / 图框）：以 hatch_retention、frame_title.frame_edges/single_frame_ok 为基线；hatch 已 4/4（C3）。
- C4（编辑/往返、只剩一个图框）：edit_round_rate=1.0 不可退化；single_frame_ok_rate 现为 0.0（图框边 16 + 模板 frame 4）。
- entity_retention 的 ATTRIB/HATCH/INSERT 0% 是现状而非目标值；提升后更新本文件并说明。
- 样例数字来自本机；脚本不按文件名特判，CI 用 ezdxf 自造夹具（tests/test_dxf_import_metrics.py）覆盖同一口径。
