# L2 expect 变异报告（E3）

命令：uv run python evals/expect_mutation.py --out <file>

| 用例 | expect 通过 | 变异 | 检出 | 检出率 |
|---|---|---|---|---|
| L2/box/bearing_seat | 是 | 2 | 2 | 100% |
| L2/box/box_cover | 是 | 2 | 2 | 100% |
| L2/box/gear_pump_body | 是 | 2 | 2 | 100% |
| L2/box/gearbox_base | 是 | 2 | 2 | 100% |
| L2/box/valve_body | 是 | 2 | 2 | 100% |
| L2/disc/bearing_cap | 是 | 2 | 2 | 100% |
| L2/disc/end_cover | 是 | 2 | 2 | 100% |
| L2/disc/flange | 是 | 2 | 2 | 100% |
| L2/disc/gear_blank | 是 | 2 | 2 | 100% |
| L2/disc/pulley | 是 | 2 | 2 | 100% |
| L2/fork/angle_bracket | 是 | 1 | 1 | 100% |
| L2/fork/bearing_support | 是 | 2 | 2 | 100% |
| L2/fork/clevis | 是 | 2 | 2 | 100% |
| L2/fork/link | 是 | 2 | 2 | 100% |
| L2/fork/shift_fork | 是 | 2 | 2 | 100% |
| L2/shaft/pump_shaft | 是 | 2 | 2 | 100% |
| L2/shaft/shaft | 是 | 2 | 2 | 100% |
| L2/shaft/sleeve | 是 | 2 | 2 | 100% |
| L2/shaft/spacer | 是 | 2 | 2 | 100% |
| L2/shaft/spline_shaft | 是 | 2 | 2 | 100% |

- 参考图 expect 通过：20/20
- 变异检出：39/39（100%）

变异算子：删除一个必需尺寸的全部覆盖（同一值的所有尺寸）；把配合代号改错（整图 fit 统一改成不同的代号）。
