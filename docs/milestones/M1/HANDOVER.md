# M1 HANDOVER：专业深度（轴套类、盘盖类）

> SPEC：`docs/milestones/M1/SPEC.md`；证据：`docs/milestones/M1/evidence/`。

## 1. 交付

| PR | 卡 | 内容 |
|---|---|---|
| #26 | SPEC | 详细设计（G1：独立评审一轮，20 条意见已处理） |
| #38 | C1 | 资源库 `linercad.res`：ISO 286 / GB/T 1800 配合（IT1–18、轴 a–u、孔按规则推导）、GB/T 1804 未注公差、普通螺纹与公差带、GB/T 1095 键、GB/T 1144 矩形花键、基准字母、Ra 优选系列 |
| #39 | C2–C5、C7、C8 | 视图机制（任意折线剖切、移出断面、局部放大、斜视图、回转体全剖 / 半剖 / 轴向孔 / 退刀槽 / 轮毂键槽、波浪线、重合断面）；语义 PMI（结构化公差三种注法、对齐 / 角度 / 倒角尺寸、基准、形位公差、粗糙度、尺寸链、未注公差）；规定画法（螺纹、螺孔、中心孔、键槽、花键及代号尺寸）；M0 遗留；Checks v1 五个规则包 + `lcad check` / `lcad skill`；HLR、几何对照、评测运行器、CI 3d job。G4 独立评审一轮，7 条已修 |
| #40 | C6 | ISO 档（`extends = "GB"`）、第一 / 第三角及投影符号、GB/T 10609.1 完整标题栏、ISO 7200 标题栏、`lcad template import` + `overlay=` 企业档 |
| #41、#43 | C9、C10 | 轴套类、盘盖类卡片；范例 shaft / sleeve / spline_shaft / flange / end_cover / pulley；L2 各 5 个零件（req + build123d 模型 + 参考图）；L1 20 个用例 |
| #42、本 PR | — | 键槽尺寸关联、引线式尺寸不能作被测要素、圆特征上的 PMI 锚点、同轴度 / 位置度缺 Φ 检查；G5 证据与本交接 |

测试：822 个（干净 clone，`uv sync --extra 3d`）全部通过；评测 30 / 30 通过（零 error、零 warning、几何对照双向覆盖率 1.0）。

## 2. 怎么验证

```bash
git clone https://github.com/Sterlingfrank1/Liner-CAD && cd Liner-CAD && uv sync --extra 3d
uv run pytest -q
uv run python evals/run.py                 # → report.json；--level L1|L2，--case <id>，--drawings <Agent 产出目录>
uv run lcad init /tmp/p --from shaft       # 其它范例：sleeve spline_shaft flange end_cover pulley bracket
uv run lcad -C /tmp/p check                # 按规则包列出检查结果
uv run lcad skill shaft                    # 零件族卡片（shaft / disc）
```

## 3. 验收（BRIEF §3）与证据

| 项 | 结果 | 证据 |
|---|---|---|
| 1 覆盖 | 两族 L2 共 10 个参考图零 error 零 warning，几何对照全部通过；每族 3 个范例 | `evidence/clean-clone.md`；`tests/test_evals.py`（CI test-3d） |
| 2 Agent 实测 | 独立 agent（Sonnet，只用 `lcad skill` 和 req.md）从零画 4 个 L2 零件（每族 2 个），初稿全部零 error、零 warning，**与 3D 模型几何对照双向 1.0**；随后每件 4 轮修改，全部完成且零 error | `evidence/g5-*.md`、`evidence/g5-initial-drawings-report.json`；下表 |
| 3 标准档 | 同一 drawing.py 以 GB / ISO 出图均零 error；企业档叠加后其做法不报违规，不叠加则报 | `tests/test_std_profiles.py`；`evidence/flange.png` / `flange_iso.png` |
| 4 规定画法 | 第一批每项都有 L1（螺纹内外、螺孔与钻尖、中心孔、退刀槽、轴 / 轮毂键槽、花键；另有半剖、阶梯剖、旋转剖），全部通过 | `evals/L1/`、`evidence/clean-clone.md` |
| 5 PMI 语义 | `model.json` 中 tolerance / datum / gtol / rough / chain 分字段、`refs` 指向被测几何（命名边或尺寸），参数变化后重查 | `tests/test_pmi.py` |
| 6 出图评审 | 独立多模态 agent 按评分表评 8 张（6 个新范例、支架、法兰 ISO 版）：全部通过（无低于 3 分项，均分 3.57–4.00），5 张在边缘 | `evidence/render-review.md` |
| 7 | CI 绿、本 HANDOVER 合并、tag `v0.1-m1` | — |

Agent 实测基线（v0.2 大规模评测的起点）：

| 零件 | 初稿构建次数（失败） | 第 1–4 轮各提交数 | 最终 |
|---|---|---|---|
| shaft/pump_shaft | 5（4 次修问题） | 2 / 8 / 1 / 3 | 0 error，1 个有理由的 accept |
| shaft/spacer | 3（2 次 `ok:false`） | 1 / 1 / 1 / 1 | 0 / 0 |
| disc/gear_blank | 3（1 次 `ok:false`） | 1 / 1 / 1 / 1 | 0 / 0 |
| disc/bearing_cap | 2 | 1 / 1 / 1 / 1 | 0 / 0 |

一次通过率（初稿零 finding 且无失败构建）0 / 4；13 / 16 轮一次提交完成。pump_shaft 第 2 轮（加垂直度框格）布局反复 8 次——形位公差框格在台阶面附近的自动避让是当前最弱项。

## 4. 已知缺口

- **资源库**：GB/T 3 退刀槽、GB/T 6403.5 越程槽、B 型中心孔未录（没有可核对的公开数据；退刀槽尺寸按设计给出）；Ra 只录优选系列（`rough_syntax` 因此只报 warn）；基准字母 ISO 集合出处为厂商文档；配合缺 j、v–zc。
- **布局**：形位公差框格、粗糙度引线在拥挤处仍会与尺寸线 / 延伸线交叉（评审第 1、6、11、12 条）；指定 `row` 的尺寸不会自动按“小内大外”调整（评审第 3、4 条）。
- **检查**：`text_30` 未实现；跨视图重复尺寸不查；`missing` 只查回转体轴向台阶。
- **画法与工具**：内孔沟槽、内倒角没有专用工具；`thread_end` 无深度，均布螺孔要逐个标代号或 accept；`turned` 的 bore 点不能命名、端面没有名字（用 `d.q` 选）；剖视里孔面的粗糙度直接标注会落在材料侧（用 `ref=尺寸`）；阶梯剖 / 旋转剖没有几何对照模式（L1 用等效模型）。
- **CLI**：构建失败时 `lcad context` 不可用；`lcad edit` 有 warning 也提交（按 DESIGN 设计，warning 不阻断），Agent 实测里出现“一轮多次提交”。
- **标题栏**：GB/T 10609.1 各区内的行分配、投影符号比例按通行做法，未逐条对照标准原文。

## 5. 偏离与决定

见 SPEC §12。实现中新增：
- 资源库以表值为准，公式只作防错测试（SPEC §1）；A 型中心孔取 ISO 866:1975 附录表 2（GB/T 145 A 型同值）。
- 花键工作长度终止线为细实线（G4 评审指出，GB/T 4459.3），SPEC §4 已同步。
- 半剖几何对照去掉模型在剖分面上的中线（图上画中心线）。
- CI 改用 runner 自带 Python（`UV_PYTHON_DOWNLOADS=never`），规避 python-build-standalone 下载 504。

## 6. 待用户人工评审

- 6 个新范例与法兰 ISO 版的出图质量（`evidence/*.png`，多模态评审意见见 `render-review.md`，尤其 end_cover、pulley 的引线交叉）。
- GB/T 10609.1 标题栏分格与投影符号画法。
- 资源库数据（`src/linercad/res/*.toml` 的 `[meta].source`），特别是键槽深度偏差（取自 JIS B 1301 = ISO 773）与基准字母禁用集。

## 7. 给 M2 的说明

- Viewer 的点选与 `@ID`：PMI、规定画法特征、辅助视图和剖切 / 放大标记都是带 ID 的元素（`DT.* G.* R.* K.* S.* V.<字母> W.*`），`model.json` 有完整意图；局部放大图里重画的几何属于 `V.<字母>` 本身。
- 问题着色：检查结果有 `pack` / `severity` / `std`，元素 `status` 为 `error / warn / accepted(...)`。
- 参数滑块：PMI 的配合偏差随参数重查；尺寸链结果在 `placement.resolved.result`。
- 评测：`evals/run.py --drawings` 可对 Agent 产出目录出一次通过率和修改轮数，M2 的交互改动可沿用这套基线。
