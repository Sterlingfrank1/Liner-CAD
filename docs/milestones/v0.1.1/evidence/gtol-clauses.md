# GB/T 1182 / 17851 / 17852 条文草稿（A4 → E4 输入）

卡 A4（issue #93）· 2026-11-21 · 数据文件 `src/linercad/res/gtol.toml`，接口 `res.gtol_rows()` / `res.gtol(char)`

## 1. 来源与读法

- 原文（**不入库**，本机 refs）：`Liner-CAD-refs/2026-11-09-res-gaps/standards-preview/`
  - `GBT-1182-2018-产品几何技术规范（GPS）.pdf`（132 页）
  - `GBT 17851-2010 产品几何技术规范(GPS) 几何公差 基准和基准体系(PDF).pdf`（17 页）
  - `GBT-17852-2018-产品几何技术规范-几何公差 论过度公差标注.pdf`（40 页）
- 读法：PyMuPDF 逐页转图片（原生扫描分辨率，17851 放大 3×），多模态逐页读；本机无 OCR。读出的条款号 / 数值 / 陈述摘要进 `gtol.toml` 与本文件，原文与图片不入库。
- 表 1 的计数：14 个特征符号、**19 个特征项目**（Position 一行含"无基准/有基准"两个 datum 子行，按 1 项计；线轮廓度 / 面轮廓度按 Form、Orientation、Location 各出现一次）。`gtol.toml` 按 19 项录，条款号取表 1 的 Subclause 列；方向规范的两行在表 1 中子条款为空，文件里注明：线轮廓度定义见 17.6 / 17.7，面轮廓度定义见 17.8 / 17.9，方向用法见 B.10.3。

## 2. `gtol.toml` 的 19 项（表 1 顺序）

每行都有 `clause`（条款号）、`targets`（被测要素种类）、`target_natures`（integral = 组成要素 / derived = 导出要素）、`zone_shapes`（公差带形状）、`modifiers`（无条件可用：CZ / SZ / UF）、`modifier_conditions`（带条件的修饰符：symbol + when + clause，when 词表见文件 `[conditions]`）与 `modifiers_unverified`（交叉引用标准里、本卡未提取的 M / L / R / F）。

| # | id | 特征项目 | 类别 | 需要基准 | 条款 | 被测要素（种类 / 性质） | 公差带形状 | 条件修饰符（symbol@when） |
|---|---|---|---|---|---|---|---|---|
| 1 | form.straightness | 直线度 | form | no | 17.2 | line / 组成或导出 | 两平行直线 / 两平行平面 / 圆柱面(φ) | UZ@integral, ACS@derived_line |
| 2 | form.flatness | 平面度 | form | no | 17.3 | surface / 组成或导出 | 两平行平面 | UZ@integral |
| 3 | form.circularity | 圆度 | form | no | 17.4 | circle / 组成 | 两同心圆（横截面内） | UZ@integral |
| 4 | form.cylindricity | 圆柱度 | form | no | 17.5 | cylindrical_surface / 组成 | 两同轴圆柱面 | UZ@integral |
| 5 | form.profile_line | 线轮廓度 | form | no | 17.6 | line / 组成或导出 | 两等距包络线（圆）/ 包络圆管(φ) | UZ@integral, OZ@profile, VA@profile_angle |
| 6 | form.profile_surface | 面轮廓度 | form | no | 17.8 | surface / 组成或导出 | 两等距包络面（球） | UZ@integral, OZ@profile, VA@profile_angle |
| 7 | orientation.parallelism | 平行度 | orientation | yes | 17.10 | line、surface / 组成或导出 | 两平行平面 / 圆柱面(φ) | UZ@integral, ><@direction_only, ACS@derived_line |
| 8 | orientation.perpendicularity | 垂直度 | orientation | yes | 17.11 | line、surface / 组成或导出 | 两平行平面 / 圆柱面(φ) | 同 7 |
| 9 | orientation.angularity | 倾斜度 | orientation | yes | 17.12 | line、surface / 组成或导出 | 两平行平面 / 圆柱面(φ) | 同 7 |
| 10 | orientation.profile_line | 线轮廓度 | orientation | yes | 17.6/17.7 | line / 组成或导出 | 两等距包络线 | UZ@integral, OZ@profile, VA@profile_angle, ><@direction_only |
| 11 | orientation.profile_surface | 面轮廓度 | orientation | yes | 17.8 | surface / 组成或导出 | 两等距包络面 | 同 10 |
| 12 | location.position | 位置度 | location | optional | 17.13 | point、line、surface / 组成或导出 | 两平行平面 / 圆柱面(φ) / 球面(Sφ) | UZ@integral_plane, ACS@derived_line, ><@direction_only |
| 13 | location.concentricity | 同心度（中心点） | location | yes | 17.14.2 | derived_point / 导出 | 圆(φ) | ACS@nominal_line_point_set |
| 14 | location.coaxiality | 同轴度（中心线） | location | yes | 17.14.3 | derived_line / 导出 | 圆柱面(φ) | ACS@derived_line |
| 15 | location.symmetry | 对称度 | location | yes | 17.15 | point、line、plane / 组成或导出 | 两平行平面 | UZ@integral, ACS@nominal_line_point_set, ACS@derived_line |
| 16 | location.profile_line | 线轮廓度 | location | yes | 17.7 | line / 组成或导出 | 两等距包络线 | UZ@integral, OZ@profile, VA@profile_angle, ><@direction_only |
| 17 | location.profile_surface | 面轮廓度 | location | yes | 17.9 | surface / 组成或导出 | 两等距包络面 | 同 16 |
| 18 | run-out.circular_runout | 圆跳动 | run-out | yes | 17.16 | circle / 组成 | 两共面同心圆 / 两等圆 / 锥面上两不等圆 | — |
| 19 | run-out.total_runout | 全跳动 | run-out | yes | 17.17 | surface / 组成 | 两同轴圆柱面 / 两平行平面 | — |

无条件修饰符 CZ / SZ / UF 对每行都成立（8.2.3.1.2、8.4.2）。修饰符代码定义见 `gtol.toml` 的 `[modifiers]`；条件代码见 `[conditions]`。M / L / R / F 来自 GB/T 16671-2018 与 ISO 10579:2010（经 8.2.3.4 / 8.2.3.5 与表 3 引用），本卡未读这两份标准，故只在 `modifiers_unverified` 里列出。

P / V / T / Q 是 8.2.3.3.2 定义的参数，不是修饰符；`pmi.py` 的旧 `MODIFIERS` 收 P / T / U 是历史遗留，见 `gtol.toml` `[meta].pmi_note` 与 `[parameters]`。对齐 `pmi.py` / 渲染留给 E4 或 F1（本卡的 res 数据已给出正确词表）。

## 3. T.syntax 可判定的条文（草稿）

定义见 `docs/proposals/benchmark-metrics.md` T.syntax：特征项目 × 基准要求 × 公差带形状 × 允许的修饰符，按 GB/T 1182 表格判。

| 条款 | 陈述摘要 | 建议规则 |
|---|---|---|
| 表 1（Datum needed 列）；17.2-17.5 | 形状公差（直线度、平面度、圆度、圆柱度）不需要基准 | 形状特征带 datum → error |
| 表 1；17.10-17.17、17.14、17.15 | 方向、位置（有基准）、同轴 / 同心、对称、跳动需要基准 | 这些特征无 datum → error |
| 表 1 位置度两行；17.13 | 位置度可以无基准（表 1 该行子条款列印 "b"，脚注未读到） | position 无 datum → 暂不判 error（待脚注原文） |
| 17.6、17.8 / 17.7、17.9 / B.10.3 | 线 / 面轮廓度：与基准不相关（form）时不能带基准；方向规范用 >< + TED 角度；位置规范至少一个基准 | profile：有基准且未标 ><、也没有位置约束 → 按位置规范检查；form 用法带基准 → error |
| 7.4；17.2 图 94/95；17.13.2；17.14.2 | 圆柱面 / 圆 / 球公差带要求公差值前注 φ / Sφ | zone 为 cylinder / circle / sphere 时缺 φ / Sφ → error |
| 8.2.3.1.2；17852-2018 5.1 | 多个要素时缺省独立公差带；用 CZ / SZ 标明组合 / 独立；全周 / 全表面应与 UF、CZ 或 SZ 组合 | 多要素 + 全周 / 全表面但无 UF / CZ / SZ → warn（原文为"应"） |
| 8.2.3.1.3 | UZ 仅可用于组成要素；与位置度组合时只用于平面要素 | UZ + 导出要素，或 position + UZ 非平面 → error（数据侧用 UZ@integral / UZ@integral_plane 判） |
| 8.2.3.1.4.1、8.2.3.1.4.2 | OZ / VA 用于轮廓度，以表明 TEF 的尺寸 / 角度未固定；VA 常与另一规范组合 | OZ / VA 用于非轮廓度 → warn / error（数据侧 OZ@profile / VA@profile_angle） |
| 8.2.3.1.4.3；B.10.3、B.10.4 | >< 仅约束方向，不约束平移；用于把位置 / 轮廓度规范标成方向规范 | >< 用于形状 / 跳动 → warn（数据侧 ><@direction_only） |
| 8.2.3.3.2 | P（峰值）、V（谷深）、T（总体范围，缺省）、Q（标准差）是参数，不是修饰符 | 把 P / V / T / Q 当修饰符 → error |
| 8.2.3.4；表 3；8.2.3.5 | M / L / R 的用法在 GB/T 16671-2018，F 在 ISO 10579:2010，本卡未读 | 只提示"见 GB/T 16671 / ISO 10579"，不判 |

## 4. T.target 可判定的条文（草稿）

定义见 `docs/proposals/benchmark-metrics.md` T.target：**引线箭头落在轮廓或界线上 = 表面；与尺寸线对齐 = 轴线 / 中心面；这个几何含义必须等于语义模型里的 target**。数据侧提供"每个特征项目允许的被测要素种类与性质"（`gtol.toml` 的 `targets` / `target_natures`）。

| 条款 | 陈述摘要 | 建议规则 |
|---|---|---|
| GB/T 1182-2018 §6（印刷页 8-10）、8.4.1 | 被测要素为组成要素时，指引线终止在轮廓或轮廓延长线上（箭头 / 圆点），或放在指引横线上指向表面；为导出要素时用参照线、终止在尺寸延长线上，或用 Ⓐ（中心要素）修饰符；Ⓐ 只可用于回转体 | 标注落点与语义 target 的 surface / axis 含义不一致 → error（T.target 主规则） |
| 表 1；17.2-17.17；B.10.2-B.10.4 | 特征项目允许的被测要素：圆度、圆柱度、圆跳动、全跳动必须是组成要素；同心度 / 同轴度必须是导出要素（点 / 直线）；位置度、对称度、轮廓度可为组成或导出 | target 的种类 / 性质不在该行的 `targets` / `target_natures` 内 → error |
| B.10.4；17.14.1 | 同轴 / 同心缺省为线要素（除非 ACS）；位置度、对称度缺省为面要素（除非相交平面框格） | 多可能而未标 ACS / 相交平面 → warn |
| B.10.6；8.4.2 | ACS 仅当被测要素的导出要素是线要素时可用 | ACS + 非线导出要素 → error（数据侧 ACS@derived_line / ACS@nominal_line_point_set） |
| 17.14.1；17.15.1；17852-2018 5.2.2 | 一组点作被测要素（同心度 / 对称度）须标 ACS 且基准为同一横截面上的点；线轮廓度的被测要素是导出线或面上已标识的线要素（位置用 TED，方向用相交平面框格） | 组合要素 / 截面标注缺失 → warn |

## 5. T.hier 可判定的条文（草稿）

定义见 `docs/proposals/benchmark-metrics.md` T.hier：**公差递进——同一要素：形状 ≤ 方向 ≤ 位置 ≤ 尺寸公差；跳动 ≥ 对应的圆度 / 同轴度**。

**声明边界（重要）：** 已读条款（§4、§6、§7、§8.2、§17.2-17.17、附录 B.8-B.10、17852-2018 §5）中没有找到一条显式的"公差递进"条款；未读章节（见 §7）也没有核过，所以只能记为"在已读条款中未找到"，不能断言标准没有。下列递进由公差带定义推得，E4 若建规则，条款依据应写"由定义推得"并注明推导：

| 条款 | 陈述摘要 | 可推得的递进 |
|---|---|---|
| 17.2-17.5；17.10-17.13；B.8 | 形状公差带为两平行平面 / 两同心圆 / 两同轴圆柱面 / 两平行直线；方向公差带是"在给定方向上"的同类区域（17.10-17.12）；位置公差带由 TED 与基准定位（17.13） | 同一要素：t_形状 ≤ t_方向 ≤ t_位置（区域包含关系） |
| 17.6-17.9；17852-2018 5.2.3 | 轮廓度公差带为直径 t 的圆 / 球的等距包络线 / 面，圆心 / 球心位于 TEF 上；form / orientation / location 的区别在 TEF 是否受基准约束（17.6-17.9、B.10.2-B.10.4） | 同一要素、同一条 TEF 定义下：t_形状轮廓 ≤ t_方向轮廓 ≤ t_位置轮廓（区域包含关系） |
| 17.16.2；17.4 | 径向圆跳动公差带 = 任一横截面内、半径差 t、圆心在基准轴线上的两同心圆；圆度 = 两同心圆（圆心为拟合中心） | 跳动 t 满足 → 圆度 ≤ t |
| 17.17.2；17.14.3 | 径向全跳动 = 半径差 t、与基准轴线同轴的两圆柱面；同轴度 = 以基准轴线为轴线的 φt 圆柱面 | 全跳动 t 满足 → 同轴度 ≤ t |
| —（未判定） | 尺寸公差与几何公差的关系涉及独立原则 GB/T 4249-2018（只读过 1182-2018 对它的引用，未读原文） | "位置 ≤ 尺寸公差"目前无法判定，不能写成规则依据 |

注意：**基准顺序不是 T.hier**（见下节"附加条文"）。

## 6. 附加条文：基准顺序 / 基准体系（不属于 T.hier，供 E4 参考）

| 条款 | 陈述摘要 | 建议规则 |
|---|---|---|
| GB/T 17851-2010 6.3.3 | 由 2-3 个要素建立基准体系时，基准代号字母按优先顺序填在公差框格第三格到第五格；第一个为第一基准、第二个为第二基准、第三个为第三基准；标注顺序对实际控制结果影响很大 | 基准超过 3 个 → error；顺序与引用不一致 → warn（规则名建议不用 T.hier） |
| GB/T 17851-2010 6.3.3 | 三基面体系需用基准目标时：第一基准 3 个、第二基准 2 个、第三基准 1 个 | 基准目标数量不符 → warn |
| GB/T 17851-2010 6.3.2 | 公共基准用短划线分开的字母标出（A-B） | 公共基准写法已在 pmi 解析 |
| GB/T 17851-2010 6.2 注 2 | 建议不要用 I、O、Q、X 作基准字母（单一谱系，`datum.toml` 的 [GB].verified = false；只是建议，规则报 warn） | 已由 `res.datum_excluded` + `datum_letter` 规则实现 |
| GB/T 1182-2018 8.2.4 | 基准与基准标注信息见 GB/T 17851 | 引用依据 |

## 7. 未读到的部分（`gtol.toml` [meta].unread / `datum.toml` [meta].unread 同步记录）

- GB/T 1182-2018：表 1 位置度"无基准"行的脚注（子条款列印 "b"）在扫描页未找到；第 9 章附加标注（9.1.2 全周 / 全表面、9.1.3 局部区域、9.1.4 区间符号）；第 10 章 TED；第 11 章局部规范；第 12-16 章辅助框格（含方向要素框格）；附录 A、C、D、E、F；第 8 章 p.25-27、p.30-32。
- GB/T 17851-2010：第 4、5 章只读了部分（表 1 已读）；第 6.2 条只从用户 2026-11-10 页面图读出，未从 PDF 复读；第 7 章基准目标、第 8 章三基面体系未读。
- GB/T 17852-2018：5.1、5.2.1-5.2.3 已读；5.2 的规则 D-H、附录 A、附录 B（16 个轮廓度示例）未读。
- 交叉引用未读：GB/T 16671-2018（M / L / R）、ISO 10579:2010（F）、ISO 1101:2017 原文（GB/T 1182-2018 为修改采用，页边竖线标出的技术差异未逐条分析）、GB/T 4249-2018、GB/T 13319-2020。
- `datum.toml` 的 `[meta].unread` 另有：ISO 5459:2011 完全未读（ISO 的 I / O / Q / X 列表来自 PTC Creo 软件规则，不是标准条文）；GB/T 17851-2010 6.2 只从用户 2026-11-10 页面图读出，未从 PDF 复读。

## 8. 待用户项 / 其它跟进

1. 表 1 位置度"无基准"行的脚注 b 原文。
2. GB/T 16671-2018 与 ISO 10579:2010 原文（M / L / R / F 的逐特征适用性）。
3. GB/T 1182-2018 第 9 章附加标注（全周 / 全表面与 UF / CZ / SZ 组合的规则）——用于 E4 的 T.syntax 补充。
4. GB/T 4249-2018（独立原则）——T.hier 的"位置 ≤ 尺寸公差"需要它才能判定。
5. `pmi.py` 的 `MODIFIERS` / 框格渲染尚未与 `gtol.toml` 词表对齐（P / T / U 是旧列表；SZ / UZ / OZ / VA / ACS / UF / >< 目前 `front.gtol` 不接受）：A4 只提供数据，留给 E4 或 F1 做（`gtol.toml` `[meta].pmi_note`）。
