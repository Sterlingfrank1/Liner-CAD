# M3 SPEC：3D 来源与复杂零件

> 依据 `BRIEF.md`、`DESIGN.md` §3.4–3.5、§6、§7、ROADMAP §6。精简规则 ROADMAP §4.1。只写决定、接口、验收映射和卡片。G1 独立评审一轮（3 个 blocker、8 个 should-fix 已并入）。

## 1. 决定（BRIEF §4）

### 1.1 3D 来源（S1）

- `d.model(path, name="main")` → `M.main`：`path` 相对图纸目录，`model.py`（定义 `model(**P) -> build123d 形体`，`P` 为图纸参数当前值）或 `.step/.stp`。只收路径，日志可重放；内容哈希写进意图。
- `V.project(name="model", cut=None, depth=0, region=None, ribs=(), hidden=True, model="main")` → 特征 `F.<视图>.<name>`，子边 `E.<视图>.<name>.<k>`：
  - 投影保留曲线类型：直线 → `line`，圆 / 圆弧 → `circle` / `arc`，椭圆 / 样条 → 分段 `line`（标 `approx` 标签）。可见边 `thick`，隐藏边 `hidden`，相切（光滑）边 `thin` 并打 `conv` 标签（过渡线）。
  - `cut`：`None` / `"full"` / `"half"`；`depth` 为剖切面沿投射方向的偏移；`region`（视图坐标点列）= 局部剖，只在区域内剖开，边界自动画波浪线 `W`。剖面区域 = 剖开后位于剖切面上的面 → 剖面线 `H.<视图>.<name>`。`ribs`（视图坐标点列）作为剖面线孤岛并画粗实线边界（GB/T 4458.6 肋板纵剖不画剖面线），对 STEP 同样适用。
  - 一个模型可投多个视图、多种剖法；阶梯 / 旋转剖、移出断面对 3D 来源本里程碑不做（偏离记录）。
- 来源记录 `intent.src3d = {"model": "M.main", "edge": i, "faces": [j, k], "hash": h}`：把投影边按几何回配到模型边（端点与中点投影距离 ≤ 0.05 mm）；轮廓线（圆柱 / 圆锥的转向线）无模型边，记 `{"model", "outline": true}`。`hash`（类型 + 端点 + 圆心 / 半径，3D、取 3 位小数）是权威，`edge` / `faces` 序号只是提示。尺寸、形位公差、基准引用 3D 来源边时把该边的 `src3d` 复制进自己的意图（`src3d_refs`），v0.2 由此映射 STEP 拓扑写 PMI。
- 模型变动后边序号可能变，脚本应优先用 `d.q` 选择器（按几何）或坐标锚点；SKILL 写明。
- 投影结果按（模型内容哈希、参数、视图、剖法）缓存在 `.linercad/cache/`（不入 git）。
- 未装 `[3d]`：`missing_extra` 错误，提示 `uv add "linercad[3d]"`。

### 1.2 装配（S3）

- `Drawing(kind="assembly")`；按 DESIGN §3.5：`d.component(path, name=None, at=(0,0,0), rot=(0,0,0), params=None, solid=False)` → `A.<name>`（`name` 缺省取目录名）；`d.std_part(std, spec, qty=1, name=None, at=..., rot=...)` → `A.<name>`；`d.bom()` 放明细栏 `T.bom`。`at` / `rot` 是 DESIGN 未写的装配位置，记入偏离。
- 组件目录至少含 `model.py`；参数缺省值由 AST 读取其 `drawing.py` 里 `d.params(...)` 的字面量（不执行），`params=` 可写装配参数表达式覆盖（参数共享）。重建装配即重读零件源 → 同步。
- 投影：组合体投一次（遮挡正确），再逐件投一次作候选，组合体的每条边按几何归属到组件（`intent.component`）；剖面区域逐件与剖切面求交。`solid=True` 与标准件中的螺栓 / 螺钉 / 销 / 键在纵剖时不剖（GB/T 4458.6）。
- 接触面单线：不同组件投影后重合的边（同类型、端点 ≤ 0.05 mm、或共线且重叠）只保留一条。
- 剖面线：按组件三维接触（`distance ≤ 0.01`）建邻接图贪心着色，色板 = 角度 45°/135° × 间距 3/1.5 mm；同一组件在各视图一致。
- 序号 `B.<k>`：引线起点在组件可见区域内，圆圈沿视图外缘按顺时针排开、引线不交叉（复用布局的交叉计数）。明细栏行与序号一一对应，标准件填标准号与规格。
- 装配尺寸用现有 `dim` API 标在装配视图上（总体、安装、配合 `H7/g6`），不加新接口。

### 1.3 标准件（S3）

只录 L3 用到的规格，`res.std_part(std, spec)` 返回尺寸并带标准号，`d.std_part` 由尺寸生成简化 3D 形体（螺纹按大径圆柱）：六角头螺栓 GB/T 5782、六角螺母 GB/T 6170、平垫圈 GB/T 97.1、圆柱销 GB/T 119.1、开槽沉头螺钉 GB/T 68、开槽锥端紧定螺钉 GB/T 71。

### 1.4 L3 三例（S3，零件模型由 Sonnet 写）

| 例 | 组件（约） | 标准件 |
|---|---|---|
| 滑动轴承 | 轴承座、轴承盖、上下轴衬、油杯简化体 | GB/T 5782、GB/T 6170 |
| 千斤顶 | 底座、螺套、螺杆、顶垫、铰杠 | GB/T 71 |
| 机用虎钳 | 固定钳身、活动钳身、钳口板 ×2、螺杆、方块螺母、垫圈 | GB/T 68、GB/T 119.1、GB/T 97.1 |

每例：主视图全剖（或半剖）+ 一个外形视图、序号、明细栏、2–4 个装配尺寸；零件用 `model.py` + 带 `d.params` 的 `drawing.py`（零件图本身不要求完整）。

### 1.5 DXF 导入（S4）

- `lcad init <目录> --from-dxf x.dxf` → 拷入 `ref.dxf`，`drawing.py` 写 `d.import_dxf("ref.dxf")`。
- LINE / ARC / CIRCLE / LWPOLYLINE → 视图 `front` 的未命名边；线型角色由图层名 / 线型映射（CONTINUOUS→thick 或按线宽 thin、HIDDEN/DASHED→hidden、CENTER/DASHDOT→center）。DIMENSION（线性 / 对齐 / 直径 / 半径 / 角度）→ 尺寸元素（测量点取 defpoint，值取 `get_measurement()`，保留覆盖文字），**不**展开其匿名块。TEXT / MTEXT → 注释；其余（SPLINE、ELLIPSE、HATCH、INSERT …）原样保留为 `X`。
- `lcad inspect x.dxf` → 图层、实体统计、范围、跳过 / 保留为 `X` 的类型，加一张临时 PNG。
- 验收 DXF：ezdxf 仓库中由其它 CAD 软件产出的示例文件一份（MIT），加一份用 ezdxf 生成的带原生 DIMENSION 的图；证据注明来源与许可。

### 1.6 版本、导出（S2）

- `lcad log` → `[{edit, commit, message, time}]`。`lcad diff A B`（edit 号或 commit）→ `git worktree add` 把整个图纸仓库检出到两个临时目录、各自重建（装配的 `../零件` 相对路径因此有效），按 ID 比较，输出 `{added, removed, intent_changed, layout_changed}` 与叠加 SVG（A 灰、B 黑、变化着色）。Viewer：`/api/versions`、`/api/diff`，左栏版本列表，选两个进入叠加视图。
- `lcad export --to <目录> [--formats dxf,pdf]` → 文件 + git tag `rev-A`、`rev-B` …（DESIGN），标题栏修订记录加一行并提交一个 commit。PDF 用已有的 matplotlib 渲染。

### 1.7 Skill 安装（S5）

`SKILL.md` 缩成路由（≤ 120 行）+ `pages/api.md`、`drafting.md`、`viewer.md`、`3d.md`、`assembly.md` + `families/*.md`。`lcad skill install --target claude|codex|opencode|generic [--dir .]`：`.claude/skills/linercad/`、`AGENTS.md` 中的标记段、`.opencode/skills/linercad/`、`LINERCAD.md`。

### 1.8 跨 Agent 评测（S7）

- 工作目录建在仓库外的临时目录，只含 `lcad skill install` 的产物和需求文本；`lcad` 走 `uv run --project <干净 clone>`。
- Codex：`codex exec`（S7 开始时按本机版本核对参数，含 Windows 沙箱与 `-o` 输出），单件超时 20 min。Claude：同样方式驱动 `claude -p --model sonnet`，不用会话内子 agent（避免看到本仓库 `CLAUDE.md`）。
- 任务：零件 2（箱体、叉架各一）+ 装配 1，每件再做 3 轮修改。
- 基线：同一 `claude -p --model sonnet`、同需求、同修改轮次，只许用 ezdxf，要求原生 DIMENSION 实体；产物经 `--from-dxf` 导入后跑同一套检查与几何对照。
- 指标统一由 `evals/run.py --drawings` 出；样本少，结论只作参考，如实写不如基线的地方。

## 2. 验收 → 证据

| BRIEF §3 | 证据 |
|---|---|
| 1 3D 来源 | `tests/test_source3d.py`（箱体模型纯投影出三视图 + 全剖 / 半剖 / 局部剖，曲线类型、`src3d`、肋板、过渡线、缓存；标注 / PMI / 检查照常；缺依赖报错）；范例 `gear_cover`（箱体、3D 来源） |
| 2 两族 | 叉架、箱体各 2–3 个范例 + 各 5 个 L2，零 error；2D 原生走几何对照，3D 来源走完整性对照（由模型的圆柱 / 孔 / 台阶推应有尺寸，运行器输出缺失列表，S6 实现） |
| 3 装配 | `tests/test_assembly.py`（明细栏、序号、剖面线邻接着色、实心件不剖、接触面单线、参数同步）；L3 三例零 error |
| 4 DXF 导入 | `tests/test_import_dxf.py` + G5 两轮 `lcad edit` |
| 5 版本 | `tests/test_versions.py`（log / diff / export）；G5 Viewer 截图 |
| 6 跨 Agent | `evidence/cross-agent.md` + `report-*.json` |
| 7 出图评审 | `evidence/render-review.md` |
| 8 | CI（含 3d job）、HANDOVER、tag |

## 3. 卡片与 PR

| 卡 / PR | 内容 | 执行 | 评审 |
|---|---|---|---|
| S1 | 3D 来源 | Opus | 核心一轮 |
| S3 | 装配 + 标准件 + L3 三例 | Opus（零件模型 Sonnet） | 核心一轮 |
| S2 + S4 + S5 | 版本 / export、M2 便宜遗留、DXF 导入、Skill 安装 | Sonnet + Opus 收口 | 无（测试覆盖） |
| S6 | 叉架、箱体卡片 + 范例 + L2 + 完整性对照 | Sonnet（每族一个） | 无 |
| S7 | 跨 Agent 评测、出图评审、G5、HANDOVER | Opus + 独立 agent | — |

## 4. 偏离记录

| 偏离 | 理由 |
|---|---|
| 相切边统一画细实线（过渡线），不细分更多过渡画法 | 精简；评审发现问题再按族修 |
| 3D 来源不做阶梯 / 旋转剖与移出断面（这些仍可用 2D 原生画法） | 本里程碑预算；全剖 / 半剖 / 偏移面 / 局部剖已覆盖两族主体 |
| `component` / `std_part` 增加 `at` / `rot`、可选 `name` | DESIGN §3.5 未写装配位置；3D 组合投影需要 |
| 组件参数缺省值用 AST 读字面量，不执行零件 `drawing.py` | 安全、快；表达式参数不支持，报错提示改写 |
| 验收 DXF 一份由 ezdxf 生成 | 许可清楚、可复现；另一份为第三方 CAD 产出 |
