# expect.py 约束与 L2 期望（E3）

命令：

    uv run python evals/expect_mutation.py --out docs/milestones/v0.1.1/evidence/expect-mutation.md
    uv run python evals/run.py --save-baseline evals/baseline.json

## 设计

- `src/linercad/expect.py`：声明式约束（feature/dim/datum/gtol/rough/note/view/any_of；must/should 两档），按几何签名匹配（直径值、配合代号、PMI 内容），不依赖元素 ID。
- `evals/L2/*/expect.py`：20 个 L2 用例各一个 expect.py（8–11 行），对参考图全部通过；进入向量：expect_dim→D，expect_datum/gtol/rough/note→T，expect_view→G。
- `evals/expect_mutation.py`：独立小变异算子——删除一个必需尺寸的覆盖（同一值的所有尺寸）、把配合代号改错；检出即证明 expect 生效。

## 20 个 L2 用例的 expect 与变异

| 用例 | 参考图 expect | 变异 | 检出 | 检出率 |
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

- 参考图 expect 通过：**20/20**（188 checks，0 violations，见 baseline.expect）
- 变异检出：**39/39（100%）**；删尺寸与改配合两类算子均覆盖。

## 分数向量与 baseline 变化

| 指标 | E3 前 baseline | E3 后 baseline | 说明 |
|---|---|---|---|
| expect | — | cases 20 / checks 188 / violations 0 / pass_rate 1.0 | 新增 expect 汇总 |
| G opportunities | 4417 | 4469 | +52 = expect_view（should 档） |
| D opportunities / score | 2830 / 0.965724 | 2896 / 0.986878 | +66 = expect_dim；D 违规 97→38 来自当前 main 的 D2/D3 排布修复（本 PR 未改 layout/place），非 expect 放水 |
| T opportunities | 247 | 317 | +70 = expect_datum/gtol/rough/note |
| A | null | null | 无变化 |

说明：expect 约束全部 must 时影响 pass/error；must=False 的 should 约束同样计机会、失败只记 warn（不降低 pass，也不虚增违规）。baseline 重新生成于当前 main；D 族提升非本 PR 改动，已在此明示。
