# M0 SPEC：骨架 + 索引

> 依据：`docs/milestones/M0/BRIEF.md`（范围、验收、待决问题）、`DESIGN.md` v1.0（下文 § 指它）、`DRAFTING-COVERAGE.md`。
> 原则：只实现 DESIGN 和 BRIEF 要求的东西；每个决定附一句理由；偏离写在第 14 节。
> 状态：v1（G1 评审后修订）。

---

## 1. 总体结构

### 1.1 数据流

```
drawing.py ──run──► Drawing(内存模型：Param + Element[])
                       │  按顺序重放 drawing.actions.jsonl（失效操作跳过并报告）
                       ▼
                    layout（视图摆放 + 标注语义放置 → 每个元素的图纸坐标图元 prims）
                       ▼
                    checks（重叠 / 越框 / 失效操作 → findings + element.status）
                       ▼
          ┌────────────┴────────────┐
   DXF writer（prims → 实体 + XDATA）   model.json（元素语义索引）
          └─────── .linercad/build/ ┘        PNG（lcad render，临时）
```

一次 `lcad edit`：**基准重建 → 在内存模型上跑临时脚本（自动记操作）→ 用“日志 + 新操作”从零重建 → 补全 place 操作的引擎取值 → 再重建 → 检查 → 追加日志 → git commit → 写产物**。最终状态永远由“源 + 日志”从零重建得到，所以“现场执行”和“日后重放”不可能分叉（§7.4）。

### 1.2 包结构

```
src/linercad/
  __init__.py        Drawing, Param, errors 的公开出口；__version__
  __main__.py        python -m linercad ≡ lcad
  errors.py          LinerError 及子类，to_dict()
  params.py          Param、ParamSet、Expr、安全表达式求值
  std/               标准档：gb.toml + 加载 / 叠加；templates/*.toml 图框标题栏
  model.py           Element、ID 规则、Drawing 容器（元素表、计数器、build 上下文）
  geometry.py        View 与 2D 几何 API（线、圆、弧、多段线、回转体、中心线、孔组）
  annotate.py        尺寸、注释、技术要求、标题栏字段、剖视、剖面线
  query.py           d["ID"]、d.q、几何选择器、d.near
  layout.py          视图摆放 + 标注布局 + 冲突 / 余量；产出 prims
  checks.py          M0 最小检查
  dxfout.py          prims → ezdxf 文档（图层、线型、字体、XDATA），model.json
  render.py          PNG 渲染（全图 / 局部）
  record.py          修改类 API 的自动记录、操作注册表、重放
  runtime.py         build 管线：跑 drawing.py → 重放 → layout → checks → 产物
  txn.py             事务：build / edit / undo；git 封装
  cli.py             lcad 子命令（argparse），JSON 输出
  skill/SKILL.md     给宿主 Agent 的最小 Skill
  examples/{shaft,flange,bracket}/drawing.py
tests/               pytest；验收用例在 tests/acceptance/
```

模块数量按职责切，不再细分；单文件超过 ~800 行再拆。

---

## 2. BRIEF §4 待决问题的决定

| # | 问题 | 决定 | 理由 |
|---|---|---|---|
| 1 | 2D 几何 API 形状 | 视图内用**视图局部模型坐标**（mm，未缩放）作图；基本图元 `line / polyline / polygon / rect / circle / arc`，带 `role`；**回转体用 `turned(name, profile=[(x, r), …])`：给上半轮廓，工具镜像出下半、在每个轮廓顶点处补竖向轮廓线、自动画轴线**；圆和孔用 `circle` + `center_mark`，均布孔用 `holes_on_circle`；线型角色取 `thick / thin / hidden / center / phantom`（粗实线 / 细实线 / 细虚线 / 细点画线 / 细双点画线） | 回转体镜像 + 顶点竖线是确定的规定画法，交给工具画对；角色覆盖 GB/T 4457.4 中 M0 用得到的线型，波浪线、双折线等随局部剖进 M1 |
| 2 | ID 命名与自动生成；XDATA appid | 见 §3.2。前缀 `V F E C D N H S T X`；名字由调用方给，缺省时按“视图内序号”自动生成；XDATA appid **`LINERCAD`**，内容 `[(1000, 元素ID), (1071, 子图元序号)]` | 前缀让 ID 一眼可读；子图元序号支撑 `d.raw` 的“元素 ID + 子图元 + DXF 属性” |
| 3 | 修改类调用如何记录；操作 schema；相对操作重放语义 | **装饰器记录器**：公开的修改类方法挂 `@mutator("op名")`；只记录临时脚本里最外层的调用；参数里的元素记成 ID、参数表达式记成源串。schema `{"edit","op","id","args"}`。相对操作（`move`）在重放时作用于当时的基准值 | 不需要代理对象，Agent 照常写 Python（§8 “动作由临时脚本调用 API 时自动记录”）；表达式记源串，改参数后重放仍跟随参数 |
| 4 | 范例放哪；测试 / 验收的图纸仓库 | 范例作为包数据放 `src/linercad/examples/<name>/drawing.py`，`lcad init <dir> --from <name>` 复制起步；测试一律用 pytest `tmp_path`，验收在系统临时目录 | `DRAFTING-COVERAGE.md` §2.3 要求 `lcad init --from <范例>`；开发仓库里永远不出现图纸 commit |
| 5 | PNG 渲染依赖 | **PyMuPDF**（ezdxf drawing add-on 的 `PyMuPdfBackend` → PDF → `get_pixmap(clip=…)`） | 原型实测：A3 整图 0.39 s（matplotlib 1.1 s）；按 PDF 坐标裁剪，局部图精确；单一依赖；以后的 PDF 导出共用 |
| 6 | 给 Agent 的错误格式 | Python 侧抛 `LinerError` 子类（带 `code / message / id / candidates / values / hint`）；**CLI 一律输出一个 JSON 对象**（`ok` 字段打头），退出码 0 成功 / 1 事务失败已回滚 / 2 用法错误 | 主要读者是 Agent，JSON 无歧义；字段固定，SKILL 里写一次就够 |

其它实现层面的决定（各附理由）：

| 决定 | 理由 |
|---|---|
| DXF 全部写在 modelspace 的**图纸坐标**（纸面 mm，原点在图幅左下角）；视图几何按绘图比例缩放后放入 | 版式、碰撞、裁剪都在一个坐标系里，确定且简单；尺寸数字来自模型值，不受比例影响 |
| 尺寸、注释等标注**分解成基本实体**（LINE / SOLID / TEXT），不用 DXF DIMENSION 实体 | 布局引擎算出的几何就是写出去的几何，碰撞检测准确；每个子实体都带 XDATA，点中任何一部分都能找到整个尺寸（§4.1） |
| 文字宽度用**固定字宽系数估算**（CJK 1.0h、其余 0.6h，再乘字宽因子），不读字体文件 | 跨机器结果一致（确定性）；估算偏保守 |
| 直径符号直接写 `Φ`（U+03A6），不用 `%%c` | 原型实测 simfang 下 `%%c` 渲染成方框 |
| DXF 保存时固定元数据（ezdxf `write_fixed_meta_data_for_testing`，保存期间临时打开） | 原型实测两次保存逐字节一致，diff 干净 |
| 内置模板（图框 + 标题栏）作为包数据，用 `Drawing(sheet="A3")` 选择；图纸目录下 `templates/` 留给 M1 的企业模板 | M0 只要“最小图框和标题栏”；企业档导入在 M1（偏离见 §14） |
| 参数只在 `drawing.py` 里改，日志不记录参数修改；临时脚本里给参数赋值直接报错并给出 `drawing.py:行号` | 参数是构建层的源（§3.2、§5.2 “写回源码”）；避免两处真相 |

---

## 3. 图纸模型

### 3.1 坐标系

| 坐标系 | 用在 | 说明 |
|---|---|---|
| 视图局部模型坐标 | `drawing.py` 和临时脚本里作图、`Query.near()` | mm，未缩放；同一套模型轴：主视图 `(u, v) = (X, Z)`，俯视图 `(X, -Y)`，左视图 `(-Y, Z)`（第一角画法下各视图靠近主视图的一侧为物体后面）。共享轴的视图只要用同一组模型坐标，摆放后自动长对正、高平齐 |
| 图纸坐标 | DXF、`model.json` 的 `bbox` / `resolved`、`d.near()`、`lcad render --focus` | 纸面 mm，原点在图幅左下角 |

### 3.2 元素与 ID

元素字段（§4.2）：

| 字段 | 类型 | M0 内容 |
|---|---|---|
| `id` | str | 见下表 |
| `kind` | str | `view / feature / edge / center / dim / note / hatch / section / table.cell / frame / raw` |
| `intent` | dict | 要表达什么。几何：形状和视图局部坐标、`role`；尺寸：`type / p1 / p2 / dir / value / expr / tol / prefix / suffix / text / role / datum`；… |
| `placement` | dict | 请求的布局字段（`side / row / offset / at / dir / length / shift`）+ `auto`（哪些字段由引擎取值）+ `resolved`（解算结果，含 `bbox`）+ `reason`（调整原因） |
| `refs` | list[str] | 所属视图（第一项）、测量对象、基准、所属特征 |
| `covers` | list[str] | 承载的参数名（来自 `value` 表达式，或显式给出） |
| `tags` | list[str] | 角色标签 |
| `src` | dict | drawing.py 创建：`{"file":"drawing.py","line":42}`；日志创建：`{"edit":"e7","line":12}`（日志行号） |
| `history` | list[str] | 日志里改过它的 edit 编号，按顺序 |
| `status` | str | `ok / warn / accepted(理由)`；M0 不产生 `unsolved` |

ID 规则（名字只允许 Unicode 字母、数字、`_`、`-`，首字符为字母）：

| 前缀 | 元素 | 格式 | 缺省命名 |
|---|---|---|---|
| `V` | 视图 | `V.<view>` | 视图名即 `front / top / left / right / bottom / rear` |
| `F` | 命名特征（一组边） | `F.<view>.<name>` | 无名几何不建特征 |
| `E` | 边（单个几何图元） | 属于特征：`E.<view>.<name>.<k>`；无名：`E.<view>.<n>` | `k` 在特征内从 1 编号，`n` 在视图内对无名边从 1 编号 |
| `C` | 中心线 | `C.<view>.<name>` | `C.<view>.<n>`；回转体轴线 `C.<view>.<特征名>` |
| `D` | 尺寸 | `D.<name>` | `value` 是单个参数的表达式且该名未被占用时用参数名，否则 `D.<view>.<n>` |
| `N` | 注释 | 引线注释 `N.<name>`；技术要求 `N.tech.<k>` | `N.<view>.<n>`；`k` 递增，删除后不复用 |
| `H` | 剖面线 | `H.<view>.<name>` | `H.<view>.<n>` |
| `S` | 剖视（剖切符号 + 剖视标注） | `S.<letter>` | 必须给字母 |
| `T` | 图框 / 标题栏 | `T.frame`；`T.title.<field>` | 固定 |
| `X` | `d.raw_add` 加的原始实体 | `X.<n>` | 全图从 1 编号 |

重复 ID 立即报 `duplicate_id`，并给出一个可用的建议名。

**无名边的编号依赖创建顺序**：`drawing.py` 在前面插入几何会让后面的无名边改号，日志里记的具体 ID 可能指向别的边。缓解：SKILL 要求凡是会被引用的几何都起名（编号只在特征内部）；这是 §4.3 “几何移动后选不中会显式报错”之外的已知风险，记在第 13 节。

### 3.3 model.json

`.linercad/build/model.json`，每次重建重写，UTF-8，`ensure_ascii=False`，`indent=1`，浮点四舍五入到 4 位：

```json
{
 "schema": "linercad.model/0",
 "drawing": {"sheet": "A3", "std": "GB", "scale": "1:1", "edit": "e7", "frame": [25, 5, 415, 292]},
 "params": [{"name": "D", "value": 30, "min": 10, "max": 60, "step": 0.5, "unit": "mm",
             "label": "外径", "tol": "h7", "rule": null, "group": null, "src": {"file": "drawing.py", "line": 5}}],
 "elements": [
  {"id": "D.D", "kind": "dim",
   "intent": {"type": "dia", "view": "front", "p1": [20, 15], "p2": [20, -15], "dir": "v",
              "value": 30, "expr": "D", "tol": "h7", "text": "Φ30h7", "role": "size"},
   "placement": {"side": "inside", "row": null, "offset": 0, "auto": [],
                 "resolved": {"line": [[...], [...]], "text_at": [...], "bbox": [x0, y0, x1, y1]}, "reason": ""},
   "refs": ["V.front"], "covers": ["D"], "tags": [], "src": {"file": "drawing.py", "line": 30},
   "history": ["e7"], "status": "ok"}
 ],
 "findings": [ ... §10 ... ],
 "stale_ops": [ ... §7.3 ... ]
}
```

元素顺序 = 创建顺序（drawing.py 在前，日志在后）。DXF 句柄不写进 model.json（图元 → 元素靠 XDATA）。

---

## 4. Python API（Agent 写构建层和临时脚本用）

命名直白、可组合；所有“点”参数接受 `(x, y)`（数字或参数表达式），或锚点串 `"<元素ID>:<锚点>"`（锚点：边的 `start / end / mid`，圆和弧的 `center`）。锚点在重放时按当时的几何求值，所以临时脚本里用锚点加的尺寸会跟着参数变。

### 4.1 Drawing 与参数

```python
from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")   # sheet: A4（竖放）/ A3 / A2（横放）；std: M0 只有 "GB"
P = d.params(
    D=Param(30, min=10, max=60, step=0.5, unit="mm", label="外径", tol="h7"),
    d1=Param(20, min=8, max=50, step=0.5, unit="mm", label="轴颈", rule="d1 < D"),
)
P.D            # Expr：.value=30.0，.src="D"，.params={"D"}
P.D / 2 - 1    # Expr：.src="D / 2 - 1"
```

- `Param(value, min=None, max=None, step=None, unit="mm", label="", tol=None, rule=None, group=None)`；创建时记下自己在 drawing.py 里的 `{"file","line"}`（M2 写回源码用）。
- `d.params(**)` 校验：值在 `[min, max]` 内、`rule` 成立，否则抛 `ParamError`（带参数名、值、范围或规则）。`d.params` 一张图只调一次。
- `Expr` 支持 `+ - * / // ** 一元负号 abs()`、比较（返回 bool）、`float()`、`round()`、格式化；源串按运算符优先级加括号。`Expr.eval(src, values)` 用 `ast` 白名单（数字、参数名、算术、比较、`and/or/not`）求值，日志重放和 `rule` 校验都用它，不用 `eval`。
- 一个 drawing.py 只能创建一个 `Drawing`；build 时由上下文捕获，不要求变量名。

### 4.2 视图与几何

```python
front = d.view("front")              # → V.front；同名再调返回同一个视图
left  = d.view("left")               # 第一角画法：左视图在主视图右侧，高平齐

front.line(p1, p2, role="thick", name=None)         # → Edge（有 name 时同时建特征 F.front.<name>）
front.polyline(points, role="thick", name=None)     # 每段一条边
front.polygon(points, role="thick", name=None)      # 闭合；可作剖面线边界
front.rect((x, y), w, h, role="thick", name=None)   # 闭合，左下角 + 宽高
front.circle(center, r, role="thick", name=None)
front.arc(center, r, start, end, role="thick", name=None)    # 角度制，逆时针
front.turned(name, profile=[(x0, r0), (x1, r1), ...], axis=0, role="thick")
front.centerline(p1, p2, name=None)                  # 两端各自外延 std 规定值
front.center_mark(center, r, name=None)              # 圆的十字中心线，外延同上
front.holes_on_circle(name, center, pcd, n, d, start=90)   # n 个孔 + 节圆点画线 + 每孔径向中心线
```

- `role`：`thick`（可见轮廓）/ `thin` / `hidden` / `center` / `phantom`；不合法时报错并列出可选值。
- `turned`：`profile` 为上半轮廓顶点 `(x, r)`，x 单调不减，r > 0。工具生成：上半各非竖直段、镜像的下半各段、**每个不同 x 处一条从 -r_max 到 +r_max 的竖线**（台阶、倒角、端面都由它表达，不重叠）、轴线 `C.<view>.<name>`（两端外延）。几何按 `axis`（轴线的 y 坐标）平移。
- 返回值：`Edge` 有 `id, length, dir("h"/"v"/None), start, end, mid, center, r`；`Feature` 有 `id, edges`。

### 4.3 标注

```python
front.dim.linear(name, p1, p2, dir=None, value=None, tol=None, role="size", datum=None,
                 prefix="", suffix="", text=None, side=None, row=None, offset=None, ref=None)
front.dim.dia(name, p1=None, p2=None, circle=None, at=None, ...)   # 非圆视图给 p1,p2；圆视图给 circle
front.dim.rad(name, circle=None, at=None, ...)                    # circle 可以是圆或弧
front.note(name, text, anchor, dir=None, length=None)             # 引线注释，锚点 + 方向
d.notes.tech(lines)            # 追加技术要求；lines 为 str 或 list[str] → N.tech.<k>
d.title(**fields)              # 标题栏字段 → T.title.<field>；字段集合由模板决定
d.section(letter, view, cut_in, through=[p1, p2], look=None)       # 全剖视 → S.<letter>
front.hatch(name, loops=[...])                                      # 剖面线 → H.front.<name>
```

- `linear`：只做水平（`dir="h"`，量 Δx）和竖直（`dir="v"`，量 Δy）。`dir` 缺省时：两点 y 相同取 h，x 相同取 v，否则报错要求给出。`ref=<边>` 等价于取这条边的两端。对齐尺寸、角度尺寸在 M1。
- `value`：缺省为几何实测值；给参数表达式时显示表达式的值，`covers` 自动取表达式里的参数。
- `role`：`size / position / overall`。**`position` 必须给 `datum`**（元素 ID 或锚点），否则声明时抛 `InvalidArgument`（§4.4）。
- 显示文字 = `prefix` + (`Φ` 或 `R`) + 数值（去掉末尾 0，最多 3 位小数）+ `tol` + `suffix`；`text` 给出时整串替换。公差 M0 只当文字处理（`"g6"`、`"±0.1"`），查表在 M1。
- `dia` 在非圆视图上按线性尺寸处理并加 `Φ`（§4.6）；在圆视图上（给 `circle`）画过圆心的尺寸线、两端箭头抵圆，沿 `at` 方向引出水平折线写字。`rad` 从圆心到圆周一端箭头，同样引出写字。
- `note`：从 `anchor`（几何上的点，带箭头）沿 `dir`（度）引出 `length`（mm），接水平折线，文字写在折线上方。
- `section`：`view` 是画成全剖的视图，`cut_in` 是标剖切位置的视图，`through` 是剖切面在 `cut_in` 视图里的迹线（两点定一条线）。Harness 画：迹线两端、`cut_in` 视图几何外侧的粗短画；短画外端垂直于迹线的箭头（`look` 缺省按投影关系推出：第一角画法下指向剖视图所在一侧；也可给 `"left/right/up/down"`）；箭头旁的字母；剖视图上方居中的 `A-A`。剖面轮廓由 Agent 自己画（§3.4）。
- `hatch`：`loops` 是闭合特征（`polygon / rect / circle` 建出的特征或其 ID）或点列；嵌套的环是孤岛。图案、角度、间距来自标准档（§6）。

### 4.4 引用与查询（§4.3）

```python
d["D.D"]                                    # 元素；找不到抛 NotFound，带相近 ID 候选
d.q.dims(view="front", role="position")     # Query；按字段相等过滤
d.q.lines(view="front").where(length=30, dir="h").near(120, 45).exactly(1)
d.q.circles(view="left").where(r=6, tol=0.1).one()     # one() = exactly(1)[0]
d.near(210, 148, r=5)                       # 图纸坐标，按距离排序的元素列表
```

- `d.q.<种类>`：`views features edges lines circles arcs centers dims notes hatches sections cells all`；写错种类报错并列出全部种类。
- `Query`：`.where(**条件, tol=0.01)` 或 `.where(函数)`、`.near(x, y, r=2.0)`（视图局部坐标，要求已按单个 `view` 过滤）、`.exactly(n)`、`.one()`、`.first()`、`.ids()`、`len()`、迭代、下标。
- `exactly(n)` 不满足时抛 `CountMismatch`：列出实际命中的元素（ID + 长度 / 方向 / 中点等关键值），`near` 用过时再给离该点最近的几个候选和距离。
- 查询对象不能直接记进日志：临时脚本里先 `.one()` 拿到元素，记录时自动变成具体 ID（§3.2）。

### 4.5 元素操作（临时脚本里的修改都走这些，自动记录）

| 调用 | 作用 | 记录的操作 |
|---|---|---|
| `el.place(**布局字段)` | 改布局：尺寸 `side / row / offset`，圆视图直径半径 `at`，注释 `dir / length`，视图 `at` | `place`，记录后补全引擎当时选定的其余字段（§7.2） |
| `el.move(dx=0, dy=0)` | 相对微调：尺寸只取外法向分量加到 `offset`（沿尺寸线的分量非 0 时报错并说明）；注释平移折线和文字（`shift`）；视图沿自由方向平移（会破坏对齐的分量报错）；边 / 特征平移几何 | `move`（相对，重放时作用于当时的基准） |
| `el.set(**意图字段)` 或 `el.tol = "g6"` | 改意图：尺寸 `value / tol / prefix / suffix / text / role / datum`；注释、标题栏字段 `text`；边 `role` | `set` |
| `el.suppress()` | 删除元素（不进 DXF 和 model.json） | `suppress` |
| `d.accept(rule, id, reason)` | 有意为之的警告放行，status 变 `accepted(理由)` | `accept` |
| `d.raw(id).entities[k].dxf.<属性> = 值` | 逃生口：改某元素第 k 个子图元的 DXF 属性 | `raw`（`{"sub":k,"attr":..,"value":..}`） |
| `d.raw_add(dxftype, **dxfattribs)` | 逃生口：加一个原始实体（图纸坐标）→ `X.<n>` | `raw_add` |
| 视图里的建图方法、`dim.*`、`note`、`notes.tech`、`hatch`、`section`、`d.view(新视图)` | 加元素 | 以方法名为操作名：`line / polyline / polygon / rect / circle / arc / turned / centerline / center_mark / holes_on_circle / dim.linear / dim.dia / dim.rad / note / notes.tech / hatch / section / view / title` |

只读属性：`id kind intent placement refs covers tags src history status view bbox`；尺寸另有 `value text side row offset`；`el.info()` 返回 model.json 里的那条记录。临时脚本里读到的布局值是本轮修改**之前**的解算结果。

在元素上调用不存在的方法 / 字段时，错误信息列出这个种类可用的方法和字段（例如调用 `delete()` 会提示 `suppress()`）。

### 4.6 错误

```python
class LinerError(Exception):
    code: str          # not_found / count_mismatch / invalid_arg / duplicate_id / param / stale /
                       # script / build / git / undo / no_ops / dirty
    message: str       # 中文，含元素 ID、原因、数值
    id: str | None
    candidates: list   # 候选 ID 或候选值
    values: dict       # 相关数值
    hint: str | None   # 下一步怎么改
    def to_dict(self) -> dict
```

---

## 5. 标注布局（§4.6）

确定性的语义放置 + 局部外推 + 冲突报告，不做全局求解器。

### 5.1 视图内布局（坐标：以视图原点为基准的纸面 mm）

1. **障碍物先就位**：几何边（圆弧离散为折线）、中心线、剖面线区域、剖切符号（位置由几何决定）。
2. **固定元素**（布局字段全部写明的）按声明顺序就位，成为障碍。
3. **自动元素**依次放入：
   - 线性尺寸（含非圆视图上的直径）：没写 `side` 时取离被测点最近的视图外侧（h 尺寸比较上 / 下边，v 尺寸比较左 / 右边；相等时 h 取 bottom、v 取 left）。同一侧按被测长度从小到大，再按声明顺序。没写 `row` 时从第 1 排试起，冲突就外推一排，最多 `max_rows` 排，并记录原因（如“第 1 排与 D.l1 冲突，外推到第 2 排”）。第 k 排尺寸线距视图几何外框 `first_row + (k-1)·row_pitch + offset`。
   - `inside`：尺寸线直接画在两被测点之间，没有尺寸界线；文字沿尺寸线依次试中点、1/4、3/4 处。
   - 文字放不下（尺寸线长 < 字宽 + 2·箭头长 + 2·间隙）时移到界线外，箭头外翻（§4.6 第 2 条）。
   - 圆视图直径 / 半径：没写 `at` 时依次试 `45, 135, 315, 225, 30, 150, 60, 120` 度。
   - 引线注释：没写 `dir` 时依次试 `45, 135, 315, 225, 60, 120, 300, 240` 度；`length` 缺省取标准档值。
4. **冲突判定**：文字框与任何非本元素的线段、文字框、剖面线区域相交；同侧同排两条尺寸线的投影区间重叠；本元素的尺寸界线穿过别的文字框。间隙取标准档 `clearance`。
5. **排不好不硬排**：所有候选都冲突时，取冲突数最少的候选（并列取最靠前的），照样画出，元素标 `warn`，findings 里给 `violations`（与谁冲突、重叠量）和 `corridors`（文字框上下左右可移动的距离，按轴对齐包围盒近似，最大 50 mm）。
6. **剖视标注** `A-A` 放在视图所有内容（含上方尺寸）之上、几何中心正上方。

### 5.2 视图摆放

1. 每个视图的“全外框” = 几何外框 ∪ 标注外框（5.1 的结果）。
2. 主视图放在原点；其余视图按标准档的投影方式相对主视图摆放（第一角：俯视在下、仰视在上、左视在右、右视在左、后视在左视之右），**共享轴对齐**（俯 / 仰视图与主视图原点 x 相同；左 / 右 / 后视图原点 y 相同），相邻全外框之间留 `view_gap`。
3. 整组居中到内图框；若与标题栏或技术要求区重叠，先上移、再左移到刚好不重叠（在内框范围内）；仍放不下就保持并由检查报告越框。
4. `V.front` 写了 `at`（图纸坐标）时整组固定在那里，不居中；任一视图的 `offset`（`move` 累积）在最后加上，只允许沿自由方向。

### 5.3 确定性

输入相同输出相同：遍历顺序 = 元素创建顺序；候选顺序固定；不用随机数和集合遍历；排序都带完整的平局规则（长度 → 声明序号）。参数变化时，固定元素保留侧、排、偏移只重算坐标，自动元素按同样习惯重排。

---

## 6. 标准档与模板（§4.7）

### 6.1 结构

- `src/linercad/std/gb.toml`：样式与数值，**每组注明依据**（`basis = "GB/T xxxx-yyyy"`，或 `basis = "convention"` 表示标准没给具体数值、取教材通行值）。
- `load_std(name, overlays=()) -> dict`：读内置档，再按顺序深度合并叠加档（dict 递归覆盖，标量和列表整体替换）。M0 只内置 GB；`"ISO"` 报错说明在 M1 提供；叠加机制用测试用的 overlay 验证（企业档 M1）。
- `src/linercad/std/templates/GB-A4.toml / GB-A3.toml / GB-A2.toml`：图幅、边距、标题栏格子（线、标签文字、命名字段槽位及字高）、技术要求区锚点。`load_template(std, sheet)`。

### 6.2 GB 档 M0 数值

| 组 | 键 | 值 | 依据 |
|---|---|---|---|
| 图线 | thick 宽 / thin 宽 | 0.5 / 0.25 mm | GB/T 4457.4-2002（粗细线宽比 2:1，d 取 0.5 组） |
| 图线颜色 | thick 白 7、thin 绿 3、hidden 黄 2、center 红 1、phantom 粉红 6；尺寸、文字、剖面线按细实线绿 3 | ACI 色号 | GB/T 18229-2000（CAD 工程制图规则，图线颜色） |
| 线型 | hidden：画 4、隔 1；center：长画 20、隔 3、点 0.5、隔 3；phantom：长画 20、隔 3、点、隔 3、点、隔 3（mm） | — | convention（教材通行：虚线画长 2~6、间隔约 1；点画线长画 15~30、间隔约 3） |
| 字体 | 字体文件 simfang.ttf，字宽因子 0.7；字高系列 1.8 2.5 3.5 5 7 10 14 20 | — | GB/T 14691-1993（长仿宋体、字高系列） |
| 尺寸 | 字高 3.5；箭头长 3、宽 1；尺寸界线超出尺寸线 2；尺寸界线起点间隙 0；文字离尺寸线 1 | mm | GB/T 4458.4-2003（箭头长 ≥ 6d，界线超出约 2）；文字间隙 convention |
| 尺寸排布 | first_row 10、row_pitch 7、max_rows 6、clearance 0.5 | mm | convention（DESIGN §4.6 给定的 GB 档默认值） |
| 中心线 | 超出轮廓 3 | mm | GB/T 4457.4-2002（点画线超出轮廓 2~5） |
| 引线注释 | 默认长度 8、折线余量 1 | mm | convention |
| 剖面线 | 45°、细实线、间距 3（ANSI31 缩放） | — | GB/T 4457.5-2013（金属材料通用剖面线 45° 细实线）；间距 convention |
| 剖切符号 | 粗短画长 6、线宽 0.7；箭头长 4；字母字高 5；剖视名称字高 5 | mm | GB/T 4458.6-2002（粗短画、箭头、字母、“×-×”）；数值 convention |
| 视图 | 投影方式 first；view_gap 8 | — | GB/T 14692-2008（第一角画法）；GB/T 4458.1-2002（基本视图配置）；间隙 convention |
| 图幅 | A0 841×1189、A1 594×841、A2 420×594、A3 297×420、A4 210×297；留装订边 a=25，c=10（A0~A2）/ 5（A3、A4） | mm | GB/T 14689-2008 |
| 比例 | 优先系列 1:1 1:2 1:5 1:10 2:1 5:1 10:1；允许系列 1:1.5 1:2.5 1:3 1:4 1:6 2.5:1 4:1 | — | GB/T 14690-1993 |
| 标题栏 | 外形 180×56，位于右下角 | mm | GB/T 10609.1-2008（外形尺寸）；**内部分格为 M0 简化版**（名称、图号、材料、比例、质量、共 张 第 张、单位、设计、审核、日期），M1 做完整版 |
| 技术要求 | 标题“技术要求”字高 5、条文字高 3.5、行距 1.6h，放在标题栏上方 | — | convention |

图层：每个角色一个图层（`THICK THIN HIDDEN CENTER PHANTOM DIM TEXT HATCH SECTION FRAME`），名称、颜色、线宽、线型都从标准档读，代码里不写死。

---

## 7. 修订层：动作日志（§3.2）

### 7.1 记录

- `drawing.py` 构建期间不记录（构建层就是代码本身），但记 `src`。
- 临时脚本里每次**最外层**调用 `@mutator` 方法记一条操作（内部嵌套调用不重复记）。
- 参数序列化：元组 → 列表；`Expr` → `{"expr": "D / 2"}`；元素 → ID 串；锚点串原样；`Query` → 报错（要求先 `.one()`）。
- 行格式（UTF-8、LF、紧凑、键顺序固定）：

```jsonl
{"edit":"e7","op":"place","id":"D.D","args":{"side":"right","row":1,"offset":0}}
{"edit":"e7","op":"set","id":"D.D","args":{"tol":"g6"}}
{"edit":"e8","op":"notes.tech","id":"N.tech.4","args":{"lines":["去毛刺"]}}
{"edit":"e9","op":"suppress","id":"D.chamfer_60","args":{}}
```

### 7.2 place 的补全

`place` 只写了部分字段时（如只写 `side`），事务在第一次重建后读取目标元素的解算结果，把同组其余字段（尺寸：`side / row / offset`；圆视图尺寸：`at`；注释：`dir / length`）补成具体值再写进日志。于是“改过布局的元素从此固定”（§4.6 第 1 条）。

### 7.3 重放

按日志顺序逐条执行：创建类操作用记录的 ID 建元素（ID 已存在 → 失效）；修改类操作先找目标（不存在 → 失效）；参数表达式按当前参数求值；任何 `LinerError` 都使这条操作失效。失效操作跳过，不影响其余操作，报告为：

```json
{"edit": "e5", "line": 9, "op": "set", "id": "D.l3", "reason": "目标不存在", "candidates": ["D.l2", "D.l4"]}
```

失效操作同时以 `stale_op` 规则进入 findings（§10）。**本次 edit 自己的新操作**在重建中失效则不是警告而是错误，整个事务回滚。

### 7.4 为什么“从零重建”

脚本在基准模型上现场执行只用来**收集操作**；提交的结果来自“drawing.py + 旧日志 + 新操作”的全新重建。这样 commit 里的日志重放出来的图，就是这次给 Agent 看的图，不存在现场与重放的差异。代价是一次 edit 重建 2~3 次，示例图单次重建目标 < 1 s。

---

## 8. 事务、CLI 与 git

### 8.1 图纸目录

```
<part>/
  drawing.py  drawing.actions.jsonl  .gitignore（.linercad/）  .gitattributes（* text=auto eol=lf）   ← 入库
  .linercad/build/{drawing.dxf, model.json}   .linercad/tmp/（临时脚本、PNG）                       ← 不入库
```

`lcad` 在当前目录工作，`-C <dir>` 指定图纸目录。图纸目录可以是独立仓库，也可以在一个大仓库的子目录里；git 命令都带 `-C` 和路径限定。

### 8.2 命令

| 命令 | 行为 | 提交 |
|---|---|---|
| `lcad init <dir> [--from shaft\|flange\|bracket] [--sheet A3]` | 建目录和源文件（`--from` 复制范例，否则写最小起步模板）；不在 git 仓库里就 `git init`；构建一次验证；提交 | `e0 · init` |
| `lcad build [-m "<原话>"]` | 重建产物。给了 `-m` 且源文件有改动时提交；构建失败不提交，源文件保持 Agent 改后的样子，旧产物不动 | `eN · <原话>` |
| `lcad edit <script.py> -m "<原话>"` | 事务执行临时脚本（脚本须定义 `apply(d)`）；见 §1.1 | `eN · <原话>` |
| `lcad undo <eK> [-m "<原话>"]` | 删掉日志里 `edit == eK` 的行；该 commit 若改过 drawing.py，按其 diff 反向应用（`git apply -R`，冲突则回滚并报告）；重建，后续依赖它的操作报为失效；提交。撤销一次撤销不支持（报错并提示重做原修改） | `eN · <原话 或 "undo eK">`，正文带 `Undo-Of: eK` |
| `lcad context [ID … \| @sel]` | 无参数：图纸摘要（图幅、参数、视图、按种类列出的元素及要点、findings、失效操作、最近几次修改）；给 ID：完整元素记录、邻近元素、源码片段（drawing.py 前后几行或日志行）、可直接粘进脚本的示例代码；`@sel` 读 `.linercad/selection.json`（M2 才会写） | 否 |
| `lcad render [--focus ID] [-o out.png] [--dpi N]` | 重建（不提交）后出 PNG 到 `.linercad/tmp/`；`--focus` 按元素外框加 15 mm 边距裁剪、提高分辨率，并把该元素画成红色 | 否 |

- **编号**：`eN` 的 N = max(日志里的编号、本目录 git 提交标题里的 `eN`) + 1。`init` 为 `e0`。
- **只提交本图源文件**：`git commit -m … -- <这几个路径>`，不碰仓库里其它已暂存的改动；不 push；没配置 git 身份时只对这次提交传 `-c user.name=linercad -c user.email=linercad@localhost`。
- `lcad edit` / `lcad undo` 发现 drawing.py 有未提交改动时拒绝（`dirty`），提示先 `lcad build -m` 提交，保证“一次修改一个 commit、commit 的 diff 就是本轮改动”。
- `.linercad/tmp/` 只保留最近 20 个文件。产物先写临时文件再替换，失败时旧产物不动。

### 8.3 输出

成功：

```json
{"ok": true, "edit": "e7", "commit": "a1b2c3d", "ops": [/* 本次追加的日志行 */],
 "changed": ["D.D"], "warnings": [/* findings 里 severity=warn 的条目 */], "stale_ops": [],
 "dxf": ".linercad/build/drawing.dxf", "model": ".linercad/build/model.json"}
```

失败（退出码 1，已回滚：日志不变、无 commit、旧产物不动）：

```json
{"ok": false, "rolled_back": true,
 "error": {"code": "not_found", "message": "找不到元素 D.DD", "id": "D.DD",
           "candidates": ["D.D", "D.d1"], "values": {}, "hint": "用 lcad context 查看全部 ID",
           "where": ".linercad/tmp/move-dim.py:3", "trace": ["move-dim.py:3  dim = d[\"D.DD\"]"]}}
```

脚本异常只列临时脚本自己的栈帧（文件:行 + 源码），不列 Harness 内部帧。

---

## 9. 输出

### 9.1 DXF

- ezdxf `R2018`，`$INSUNITS=4`（mm），`$MEASUREMENT=1`；图层、线型（标准档里的图案）、文字样式 `LC`（字体、字宽因子）、appid `LINERCAD` 按标准档建立。
- 元素 → prims → 实体：LINE、CIRCLE、ARC、TEXT（尺寸文字竖排时旋转 90°，字头朝左）、SOLID（实心箭头）、HATCH（ANSI31 按间距缩放）。每个实体带 XDATA `[(1000, id), (1071, 子图元序号)]`。
- 实体顺序 = 元素顺序 × 子图元顺序；保存时固定元数据，同输入逐字节一致。

### 9.2 PNG

ezdxf drawing add-on + PyMuPDF：白底、全部黑色（`ColorPolicy.BLACK`）、绝对线宽；页面 = 图幅尺寸、零边距、1:1，于是 PDF 坐标与图纸坐标一一对应，`--focus` 用 `clip` 精确裁剪。整图默认 150 dpi，局部 300 dpi。字体找不到时 ezdxf 自动替代（CI 上中文可能显示为方框，不影响测试）。

---

## 10. 最小检查（§4.5 的子集；完整 Checks v1 在 M1）

| 规则 | 内容 | 严重度 | 依据 |
|---|---|---|---|
| `overlap` | 文字框（尺寸数字、注释、字母、剖视名称）与其它元素的线段、文字框、剖面线区域相交 | warn | GB/T 4458.4-2003（尺寸数字不能被任何图线通过） |
| `out_of_frame` | 元素外框越出内图框，或压到标题栏 / 技术要求区（这两区自己的元素除外） | warn | GB/T 14689-2008 |
| `stale_op` | 日志重放中的失效操作 | warn | §3.2 |

finding 结构：`{"rule","severity","id","message","violations":[{"with","overlap"}],"corridors":{"left","right","up","down"},"std"}`。M0 的检查都不阻断提交，结果在输出的 `warnings` 和 model.json 里；`accept` 过的不再报。

---

## 11. Skill 与范例

- **`src/linercad/skill/SKILL.md`**（≤ 300 行）：是什么；工作循环（`context` → 写 `.linercad/tmp/*.py` 的 `apply(d)` → `edit -m 原话` → 读 JSON → `render` 自检 → 必要时 `undo`）；改 drawing.py 还是写临时脚本；API 速查；坐标和 ID；错误 JSON 和常见 code；三类零件的 GB 表达要点（轴：轴线水平、直径 inside、长度在下方成链 + 总长；法兰：全剖主视图 + 端面视图、剖切符号；支架：三视图、虚线、长对正高平齐）；不要做的事（不手改产物、不自己 git commit）。宿主 Agent 只看它就能完成出图和修改。
- **三个范例**（`src/linercad/examples/`），都用 A3、1:1、带标题栏和技术要求，构建零 warning：
  - `shaft` 阶梯轴：五段，两端倒角；主视图；直径 inside、轴向长度链式在下 + 总长。
  - `flange` 法兰盘：盘 + 凸台 + 通孔 + 4 个均布螺栓孔；**主视图全剖**（剖面线、`A-A`），左视图为端面视图并标剖切符号、`4×Φ…` 孔。
  - `bracket` 支架：L 形底板 + 立板，底板两孔、立板一孔；主、俯、左三视图，虚线表达孔。

---

## 12. 验收项 → 测试 / 演示

| BRIEF §3 | 映射 |
|---|---|
| 1 三图 `lcad build` 出 DXF；法兰全剖，剖面线、剖切符号、剖视标注齐全 | `tests/acceptance/test_examples.py`：从范例 `init` 到临时目录、`build`，断言 DXF 存在、零 error；法兰断言存在 `H.front.*`（HATCH 实体）、`S.A`（左视图里的粗短画 + 箭头 + 字母、主视图上方 `A-A`）。演示：G5 时从干净 clone 跑 |
| 2 每图 ≥ 5 轮对话修改，覆盖六类 | **自动化**：`tests/acceptance/test_rounds.py`，每个零件 6 轮固定脚本：改布局（换侧 / 换排 / 微调）、改意图（值 / 公差文字）、加删元素、改 drawing.py 参数后 `build -m` 重放（断言相对操作仍生效、无失效操作）、`undo` 较早一轮、失败事务（引用不存在的 ID → 退出码 1、候选非空、无 commit、日志不变）。**演示**：G5 时由只拿到 `SKILL.md` 和用户原话的独立 agent 完成，记录进 `evidence/` |
| 3 `git ls-files` 只有源文件；每轮恰好一个 commit；失败不产生 commit | `test_rounds.py` 每轮后断言 `git ls-files` 集合与 commit 数；演示中同样核对并记录 |
| 4 确定性 | `tests/test_determinism.py`：同输入重建两次，DXF 字节和 model.json 字节相同；另比较实体列表（类型、属性、XDATA） |
| 5 出图质量 | G5：三张整图 PNG + 评分表交给独立多模态 agent 评审（视图、线型、尺寸重叠 / 越界、剖视表达），结论写进 HANDOVER |
| 6 CI、HANDOVER、tag | GitHub Actions（ubuntu py3.11 + windows py3.13）；HANDOVER PR；`v0.1-m0` tag |

单元测试按模块：参数与表达式、标准档加载叠加、ID 与查询（含错误候选）、几何（回转体镜像与竖线、孔组）、标注意图、布局（换排、外推、文字外移、冲突报告、确定性）、DXF（XDATA 齐全、图层线型）、记录与重放（失效、place 补全、move 相对、raw）、事务（回滚、dirty、编号）、CLI（JSON 结构、退出码）。

---

## 13. 卡片

每张卡一个 issue（label `card`，milestone `M0 骨架+索引`）、一个分支 `m0/<slug>`、一个 PR（第一个 commit 是会失败的测试）。

| # | slug | 内容 | 档位 | 依赖 |
|---|---|---|---|---|
| C1 | `skeleton-ci` | pyproject（uv、uv_build）、包骨架、`lcad --version` 与 `python -m linercad`、pytest、ruff、GitHub Actions、`errors.py` | Opus | — |
| C2 | `std-profile` | `gb.toml`（§6.2 数值 + 依据）、三个模板、`load_std` 叠加、`load_template` | Sonnet | C1 |
| C3 | `params` | `Param / ParamSet / Expr`、安全求值、rule 与范围校验、源码位置 | Sonnet | C1 |
| C4 | `model-core` | `Element`、ID 规则、`Drawing` 容器与 build 上下文、视图、2D 几何（含 `turned`、`holes_on_circle`、中心线）、锚点、查询与候选、`@mutator` 钩子（记录器为空实现） | Opus | C2 C3 |
| C5 | `annotations` | 尺寸三类、注释、技术要求、标题栏字段、剖视 `section`、剖面线 `hatch`（意图层） | Opus | C4 |
| C6 | `layout-checks` | §5 布局（视图摆放、尺寸 / 注释放置、剖切符号与剖视名称、冲突与余量）、§10 检查、prims | Opus | C5 |
| C7 | `dxf-output` | §9.1 DXF 写出、model.json、确定性测试 | Opus | C6 |
| C8 | `action-log` | §7 记录器、操作注册表、重放与失效、place 补全、move、set、suppress、accept、raw | Opus | C6 |
| C9 | `txn-cli` | runtime 管线、§8 事务与 git、CLI 全部命令、JSON 输出与退出码 | Opus | C7 C8 |
| C10 | `render-png` | §9.2 PNG 渲染与 `--focus` | Sonnet | C7 |
| C11 | `examples` | 三个范例 + `init --from` 测试 + 零 warning | Sonnet | C9 |
| C12 | `skill` | `SKILL.md` | Sonnet | C9 |
| C13 | `acceptance-tests` | `tests/acceptance/`（§12 第 1~4 项的自动化部分） | Sonnet | C11 |

并行：C2 ∥ C3；C8 与 C10 在 C7 后可并行（C10 只碰 `render.py`）；C11 ∥ C12。核心卡（C4–C9）由里程碑会话（Opus）顺序完成。每张卡的 Goal 条件写在 issue 里。

---

## 14. 风险

| 风险 | 缓解 |
|---|---|
| 无名边编号随 drawing.py 改动漂移，日志里的具体 ID 指向别的边 | SKILL 要求被引用的几何起名；编号只在特征内；M1 视评测情况考虑给边操作加几何指纹校验 |
| 估算字宽与真实字体不一致，渲染出来仍有轻微压线 | 系数偏保守；`lcad render --focus` 自检；评审时关注 |
| 自动居中使加一个尺寸就让整组视图平移几毫米 | 视图相对关系不变；需要钉住时用 `V.front.place(at=…)` |
| CI（Linux）无中文字体 | PNG 测试只断言产出，不比像素 |
| 布局质量不足导致 Agent 多轮调布局 | §4.6 的立场：先给事实和余量，评测显示需要时再考虑求解器 |

---

## 15. 偏离记录（相对 DESIGN.md v1.0）

| DESIGN | M0 做法 | 理由 |
|---|---|---|
| §3.3 日常产出含渲染用 SVG | M0 只产出 DXF 和 model.json；带 `data-id` 的 SVG 随 Viewer 在 M2 | BRIEF §2 把 SVG 划给 M2；M0 没有消费者 |
| §3.1 示例 `Drawing(template="templates/A3-GB.dxf")`，图纸目录有 `templates/` | M0 用内置数据模板 `Drawing(sheet="A3")`；`templates/` 留给 M1 企业模板，`git ls-files` 里可以没有它 | BRIEF 只要求最小图框标题栏；模板导入在 M1 |
| §7 CLI 列表含 `check / view / params / log / diff / template / export` | M0 只做 `init / build / edit / undo / context / render`；检查结果随 build / edit 输出 | BRIEF §2 的范围 |
| §4.2 查询 `d.selection()` | M0 不提供（`lcad context @sel` 能读 selection.json） | Viewer 在 M2 |
| §6 `lcad undo` 生成反向提交 | 撤销“一次撤销”在 M0 不支持，报错提示重做原修改 | 需要把删掉的行插回原位，M0 不值得为它加机制 |
| §4.6 线性 / 对齐尺寸 | M0 线性尺寸只做水平 / 竖直 | BRIEF 的“标注最小集”；对齐、角度尺寸进 M1 |
