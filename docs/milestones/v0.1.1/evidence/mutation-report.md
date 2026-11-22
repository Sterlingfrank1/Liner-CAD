# 规则变异报告（E2：检出率 / 误报率）

命令：uv run python evals/mutate.py

- 规则数：35；变异数：35；检出：35；检出率：1.0；参考图误报：0；跳过用例：0；债务冻结精确：True
- 冻结已知债务（E5 排布 + 径向引线交叉现存违规）：97 条，分布在 20 个参考图；变异框架把已知债务算真阳性

## baseline 变更（新增项，不是退化）

| 族 | E5 基线 | E2 基线 | 变化 | 来源 |
|---|---|---|---|---|
| G | 1.0 (4417/0) | 1.0 (4417/0) | +0 机会 / +0 违规 | 不变 |
| D | 0.972252 (2775/77) | 0.965724 (2830/97) | +55 机会 / +20 违规 | 新增 place_leader_cross 规则的 20 条真实交叉 |
| T | 1.0 (247/0) | 1.0 (247/0) | +0 机会 / +0 违规 | 不变 |

原 34 条规则没有新增违规（E5 的 77 条债务不变），新增的 20 条来自 place_leader_cross；G/T 仍 1.0，D 的下降全部来自新增规则的已知真阳性（同时冻结进 evals/known-debt.json）。

| 规则 | 参考图机会 | 变异基座机会 | 变异 | 检出 | 检出率 | 误报 | 基线 |
|---|---|---|---|---|---|---|---|
| center_mark | 73 | — | 1 | 1 | 100% | 0 | L1/spline_6x23x26x6 |
| chain_limit | 0 | 1 | 1 | 1 | 100% | 0 | fixture:chain_limit |
| closed_loop | 215 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| conv_dim | 33 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| datum_letter | 19 | — | 1 | 1 | 100% | 0 | L2/disc/bearing_cap |
| dev_order | 52 | — | 1 | 1 | 100% | 0 | L1/keyway_d28 |
| duplicate | 247 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| general_tol | 40 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| gtol_syntax | 28 | — | 1 | 1 | 100% | 0 | L2/disc/bearing_cap |
| line_width | 400 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| missing | 30 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| out_of_frame | 2136 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| overlap | 809 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| param_cover | 219 | — | 1 | 1 | 100% | 0 | L2/box/bearing_seat |
| place_arrow | 373 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_balloon_align | 0 | 1 | 1 | 1 | 100% | 0 | fixture:place_balloon_align |
| place_balloon_cross | 0 | 2 | 1 | 1 | 100% | 0 | fixture:place_balloon_cross |
| place_balloon_spacing | 0 | 1 | 1 | 1 | 100% | 0 | fixture:place_balloon_spacing |
| place_dim_cross | 365 | 2 | 1 | 1 | 100% | 0 | fixture:place_dim_cross |
| place_dim_outline | 287 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_ext_line | 245 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_leader_cross | 55 | — | 1 | 1 | 100% | 0 | L2/disc/gear_blank |
| place_nesting | 72 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_row_spacing | 72 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_text_direction | 285 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| place_text_overlap | 365 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| rough_default | 20 | — | 1 | 1 | 100% | 0 | L2/box/bearing_seat |
| rough_fit | 25 | — | 1 | 1 | 100% | 0 | L2/box/bearing_seat |
| rough_syntax | 63 | — | 1 | 1 | 100% | 0 | L2/box/bearing_seat |
| scale | 41 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| section_ref | 30 | — | 1 | 1 | 100% | 0 | L1/keyway_d28 |
| sheet | 40 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| stale_op | 0 | 1 | 1 | 1 | 100% | 0 | fixture:stale_op |
| text_height | 809 | — | 1 | 1 | 100% | 0 | L1/thread_ext_M20 |
| view_align | 46 | — | 1 | 1 | 100% | 0 | L1/spline_6x23x26x6 |

