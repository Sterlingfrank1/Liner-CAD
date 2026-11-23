# 规则变异报告（E2：检出率 / 误报率）

命令：uv run python evals/mutate.py

- 规则数：37；变异数：39；检出：39；检出率：1.0；参考图误报：0；跳过用例：0；债务冻结精确：True
- 冻结已知债务（E5 排布 + 径向引线交叉现存违规）：38 条，分布在 12 个参考图；变异框架把已知债务算真阳性

## 覆盖边界（已知盲区，明示不静默）

- place_dim_cross 只判尺寸线×尺寸线（frame 与 leader 的尺寸线），不判尺寸界线、中心线。
- place_dim_outline 只判 frame 型尺寸线×轮廓；leader 型整体不判（引线本来要穿过轮廓到要素）。
- place_ext_line 只判尺寸界线自身的超出 / 起点 / 穿越轮廓。
- place_leader_cross（E2）只判径向引线×其它尺寸线/引线；径向引线×尺寸界线、×中心线、×轮廓未计量。

### 与 place_dim_cross 的已知重叠计账（明示，不隐藏）

place_leader_cross 是径向引线专用子规则；place_dim_cross 本就判 leader 型尺寸线，因此同一批径向引线×尺寸线的物理交叉被两条规则各计一次：族分数对同一物理交叉计双次，E2 的 D 违规 77→97 中的 +20 即此。这是按规则族划分的已知重叠，不是隐藏或口径错误。

- 这些盲区中，D1 在 layout 放置阶段用 placement.resolved 的 crossings / violations / corridors（with + kind：overlap / cross / coincide / outline）记录可避免交叉并写进 reason；残余不可避免者由 E2 的 warn 规则承接；把引线扩到尺寸界线 / 中心线 / 轮廓属 D2 或 place 子规则扩展，另卡处理。
- 另注：D1 evidence 把残余的 outline 交叉也写成由 E2 承接；place_leader_cross 实际只覆盖 引线×尺寸线/引线，引线×轮廓仍无 warn 规则承接，该措辞由 lead 在 F1 docs PR 统一勘正。

## baseline 变更（新增项，不是退化）

| 族 | E5 基线 | E2 基线 | 变化 | 来源 |
|---|---|---|---|---|
| G | 1.0 (4417/0) | 1.0 (4469/0) | +52 机会 / +0 违规 | E3 expect_view +52 |
| D | 0.972252 (2775/77) | 0.986906 (2902/38) | +127 机会 / +-39 违规 | E3 expect_dim +72；违规 97→38 来自 D2/D3 排布修复，不是新规则放宽 |
| T | 1.0 (321/0) | 1.0 (403/0) | +82 机会 / +0 违规 | E3 expect +74；E4 T.syntax/T.target/T.hier +83 |

原 34 条规则没有新增违规（E5 的 77 条债务不变），新增的 20 条来自 place_leader_cross；G/T 仍 1.0，D 的下降全部来自新增规则的已知真阳性（同时冻结进 evals/known-debt.json）。

| 规则 | 参考图机会 | 变异基座机会 | 变异 | 检出 | 检出率 | 误报 | 基线 |
|---|---|---|---|---|---|---|---|
| center_mark | 73 | 1 | 1 | 1 | 100% | 0 | L1/spline_6x23x26x6 |
| chain_limit | 0 | 1 | 1 | 1 | 100% | 0 | fixture:chain_limit |
| closed_loop | 215 | 3 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| conv_dim | 33 | 1 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| datum_letter | 19 | 1 | 1 | 1 | 100% | 0 | L2/disc/bearing_cap |
| dev_order | 52 | 2 | 1 | 1 | 100% | 0 | L1/keyway_d28 |
| duplicate | 247 | 2 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| general_tol | 40 | 1 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| gtol_hier | 0 | 1 | 1 | 1 | 100% | 0 | fixture:gtol_hier |
| gtol_syntax | 59 | 8 | 1 | 1 | 100% | 0 | L2/disc/bearing_cap |
| gtol_target | 51 | 6 | 1 | 1 | 100% | 0 | L2/disc/bearing_cap |
| line_width | 400 | 10 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| missing | 30 | 1 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| out_of_frame | 2136 | 19 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| overlap | 809 | 9 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| param_cover | 219 | 16 | 1 | 1 | 100% | 0 | L2/box/bearing_seat |
| place_arrow | 373 | 5 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_balloon_align | 0 | 1 | 1 | 1 | 100% | 0 | fixture:place_balloon_align |
| place_balloon_cross | 0 | 2 | 1 | 1 | 100% | 0 | fixture:place_balloon_cross |
| place_balloon_spacing | 0 | 1 | 1 | 1 | 100% | 0 | fixture:place_balloon_spacing |
| place_dim_cross | 365 | 2 | 1 | 1 | 100% | 0 | fixture:place_dim_cross |
| place_dim_outline | 287 | 4 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_ext_line | 245 | 3 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_leader_cross | 55 | 2 | 3 | 3 | 100% | 0 | L2/disc/gear_blank |
| place_nesting | 72 | 1 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_row_spacing | 72 | 1 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_text_direction | 285 | 4 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_text_overlap | 365 | 5 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| rough_default | 20 | 1 | 1 | 1 | 100% | 0 | L2/box/bearing_seat |
| rough_fit | 25 | 1 | 1 | 1 | 100% | 0 | L2/box/bearing_seat |
| rough_syntax | 63 | 2 | 1 | 1 | 100% | 0 | L2/box/bearing_seat |
| scale | 41 | 1 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| section_ref | 30 | 2 | 1 | 1 | 100% | 0 | L1/keyway_d28 |
| sheet | 40 | 1 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| stale_op | 0 | 1 | 1 | 1 | 100% | 0 | fixture:stale_op |
| text_height | 809 | 9 | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| view_align | 46 | 1 | 1 | 1 | 100% | 0 | L1/spline_6x23x26x6 |
