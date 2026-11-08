# M0 HANDOVER：骨架 + 索引

> 里程碑会话交接。SPEC：`docs/milestones/M0/SPEC.md`；证据：`docs/milestones/M0/evidence/`。

## 1. 交付

| PR | 卡 | 内容 |
|---|---|---|
| #2 | SPEC | M0 详细设计（G1：两轮独立评审） |
| #16 | C1 | 工程骨架、`lcad` / `python -m linercad`、JSON CLI、CI（lint + ubuntu py3.11 + windows py3.13） |
| #18 | C2 | GB 标准档（数值注明标准号或 convention）、A4/A3/A2 模板、叠加机制 |
| #19 | C3 | `Param` / 参数表达式 / 安全求值 |
| #21 | C4–C7 | 元素模型与 ID、2D 几何（回转体、均布孔、中心线）、查询、标注意图、布局引擎与检查、DXF（XDATA 三级索引）与 model.json |
| #22 | C8–C10 | 动作日志记录与重放、事务（init/build/edit/undo）与 git、`lcad` 全部 M0 命令、PNG 渲染 |
| #23 | C11–C13 | 三个范例（轴、全剖法兰盘、支架）、`SKILL.md`、验收自动化测试 |

测试：516 个，全绿（本机 Windows、CI 两平台、干净 clone：`evidence/clean-clone-pytest.txt`）。

## 2. 怎么验证

```bash
git clone https://github.com/Sterlingfrank1/Liner-CAD && cd Liner-CAD && uv sync
uv run pytest -q                        # 含 tests/acceptance：三零件各 8 轮修改 + 字节级确定性
uv run lcad init /tmp/p --from flange   # 任一范例
uv run lcad -C /tmp/p render            # → /tmp/p/.linercad/tmp/render.png
```

## 3. 验收（BRIEF §3）与证据

| 项 | 结果 | 证据 |
|---|---|---|
| 1 三图出 DXF；法兰全剖，剖面线 / 剖切符号 / 剖视标注齐全 | 通过，三图零 warning | `tests/test_examples.py`；`evidence/*.png` |
| 2 每图 ≥ 5 轮对话修改（独立 agent 只拿 SKILL.md 和用户原话） | 通过：3 零件 × 8 轮，21 轮各提交一次，3 轮（按设计引用不存在的元素）回滚且无 commit，`git ls-files` 只有 4 个源文件 | `evidence/g5-*.md`（每轮的脚本、命令、JSON）、`evidence/g5-*-after-rounds.png` |
| 2b 同样的修改做成确定性测试 | 通过 | `tests/acceptance/test_rounds.py` |
| 3 只入库源文件；每轮一个 commit；失败不提交 | 通过 | 同上（每轮断言 `git ls-files` 与 commit 数） |
| 4 确定性 | 通过（DXF、model.json 字节一致，跨进程） | `test_rebuild_is_deterministic`、`test_core_regressions.py` |
| 5 出图质量评审 | 支架通过；轴 3.4、法兰 3.3 略低于 3.5，指出的图形问题已修正，其余见评审记录 | `evidence/render-review.md` |
| 6 CI、HANDOVER、tag | 本 PR + `v0.1-m0` | — |

## 4. 已知缺口

- 线性尺寸只有水平 / 竖直（对齐、角度尺寸在 M1）；公差只作文字（查表在 M1）。
- drawing.py 里**无名**几何的编号会随增删漂移，日志里引用它的操作可能指向别的边；SKILL 要求被引用的几何起名。`turned` 的边号在轮廓拓扑变化时也会变。
- 标题栏是 180×56 外形下的简化分格；企业模板导入在 M1。
- 撤销“一次撤销”不支持。
- 布局是局部规则，复杂零件仍可能需要 Agent 换侧 / 换排（引擎会给出 violations 和 corridors）。
- 出图评审的两点未改：PNG 中粗细线对比偏弱（DXF 线宽正确）；轴的 Φ 文字有的在轮廓内、有的移到外侧（引擎按冲突选位）。
- `lcad build` 的输出没有 `changed`（只有 edit 给出）；G5 agent 指出，M1 视需要补。
- G5 在 SKILL 修订前运行；它指出的 SKILL 问题（move 方向约定、`at` 角度约定、`place` 保留未给字段、`--focus` 文件名、Windows UTF-8）已在 #23 修正，修正后的 SKILL 未再跑一遍 G5。

## 5. 偏离与决定

见 SPEC §15（偏离）和 §2（决定）。实现中新增的决定：
- 非 ASCII 字符（Φ × ± 等）在 simfang 中为全角，字宽按全角估算；ASCII 系数 0.732（实测 0.7314 向上取整）。
- 中心线：直线中心线整段写出并按长度设线型比例（首末为长画）；十字中心线、均布孔径向中心线从中心向外分段（交点为长画）。
- ruff 忽略 B904 / B905 / E501（行长交给 formatter），不对 `*.md` 运行。
- 流程按 ROADMAP §4.1–4.2 精简：C4–C7、C8–C10、C11–C13 各合并为一个 PR；核心两段各一轮独立评审。

## 6. 待用户人工评审

- 三张范例图的出图质量（`evidence/*.png`；多模态评审结论见 `evidence/render-review.md`）。
- 简化标题栏分格是否可接受（M1 做 GB/T 10609.1 完整版）。

## 7. 给 M1 的说明

- 尺寸 / 公差 / 基准意图已经是独立字段（`value / expr / tol / datum / refs`），M1 做配合查表与形位公差时继续保持语义化（v0.2 要输出 STEP AP242 PMI，见 ROADMAP §6）。
- 扩展规定画法：在 `geometry.py` 加特征级工具（如螺纹、键槽），标注在 `annotate.py`，布局在 `layout.py` 的候选机制上加。
- 检查规则在 `checks.py`，结构 `{rule, severity, id, violations, corridors, std}`；Checks v1 按 DESIGN §4.5 扩充。
- `lcad` 的 JSON 契约与错误 code 已在 SKILL.md 公开，改动需同步。
