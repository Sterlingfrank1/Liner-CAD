# GB/T 1182-2018 形位公差条款覆盖率（E4）

命令：uv run python evals/gtol_coverage.py --out <this file>

- 数据源：src/linercad/res/gtol.toml（A4；自记 verified=False，只读到一份 PDF 谱系）
- 表1 行覆盖率：**19/19 = 100%**
- 表1 子条款号：18 个（17.10、17.11、17.12、17.13、17.14.2、17.14.3、17.15、17.16、17.17、17.2、17.3、17.4、17.5、17.6、17.6/17.7、17.7、17.8、17.9）
- clause_refs：23 个（17.10、17.11、17.12、17.13、17.14、17.15、17.16、17.17、17.2、17.3、17.4、17.5、17.6、17.7、17.8、17.9、8.2.3.1.3、8.2.3.1.4.3、B.10.2、B.10.3、B.10.4、B.10.6、B.8）

## 三条规则与 catalog 条款

| 规则 | benchmark | 条款（catalog） | 条款状态 | 规则状态 |
|---|---|---|---|---|
| gtol_syntax | T.syntax | GB/T 1182-2018 表1；7.4；8.2.4 | read | done |
| gtol_target | T.target | GB/T 1182-2018 表1；17.2-17.17；B.10 | read | done |
| gtol_hier | T.hier | GB/T 4249-2018 | pending | done |

## 表1 逐行覆盖（19 行）

| 行 | 特征项目 | 表1 子条款 | T.syntax 数据 | T.target 数据 | T.hier 类别 |
|---|---|---|---|---|---|
| form.straightness | straightness | 17.2 | 是 | 是 | 是 |
| form.flatness | flatness | 17.3 | 是 | 是 | 是 |
| form.circularity | circularity | 17.4 | 是 | 是 | 是 |
| form.cylindricity | cylindricity | 17.5 | 是 | 是 | 是 |
| form.profile_line | profile_line | 17.6 | 是 | 是 | 是 |
| form.profile_surface | profile_surface | 17.8 | 是 | 是 | 是 |
| orientation.parallelism | parallelism | 17.10 | 是 | 是 | 是 |
| orientation.perpendicularity | perpendicularity | 17.11 | 是 | 是 | 是 |
| orientation.angularity | angularity | 17.12 | 是 | 是 | 是 |
| orientation.profile_line | profile_line | 17.6/17.7 | 是 | 是 | 是 |
| orientation.profile_surface | profile_surface | 17.8 | 是 | 是 | 是 |
| location.position | position | 17.13 | 是 | 是 | 是 |
| location.concentricity | concentricity | 17.14.2 | 是 | 是 | 是 |
| location.coaxiality | concentricity | 17.14.3 | 是 | 是 | 是 |
| location.symmetry | symmetry | 17.15 | 是 | 是 | 是 |
| location.profile_line | profile_line | 17.7 | 是 | 是 | 是 |
| location.profile_surface | profile_surface | 17.9 | 是 | 是 | 是 |
| run-out.circular_runout | circular_runout | 17.16 | 是 | 是 | 是 |
| run-out.total_runout | total_runout | 17.17 | 是 | 是 | 是 |

## 说明

- T.syntax 按行数据判：基准有无（datum）、公差带形状（zone_shapes）、修饰符（modifiers / modifier_conditions）、轴线 + 圆柱带的 Φ、基准引用已定义；
- T.target 按行数据判：被测要素 targets / target_natures（形状类要素进一步按引用几何约束），基准 target 字段与引用几何一致；
- T.hier 按行 category 判形状/方向/位置递进与跳动≥对应圆度/同轴度；尺寸公差与几何公差的比较未判（gtol-clauses.md 记录 GB/T 4249-2018 原文未读，catalog 条款状态 pending）；
- 未读条款（A4 meta.unread：1182 第9章、17851 部分、17852 规则 D-H 等）不在本报告声称覆盖；M/L/R/F 等来自未读标准的修饰符按 modifiers_unverified 报为不可判。


## E4 规则读数（参考图 / 变异 / baseline）

| 项 | 数值 |
|---|---|
| 参考图 T.syntax 机会 / 违规 | 59 / 0 |
| 参考图 T.target 机会 / 违规 | 51 / 0 |
| 参考图 T.hier 机会 / 违规 | 1 / 0 |
| 变异（E2 框架，全规则） | 39/39 检出（100%），误报 0，known-debt exact |
| baseline T 族 | 机会 321 → 403（+82），违规 0，分数 1.0；--baseline regressions [] |

baseline 由 evals/run.py --save-baseline evals/baseline.json 重新生成；新增项仅为三条规则机会数，违规/分数/40 例未变。
