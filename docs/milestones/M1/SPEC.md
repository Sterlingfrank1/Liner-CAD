# M1 SPEC：专业深度（轴套类、盘盖类）

> 依据 `BRIEF.md`、`DESIGN.md` v1.0、`DRAFTING-COVERAGE.md`、M0 `HANDOVER.md`。流程按 ROADMAP §4.1 精简规则。只写决定、接口、验收映射和卡片。

## 1. 总体决定

| # | 问题（BRIEF §4） | 决定 |
|---|---|---|
| 1 | 资源库格式与位置 | 包内 `linercad/res/`：每个标准一个 TOML 数据文件（`[meta]` 写标准号+版本+ISO 对照+来源），`res/__init__.py` 是很薄的查询函数。**IT 公差和基本偏差录 ISO 286-1 表值，用公式做防错校核**（0–3 mm 段与圆整规则有例外，纯公式会算错）；孔的基本偏差由轴按 ISO 286-1 通用规则 / 特殊规则（Δ）推出；螺纹中径、小径用 GB/T 196 公式；其余查表 |
| 2 | PMI schema 与关联 | 公差、基准、形位公差、粗糙度都是元素，意图分字段（§3），`refs` 指向被测几何（边 / 特征 / 尺寸）。被测对象是尺寸时表示“尺寸要素的轴线 / 中心面”，是边或特征时表示“表面”。`model.json` 原样输出，v0.2 映射 AP242 |
| 3 | 剖视、断面、放大共用机制 | **剖切符号元素 `S.<字母>`（任意折线路径）+ 目标视图 + 剖面线**。全剖 / 阶梯剖 / 旋转剖 = 同一个 `d.section`，路径点数和转角决定画法；移出断面、局部放大、斜视图是**辅助视图**（`V.<字母>`，自由摆放、可有自己的比例）；半剖由回转体工具生成；局部剖 / 断裂用波浪线元素；重合断面 = 细实线轮廓的剖面线 |
| 4 | 评测目录、输出、阈值 | 仓库根 `evals/`（不随包分发）；L1 参数化模板，L2 每零件一目录；运行器 `evals/run.py` 输出 `report.json`（逐用例 + 汇总）。几何对照：采样间距 0.5 mm，点到对方折线距离 ≤ 0.05 mm 视为匹配，**双向覆盖率都 ≥ 0.98** 判通过 |
| 5 | 零件族卡片路由 | `skill/families/shaft.md`、`disc.md`，每张 ≤ 1 页；`SKILL.md` §6 改成路由表；`lcad skill [family]` 打印 SKILL 或卡片（任何 Agent 都能取到） |
| 6 | PR 分组 | §9 四组；核心组各一轮独立评审 |

其它决定：
- **严重度**：`error` = 违反标准的确定错误（配合代号、形位公差语法、粗糙度数值、规定画法缺项等）；`warn` = 布局和启发式检查。build/edit 不因 error 失败（图照样出），输出里分开列出；L2 参考图要求零 error。
- **3D 依赖**：`linercad[3d]` = build123d；HLR 代码在包内 `linercad/hlr.py`（M3 转正式来源时复用），几何对照与运行器在 `evals/`。CI 增加一个 ubuntu job 装 `--extra 3d` 跑几何对照测试；其它 job 跳过（`pytest.importorskip`）。
- **新 ID 前缀**：`DT.<字母>` 基准、`G.<名>` 形位公差、`R.<名>` 粗糙度（`R.default` 为“其余”）、`K.<名>` 尺寸链、`W.<视图>.<名>` 波浪线 / 断裂线、`P.<名>` 参数（只用于检查结果和 accept）。辅助视图 `V.<字母>`；剖切 / 放大 / 斜视标记都是 `S.<字母>`。

## 2. 资源库 `linercad.res`

```python
from linercad import res
res.it(7, 30)                 # → 0.021（mm）；GB/T 1800.1-2020 ↔ ISO 286-1:2010
res.fit("H7", 30)             # → {"code":"H7","upper":0.021,"lower":0.0,"it":7,"std":...}
res.fit("k6", 30); res.fit("JS9", 8)
res.general_tol("m", 45)      # → {"upper":0.3,"lower":-0.3,"class":"m","std":"GB/T 1804-2000"}；kind="linear|chamfer|angle"
res.thread("M20x1.5")         # → {"d":20,"P":1.5,"d2":19.026,"d1":18.376,"coarse":False,"std":"GB/T 196-2003"...}
res.key(32)                   # → {"b":10,"h":8,"t1":5.0,"t2":3.3,"d_range":[30,38],"std":"GB/T 1095-2003"}
res.center_hole("A", 2.5)     # → {"type":"A","d":2.5,"D":5.3,"designation":"A2.5/5.3","std":"GB/T 145-2001"}
res.thread_undercut(2.5)      # 外螺纹退刀槽：{"g2":..,"g1":..,"dg_offset":..,"r":..,"std":"GB/T 3-1997"}（d - dg_offset = 槽底直径）
res.grinding_groove(30)       # 外圆磨削越程槽：{"b":..,"h":..,"r":..,"std":"GB/T 6403.5-2008"}
res.spline("6x23x26x6")       # → {"N":6,"d":23,"D":26,"B":6,"series":"light","std":"GB/T 1144-2001"}
res.rough_series()            # GB/T 1031-2009 Ra 优选系列
```
- 数值单位 mm；每个返回值带 `std`。查不到时 `InvalidArgument`，`candidates` 给最近的规格。
- 覆盖范围：公称尺寸 ≤ 500；轴 `a b c d e f g h js k m n p r s t u`，孔同名大写（录不准的字母宁可不录，列进 HANDOVER 缺口）；IT1–IT18。
- 尺寸段“大于 a 至 b”含上界（`res.it(7, 30)` 落在 18–30 段）；js/JS = ±IT/2（保留小数，同 GB/T 1800.2 表）。
- 普通螺纹公差带（GB/T 197-2018）：录可选公差带列表（`4h…8g`、`4H…7H` 及 `5g6g` 这类组合），`cls` 校验并给候选。
- 基准字母禁用集（GB/T 1182 / ISO 5459）录进资源库，注明出处。
- 校核测试：每张表 ≥ 5 个已知表值（配合 ≥ 20 个，含尺寸段边界）；IT5–IT18 与公式 `i = 0.45·D^(1/3) + 0.001·D`（D 取尺寸段几何平均）在圆整范围内一致，IT1–IT4 只比表值；基本偏差 d/e/f/g 与公式一致。

## 3. 语义 PMI 与尺寸体系

### 3.1 尺寸公差（扩展 M0 `Dim`）
- `tol` 仍接受字符串（M0 契约不变）：配合代号 `"k6"`、`"H7"`，对称 `"±0.1"`，偏差 `"+0.021/0"`、`"-0.02/-0.05"`。`fit` 是 `tol` 的别名（DESIGN §3.2 写法）。
- 意图新增 `tolerance`（解析结果）和 `tol_show`：
```json
"tol": "k6",
"tolerance": {"kind": "fit", "code": "k6", "upper": 0.015, "lower": 0.002, "envelope": false, "std": "GB/T 1800.2-2020"},
"tol_show": "code"            // code | dev | both（GB/T 4458.5 三种注法）；numeric 公差固定 dev
```
  `kind`：`fit / dev / sym`；`envelope`（包容要求 Ⓔ，GB/T 4249 / ISO 14405-1）属于尺寸公差，用 `envelope=True` 给出。配合按尺寸的公称值查表；值随参数变化重查。代号不存在 → 声明时 `invalid_arg`（带候选）。
- 文字：`code` → `Φ30k6`；`dev` → `Φ30` + 上下偏差叠放（字高 `dim.tol_height`，GB 2.5）；`both` → `Φ30k6(+0.015/+0.002)` 叠放在括号里；对称 → `Φ30±0.1`。
- 新增尺寸：`v.dim.aligned(name, p1, p2, ...)`（`side` 取最接近法向的 top/bottom/left/right）、`v.dim.angle(name, line1, line2, value=, r=)`（文字水平，GB/T 4458.4）、`v.dim.chamfer(name, edge, ...)`（45° 注 `C<n>`，否则注 `<n>×<角>°`；引线注释形式）、`reference=True` 参考尺寸（文字加括号，不参与封闭检查）。
- 未注公差：`d.general_tol("m")` → 一条技术要求 `N.tech.<k>`（意图带 `gentol`），尺寸链计算对未注公差的环取 `res.general_tol`。

### 3.2 基准、形位公差、粗糙度
```python
front.datum("A", ref="D.d1")                       # → DT.A；ref 是尺寸 → 轴线基准（三角形对齐尺寸线）；是边 → 表面基准
front.gtol("run1", "circular_runout", 0.02, datums=["A-B"], ref="D.d3")   # → G.run1
front.gtol("perp", "perpendicularity", 0.03, datums=["A"], ref="E.front.body.shoulder", zone=None, modifiers=[])
front.rough("bore", 1.6, ref="E.front.body.3", param="Ra", removal="required", process=None)   # → R.bore
d.rough_default(6.3)                               # → R.default：标题栏附近“通用符号 + 圆括号里的基本符号”（GB/T 131-2006 已取消“其余”字样）
```
意图字段（全部单独存放，不拼字符串）：
- `datum`：`letter, view, target: "axis"|"surface", ref`
- `gtol`：`char`（14 项，GB/T 1182-2018 ↔ ISO 1101:2017）、`value`、`zone: "dia"|"sphere"|null`、`modifiers`（`M L P F CZ` 等；包容要求不在这里）、`datums`：`[{"letters": ["A", "B"], "common": true, "modifiers": []}]`（列表顺序即优先级，`"A-B"` 写法解析成这个结构，可直接映射 AP242 基准体系）、`target`、`ref`、`std`
- `rough`：`param`（`Ra Rz`）、`value`、`removal: required|forbidden|any`、`process`、`target`、`ref`、`std`；`R.default` 另有 `default: true`
- **被测几何要有稳定名字**：`turned` 的轮廓点可写成 `(x, r, "名字")`，从这一点起的上、下轮廓边得到 `E.<v>.<特征>.<名字>` / `<名字>_lo`，插入退刀槽等不会改变它们；PMI 的 `ref` 优先用命名边、特征或尺寸，序号边只作兜底（`model.json` 的关联在增删几何后不漂移）
- 布局：引线类，`dir`/`length` 或贴边（粗糙度：表面法向朝上 / 朝左直接标注，朝下 / 朝右走引线，GB/T 131-2006 读取方向）。符号（14 个形位公差符号、基准三角、粗糙度符号、深度 ↧、花键 ⨅）用线、弧、实心三角画，不依赖字体。

### 3.3 尺寸链
```python
d.chain("axial", closing="l5", increase=["D.L"], decrease=["D.l1", "D.l2", "D.l3", "D.l4"],
        require=None)                              # → K.axial
```
意图：环及增减、封闭环名、`result`：`{"nominal", "wc": {"upper","lower"}, "rss": {"upper","lower"}}`。极值法：ES0 = ΣES增 − ΣEI减，EI0 = ΣEI增 − ΣES减；均方根法：中间偏差 Δ0 = ΣΔ增 − ΣΔ减，T0 = √ΣTi²，偏差 = Δ0 ± T0/2。公差取各环 `tolerance`，没有的取未注公差。封闭环本身不应标注（`closed_loop` 检查）。`require=(lower, upper)` 给出时，wc 超出 → `tolerancing.chain_limit` error。

### 3.4 参数覆盖
每个 `Param` 必须被某个尺寸 `covers`、或出现在技术要求 / 尺寸链里，否则 `dimensioning.param_cover` warn（id = `P.<名>`）。

## 4. 规定画法第一批（内核工具，`geometry.py` / 新 `features.py`）

| 工具 | 画法（标准） | 语义元素 |
|---|---|---|
| `v.turned(name, profile, bore=, cut=None\|"full"\|"half", half="top", holes=[...], grooves=[...], hidden=True)` | 回转体外形 + 内孔；`cut` 时自动生成剖面区域、剖面线、孔后可见线；半剖上下半分画；`holes` 是轴向孔（盘盖的螺栓孔）剖到的样子；`grooves` 把退刀槽 / 越程槽拼进轮廓（GB/T 4458.6、4457.5） | `F.<v>.<name>` + 子特征 `F.<v>.<groove>` |
| `v.thread(name, spec, x0, x1, axis=0, kind="ext"\|"int", cls=None)` | 外螺纹：大径粗、小径细（实际 d1，但与粗线在图纸上至少隔 0.7 mm，GB/T 4457.4）、终止线粗；剖面线画到粗线为止；内螺纹（剖视）：小径粗、大径细；不剖时全部虚线（GB/T 4459.1） | `F.<v>.<name>` type thread |
| `v.thread_end(name, c, spec, kind)` | 端视图：外螺纹大径粗圆 + 小径约 3/4 细圆弧；内螺纹相反 | 同上 |
| `v.tapped_hole(name, at, dir, spec, depth, drill_depth=None, cut=True)` | 螺孔（通孔 / 不通孔），钻孔锥角画 120°；`loop()` 可作剖面线孤岛 | type tapped_hole |
| `v.center_hole(name, at, type="A", d=, keep=True\|None\|False)` | GB/T 4459.5 简化表示：符号 + 代号 `GB/T 4459.5-A2.5/5.3` | type center_hole |
| `v.keyway(name, x0, length, d, axis=0, facing="viewer")` | 主视图键槽长圆形轮廓；宽、深取 `res.key(d)` | type keyway |
| `v.keyway(name, ..., kind="hub")` / `v.keyway_end(name, c, d, kind="hub")` | 轮毂键槽：剖视图里上半孔壁画到 d+t2；端视图孔圆上的矩形缺口 | type keyway |
| `secview.shaft_cut(name, d, keyway=None)` | 移出断面里的轴截面：圆 + 键槽缺口 + 剖面线 + 中心线；缺口方位按 §5 的局部坐标算 | type shaft_cut |
| `v.spline(name, spec, x0, x1, axis=0)` / `v.spline_end(name, c, spec)` | 矩形花键：大径粗、小径细、工作长度终止线细；端面画全部齿形（GB/T 4459.3） | type spline |
| 标注：`v.dim.keyway(name, feature, what="b"\|"depth")`（宽 b 带 N9/JS9，深度注 d−t1 / d+t2，偏差取 `res.key`）、`v.dim.thread(name, feature)`、`v.dim.groove(name, groove, fmt="wd"\|"wh")`、`v.dim.hole(name, feature, n=)`、`v.dim.spline(name, feature)` | 螺纹代号注在大径上（`M20×1.5-6g`，粗牙不注螺距）；退刀槽 `槽宽×直径` 或 `槽宽×槽深`；孔的旁注（`4×M8-6H↧16`）；花键代号 | 尺寸 / 引线元素，`refs` 指向特征 |

规定画法产生的“非真实轮廓”图元（螺纹终止线、小径细线、花键终止线）打 `tags=["conv"]`，几何对照时跳过。反过来，3D 模型里有、规定画法故意不画的边（花键齿侧、螺纹端面的倒角圆、中心孔锥面），由特征给出**遮罩区域**（`intent.mask`，视图局部坐标的多边形），几何对照时去掉落在遮罩里的模型边。

## 5. 视图

| 调用 | 说明 |
|---|---|
| `d.section(letter, view, cut_in, through=[p1, p2, ...], look=None)` | 剖切路径任意折线。2 点 = 全剖 / 半剖；多段直角转折 = 阶梯剖；两段夹角 ≠ 90° = 旋转剖。起、迄、转折处画粗短画并标字母，起迄加箭头（GB/T 4458.6）；`intent.kind` 自动判定 |
| `sec = d.removed_section(letter, parent, through=[p1, p2], look=None)` | 移出断面：标记在 parent，返回辅助视图 `V.<字母>`。**局部坐标**（= 顺着箭头看过去的视图）：迹线单位向量 t（p1→p2，翻成 +y 分量为正；水平迹线翻成 +x），箭头方向 a（parent 平面内，⟂ t），z 指向 parent 的观察者；局部 v = parent 坐标在 t 上的投影，局部 u = 深度坐标（沿 z）× sign((a × t)·z)。例：主视图竖直迹线、箭头向左（a = −x，t = +y），(a × t)·z = −1，所以朝主视图观察者的一侧在断面里是 −u。`hlr.slice` 和 `shaft_cut` 用同一公式。默认摆在剖切线延长线上、主视图组下方，可 `place(at=)` / `move` |
| `det = d.detail(letter, parent, center, r, scale="4:1")` | 局部放大：parent 上画细实线圆 + 罗马字母；`V.<字母>` 自动裁剪、按自己的比例重画 parent 的边、中心线、剖面线（剖面线按图纸间距重新生成）；边界在材料内的部分画波浪线；标注 `I / 4:1`。局部坐标 = parent 的模型坐标，可以直接在放大图上标尺寸；`scale` 是相对零件的绝对比例。字母由 Agent 给（GB 用罗马数字，ISO 用大写字母） |
| `obl = d.oblique(letter, parent, at, look, rotate=False)` | 斜视图：parent 上画箭头和字母，`V.<字母>` 由 Agent 画几何，沿投射方向摆放；`rotate=True` 时标旋转符号 |
| `v.wavy(name, points)` | 局部剖、断裂边界：细波浪线（确定性生成）→ `W.<v>.<name>` |
| `v.hatch(name, loops, outline=None\|"thin")` | `outline="thin"` 即重合断面 |

实现：每个视图有自己的比例（缺省为图纸比例）。标注一律画全（字母、箭头）；GB/T 4458.6 允许省略的情形（按投影关系配置时省箭头、过对称面时省标注）由 Agent 选择不建 `S` 元素，检查不因此报错。辅助视图在基本视图组摆好之后，按“剖切线延长线 → 下方 → 右侧 → 上方”在图框内找空位，避开已占区域；排不下就照常放并报 `out_of_frame`。

## 6. 标准档、模板、企业档

- `std="ISO"`：`iso.toml` 继承 GB（`extends = "GB"`），只改投影识别符号显示、标签语言、各规则的标准号（带年份：ISO 128-1/-2:2020、129-1:2018、286-1:2010、1101:2017、1302:2002（↔ GB/T 131-2006；新版 ISO 21920-1:2021 写进 basis）、2768-1:1989、5455、5457、7200:2004 …）、基准字母禁用集。ISO 档可设 `projection="third"`。
- 模板：`GB-A4/A3/A2/A1/A0` 换成 GB/T 10609.1-2008 完整标题栏（180×56：更改区、签字区、其他区、名称及代号区，含投影符号格）；`ISO-A4…A0` 用 ISO 7200 字段（≤180 宽）+ 投影识别符号（ISO 5456-2）。**两档字段名统一**（`name drawing_no material mass scale sheet company designer checker approver process standardizer date revision`），同一份 drawing.py 改 `std=` 就能出另一档。
- `lcad template import <file.dxf> --name <名>` → `templates/<名>.toml`（企业档叠加）：图层线宽 / 颜色、文字字高、标注字高与箭头、一个标题栏块（名为 `TITLE*` 或含 ATTDEF 的块 → 标题栏线和字段）。`Drawing(..., overlay="<名>")` 叠加；布局和检查都用叠加后的档。

## 7. Checks v1

结构沿用 M0：`{rule, pack, severity, id, message, violations, corridors, std}`，`std` 按当前标准档取。`d.accept(rule, id, reason)` 对所有规则可用。`lcad check` 输出全部结果（按 pack 分组）。

| pack | 规则 | 严重度 | 依据（GB 档） |
|---|---|---|---|
| drafting | `line_width`（粗细 2:1、在系列内）、`text_height`（不在 GB/T 14691 字高系列 → error；尺寸文字不等于档内字高 → warn）、`scale`（优先 / 允许系列）、`sheet`（基本幅面）、`conv_dim`（螺纹、花键、键槽、退刀槽、中心孔特征都有代号或必需尺寸）、`section_ref`（剖切标记与目标视图配对、字母不重）、`center_mark`（整圆有中心线） | error / error·warn / warn / error / error / error / warn | GB/T 4457.4、14691、14690、14689、4459.1/.3/.5、1095、4458.6 |
| dimensioning | `position_datum`（M0 声明期）、`duplicate`（同视图同测量对象）、`closed_loop`（每视图每方向的尺寸图有环，参考尺寸除外）、`missing`（回转体轴向台阶面没有全部连通）、`param_cover`、`text_30`（对齐尺寸在 30° 禁区） | — / warn / warn / warn / warn / warn | GB/T 4458.4、16675.2 |
| tolerancing | `fit_code`（声明期）、`dev_order`（上偏差 ≥ 下偏差）、`gtol_syntax`（形状公差不带基准；方向 / 跳动 / 同轴 / 对称必须带基准；基准字母已定义；值 > 0）、`datum_letter`（重复字母；禁用字母集取自资源库）、`general_tol`（有未注公差尺寸但没有未注公差说明）、`chain_limit` | — / error / error / error / warn / error | GB/T 1800.1、1182、17851、1804 |
| surface | `rough_syntax`（参数合法；数值不在 GB/T 1031 优选系列 → warn（资源库只录了优选系列））、`rough_default`（有粗糙度但没有通用符号且未全标）、`rough_fit`（IT ≤ 7 的配合面没有粗糙度） | error·warn / warn / warn | GB/T 131、1031 |
| layout | `overlap`、`out_of_frame`、`view_align`、`stale_op`（M0） | warn | GB/T 4458.4、14689、4458.1 |

`closed_loop` / `missing` 的图：每个视图、每个方向（h/v）一个图，节点是尺寸端点坐标，边是线性尺寸、倒角注、退刀槽注；`missing` 的节点取回转体轮廓的台阶 x 坐标。

## 8. 评测集与几何对照

```
evals/
  run.py                          # 运行器：uv run python evals/run.py [--level L1|L2] [--case id] [--drawings dir] [--out report.json]
  geocmp.py                       # 几何对照
  L1/templates/<name>.py          # 参数化：drawing 模板 + build123d 模型模板（同一文件两个函数）
  L1/cases.toml                   # [[case]] id / template / params
  L2/<family>/<part>/req.md       # 需求描述（给 Agent 的唯一材料，连同 SKILL.md）
  L2/<family>/<part>/model.py     # build123d 模型：def model() -> Part（模型坐标 = 图纸模型轴，§SPEC M0 3.1）
  L2/<family>/<part>/drawing.py   # 参考图
  L2/<family>/<part>/case.toml    # 视图对照方式：[[view]] name / mode = plain|full|half / plane / hidden
```
- `linercad/hlr.py`（私有：不进 `__all__`、不进 CLI）：`project(shape, view, hidden=False) -> {"visible": [polyline], "hidden": [...]}`（视图轴按 M0 SPEC §3.1）；`section(shape, view, mode)` 先切再投影（全剖去掉近半，半剖去掉近侧四分之一）；`slice(shape, plane)` 给移出断面。
- `geocmp.compare(d, view, proj, tol=0.05, step=0.5)`：只比 `thick`（和要求时的 `hidden`）且不带 `conv` 标签的边，模型边去掉落在特征遮罩（§4）里的部分；L1/L2 的 3D 模型把螺纹建成光圆柱（外螺纹大径、内螺纹小径），钻孔锥角建成 120°；输出 `cov_drawing`、`cov_model`、未匹配片段（带元素 ID）。
- `report.json`：`cases[]`（id、level、errors、warnings、geo、pass）+ `summary`（用例数、零 error 率、几何通过率、一次通过率、修改轮数——后两项来自 `--drawings` 指向的 Agent 产出目录的 git 历史）。加用例只加文件。

## 9. 卡片与 PR 分组

| 组 | 卡片（issue） | 执行 | 评审 |
|---|---|---|---|
| A | C1 资源库 `res`（数据 + 查询 + 校核测试） | Sonnet，worktree，与 B 并行 | 作者自查（配合 ≥ 20 个表值测试） |
| B | C2 视图机制（剖切路径、辅助视图、放大裁剪、波浪线、视图比例、回转体 `bore/cut/holes/grooves`、命名轮廓边）；C3 PMI 与尺寸体系（§3）；C4 规定画法工具（§4）；C5 M0 遗留（PNG 线宽、Φ 文字位置、`build` 的 `changed`） | Opus（本会话），堆叠分支 | **一轮**（C2–C4） |
| C | C6 标准档与模板（ISO 档、GB/T 10609.1、ISO 7200、投影符号、`template import`、overlay）；C7 Checks v1 + `lcad check` | C6 Sonnet；C7 Opus | C7 并入 D 的评审 |
| D | C8 HLR + 几何对照 + 运行器 + CI 3d job；C9 零件族卡片 + 范例（轴套 3：阶梯轴、衬套、花键轴；盘盖 2–3：法兰、端盖、带轮坯）；C10 L1 用例（第一批每项 ≥ 1）+ L2 用例（每族 5 个） | C8 Opus；C9、C10 Sonnet（每族一个） | **一轮**（C7 + C8） |
| G5 | 干净 clone 验收、独立 Agent 实测、出图评审、HANDOVER | 本会话 + 独立 agent | — |

卡片 Goal（写进各 issue）：
- C1：`res` 的全部查询函数按 §2 返回带 `std` 的数值；每表 ≥ 5 个、配合 ≥ 20 个已知表值测试通过；公式防错测试通过；查不到给候选。
- C2：§5 全部调用和 `turned(bore/cut/holes/grooves)` 可用、可记录重放；`tests/test_views.py` 全绿；M0 范例输出不变。
- C3：§3 全部元素进 `model.json`，字段分存、关联被测几何；参数变化后偏差重查；`tests/test_pmi.py` 全绿。
- C4：§4 每个工具画法符合所列标准，产出语义元素和代号标注；`tests/test_conv.py` 全绿。
- C5：PNG 粗细线可分辨；同一轴上直径文字位置一致；`lcad build` 输出 `changed`。
- C6：同一 drawing.py 以 GB / ISO 出图；完整 GB/T 10609.1 与 ISO 7200 标题栏；`template import` + overlay 后检查用叠加值。
- C7：§7 全部规则带 pack、严重度、标准号；`lcad check` 可用；`accept` 对全部规则生效。
- C8：L1/L2 用例能批量跑出 `report.json`；几何对照在已知正确 / 错误的图上分别通过 / 失败；CI 3d job 绿。
- C9：两张卡片 ≤ 1 页且被 SKILL 路由；每族 2–3 个范例零 error，可 `lcad init --from`。
- C10：第一批规定画法每项 ≥ 1 个 L1 用例、每族 5 个 L2 用例，全部零 error 且几何对照通过。

## 10. 验收 → 测试 / 演示

| BRIEF §3 | 证据 |
|---|---|
| 1 覆盖 | `tests/test_evals.py`：全部 L2 参考图零 error；有 build123d 时几何对照通过（CI 3d job）；`tests/test_examples.py` 覆盖新范例；`evals/run.py` 报告存 `evidence/` |
| 2 Agent 实测 | G5：独立 agent 只拿 `SKILL.md`（+卡片）和 `req.md`，每族 2 个 L2 零件从零出图 + 各 3 轮以上修改；记录在 `evidence/g5-*.md`，运行器 `--drawings` 出基线指标 |
| 3 标准档 | `tests/test_std_profiles.py`：同一 drawing.py 以 GB / ISO 出图都零 error；叠加测试用企业 DXF（字高 2.5、线宽 0.7/0.35、自定标题栏）后零 error，且同样的做法不叠加时被检查出来 |
| 4 规定画法 | `tests/test_evals.py` 的 L1 部分：每项 ≥ 1 个用例零 error（+ 几何对照） |
| 5 PMI 语义 | `tests/test_pmi.py`：`model.json` 里 `tolerance / gtol / datum / rough` 字段齐全、`refs` 指向被测几何、参数变化后偏差重查 |
| 6 出图评审 | G5：多模态 agent 按 M0 评分表评审全部范例图，写进 HANDOVER |
| 7 | CI、HANDOVER、tag |

## 11. 风险

- 工作量最大的是 C2–C4 和 L2 内容。L2 每族先做 5 个，够验收即止。
- build123d 体积大：只在一个 CI job 装；本地开发装进 venv。
- 标准数值：查不准的不录，列进缺口；所有表值有出处字段。

## 12. 偏离记录

| 偏离 | 理由 |
|---|---|
| DESIGN §3.4 说剖视的剖面线由 Agent 画；M1 的回转体 `turned(cut=...)` 自动生成剖面区域和剖面线 | 轴套、盘盖几乎都是回转体，自动生成既更准也更省；非回转体仍由 Agent 画 |
| DESIGN §4.5 规则包的部分规则（如 GB/T 4458.4 所有细则、跨视图重复尺寸）只实现一部分 | 精简规则：先实现有确定判据的；其余列入缺口 |
| 不实现 dimensioning.`text_30`（30° 禁区） | 只适用对齐尺寸，判据方向在标准图示里不易确定，先列为缺口 |
| 不做 `dim.chain/baseline` 批量助手 | DESIGN §4.6 的排号规则已让链式自然同排、基准式逐排外推；卡片里示范写法即可 |
| 资源库 IT / 基本偏差以表值为准、公式只做校核（BRIEF 写“用公式算”） | ISO 286-1 的 0–3 mm 段和圆整规则不完全由公式给出，表值才是规范值 |
| 局部放大图的裁剪内容属于 `V.<字母>` 元素本身，而不是原边元素 | 原边的 bbox 不跨两个视图，选取和 `--focus` 不乱 |
