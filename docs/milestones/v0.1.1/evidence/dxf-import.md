# DXF 导入评测（C1 / issue #76）

2026-11-21 · 流 W1 · 脚本 evals/dxf_import.py · 样例原图不入库（本文件只放数字）。

复现：uv run python evals/dxf_import.py "<sample 目录>" --out report.json

## 指标口径（脚本按此输出 JSON；每条读数都由实际导入结果推导）

| 指标 | 含义 | 当前实现下的已知边界 |
|---|---|---|
| entity_retention | 按 DXF 实体类型统计：源实体中有多少变成模型元素 | HATCH / INSERT / POINT / ATTRIB 等导入器跳过的类型恒为 0；退化实体（零长线等）不计 |
| layer_retention | 有内容的源图层、其内容能否真的进入模型（按导入器逐实体行为判定，含尺寸缺 defpoint、raw 打包失败、退化 edge）；names_preserved 从导入元素的 intent.dxf.layer 统计 | dimensions / notes 不携带图层 meta，names_preserved 只反映 edges（C2 可提升） |
| dimension_retention | DIMENSION 作为尺寸保留的比例；降级为 note 单列 as_note；缺 defpoint 等无法导入的单列 skipped | 与被测几何对不上时降级为 note，属现状 |
| text_retention | TEXT / MTEXT 作为**普通文字元素**保留的比例（as_text，按内容多重集匹配）；目前只有 leader note（as_note） | 导入器当前没有普通文字元素：主比率 = 0，note_rate 为现状读数；C2 引入普通文字后主比率才有意义 |
| hatch_retention | HATCH 作为 hatch 保留的比例 | 导入器当前没有 hatch 桶：0 |
| frame_title | sheet_guess（available / fits，按模板图框+标题栏校验）、标题/图框 INSERT、图框层几何（frame_edges，按 handle 匹配）、标题属性字段（全部顶层 ATTRIB + 标题 INSERT 属性）、标题层文字 | INSERT / ATTRIB 当前 skipped；图框层几何作为普通 edges 导入（不是图框元素），C4 的"只剩一个图框"需要在此读数上处理 |
| inspect | 同一文件跑 lcad inspect CLI，并**比对** maps_to 与 scan 分类、sheet 与 guess_sheet（maps_match / sheet_match） | — |
| edit_round | 端到端：init --from-dxf → 按尺寸侧向移一个尺寸 → 改一段文字 → edit/build；从 edit 输出 ops 验证 move + set 都发生 | 失败时 JSON 带 error / edit_code / build_ok |

## 4 个样例 DXF 的基线（本机，2026-11-21；sha 前 12 位）

样例不入库。4 个文件为平铣刀/牛鼻铣刀/球头铣刀/钻头铣刀（PCCAD 风格：标题栏 = INSERT + ATTRIB，
填充 = HATCH，文字 = MTEXT）。磨头只有 PDF，按 issue 不做 DXF 评测。

| 文件 | sha12 | bytes | 实体 源/保留 | entity rate | dims（保尺寸/降级/跳过） | text（as_text/as_note） | hatch | layer（内容/进入模型，names） | 图框 INSERT / 图框边 | 标题属性字段 | sheet | inspect | edit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 平头铣刀.dxf | ceb03019b2c8 | 118533 | 114/61 | 0.5351 | 6/6 · 0 · 0 | 0 / 16 | 0/1 | 7/5 · names 4 | 1 / 4（保留 4） | 49 | A3 1:1 fits | ok · 匹配 | 通过（dy） |
| 牛鼻铣刀.dxf | 0ee2981ad1f0 | 95520 | 74/68 | 0.9189 | 7/7 · 0 · 0 | 0 / 19 | 0/1 | 7/6 · names 4 | 1 / 4（保留 4） | 3 | A3 1:1 fits | ok · 匹配 | 通过（dy） |
| 球头铣刀.dxf | bab1f472030d | 92729 | 68/61 | 0.8971 | 5/6 · 1 · 0 | 0 / 16 | 0/1 | 7/5 · names 4 | 1 / 4（保留 4） | 4 | A3 1:1 fits | ok · 匹配 | 通过（dx，right） |
| 钻头铣刀.dxf | 353b4f2f7bbd | 93820 | 69/62 | 0.8986 | 7/7 · 0 · 0 | 0 / 16 | 0/1 | 7/5 · names 4 | 1 / 4（保留 4） | 4 | A3 1:1 fits | ok · 匹配 | 通过（dy） |
| **合计** | — | 400602 | **325/252** | **0.7754** | **25/26 · 1 · 0（0.9615）** | **0/67（主 0.0, note 1.0）** | **0/4** | **21/28（0.75）· names 16** | **4 / 16（保留 16）** | **60** | **4/4 available+fits** | **4/4 ok · 4/4 匹配** | **4/4** |

按类型（合计）：LINE 156/156、MTEXT 67/67、DIMENSION 26/26（其中 25 保持为尺寸）、ARC 3/3（均 1.0）；
ATTRIB 0/60、HATCH 0/4、INSERT 0/9（导入器当前跳过，是现状读数不是目标值）。

补充：layer_retention 的 not_imported 为「5剖面线层」（只含 HATCH）与「6文字层」（只含 ATTRIB）；
标题栏是 INSERT + ATTRIB，故 title_layer_texts = 0 / title_text_retention = null；图框层几何 4 条/文件
全部作为普通 edges 导入（frame_edges 16/16）——即"图框/图框元素"尚未被识别，C4 要在此基础上做"只剩一个图框"。

## 评审（Codex 第 1、2 轮）处理与口径修正

- edit_round 按尺寸侧向生成候选（bottom/top→dy、left/right→dx），并从 edit 输出 ops 验证 move + set 都发生；
  独立夹具覆盖 right 侧尺寸（dx 移动）。
- text_retention 拆 as_text（普通文字元素，按内容多重集匹配；主比率）与 as_note（现状）；
  重复文字、%%c→Φ、内容不匹配反例都有测试。
- names_preserved / hatch retained / frame_inserts_retained / title_attrib_retained / frame_edges_retained
  全部从实际创建元素（含 dxf handle）统计并与源实体匹配，不再写死 0。
- layer_retention 按导入器逐实体行为判定：退化 edge、缺 defpoint 的尺寸、raw 打包失败都不算该层内容进入模型。
- 新增 lcad inspect CLI 评测并**比对** maps_to / sheet（maps_match、sheet_match、inspect_match_rate）；
  只靠退出码不算通过。
- sheet_guess 拆 available / fits（模板图框与标题栏尺寸校验），并有不 fit 反例。
- 顶层 ATTRIB 全量计数（不再用字段白名单，平头样例从 22 → 49）；图框层几何单独单列 frame_edges。
- glob 大小写不敏感（.DXF 也评测）；evidence 末尾无多余空行。

## 口径用途（C2 / C3 / C4 的尺子）

- C2/C3（导入精化：普通文字、图层、标题栏/图框、HATCH）：以 text_retention.as_text、layer_retention（含 names_preserved）、
  frame_title（含 frame_edges）、hatch_retention 为基线，改进后由同一命令输出新读数逐字段对比。
- C4（编辑/往返、只剩一个图框）：以 edit_round_rate = 1.0（4/4）为不可退化门槛；frame_edges/frame_inserts 是"图框"读数，
  C4 需要把图框层几何与标题栏元素与"一个图框"的目标对齐。
- entity_retention 的 ATTRIB/HATCH/INSERT 0% 是现状而非目标值；提升后更新本文件并说明。
- 样例数字来自本机；脚本不按文件名特判，CI 用 ezdxf 自造夹具（tests/test_dxf_import_metrics.py）覆盖同一口径。
