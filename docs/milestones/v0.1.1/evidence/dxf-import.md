# DXF 导入评测（C1 / issue #76）

2026-11-21 · 流 W1 · 脚本 evals/dxf_import.py · 样例目录（本机，入库）不包含任何原图。

复现：uv run python evals/dxf_import.py "<sample 目录>" --out report.json

## 指标口径（脚本按此输出 JSON）

| 指标 | 含义 | 当前实现下的已知边界 |
|---|---|---|
| entity_retention | 按 DXF 实体类型统计：源实体中有多少变成模型元素（edges / raw / notes / dims 全算命中） | HATCH / INSERT / POINT / ATTRIB 等导入器跳过的类型恒为 0 |
| layer_retention | 有内容的源图层数、其中至少有一条内容进入模型的图层数；另外记录 names_preserved | 模型元素当前不携带图层字段，故 names_preserved = 0（口径如实，不粉饰） |
| dimension_retention | DIMENSION 实体中作为尺寸保留的比例（as_dimension）；降级为文字 note 的单独计 as_note | 与被测几何对不上（找不到圆/线）时降级为 note，属现状 |
| text_retention | TEXT / MTEXT 以 note 形式保留的比例，按 clean_text 后的文字多重集匹配 | 标题栏 INSERT 内的属性文字不在 TEXT/MTEXT 口径内（见 frame_title） |
| hatch_retention | HATCH 实体保留比例 | 导入器当前没有 hatch 桶，HATCH 全部 skipped：恒为 0 |
| frame_title | 由范围猜图幅（sheet_guess）、标题/图框 INSERT 数、标题属性字段数、标题层文字保留数 | INSERT / ATTRIB 当前 skipped；只有普通 TEXT/MTEXT 能留下 |
| edit_round | 端到端：init --from-dxf → 移一个尺寸（沿法线）→ 改一段文字 → edit/build 成功 | 失败时 JSON 带 error / edit_code / build_ok，便于定位 |

## 4 个样例 DXF 的基线（本机，2026-11-21）

样例不入库；表中 sha 仅前 12 位。4 个文件均为平铣刀/牛鼻铣刀/球头铣刀/钻头铣刀（PCCAD 风格：
标题栏是 INSERT + ATTRIB，填充为 HATCH，文字是 MTEXT）。磨头只有 PDF，按 issue 不做 DXF 评测。

| 文件 | bytes | 实体 | entity_retention | dims（as_dim/as_note） | text | hatch | layers（内容/进入模型） | 标题属性字段 | 图幅猜测 | edit_round |
|---|---|---|---|---|---|---|---|---|---|---|
| 平头铣刀.dxf | 118533 | 114 | 0.5351（61/114） | 6/6 · 0（1.0） | 16/16（1.0） | 0/1（0.0） | 7 / 5（0.7143） | 22 | A3 1:1 | 通过 |
| 牛鼻铣刀.dxf | 95520 | 74 | 0.9189（68/74） | 7/7 · 0（1.0） | 19/19（1.0） | 0/1（0.0） | 7 / 6（0.8571） | 2 | A3 1:1 | 通过 |
| 球头铣刀.dxf | 92729 | 68 | 0.8971（61/68） | 5/6 · 1（0.8333） | 16/16（1.0） | 0/1（0.0） | 7 / 5（0.7143） | 2 | A3 1:1 | 通过 |
| 钻头铣刀.dxf | 93820 | 69 | 0.8986（62/69） | 7/7 · 0（1.0） | 16/16（1.0） | 0/1（0.0） | 7 / 5（0.7143） | 2 | A3 1:1 | 通过 |
| **合计** | 400602 | **325** | **0.7754（252/325）** | **25/26 · 1（0.9615）** | **67/67（1.0）** | **0/4（0.0）** | **28 / 21（0.75）** | **28** | **4/4** | **4/4** |

按类型（合计）：LINE 156/156（1.0）、MTEXT 67/67（1.0）、DIMENSION 26/26（1.0，其中 25 保持为尺寸）、
ARC 3/3（1.0）；ATTRIB 0/60、HATCH 0/4、INSERT 0/9（导入器跳过）。

补充：layer_retention 的 not_imported 为「5剖面线层」（只含 HATCH）与「6文字层」（只含 ATTRIB）；
标题栏是 INSERT + 顶部 ATTRIB，故 title_layer_texts = 0 / title_text_retention = null（没有标题层文字，
属性字段数 22/2/2/2 单独记录）。title_attrib_retained 与 frame_inserts_retained 当前均为 0，
这两个字段就是 C2/C3 要改进的读数。

## 口径用途（C2 / C3 / C4 的尺子）

- C2/C3（导入精化：图层、标题栏/图框、HATCH）：以本文件的 layer_retention / frame_title / hatch_retention 为基线，
  改进后由 evals/dxf_import.py 同一命令输出新读数，逐字段对比。
- C4（编辑/往返）：以 edit_round_rate = 1.0（4/4）为不可退化的门槛；任何文件 edit_round 由 true 变 false 视为回归。
- entity_retention 的 ATTRIB/HATCH/INSERT 0% 是现状而非目标值；C2/C3 提升后应更新本文件并说明。
- 样例数字来自本机运行；脚本不读样例文件名做特判，CI 用 ezdxf 自造夹具（tests/test_dxf_import_metrics.py）覆盖同一口径。

