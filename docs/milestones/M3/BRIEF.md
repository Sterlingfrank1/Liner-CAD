# M3 BRIEF：3D 来源与复杂零件

> 写给 M3 里程碑会话。流程、门禁和**精简规则**见 `docs/ROADMAP.md`（§4.1–4.2 优先）；设计依据见 `DESIGN.md` §3.4–3.5、§6、§7（下文 § 均指它）和 `DRAFTING-COVERAGE.md`；上一阶段见 `docs/milestones/M2/HANDOVER.md`（尤其 §7）。M3 之后是 v0.1.0 发布（监督会话负责）。

## 1. 目标

把 v0.1 补齐成一个完整的产品：

- **3D 投影成为正式几何来源**，并以此打开叉架类、箱体类和装配图；
- 补上**版本对比**和 **DXF 导入**；
- 把 Skill 做成**任意 Agent 可安装**的形式，并用**跨 Agent 评测**和“裸写 ezdxf”基线证明 harness 的价值（§10 评测标尺）。

同时为 v0.2 留好接口（ROADMAP §6）：3D 来源保留到模型拓扑的引用，使 PMI 将来能映射到 STEP AP242。

## 2. 范围

| 模块 | 内容 | 依据 |
|---|---|---|
| 3D 来源 | 可选依赖 `linercad[3d]`（build123d），复用 M1 的 HLR 代码。<br>源可以是建模代码或 `models/*.step`。视图由投影得到可见线、隐藏线、相切边，边作为未命名几何、用选择器引用。<br>标注、PMI、检查、Viewer、版本管理不因来源而变。<br>未装 3D 依赖时给出清楚的报错和安装提示。<br>投影边记录它来自哪个面 / 边（v0.2 STEP PMI 要用），但不做 STEP 输出 | §3.4、ROADMAP §6 |
| 叉架类、箱体类 | 规定画法：肋板纵剖不画剖面线、铸造圆角与过渡线、相贯线（来自 3D）、多种剖视组合、螺孔。<br>每族一张卡片、2–3 个范例；L2 每族 5 个（需求 + 3D 模型 + 参考图） | COVERAGE §6、§2.2 |
| 装配图 | `Drawing(kind="assembly")`、`d.component("../part")`（引用零件图目录，参数共享）、`d.std_part(标准号, 规格, qty)`。<br>标准件从资源库取，只录 L3 用例用到的。<br>序号、明细栏自动生成；相邻零件剖面线错开；实心件纵剖不剖；接触面一条线；装配尺寸。<br>主要走 3D 装配投影，2D 原生只做简单示意 | §3.5 |
| L3 评测 | 3 个经典装配（建议：千斤顶、机用虎钳、球阀或齿轮油泵），自建模型，教材只作参考。<br>运行器沿用 `evals/run.py`；v0.2 再扩到 10 个左右 | COVERAGE §2.4 |
| DXF 导入 | `lcad init --from-dxf x.dxf` 或等价 API。线条成为未命名几何，可用选择器引用；DXF 尺寸实体转成尺寸元素。<br>导入后可以 `lcad edit`；`lcad inspect ref.dxf` 输出结构摘要和一张临时渲染图 | §3.4、§7 |
| 版本对比 | `lcad log`；`lcad diff A B`：语义 diff（增删 / 意图 / 布局）+ 视觉叠加 SVG。<br>Viewer 加版本列表和对比视图，复用 `svgout.svg()` 和 `data-id` | §6、§5.4 |
| Skill 与安装 | `lcad skill install --target claude\|codex\|opencode\|generic`。<br>路由式：短 `SKILL.md` + 按需读取的 API 页、族卡片、制图规范页。<br>把 M2 HANDOVER §4 的 Skill 缺口补上 | §7 |
| 跨 Agent 评测 | 两个不同的 Agent（Claude Sonnet；本机 Codex CLI `codex`）只拿装好的 Skill，各自完成：<br>· 四族各 1 个 L2 零件；<br>· 1 个 L3 装配；<br>· 每件 3 轮修改。<br>另做“同一模型裸写 ezdxf”的基线，至少 2 个 L2 零件。<br>运行器统一输出违规数、几何对照、一次通过率、修改轮数 | §10 评测标尺、COVERAGE §2.4 |
| `lcad export` | 定稿：导出 DXF / PDF、打 git tag、修订表加一行（最小实现） | §6 |

**顺带（M2 遗留，挑便宜的）：**

- Viewer 初始视图按内容适配；
- 违反 rule 时去掉行内[写回源码]，并说明原因；
- 画布标示预览态；
- 嵌套在外径尺寸内侧的内孔引线穿越（`tests/test_layout_m2.py` 基线）。

其余界面意见留给 v0.2。

**不做：**

- STEP / PMI 输出（v0.2）；
- 齿轮、弹簧、轴承、钣金、焊接等族（“之后”）；
- MCP 封装；
- 大规模评测（v0.2）。

## 3. 验收（G5）

1. **3D 来源：** 至少一个箱体类零件的视图完全由 3D 投影得到，标注、PMI、检查和 Viewer 照常可用；没装 `[3d]` 时报错清楚。
2. **两族覆盖：** 叉架类、箱体类的 L2 参考图零 error。2D 原生的参考图几何对照通过；3D 来源的参考图做完整性对照（应有的定形 / 定位尺寸不缺）。每族 2–3 个范例。
3. **装配：** 3 个 L3 装配都能出图，明细栏、序号、剖面线方向 / 间距、实心件不剖、接触面单线都对，零 error。修改一张零件图的参数，装配图重建后同步。
4. **DXF 导入：** 一张非本工具产出的 DXF 导入后，能用选择器引用线条、尺寸成为元素，并完成 2 轮 `lcad edit`。
5. **版本：** 对一个做过 3 轮以上修改的图，`lcad log` / `lcad diff` 输出正确；Viewer 能切换版本、看叠加对比。
6. **跨 Agent：**
   - Claude 和 Codex 各自只用 `lcad skill install` 装好的 Skill 完成 §2 的任务；
   - 两者结果和“裸写 ezdxf”基线一起记入 `evidence/`；
   - 看指标上 harness 是否明显更好；不好的地方如实写进 HANDOVER。
7. **出图评审：** 新范例和装配图由独立多模态 agent 评审，结论写进 HANDOVER；需要用户看的列进“待用户人工评审”。
8. CI 通过（含 3d job），HANDOVER 合并，tag `v0.1-m3` 已推送。

## 4. 留给 SPEC 决定

1. 3D 来源的 API 形状（`d.view(..., source=model)` 还是单独的 `d.project(...)`）；投影边的命名、选择器，以及到 3D 拓扑的引用怎么存。
2. 装配图的数据模型：组件、标准件、序号、明细栏是什么元素；零件图参数如何共享；剖面线错开的规则。
3. 标准件录哪些（只录 L3 用到的螺栓、螺母、垫圈、销等，注明标准号）。
4. DXF 导入的尺寸实体映射范围；用哪张公开 DXF 做验收（注明来源与许可）。
5. 跨 Agent 评测怎么驱动 Codex CLI（非交互模式、工作目录、超时），以及“裸写 ezdxf”基线怎么公平设置（同一需求、同一检查）。
6. 分几组 PR。建议：3D 来源 → 叉架 / 箱体（卡片、范例、L2）→ 装配 + L3 → DXF 导入 + 版本对比 + export → Skill 安装 + 跨 Agent 评测 → G5。

M3 和 M1 一样大，账户是 Pro 计划：按 ROADMAP §4.1 精简规则执行，额度用完按 §4.2 写进度笔记并以 `M3 BLOCKED — usage limit` 结束。

## 5. Goal 条件

> M3 done when: SPEC merged; all M3 PRs merged, CI green; a box part drawn purely from 3D projection; fork and box families covered (L2 zero errors, 2–3 examples each); 3 L3 assemblies build with BOM, balloons, correct hatching; a foreign DXF imports and edits; lcad log/diff and Viewer version compare work; Claude and Codex, with only the installed skill, draw and edit parts and an assembly, vs a bare-ezdxf baseline; render review recorded; HANDOVER merged; tag v0.1-m3 pushed.
