# DXF 导入评测（C1 / issue #76）

2026-11-21 · 流 W1 · 脚本 evals/dxf_import.py · 样例原图不入库（本文件只放数字）。

复现：uv run python evals/dxf_import.py "<sample 目录>" --out report.json

## 指标口径（脚本按此输出 JSON；每条读数都由实际导入结果推导）

| 指标 | 含义 | 当前实现下的已知边界 |
|---|---|---|
| entity_retention | 按 DXF 实体类型统计：源实体中有多少变成模型元素 | HATCH / INSERT / POINT / ATTRIB 等导入器跳过的类型恒为 0；退化实体（零长线等）不计 |
| layer_retention | 有内容的源图层、其内容能否真的进入模型（按导入器逐实体行为判定，退化实体不算）；names_preserved 从导入元素的 intent.dxf.layer 统计 | dimensions / notes 当前不携带图层 meta，故 names_preserved 只反映 edges（C2 可提升） |
| dimension_retention | DIMENSION 作为尺寸保留的比例；降级为 note 单列 as_note | 与被测几何对不上时降级为 note，属现状 |
| text_retention | TEXT / MTEXT 作为**普通文字元素**保留的比例（as_text）；目前只有 leader note（as_note），separately 记录 | 导入器当前没有普通文字元素：主比率 = 0，note_rate 为现状读数；C2 引入普通文字后主比率才有意义 |
| hatch_retention | HATCH 作为 hatch 保留的比例 | 导入器当前没有 hatch 桶：0 |
| frame_title | sheet_guess（available / fits，按模板图框 + 标题栏尺寸校验）、标题/图框 INSERT、标题属性字段、标题层文字；retained 均从导入结果统计 | INSERT / ATTRIB 当前 skipped；只有普通 TEXT/MTEXT 能留下 |
| inspect | 同一文件跑 lcad inspect CLI（ok / maps_to / sheet）：C1 同时评测 inspect 与 import 两个入口 | — |
| edit_round | 端到端：init --from-dxf → 按尺寸侧向移一个尺寸 → 改一段文字 → edit/build；两个操作都从 edit 输出的 ops 和重建结果验证 | 失败时 JSON 带 error / edit_code / build_ok |

## 4 个样例 DXF 的基线（本机，2026-11-21；sha 前 12 位）

样例不入库。4 个文件为平铣刀/牛鼻铣刀/球头铣刀/钻头铣刀（PCCAD 风格：标题栏 = INSERT + ATTRIB，
填充 = HATCH，文字 = MTEXT）。磨头只有 PDF，按 issue 不做 DXF 评测。

| 文件 | sha12 | bytes | 实体 源/保留 | entity rate | dims（保尺寸/降级） | text（as_text/as_note） | hatch | layer（内容/进入模型，names） | 标题属性字段 | sheet | inspect | edit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 平头铣刀.dxf | ceb03019b2c8 | 118533 | 114/61 | 0.5351 | 6/6 · 0 | 0 / 16 | 0/1 | 7/5 · names 4 | 22 | A3 1:1 fits | ok | 通过（dy） |
| 牛鼻铣刀.dxf | 0ee2981ad1f0 | 95520 | 74/68 | 0.9189 | 7/7 · 0 | 0 / 19 | 0/1 | 7/6 · names 4 | 2 | A3 1:1 fits | ok | 通过（dy） |
| 球头铣刀.dxf | bab1f472030d | 92729 | 68/61 | 0.8971 | 5/6 · 1 | 0 / 16 | 0/1 | 7/5 · names 4 | 2 | A3 1:1 fits | ok | 通过（dx，right） |
| 钻头铣刀.dxf | 353b4f2f7bbd | 93820 | 69/62 | 0.8986 | 7/7 · 0 | 0 / 16 | 0/1 | 7/5 · names 4 | 2 | A3 1:1 fits | ok | 通过（dy） |
| **合计** | — | 400602 | **325/252** | **0.7754** | **25/26 · 1（0.9615）** | **0/67（主 0.0，note 1.0）** | **0/4** | **21/28（0.75）· names 16** | **28** | **4/4 available+fits** | **4/4** | **4/4** |

按类型（合计）：LINE 156/156、MTEXT 67/67、DIMENSION 26/26（其中 25 保持为尺寸）、ARC 3/3（均 1.0）；
ATTRIB 0/60、HATCH 0/4、INSERT 0/9（导入器当前跳过，是现状读数不是目标值）。

补充：layer_retention 的 not_imported 为「5剖面线层」（只含 HATCH）与「6文字层」（只含 ATTRIB）；
标题栏是 INSERT + ATTRIB，故 title_layer_texts = 0 / title_text_retention = null（没有标题层文字，
属性字段数 22/2/2/2 单独记录）；frame_inserts_retained 与 title_attrib_retained 当前均为 0。

## 评审（Codex 第 1 轮 8 条）处理与口径修正

- edit_round 不再"两次 move 失败也算过"：按尺寸侧向（bottom/top→dy、left/right→dx）生成移动候选，
  并从 edit 输出的 ops 验证真的发生了 move（球头样例的 right 侧尺寸现在用 dx 移动并记录 move_args）。
- text_retention 拆成 as_text（普通文字元素，主比率）与 as_note（现状）；样例主比率 0.0、note_rate 1.0，
  C2 引入普通文字元素后主比率才有提升意义。
- names_preserved / hatch_retention.retained / frame_inserts_retained / title_attrib_retained 全部从
  实际创建的元素统计，不再写死 0（样例 names_preserved = 16，其余见上表）。
- layer_retention 改用导入器逐实体行为判定（退化实体不算），并新增退化图层夹具覆盖。
- 新增 inspect CLI 评测（evaluate_file 调用 lcad inspect 并比对 maps_to/sheet），
  与 init --from-dxf 一起构成 C1 的两个入口。
- sheet_guess 拆成 available / fits（按模板图框与标题栏尺寸校验），不再把"能返回值"当准确率。
- 测试补齐：as_note、clean_text（%%c → Φ）、重复文字多重集、顶层 \U+ ATTRIB/图层、right 侧尺寸移动、
  edit 的 move/ops 验证；evidence 增加 sha12 列。

## 口径用途（C2 / C3 / C4 的尺子）

- C2/C3（导入精化：普通文字、图层、标题栏/图框、HATCH）：以 layer_retention（含 names_preserved）、
  frame_title、hatch_retention、text_retention.as_text 为基线，改进后由同一命令输出新读数逐字段对比。
- C4（编辑/往返）：以 edit_round_rate = 1.0（4/4）为不可退化门槛；任何文件 edit_round 由 true 变 false 视为回归。
- entity_retention 的 ATTRIB/HATCH/INSERT 0% 是现状而非目标值；提升后更新本文件并说明。
- 样例数字来自本机；脚本不按文件名特判，CI 用 ezdxf 自造夹具（tests/test_dxf_import_metrics.py）覆盖同一口径。

