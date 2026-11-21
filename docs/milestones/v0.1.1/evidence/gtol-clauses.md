# GB/T 1182 / 17851 / 17852 条文草稿（A4 → E4 输入）

卡 A4（issue #93）· 2026-11-21 · 数据文件 `src/linercad/res/gtol.toml`，接口 `res.gtol_rows()` / `res.gtol(char)`

## 1. 来源与读法

- 原文（**不入库**，本机 refs）：`Liner-CAD-refs/2026-11-09-res-gaps/standards-preview/`
  - `GBT-1182-2018-产品几何技术规范（GPS）.pdf`（132 页）
  - `GBT 17851-2010 产品几何技术规范(GPS) 几何公差 基准和基准体系(PDF).pdf`（17 页）
  - `GBT-17852-2018-产品几何技术规范-几何公差 论过度公差标注.pdf`（40 页）
- 读法：PyMuPDF 逐页转图片（原生扫描分辨率，17851 放大 3×），多模态逐页读；OCR 不可用。读出的数值/条款号/陈述摘要进 `gtol.toml` 与本文件，原文与图片不入库。
- 与 GB/T 1182-2018 表 1 的对应：表 1 有 14 个特征符号、**19 个特征项目**（Position 一行含"无基准/有基准"两个 datum 子行，按 1 项计；线/面轮廓度按 Form / Orientation / Location 各出现一次）。`gtol.toml` 按 19 项录，条款号取表 1 的 Subclause 列；线/面轮廓度的方向规范行在表 1 中子条款为空，文件里注明定义见 17.6/17.7 与 B.10.3。

## 2. `gtol.toml` 的 19 项（表 1 顺序）

| # | id | 特征项目 | 类别 | 需要基准 | 条款 | 允许的被测要素 | 公差带形状 | 允许的修饰符 |
|---|---|---|---|---|---|---|---|---|
| 1 | form.straightness | 直线度 | form | no | 17.2 | line | 两平行直线 / 两平行平面 / 圆柱面(φ) | CZ SZ UF UZ ACS |
| 2 | form.flatness | 平面度 | form | no | 17.3 | surface | 两平行平面 | CZ SZ UF UZ |
| 3 | form.circularity | 圆度 | form | no | 17.4 | circle | 两同心圆（横截面内） | CZ SZ UF UZ |
| 4 | form.cylindricity | 圆柱度 | form | no | 17.5 | cylindrical_surface | 两同轴圆柱面 | CZ SZ UF UZ |
| 5 | form.profile_line | 线轮廓度 | form | no | 17.6 | line | 两等距包络线（圆）/ 包络圆管(φ) | CZ SZ UF UZ OZ VA |
| 6 | form.profile_surface | 面轮廓度 | form | no | 17.8 | surface | 两等距包络面（球） | CZ SZ UF UZ OZ VA |
| 7 | orientation.parallelism | 平行度 | orientation | yes | 17.10 | line / surface | 两平行平面 / 圆柱面(φ) | CZ SZ UF UZ >< |
| 8 | orientation.perpendicularity | 垂直度 | orientation | yes | 17.11 | line / surface | 两平行平面 / 圆柱面(φ) | CZ SZ UF UZ >< |
| 9 | orientation.angularity | 倾斜度 | orientation | yes | 17.12 | line / surface | 两平行平面 / 圆柱面(φ) | CZ SZ UF UZ >< |
| 10 | orientation.profile_line | 线轮廓度 | orientation | yes | 17.6/17.7 | line | 两等距包络线 | CZ SZ UF UZ OZ VA >< |
| 11 | orientation.profile_surface | 面轮廓度 | orientation | yes | 17.8 | surface | 两等距包络面 | CZ SZ UF UZ OZ VA >< |
| 12 | location.position | 位置度 | location | optional | 17.13 | point / line / surface | 两平行平面 / 圆柱面(φ) / 球面(Sφ) | CZ SZ UF UZ ACS |
| 13 | location.concentricity | 同心度（中心点） | location | yes | 17.14.2 | derived_point | 圆(φ) | CZ SZ UF ACS |
| 14 | location.coaxiality | 同轴度（中心线） | location | yes | 17.14.3 | derived_line | 圆柱面(φ) | CZ SZ UF ACS |
| 15 | location.symmetry | 对称度 | location | yes | 17.15 | point / line / plane | 两平行平面 | CZ SZ UF ACS |
| 16 | location.profile_line | 线轮廓度 | location | yes | 17.7 | line | 两等距包络线 | CZ SZ UF UZ OZ VA >< |
| 17 | location.profile_surface | 面轮廓度 | location | yes | 17.9 | surface | 两等距包络面 | CZ SZ UF UZ OZ VA >< |
| 18 | run-out.circular_runout | 圆跳动 | run-out | yes | 17.16 | circle | 两共面同心圆 / 两等圆 / 锥面上两不等圆 | CZ SZ UF |
| 19 | run-out.total_runout | 全跳动 | run-out | yes | 17.17 | surface | 两同轴圆柱面 / 两平行平面 | CZ SZ UF |

修饰符代码定义见 `gtol.toml` 的 `[modifiers]`。M / L / R / F 来自 GB/T 16671-2018 与 ISO 10579:2010（经 8.2.3.4 / 8.2.3.5 与表 3 引用），本卡未读这两份标准，故只写在 `[modifiers]`、不逐项列入每行。

## 3. T.syntax 可判定的条文（草稿）

| 条款 | 陈述摘要 | 建议规则 |
|---|---|---|
| 表 1（Datum needed 列）；17.2-17.5 | 形状公差（直线度、平面度、圆度、圆柱度）不需要基准 | 形状特征带 datum → error |
| 表 1；17.10-17.17、17.14、17.15 | 方向、位置（有基准）、同轴/同心、对称、跳动需要基准 | 这些特征无 datum → error |
| 表 1 位置度两行；17.13 | 位置度可以无基准（表 1 子条款列印 "b"，脚注未读到） | position 无 datum → 暂不判 error（待脚注原文） |
| 17.6、17.8 / 17.7、17.9 / B.10.3 | 线、面轮廓度：不相关（form）时不能带基准；方向规范用 >< + TED 角度；位置规范至少一个基准 | profile：有 datum 但无 >< 且无位置约束时按位置规范检查；form 用法带 datum → error |
| 7.4；17.2 图 94/95；17.13.2；17.14.2 | 圆柱面/圆/球公差带要求公差值前注 φ / Sφ | zone 为 cylinder/circle/sphere 时缺 φ/Sφ → error |
| 8.2.3.1.2；17852-2018 5.1 | 多个要素时缺省独立公差带；用 CZ/SZ 标明组合/独立；全周/全表面应与 UF、CZ 或 SZ 组合 | 多要素 + 全周/全表面但无 UF/CZ/SZ → warn（原文为"应"） |
| 8.2.3.1.3 | UZ 仅可用于组成要素；与位置度组合时只用于平面要素 | UZ + 导出要素，或 position + UZ 非平面 → error |
| 8.2.3.1.4.1、8.2.3.1.4.2 | OZ / VA 用于轮廓度，以表明 TEF 的尺寸/角度未固定；VA 常与另一规范组合 | OZ/VA 用于非轮廓度 → warn/error |
| 8.2.3.1.4.3 | >< 仅约束方向，不约束平移；通常可用平行度代替 | >< 用于形状/跳动 → warn |
| 8.2.3.4；表 3 | M、L、R 的用法在 GB/T 16671-2018，本卡未读 | 暂只提示"见 GB/T 16671"（不判） |
| 8.2.3.5；表 3 | F（自由状态）在 ISO 10579:2010，本卡未读 | 暂不判 |

## 4. T.target 可判定的条文（草稿）

| 条款 | 陈述摘要 | 建议规则 |
|---|---|---|
| 17.4、17.5 | 圆度、圆柱度的被测要素是**组成要素** | target=导出要素 → error |
| 17.16.1、17.17.1 | 圆跳动、全跳动的被测要素是组成要素 | 同上 |
| 17.14.1 | 同心度/同轴度的被测要素是导出要素（点或直线） | target=组成要素 → error |
| 17.2、17.3、17.6-17.13、17.15 | 被测要素可以是组成要素或导出要素（形状分别按特征限定） | 其它组合 → 按表按条款判 |
| B.10.4；17.14.1；17.15.1 | 同轴/同心缺省为线要素（除非 ACS）；位置度、对称度缺省为面要素（除非相交平面框格） | 多可能而未标 ACS/相交平面 → warn |
| 6（p.8-10）；17.14.1 | 导出要素标注：用参照线连到尺寸延长线，或回转体上用 Ⓐ（中心要素）修饰符；Ⓐ 只可用于回转体 | 导出要素标注未按规则 → warn |
| B.10.6；8.4.2 | ACS 仅当被测要素的导出要素是线要素时可用 | ACS + 非线导出要素 → error |
| 17852-2018 5.2.2 | 线轮廓度的被测要素：导出要素，或已标识组成/导出面上规定方向/位置的线要素；面轮廓度可为组成或导出要素 | 线轮廓度 target 非线要素 → error |
| 17.13.1；17852-2018 | 位置度的导出曲线/导出曲面见 GB/T 17852 | 仅提示 |

## 5. T.hier 可判定的条文（草稿）

| 条款 | 陈述摘要 | 建议规则 |
|---|---|---|
| GB/T 17851-2010 6.3.3 | 基准体系由 2-3 个要素建立时，基准代号字母按**优先顺序**填在公差框格第三格到第五格；第一个为第一基准、第二个为第二基准、第三个为第三基准；标注顺序对实际控制结果影响很大 | 基准超过 3 个 → error；基准字母顺序重复/未定义 → error |
| GB/T 17851-2010 6.3.3 | 三基面体系中需用基准目标时：第一基准 3 个、第二基准 2 个、第三基准 1 个 | 基准目标数量不符 → warn |
| GB/T 17851-2010 6.3.2 | 公共基准用短划线分开的字母标出（A-B） | 公共基准写法 → 已在 pmi 解析 |
| GB/T 17851-2010 6.2 注 2 | 建议不要用 I、O、Q、X 作基准字母 | 已由 `res.datum_excluded` + `datum_letter` 规则实现 |
| GB/T 1182-2018 8.2.4 | 基准与基准标注信息见 GB/T 17851 | 引用依据 |
| GB/T 1182-2018 17.10.4 等 | 定向平面框格可指定辅助基准（如"基准 B 为基准 A 的辅助基准"） | 辅助基准关系检查（E4 可选） |

## 6. 未读到的部分（`gtol.toml` [meta].unread / pending 同步记录）

- GB/T 1182-2018：表 1 位置度"无基准"行的脚注（子条款列印 "b"）在扫描页未找到；第 9 章附加标注（9.1.2 全周/全表面、9.1.3 局部区域、9.1.4 区间符号）；第 10 章 TED；第 11 章局部规范；第 12-16 章辅助框格；附录 A、C、D、E、F；第 8 章 p.25-27、p.30-32。
- GB/T 17851-2010：第 4、5 章只读了部分（表 1 已读）；第 7 章基准目标、第 8 章三基面体系未读；6.2 条文字取自用户 2026-11-10 提供的页面图，未从 PDF 复读。
- GB/T 17852-2018：5.1、5.2.1-5.2.3 已读；5.2 的规则 D-H、附录 A、附录 B（16 个轮廓度示例）未读。
- 交叉引用未读：GB/T 16671-2018（M/L/R）、ISO 10579:2010（F）、ISO 1101:2017 原文（GB/T 1182-2018 为修改采用，页边竖线标出的技术差异未逐条分析）、GB/T 4249-2018、GB/T 13319-2020。
- 表 1 的计数：14 个特征符号、20 个规格行；本文件按 19 个特征项目录（Position 两个 datum 子行合并为 1 项）。若 E4 需要 20 行，请先与原标准核对。

## 7. 待用户项

1. 表 1 位置度"无基准"行的脚注 b 原文。
2. GB/T 16671-2018 与 ISO 10579:2010 原文（M/L/R/F 的逐特征适用性）。
3. GB/T 1182-2018 第 9 章附加标注（全周/全表面与 UF/CZ/SZ 组合的规则）——用于 E4 的 T.syntax 补充。
