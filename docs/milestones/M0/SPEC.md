# M0 SPEC：骨架 + 索引

> 依据：`docs/milestones/M0/BRIEF.md`（范围、验收、待决问题）、`DESIGN.md` v1.0（下文 § 指它）、`DRAFTING-COVERAGE.md`。
> 原则：只实现 DESIGN 和 BRIEF 要求的东西；每个决定附一句理由；偏离写在第 15 节。
> 状态：v2，已按 G1 独立评审的意见修订（评审意见与处理见第 16 节）。

---

## 1. 总体结构

### 1.1 数据流

```
drawing.py ──run──► Drawing（内存模型：Param + Element[]）
                       │  按顺序重放 drawing.actions.jsonl（失效操作跳过并报告）
                       ▼
                    layout（视图内标注语义放置 → 视图摆放 → 每个元素的图纸坐标图元 prims）
                       ▼
                    checks（重叠 / 越框 / 视图对齐 / 失效操作 → findings + element.status）
                       ▼
          ┌────────────┴────────────┐
   DXF writer（prims → 实体 + XDATA）   model.json（元素语义索引）       PNG（lcad render，临时）
          └───────── .linercad/build/ ┘
```

一次 `lcad edit`：**基准重建 → 在内存模型上跑临时脚本（自动记操作）→ 用“日志 + 新操作”从零重建 → 补全布局类操作的引擎取值 → 再重建 → 检查 → 追加日志 → git commit → 写产物**。提交的状态永远由“源 + 日志”从零重建得到，现场执行和日后重放不会分叉（§7.4）。

### 1.2 包结构

```
src/linercad/
  __init__.py        Drawing, Param, errors；__version__
  __main__.py        python -m linercad ≡ lcad
  errors.py          LinerError 及子类，to_dict()
  params.py          Param、ParamSet、Expr、安全表达式求值
  std/               gb.toml + load_std / load_template；templates/GB-A4|A3|A2.toml
  model.py           Element、ID 规则、Drawing 容器、build 上下文
  geometry.py        View 与 2D 几何（线、圆、弧、多段线、回转体、中心线、孔组）、锚点
  annotate.py        尺寸、注释、技术要求、标题栏字段、剖视、剖面线（意图层）
  query.py           d["ID"]、d.q、几何选择器、d.near
  text.py            字宽 / 字高估算（标准档里的实测系数）
  layout.py          视图内布局 + 视图摆放 + 图框标题栏技术要求排版；产出 prims
  checks.py          M0 最小检查
  dxfout.py          prims → ezdxf 文档（图层、线型、字体、XDATA），model.json
  render.py          PNG 渲染（全图 / 局部）
  record.py          修改类 API 的自动记录、操作注册表、重放
  runtime.py         build 管线
  txn.py             事务：init / build / edit / undo；git 封装
  cli.py             lcad 子命令（argparse），JSON 输出
  skill/SKILL.md     给宿主 Agent 的最小 Skill
  examples/{shaft,flange,bracket}/drawing.py
tests/               pytest；验收在 tests/acceptance/
```

---

## 2. BRIEF §4 待决问题的决定

| # | 问题 | 决定 | 理由 |
|---|---|---|---|
| 1 | 2D 几何 API 形状 | 视图内用**视图局部模型坐标**（mm，未缩放）作图；基本图元 `line / polyline / polygon / rect / circle / arc`，带 `role`；**回转体用 `turned(name, profile=[(x, r), …])`：给上半轮廓，工具镜像出下半、在每个轮廓转折处补一条贯通全径的竖线、自动画轴线**；圆和孔用 `circle` + `center_mark`，均布孔用 `holes_on_circle`；线型角色 `thick / thin / hidden / center / phantom`（粗实线 / 细实线 / 细虚线 / 细点画线 / 细双点画线） | 回转体镜像 + 转折竖线是确定的规定画法，交给工具画对；角色覆盖 M0 用到的线型，波浪线等随局部剖进 M1 |
| 2 | ID 命名与自动生成；XDATA appid | 见 §3.2：前缀 `V F E C D N H S T X`；**标注类（D、引线 N、H）必须起名**；临时脚本里创建的无名元素用**带 edit 编号的名字**（`e7_1`）；XDATA appid **`LINERCAD`**，内容 `[(1000, 元素ID), (1071, 子图元序号)]` | 前缀让 ID 一眼可读；日志里引用的 ID 不随 drawing.py 的增删而漂移；子图元序号支撑 `d.raw` |
| 3 | 修改类调用如何记录；schema；相对操作重放语义 | **装饰器记录器**：公开的修改类方法挂 `@mutator("op")`，临时脚本里只记录最外层调用；元素记成 ID、参数表达式记成源串、视图作用域的创建操作带 `view`；schema `{"edit","op","id","args"}`；`move` 是相对操作，重放时作用于当时的基准值；布局类操作（`place / move`）记录前补全引擎当时选定的其余布局字段 | Agent 照常写 Python（§8 “动作由临时脚本调用 API 时自动记录”）；表达式记源串，改参数后重放仍跟随参数；补全实现 §4.6 第 1 条 |
| 4 | 范例放哪；测试 / 验收图纸仓库 | 范例是包数据 `src/linercad/examples/<name>/drawing.py`，`lcad init <dir> --from <name>` 复制起步；测试一律用 pytest `tmp_path`，验收在系统临时目录 | `DRAFTING-COVERAGE.md` §2.3 要求 `lcad init --from <范例>`；开发仓库永不出现图纸 commit |
| 5 | PNG 渲染依赖 | **matplotlib**（ezdxf drawing add-on 的 `MatplotlibBackend`），`ax.set_xlim/ylim` 精确裁剪 | 原型实测 A3 整图约 1.1 s、中文正常；PyMuPDF 更快（0.4 s）但是 AGPL-3.0，不进核心依赖 |
| 6 | 给 Agent 的错误格式 | Python 侧抛 `LinerError` 子类（`code / message / id / candidates / values / hint`）；**CLI 一律向 stdout 输出一个 UTF-8 JSON 对象**（`ok` 打头），用法错误也是 JSON；退出码 0 成功 / 1 事务失败已回滚 / 2 用法错误 | 主要读者是 Agent；Windows 管道默认 GBK，统一 UTF-8 防乱码 |

其它实现决定（各附理由）：

| 决定 | 理由 |
|---|---|
| DXF 全部写在 modelspace 的**图纸坐标**（纸面 mm，原点在图幅左下角）；视图几何按绘图比例缩放后放入 | 版式、碰撞、裁剪在一个坐标系里，确定且简单；尺寸数字来自模型值，不受比例影响 |
| 尺寸、注释等标注**分解成基本实体**（LINE / SOLID / TEXT），不用 DXF DIMENSION 实体 | 布局引擎算的几何就是写出去的几何，碰撞检测准确；每个子实体都带 XDATA，点中任一部分都能找到整个尺寸（§4.1） |
| **字高按 GB 字高给出；DXF TEXT 的 height 是大写字母高（cap height）**。实测 simfang：中文字身 = 1.463 × cap height、半角字符宽 0.731 × cap height。所以**含中文的文字 DXF height = h / 1.463**（中文字身 = h），纯西文 = h；字宽按实测系数 × 字宽因子估算，不读字体文件 | 尺寸数字和汉字都符合 GB/T 14691 的字高；估算是固定常数，跨机器结果一致（确定性）；有测试保证估算 ≥ ezdxf 实测宽度 |
| 直径符号直接写 `Φ`（U+03A6），不用 `%%c` | 原型实测 simfang 下 `%%c` 渲染成方框 |
| DXF 保存时固定元数据（ezdxf `write_fixed_meta_data_for_testing`，仅保存期间打开） | 原型实测两次保存逐字节一致，diff 干净 |
| 内置模板（图框 + 标题栏）作为包数据，`Drawing(sheet="A3")` 选择；图纸目录的 `templates/` 留给 M1 企业模板 | M0 只要最小图框标题栏（偏离见 §15） |
| 参数只在 `drawing.py` 声明和修改；临时脚本通过只读的 `d.P` 使用参数表达式；给参数赋值报错并给出 `drawing.py:行号` | 参数是构建层的源（§3.2、§5.2 写回源码）；避免两处真相 |
| 中心线按“从中心向两端”分段写出（直线中心线分两半、十字中心线分四段），每段从长画起头 | GB/T 4457.4 要求点画线相交处为长画、首末两端为长画；DXF 线型图案从线段起点开始，这样相交处和外端都落在长画上 |
| 文字落在剖面线区域内时，DXF 写出时把文字框作为剖面线的孤岛（剖面线在文字处断开），不算冲突 | GB/T 4458.4：尺寸数字不能被任何图线通过，否则把图线断开 |

---

## 3. 图纸模型

### 3.1 坐标系

| 坐标系 | 用在 | 说明 |
|---|---|---|
| 视图局部模型坐标 | drawing.py 和临时脚本里作图；`Query.near()` | mm，未缩放。模型轴右手系，主视图从 −Y 向 +Y 看：主视 `(u, v) = (X, Z)`；俯视 `(X, Y)`；仰视 `(X, −Y)`；左视 `(−Y, Z)`；右视 `(Y, Z)`；后视 `(−X, Z)`。（第一角画法下，俯、仰、左、右视图靠近主视图的一侧都是物体后面。）共享轴的视图用同一组模型坐标作图，摆放后自动长对正、高平齐 |
| 图纸坐标 | DXF、`model.json` 的 `bbox / resolved`、`d.near()`、`lcad render --focus` | 纸面 mm，原点在图幅左下角 |

换算：`view.to_sheet(x, y)` / `view.to_local(x, y)`（布局之后可用）；`lcad context` 列出每个视图的原点和比例。

### 3.2 元素与 ID

元素字段（§4.2）：

| 字段 | M0 内容 |
|---|---|
| `id` | 见下表 |
| `kind` | `view / feature / edge / center / dim / note / hatch / section / table.cell / frame / raw` |
| `intent` | 要表达什么。几何：形状、视图局部坐标、`role`；尺寸：`type / view / p1 / p2 / dir / measured / value / expr / tol / prefix / suffix / override / text / role / datum`（或 `circle / c / r`）；… |
| `placement` | 请求的布局字段（尺寸 `side / row / offset` 或 `at`；注释 `dir / length / shift`；视图 `at / offset`）+ `auto`（由引擎取值的字段）+ `resolved`（解算结果，含 `bbox`）+ `reason`（调整原因） |
| `refs` | 所属视图（第一项）、所属特征、测量对象、锚点所在元素、基准 |
| `covers` | 承载的参数名：`value` 表达式里的参数（尺寸不继承 `Param.tol`） |
| `tags` | 角色标签 |
| `src` | drawing.py 创建：`{"file":"drawing.py","line":42}`（调用栈里最内层的 drawing.py 帧）；日志创建：`{"edit":"e7","line":12}`（日志行号） |
| `history` | 日志里创建或改过它的 edit 编号，按顺序 |
| `status` | `ok / warn / accepted(理由)` |

ID 规则（名字：Unicode 字母、数字、`_`、`-`，字母开头）：

| 前缀 | 元素 | 格式 | 名字 |
|---|---|---|---|
| `V` | 视图 | `V.<view>` | `front / top / bottom / left / right / rear` |
| `F` | 特征（一组边） | `F.<view>.<name>` | 可选；`polyline / polygon / rect` 不给名字时自动取 `<类型>_<n>` |
| `E` | 边 | 属于特征：`E.<view>.<特征名>.<k>`；无名单线 / 圆 / 弧：`E.<view>.<n>` | 特征内按创建顺序编号 |
| `C` | 中心线 | `C.<view>.<name>`，缺省 `C.<view>.<n>`；回转体轴线 `C.<view>.<特征名>`；孔组节圆 `C.<view>.<特征名>`、各孔径向线 `C.<view>.<特征名>.<k>` | 可选 |
| `D` | 尺寸 | `D.<name>` | **必须** |
| `N` | 引线注释 / 技术要求 | `N.<name>` / `N.tech.<k>` | 引线注释**必须**；技术要求按条编号，删除后不复用 |
| `H` | 剖面线 | `H.<view>.<name>` | **必须** |
| `S` | 剖视 | `S.<letter>` | 字母 |
| `T` | 图框 / 标题栏 | `T.frame`；`T.title.<field>` | 固定 |
| `X` | `d.raw_add` 加的实体 | `X.<n>` | 自动 |

- **临时脚本里创建的无名元素**，自动编号部分换成 `e<编号>_<n>`（例如 `E.front.e7_1`、`F.front.rect_e7_1`、`N.tech.e7_1`、`X.e7_1`），重放时用日志里记录的 ID 原样重建。这样日志里的 ID 不受 drawing.py 增删元素的影响。
- **多元素创建**：一次调用只有一个主 ID（返回的那个），子元素由主 ID 按固定顺序派生：
  - `turned`：边 = 上半各非竖直段（左→右）、下半各段（左→右）、各转折竖线（左→右）；轴线 `C.<view>.<name>`。
  - `holes_on_circle`：孔 `E.<view>.<name>.<k>` 从 `start` 角起逆时针；节圆 `C.<view>.<name>`；径向线 `C.<view>.<name>.<k>`。
  - `polyline / polygon / rect`：边按点序。
- 重复 ID 立即报 `duplicate_id`，并给出一个可用的建议名。
- 仍有的漂移风险：drawing.py 里**无名**的边和中心线按视图内顺序编号；在前面插入几何会让后面的编号变化。SKILL 要求凡是会被引用的几何都起名（见 §14）。

### 3.3 model.json

`.linercad/build/model.json`，每次重建重写；UTF-8、`ensure_ascii=False`、`indent=1`；浮点四舍五入到 4 位：

```json
{
 "schema": "linercad.model/0",
 "drawing": {"sheet": "A3", "std": "GB", "scale": "1:1", "edit": "e7", "frame": [25, 5, 415, 292],
             "views": {"front": {"origin": [120.5, 180.0], "scale": 1.0}}},
 "params": [{"name": "D", "value": 30, "min": 10, "max": 60, "step": 0.5, "unit": "mm",
             "label": "外径", "tol": "h7", "rule": null, "group": null, "src": {"file": "drawing.py", "line": 5}}],
 "elements": [
  {"id": "D.D", "kind": "dim",
   "intent": {"type": "dia", "view": "front", "p1": [20, 15], "p2": [20, -15], "dir": "v", "measured": 30,
              "value": 30, "expr": "D", "tol": "h7", "prefix": "", "suffix": "", "override": null,
              "text": "Φ30h7", "role": "size", "datum": null},
   "placement": {"side": "inside", "row": null, "offset": 0, "auto": [],
                 "resolved": {"bbox": [140.2, 165.0, 146.0, 195.0]}, "reason": ""},
   "refs": ["V.front"], "covers": ["D"], "tags": [], "src": {"file": "drawing.py", "line": 30},
   "history": ["e7"], "status": "ok"}
 ],
 "findings": [ "... §10 ..." ]
}
```

元素顺序 = 创建顺序（drawing.py 在前，日志在后）。图元 → 元素靠 DXF 的 XDATA，model.json 不存句柄。

---

## 4. Python API

命名直白、可组合。所有“点”参数接受 `(x, y)`（数字或参数表达式），或**锚点串** `"<元素ID>:<锚点>"`（边的 `start / end / mid`，圆、弧、十字中心线的 `center`）。锚点在重放时按当时的几何求值，所以用锚点加的尺寸会跟着参数变。

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
d.P            # 同一个 ParamSet；临时脚本里用它（只读）
```

- `Param(value, min=None, max=None, step=None, unit="mm", label="", tol=None, rule=None, group=None)`；创建时记下自己在 drawing.py 的 `{"file","line"}`（M2 写回源码用）。
- `d.params(**)` 一张图调用一次；校验值在 `[min, max]` 内、`rule` 成立，否则 `ParamError`（带参数名、值、范围或规则）。临时脚本里调用 `d.params` 或给 `d.P.<name>` 赋值都报 `ParamError`，提示去改 drawing.py 的那一行。
- `Expr` 支持 `+ - * / // **`、一元负、`abs()`、比较（返回 bool）、`float() / int() / round()`（后三者返回数字）、格式化；源串按优先级最少加括号。`eval_expr(src, values)` 用 `ast` 白名单求值：数字、参数名、算术、一元运算、比较、`and/or/not`、`abs(...)` 调用；其它节点报错。日志重放和 `rule` 校验都用它，不用 `eval`。
- 一个 drawing.py 只创建一个 `Drawing`；build 时由上下文捕获，不要求变量名。

### 4.2 视图与几何

```python
front = d.view("front")              # → V.front；已存在则返回同一个（不记录操作）
left  = d.view("left")               # 第一角画法：左视图在主视图右侧，高平齐

front.line(p1, p2, role="thick", name=None)         # → Edge；有 name 时同时建特征 F.front.<name>
front.polyline(points, role="thick", name=None)     # → Feature
front.polygon(points, role="thick", name=None)      # → Feature（闭合，可作剖面线边界）
front.rect((x, y), w, h, role="thick", name=None)   # → Feature（闭合）
front.circle(center, r, role="thick", name=None)    # → Edge；有 name 时同时建闭合特征
front.arc(center, r, start, end, role="thick", name=None)   # 角度制，逆时针
front.turned(name, profile=[(x0, r0), (x1, r1), ...], axis=0, role="thick")   # → Feature
front.centerline(p1, p2, name=None)                  # → CenterLine；两端各外延标准档值
front.center_mark(center, r, name=None)              # 圆的十字中心线，外延同上
front.holes_on_circle(name, center, pcd, n, d, start=90)   # → Feature：n 个孔 + 节圆 + 径向中心线
```

- `turned`：`profile` 为上半轮廓 `(x, r)`，x 单调不减，r > 0。工具画上半各非竖直段、镜像的下半各段，以及**每个转折处一条从 −r_max 到 +r_max 的竖线**（端面、台阶、倒角圆都由它表达；同一 x 的多个点取最大 r；共线的中间点不画竖线），再画轴线。`axis` 是轴线的 y。
- `Edge` 只读属性：`shape role length dir("h"/"v"/None) start end mid center r feature`。`Feature`：`type edges closed`。

### 4.3 标注

```python
front.dim.linear(name, p1=None, p2=None, dir=None, value=None, tol=None, role="size", datum=None,
                 prefix="", suffix="", text=None, side=None, row=None, offset=None, ref=None)
front.dim.dia(name, p1=None, p2=None, circle=None, at=None, ...)  # 非圆视图给 p1,p2；圆视图给 circle
front.dim.rad(name, circle, at=None, ...)                          # circle 必须是圆弧
front.note(name, text, anchor, dir=None, length=None)              # 引线注释
d.notes.tech(lines)            # 追加技术要求（str 或 list[str]），每条一个 N.tech.<k>
d.title(**fields)              # 标题栏字段，等价于逐个 d["T.title.<field>"].set(text=...)
d.section(letter, view, cut_in, through=[p1, p2], look=None)       # 全剖视 → S.<letter>
front.hatch(name, loops=[...])                                      # 剖面线 → H.front.<name>
```

- `linear`：M0 只做水平（`dir="h"`，量 Δx）和竖直（`dir="v"`，量 Δy）。`dir` 缺省：两点 y 相同取 h、x 相同取 v，否则报错要求给出。`ref=<直线边>` 等价于取它的两端。
- `value`：缺省为几何实测值；给参数表达式时显示表达式的值，`covers` 取表达式里的参数。
- `role`：`size / position / overall`。**`position` 必须给 `datum`**（元素 ID 或锚点），否则声明时报 `invalid_arg`（§4.4）。
- 显示文字 = `prefix` + (`Φ` / `R`) + 数值（去尾零，最多 3 位小数）+ `tol` + `suffix`；`text` 给出时整串替换（`set(text=None)` 恢复）。公差 M0 只作文字（`"g6"`、`"±0.1"`），查表在 M1。
- `dia`：非圆视图按线性尺寸处理并加 `Φ`；圆视图给 `circle`（圆、圆弧，或孔组 / 节圆这类圆形中心线），尺寸线过圆心、两端箭头抵圆，沿 `at` 方向引出水平折线写字。`rad` 只用于圆弧（整圆用直径，GB/T 4458.4），一端箭头抵圆弧，同样引出写字。
- `note`：从 `anchor`（几何上的点，带箭头）沿 `dir`（度）引出 `length`（mm），接水平折线，文字在折线上方。
- `section`：`view` 是画成全剖的视图，`cut_in` 是标剖切位置的视图，`through` 是剖切面在 `cut_in` 里的迹线（两点定线）。Harness 画：`cut_in` 视图几何外侧、迹线两端的粗短画；短画外端垂直于迹线的箭头（`look` 缺省按投影关系推出：第一角指向剖视图一侧，第三角相反；也可给 `left/right/up/down`，不能与迹线平行）；箭头外侧的字母；剖视图上方的 `A-A`。剖面轮廓由 Agent 自己画（§3.4）。
- `hatch`：`loops` 是闭合特征（`polygon / rect / circle`）或其 ID、圆边，或点列；嵌套的环是孤岛。图案、角度、间距来自标准档。

### 4.4 引用与查询（§4.3）

```python
d["D.D"]                                    # 元素；找不到抛 not_found，带相近 ID
d.q.dims(view="front", role="position")     # Query；按字段过滤
d.q.lines(view="front").where(length=30, dir="h").near(120, 45).exactly(1)   # near 用视图局部坐标
d.q.circles(view="left").where(r=6, tol=0.1).one()
d.near(210, 148, r=5)                       # 图纸坐标；按距离、面积排序
```

- `d.q.<种类>`：`views features edges lines circles arcs centers dims notes hatches sections cells all`；写错种类报错并列出全部。
- `Query`：`.where(**条件, tol=0.01)` 或 `.where(函数)`；`.near(x, y, r=2.0)`（视图局部坐标，结果必须属于同一视图，否则报错要求先 `view=`）；`.exactly(n)`、`.one()`、`.first()`、`.ids()`、`len()`、迭代、下标。
- `exactly(n)` 不满足时报 `count_mismatch`：列出实际命中的元素（ID、长度、方向、中点等），用过 `near` 时再给最近的几个候选和距离。
- 查询对象不能记进日志：临时脚本里先 `.one()` 取出元素，记录时自动变成具体 ID（§3.2）。

### 4.5 元素操作（临时脚本里的修改都走这些，自动记录）

| 调用 | 作用 | 记录 |
|---|---|---|
| `el.place(**布局字段)` | 尺寸 `side / row / offset`；圆视图直径半径 `at`；注释 `dir / length`；视图 `at`（图纸坐标，钉住整组视图，只对 `V.front`） | `place`，补全同组其余字段（§7.2） |
| `el.move(dx=0, dy=0)` | 相对微调。尺寸：只取外法向分量加到 `offset`（`inside` 尺寸取垂直于尺寸线的方向），沿尺寸线的分量非 0 报错；注释：平移折线和文字（`shift`）；视图：`V.front` 平移整组，其它视图只能沿不破坏对齐的方向（俯 / 仰视图只能 dy，左 / 右 / 后视图只能 dx）；边、特征、中心线：平移几何 | `move`，并补全同组的侧 / 排（或方向 / 长度），即“改过布局的元素从此固定” |
| `el.set(**意图字段)` 或 `el.tol = "g6"` | 尺寸 `value / tol / prefix / suffix / text / role / datum`；注释、标题栏字段 `text`；边 `role`；剖视 `look` | `set` |
| `el.suppress()` | 删除元素，连带它拥有的子元素（视图 → 视图里的元素；特征 → 边和它的中心线）。还有别的元素通过 `refs` 引用它时报错并列出这些元素 | `suppress` |
| `d.accept(rule, id, reason)` | 有意为之的警告放行，status 变 `accepted(理由)` | `accept` |
| `d.raw(id).entities[k].dxf.<属性> = 值` | 逃生口：改某元素第 k 个子图元的 DXF 属性（§7.5） | `raw` |
| `d.raw_add(dxftype, **dxfattribs)` | 逃生口：加一个原始实体（图纸坐标）→ `X.<n>` | `raw_add` |
| 建图和标注方法、`d.view(新视图)` | 加元素 | 以方法名为操作名：`view line polyline polygon rect circle arc turned centerline center_mark holes_on_circle dim.linear dim.dia dim.rad note notes.tech hatch section raw_add` |

- 只读属性：`id kind intent placement refs covers tags src history status view bbox`（`intent / placement` 返回深拷贝，改它不影响模型）；尺寸另有 `value text side row offset at`；`el.info()` 返回 model.json 里的那条记录。
- 临时脚本里读到的布局值是本轮修改**之前**的解算结果；本轮新建的元素布局值为 `None`。
- 在元素上调用不存在的方法 / 字段，错误列出这个种类可用的方法和字段（`delete()` 会提示 `suppress()`）。

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

1. **视图几何外框** G = 该视图全部边（含虚线）的外框，不含中心线外延、剖面线和剖切符号。第 k 排尺寸线距 G 对应边 `first_row + (k-1)·row_pitch + offset`。
2. **障碍物先就位**：边、中心线、剖切符号（位置由 G 和迹线决定）。
3. **固定元素**（布局字段全部写明的）按声明顺序就位，成为障碍。
4. **自动元素**依次放入：
   - **线性尺寸**（含非圆视图上的直径）：没写 `side` 时按两被测点中点相对 G 中心的位置取最近外侧（h 尺寸：中点在 G 中心之上取 top，否则 bottom；v 尺寸：在右取 right，否则 left）。同一侧按被测长度从小到大、再按声明顺序。没写 `row` 时从第 1 排试起，冲突就外推一排，最多 `max_rows` 排，记录原因（如“第 1 排与 D.l1 冲突，外推到第 2 排”）。
   - **文字**：水平尺寸写在尺寸线上方；竖直尺寸写在尺寸线左侧、旋转 90°（字头朝左）。依次试中点、3/4、1/4 处；放不下（尺寸线长 < 字宽 + 2·箭头长 + 2·间隙）时移到界线外（水平尺寸先右后左，竖直尺寸先上后下），箭头外翻。
   - `inside`：尺寸线直接画在两被测点之间，没有尺寸界线；`offset` 把尺寸线沿垂直方向平移。
   - **圆视图直径 / 半径**：没写 `at` 时依次试 `45, 135, 315, 225, 30, 150, 60, 120` 度。小圆（直径 < 2·箭头长 + 1）改为单箭头从外指向圆。
   - **引线注释**：没写 `dir` 时依次试 `45, 135, 315, 225, 60, 120, 300, 240` 度；`length` 缺省取标准档值。
5. **冲突判定**：文字框（外扩 `clearance`）与任何别的元素的线段或文字框相交；本元素的尺寸线、尺寸界线、引线穿过别的文字框；两条平行尺寸线共线（距离 < 0.01）且投影区间的**开区间**交集长度 > 0（端点相接的链式尺寸不算冲突，可以同排）。文字落在剖面线区域内不算冲突（写 DXF 时开孤岛）。
6. **排不好不硬排**：全部候选都冲突时，取冲突数最少的候选（并列取最靠前的），照样画出，并在 `reason` 里写明；检查（§10）会把它标为 `warn`，给出 `violations` 和 `corridors`。
7. **剖视名称** `A-A` 放在该视图全部内容之上 `label_gap` 处、G 的中心正上方。

### 5.2 视图摆放

1. 每个视图的“全外框” = 它全部 prims 的外框。
2. 主视图原点放在 (0, 0)；俯 / 仰视图按标准档投影方式放在主视图下 / 上方，**原点 x 与主视图相同**（长对正）；左 / 右视图放在主视图右 / 左侧，**原点 y 相同**（高平齐）；后视图放在左视图（第一角）右侧，原点 y 相同。相邻全外框之间留 `views.gap`；左右方向放的视图如果与已放好的视图重叠，继续外移到不重叠。
3. 只有一个视图时它就是基准；多个视图时必须有 `front`。
4. 整组居中到内图框；与标题栏或技术要求区重叠时先上移、再左移到刚好不重叠（不越出内框）；仍放不下就保持，由检查报告越框。
5. `V.front` 写了 `at` 时整组按它定位，不居中；各视图的 `offset`（`move` 累积）最后加上。

### 5.3 图框、标题栏、技术要求

- `T.frame`：图幅边线（细）、内图框（粗）、标题栏线（外粗内细）和固定标签。
- `T.title.<field>`：值文字在模板槽位内居中；超宽时按比例缩小字高（不小于 2.5）。
- 技术要求：标题“技术要求”和编号条文（按现存条目的顺序编号 `1.` `2.` …）从标题栏上方 `tech_notes.gap` 处向上排，左对齐标题栏左边；标题文字挂在第一条技术要求元素上。

### 5.4 确定性

输入相同输出相同：遍历顺序 = 元素创建顺序；候选顺序固定；不用随机数、不遍历集合；排序都有完整的平局规则。参数变化时，固定元素保留侧、排、偏移，只重算坐标；自动元素按同样习惯重排。

---

## 6. 标准档与模板（§4.7）

### 6.1 结构

- `src/linercad/std/gb.toml`：样式与数值，**每组注明依据** `basis`（标准号，或 `convention` = 标准没给具体数值、取教材通行值或实测值）。
- `load_std(name, overlays=()) -> dict`：读内置档，按顺序深度合并叠加档（dict 递归覆盖，标量和列表整体替换）。M0 只内置 GB；`"ISO"` 报错说明在 M1 提供；叠加机制用测试 overlay 验证（企业档在 M1）。
- `src/linercad/std/templates/GB-A4.toml / GB-A3.toml / GB-A2.toml`：图幅、边距、标题栏线和标签、命名字段槽位、技术要求区。`load_template(std, sheet)` 读入后补算 `title_block.origin` 和 `frame`（内图框）。

### 6.2 GB 档 M0 数值

| 组 | 值 | 依据 |
|---|---|---|
| 线宽 | 粗 0.5、细 0.25；剖切符号 0.7 | GB/T 4457.4-2002（粗:细 = 2:1，d 取 0.5 组；剖切符号线宽 1~1.5d） |
| 颜色（ACI） | 粗实线白 7、细实线绿 3、细虚线黄 2、细点画线红 1、细双点画线粉红 6；尺寸、文字、剖面线按细实线绿 3 | GB/T 14665-2012（机械工程 CAD 制图规则，与 GB/T 18229-2000 一致） |
| 线型图案（mm） | 虚线 画 4 隔 1；点画线 长画 20、隔 3、点 0.5、隔 3；双点画线 长画 20、隔 3、点、隔 3、点、隔 3 | convention。GB/T 17450-1998 以线宽 d 的倍数给出（画 12d、隔 3d、长画 24d、点 ≤0.5d），按细线 d=0.25 得画 3、隔 0.75、长画 6，屏幕和打印上过密；M0 取教材通行值（虚线画长 2~6、间隔约 1；点画线长画 15~30、间隔约 3）。点画线首末为长画、相交于长画由写出方式保证（§2） |
| 字体 | simfang.ttf，字宽因子 0.7；字高系列 1.8 2.5 3.5 5 7 10 14 20 | GB/T 14691-1993（长仿宋体，字宽约 h/√2） |
| 字形实测 | 中文字身 / cap height = 1.463；半角字符宽 / cap height = 0.731 | convention（ezdxf.fonts 对 simfang.ttf 的实测，见 §2） |
| 尺寸 | 字高 3.5；箭头长 3；尺寸界线超出尺寸线 2；界线起点间隙 0；文字离尺寸线 1 | 箭头长：GB/T 4458.4-2003（≥ 6d）；其余 convention（教材：界线超出约 2~3） |
| 箭头宽 | 1 | convention |
| 尺寸排布 | first_row 10、row_pitch 7、max_rows 6、clearance 0.5 | convention（DESIGN §4.6 给定的 GB 档默认值） |
| 中心线 | 超出轮廓 3 | convention（教材：超出 2~5；GB/T 4457.4 规定首末两端为长画） |
| 引线注释 | 默认长度 8、折线余量 1 | convention |
| 剖面线 | 45° 细实线，间距 3（ANSI31 按间距缩放） | GB/T 4457.5-2013（金属材料通用剖面线）；间距 convention |
| 剖切符号 | 粗短画长 6、离几何外框 2；箭头线长 6；字母字高 5；剖视名称字高 5、离视图内容 4 | GB/T 4458.6-2002（粗短画、箭头、字母、“×-×”）；数值 convention |
| 视图 | 投影 first；视图间距 8；各视图相对主视图的格位（第一角：俯 [0,-1]、仰 [0,1]、左 [1,0]、右 [-1,0]、后 [2,0]；第三角上下左右相反，后 [2,0]） | GB/T 14692-2008（第一角画法）；GB/T 4458.1-2002（基本视图配置）；间距 convention |
| 图幅 | A0 841×1189、A1 594×841、A2 420×594、A3 297×420、A4 210×297；装订边 a=25，c=10（A0~A2）/ 5（A3、A4） | GB/T 14689-2008 |
| 比例 | 优先 1:1 1:2 1:5 1:10 2:1 5:1 10:1；允许 1:1.5 1:2.5 1:3 1:4 1:6 2.5:1 4:1 | GB/T 14690-1993 |
| 标题栏 | 外形 180×56，在图框右下角；**内部分格为 M0 简化版**（名称、图号、材料、比例、质量、共 张 第 张、单位、设计、审核、日期） | GB/T 10609.1-2008（外形尺寸）；分格 M1 做完整版 |
| 技术要求 | 标题字高 5、条文字高 3.5、行距 1.6h、离标题栏 5 | convention |

图层：每个角色一个图层 `THICK THIN HIDDEN CENTER PHANTOM DIM TEXT HATCH SECTION`，名称、颜色、线宽、线型都从标准档读。图框和标题栏线用 THICK / THIN，标题栏和技术要求文字用 TEXT。

---

## 7. 修订层：动作日志（§3.2）

### 7.1 记录

- 构建 drawing.py 时不记录（构建层就是代码本身），只记 `src`。
- 临时脚本里每次**最外层**调用 `@mutator` 方法记一条操作；内部嵌套调用不重复记；`d.view()` 取已有视图、`d.title()` 本身不记（它展开成逐字段的 `set`）；`d.notes.tech([...])` 每条记一条。
- 参数序列化：元组 → 列表；`Expr` → `{"expr": "D / 2"}`；元素 → ID 串；锚点串原样；`Query` → 报错（要求先 `.one()`）。
- **创建类操作**：`id` = 主 ID；视图作用域的操作（几何、`dim.*`、`note`、`hatch`）`args` 里带 `"view"`。**修改类操作**（`place move set suppress accept raw`）：`id` = 目标 ID。
- 行格式（UTF-8、LF、紧凑、键顺序固定）：

```jsonl
{"edit":"e7","op":"place","id":"D.D","args":{"side":"right","row":1,"offset":0}}
{"edit":"e7","op":"set","id":"D.D","args":{"tol":"g6"}}
{"edit":"e8","op":"notes.tech","id":"N.tech.e8_1","args":{"text":"去毛刺"}}
{"edit":"e8","op":"dim.linear","id":"D.l9","args":{"view":"front","name":"l9","p1":"E.front.body.3:start","p2":"E.front.body.5:end"}}
{"edit":"e9","op":"suppress","id":"D.chamfer","args":{}}
```

### 7.2 布局类操作的补全

`place` 和 `move` 的目标若有未写明的同组布局字段（尺寸：`side / row / offset` 中的 `side / row`；圆视图尺寸：`at`；注释：`dir / length`），事务在第一次重建后读取目标的解算结果，把这些字段补成具体值写进日志行的 `args`（`move` 行同时带 `dx / dy` 和补全的字段；重放时先设绝对字段，再加相对量）。于是“改过布局的元素从此固定”（§4.6 第 1 条），只有 `offset / shift` 保持相对。

### 7.3 重放

按日志顺序逐条执行：创建类操作用记录的 ID 建元素（ID 已存在 → 失效）；修改类操作先找目标（不存在 → 失效）；参数表达式和锚点按当时的值求值；任何 `LinerError` 都使这条操作失效；非 `LinerError` 异常同样记为失效，原因写“内部错误：类型: 信息”。失效操作跳过、不影响其余操作，以 `stale_op` 规则进入 findings（§10），附 `edit / line / op / candidates`。

**本次 edit 自己的新操作**在重建中失效则是错误：整个事务回滚（code `stale`；非 `LinerError` 时 code `build`）。

处理失效操作的办法（写进 SKILL）：撤销产生它的那一轮（`lcad undo eK`）；或者重新做一次修改，再撤销旧的一轮；或者 `d.accept("stale_op", <目标ID>, 理由)`；也可以手改 `drawing.actions.jsonl` 后 `lcad build -m`。

### 7.4 为什么“从零重建”

脚本在基准模型上现场执行只用来**收集操作**；提交的结果来自“drawing.py + 旧日志 + 新操作”的全新重建。commit 里的日志重放出来的图，就是这次给 Agent 看的图。代价是一次 edit 重建 2~3 次，范例图单次重建目标 < 1 s。

### 7.5 逃生口 `d.raw`

- `d.raw(id)` 返回只读代理：`.entities` 是该元素按写出顺序的子实体列表，每项有 `.dxftype` 和 `.dxf`；只支持 `.dxf.<属性>` 读写，调用其它方法报错（避免改了却不会被记录）。
- 读：返回当前构建里该实体的属性值。写：记 `raw` 操作 `{"sub": k, "attr": "color", "value": 1}`（向量写成列表），在**写 DXF 时**作为覆盖应用；不影响布局和检查。重放时 `k` 越界或属性名无效 → 失效。
- `d.raw_add(dxftype, **dxfattribs)`：在图纸坐标里加一个原始实体，元素 `X.<n>`（kind `raw`），带 XDATA；不参与布局和检查。

---

## 8. 事务、CLI 与 git

### 8.1 图纸目录

```
<part>/
  drawing.py  drawing.actions.jsonl  .gitignore（.linercad/）  .gitattributes（* text=auto eol=lf）   ← 入库（M0 无 templates/）
  .linercad/build/{drawing.dxf, model.json}   .linercad/tmp/（临时脚本、PNG）                       ← 不入库
```

`lcad` 在当前目录工作，`-C <dir>` 指定图纸目录。图纸目录可以是独立仓库，也可以在大仓库的子目录里；git 命令都带 `-C` 和路径限定，子进程统一 UTF-8。

### 8.2 命令

| 命令 | 行为 | 提交 |
|---|---|---|
| `lcad init <dir> [--from shaft\|flange\|bracket] [--sheet A3]` | 目录已有 `drawing.py` 或日志时拒绝；建源文件（`--from` 复制范例，否则写最小起步模板）和空日志；不在 git 仓库里就 `git init`；构建一次验证 | `e0 · init` |
| `lcad build [-m "<原话>"]` | 重建产物。给了 `-m` 且本图源文件（含手改的日志）有改动时提交；构建失败不提交，源文件保持 Agent 改后的样子，旧产物不动 | `eN · <原话>` |
| `lcad edit <script.py> -m "<原话>"` | 事务执行临时脚本（须定义 `apply(d)`），见 §1.1。**本图源文件里未提交的改动（例如同一轮里改了 drawing.py 的参数）一并进入这个 commit**。脚本没产生任何操作 → `no_ops` 失败 | `eN · <原话>` |
| `lcad undo <eK> [-m "<原话>"]` | 要求本图源文件没有未提交改动（`dirty`）；删掉日志里 `edit == eK` 的行；该 commit 若改过 drawing.py，按它的 diff 反向应用（`git apply -R`），冲突则回滚并报告冲突的文件和内容；重建（后续依赖它的操作报为失效）；提交。`e0` 和撤销一次撤销不支持（报错说明）；未知编号报错并列出可撤销的编号 | `eN · <原话 或 "undo eK">`，正文带 `Undo-Of: eK` |
| `lcad context [ID … \| @sel]` | 无参数：摘要（图幅、比例、各视图原点、参数、按种类列出的元素要点、findings、最近几次修改）；给 ID：完整记录、邻近元素、源码片段（drawing.py 前后几行或日志行）、可直接粘进脚本的示例代码；`@sel` 读 `.linercad/selection.json`（M2 才会写） | 否 |
| `lcad render [--focus ID] [-o out.png] [--dpi N]` | 重建（不提交）后出 PNG 到 `.linercad/tmp/`；`--focus` 按元素外框加 15 mm 边距裁剪、提高分辨率，该元素画成红色 | 否 |

- **编号**：`eN` 的 N = max(日志里的编号、本目录 git 提交标题里的 `eN`) + 1；`init` 为 `e0`。
- **只提交本图源文件**：`git add` + `git commit -m … -- <本图源文件路径>`，不碰仓库里其它已暂存的改动；不 push；没配置 git 身份时只对这次提交加 `-c user.name=linercad -c user.email=linercad@localhost`。
- **回滚**：日志在 commit 前追加，commit 失败就恢复原内容；产物最后写，先写临时文件再替换。
- `.linercad/tmp/` 只保留最近 20 个文件。

### 8.3 输出

成功：

```json
{"ok": true, "edit": "e7", "commit": "a1b2c3d", "ops": [/* 本次追加的日志行 */],
 "changed": ["D.D"], "warnings": [/* findings，本次新出现的带 "new": true */],
 "dxf": ".linercad/build/drawing.dxf", "model": ".linercad/build/model.json"}
```

`changed` = 本次操作创建或作用的元素 ID。失败（退出码 1，已回滚：日志不变、无 commit、旧产物不动）：

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

- ezdxf `R2018`，`$INSUNITS=4`（mm），`$MEASUREMENT=1`；图层、线型（标准档图案）、文字样式 `LC`（字体、字宽因子）、appid `LINERCAD` 按标准档建立。
- prims → 实体：LINE、CIRCLE、ARC、TEXT（中心对齐；竖直尺寸文字旋转 90°；字宽因子写在实体上）、SOLID（实心箭头）、HATCH（ANSI31 按间距缩放；落在区域内的文字框加为孤岛）。每个实体带 XDATA `[(1000, id), (1071, 子图元序号)]`。
- 实体顺序 = 元素顺序 × 子图元顺序；`raw` 覆盖在此时应用；保存时固定元数据，同输入逐字节一致。

### 9.2 PNG

ezdxf drawing add-on + matplotlib：白底；线宽按绝对值；画布 = 图幅尺寸（英寸 = mm / 25.4），坐标轴范围 = 图幅，所以图纸坐标与像素一一对应；`--focus` 用 `set_xlim / set_ylim` 精确裁剪。颜色：通过属性覆盖把全部实体画成黑色、焦点元素画成红色。整图默认 150 dpi，局部 300 dpi。字体缺失时 ezdxf 自动替代（Linux CI 上中文可能是方框，不影响测试）。

---

## 10. 最小检查（§4.5 的子集；完整 Checks v1 在 M1）

| 规则 | 内容 | 严重度 | 依据 |
|---|---|---|---|
| `overlap` | 文字框（尺寸数字、注释、字母、剖视名称、标题栏值、技术要求）与其它元素的线段、文字框相交（剖面线除外，见 §2） | warn | GB/T 4458.4-2003（尺寸数字不能被任何图线通过） |
| `out_of_frame` | 元素外框越出内图框，或压到标题栏 / 技术要求区（这两区自己的元素除外） | warn | GB/T 14689-2008 |
| `view_align` | 主视与俯 / 仰视图几何的 X 范围、主视与左 / 右 / 后视图的 Z 范围、俯视的 Y 范围与左视的 Y 范围不一致（容差 0.01 mm × 比例） | warn | GB/T 4458.1-2002（长对正、高平齐、宽相等）；DESIGN §3.4 |
| `stale_op` | 日志重放中的失效操作 | warn | DESIGN §3.2 |

finding：`{"rule","severity","id","message","violations":[{"with","overlap"}],"corridors":{"left","right","up","down"},"std"}`，`stale_op` 另带 `edit / line / op / candidates`。`corridors` 是文字框上下左右可移动的距离（按障碍物外框近似，最大 50 mm）。M0 的检查都不阻断提交；`accept` 过的不再报。

---

## 11. Skill 与范例

- **`src/linercad/skill/SKILL.md`**（≤ 300 行）：是什么；工作循环（`lcad context` → 写 `.linercad/tmp/*.py` 的 `apply(d)` → `lcad edit 脚本 -m 用户原话` → 读 JSON → `lcad render` 自检 → 需要时 `lcad undo`）；什么时候改 drawing.py（参数、视图、几何结构）、什么时候写临时脚本（标注、布局、意图），两者可在同一轮里一起提交；API 速查；坐标和 ID（标注要起名、被引用的几何要起名）；错误 JSON 和常见 code；处理失效操作的办法；三类零件的 GB 表达要点（轴：轴线水平、直径 inside、长度链式但留一段不注或加括号作参考尺寸、总长单独一排；法兰：全剖主视图 + 端面视图、剖切符号、`n×Φd EQS` 和节圆直径；支架：三视图、虚线、长对正高平齐）；不要做的事（不手改产物、不自己 git commit）。
- **三个范例**（`src/linercad/examples/`），A3、1:1、标题栏和技术要求齐全，构建零 warning：
  - `shaft` 阶梯轴：五段、两端倒角；主视图；直径 inside；轴向长度链式在下方（留一段不注），总长另起一排。
  - `flange` 法兰盘：盘 + 凸台 + 通孔 + 4 个均布螺栓孔（位于 0°/90°/180°/270°，剖切面过两孔）；**主视图全剖**（剖面线、`A-A`），左视图为端面视图，标剖切符号、`4×Φ… EQS` 和节圆直径。
  - `bracket` 支架：L 形底板 + 立板，底板两孔、立板一孔；主、俯、左三视图（俯视 `(X, Y)`，立板在靠近主视图一侧），虚线表达孔。

---

## 12. 验收项 → 测试 / 演示

| BRIEF §3 | 映射 |
|---|---|
| 1 三图 `lcad build` 出 DXF；法兰全剖，剖面线、剖切符号、剖视标注齐全 | `tests/acceptance/test_examples.py`：每个范例 `init --from` 到临时目录、`build`，断言 DXF 存在、零 warning；法兰断言 HATCH 实体、`S.A` 在左视图的粗短画 + 箭头 + 字母、主视图上方 `A-A`。G5 从干净 clone 演示 |
| 2 每图 ≥ 5 轮对话修改，覆盖各类 | **固定的用户请求清单**（下表）同时用于：① `tests/acceptance/test_rounds.py`（手写的确定性脚本，经 CLI 驱动）；② G5 独立 agent（只拿 SKILL.md 和这些请求原话），它写的临时脚本和 CLI 输出归档到 `evidence/` |
| 3 `git ls-files` 只有源文件；每轮恰好一个 commit；失败不产生 commit | 每轮后断言 `git ls-files` = `{drawing.py, drawing.actions.jsonl, .gitignore, .gitattributes}`，commit 数 = 成功轮数 + 1（init） |
| 4 确定性 | `tests/test_determinism.py`：同输入重建两次，DXF 字节和 model.json 字节相同；另比较实体列表（类型、属性、XDATA） |
| 5 出图质量 | G5：三张整图 PNG + 下面的评分表交给独立多模态 agent，结论写进 HANDOVER |
| 6 CI、HANDOVER、tag | GitHub Actions（lint；ubuntu py3.11；windows py3.13）；HANDOVER PR；`v0.1-m0` tag |

**用户请求清单**（每个零件 8 轮，覆盖 BRIEF 列的六类；第 7 轮按设计会失败）：

| 轮 | 类别 | 轴 | 法兰盘 | 支架 |
|---|---|---|---|---|
| 1 | 改布局（换侧） | 把总长尺寸挪到轴的上方 | 把凸台外径尺寸挪到主视图另一侧 | 把总高尺寸挪到主视图右侧 |
| 2 | 改意图（公差文字） | 最粗那段的直径加公差 k6 | 中心孔直径加公差 H7 | 立板孔直径加公差 H8 |
| 3 | 加元素 | 加一条技术要求：去除毛刺锐边 | 在主视图标注凸台长度 | 在俯视图标注两孔的孔距 |
| 4 | 删元素 | 删掉右端倒角的标注 | 删掉第 3 条技术要求 | 删掉左视图上的板厚尺寸 |
| 5 | 改参数后日志重放 | 总长改成 原值+20（改 drawing.py 参数） | 外径加大 10 | 底板加长 10 |
| 6 | 改布局（换排 / 微调） | 把第 1 轮挪过的总长尺寸再往外挪 3 mm | 把节圆直径的引出角度换到左上方 | 把孔距尺寸放到第 2 排 |
| 7 | 失败事务回滚 | 把不存在的尺寸 D.key 的公差改成 h9（应报错并回滚，向用户说明） | 同左，用不存在的 D.slot | 同左，用不存在的 D.rib |
| 8 | 撤销较早一轮 | 撤销第 2 轮 | 撤销第 3 轮 | 撤销第 2 轮 |

**出图评分表**（每项 1~5 分；通过：没有低于 3 分的项，均分 ≥ 3.5）：视图选择与投影关系（三视图对齐、方向正确）；线型线宽（粗细、虚线、点画线的使用）；尺寸（无重叠、无越界、文字方向、排布清楚、无封闭尺寸链）；剖视表达（剖面线、剖切符号、箭头、字母、`A-A`）；图框标题栏和技术要求；整体观感。

单元测试按模块覆盖：参数与表达式、标准档加载叠加、ID 与查询（含错误候选）、几何（回转体、孔组、六个视图的轴映射）、标注意图、文字估算（≥ ezdxf 实测，有 simfang 时运行）、布局（换排、外推、文字外移、冲突报告、确定性）、DXF（XDATA、图层线型、剖面线孤岛、中心线分段）、记录与重放（失效、补全、move 相对、raw）、事务（回滚、dirty、编号、源文件一并提交）、CLI（JSON 结构、退出码、UTF-8）。

---

## 13. 卡片

每张卡一个 issue（label `card`，milestone `M0 骨架+索引`）、一个分支 `m0/<slug>`、一个 PR（第一个 commit 是会失败的测试）。

| # | slug | 内容 | 档位 | 依赖 |
|---|---|---|---|---|
| C1 | `skeleton-ci` | pyproject（uv、uv_build）、包骨架、`lcad --version` 与 `python -m linercad` 等价、JSON 用法错误、UTF-8 stdout、pytest、ruff、GitHub Actions、`errors.py` | Opus | — |
| C2 | `std-profile` | `gb.toml`（§6.2 数值 + 依据）、三个模板、`load_std` 叠加、`load_template` | Sonnet | C1 |
| C3 | `params` | `Param / ParamSet / Expr`、安全求值、范围与 rule 校验、源码位置、只读赋值报错 | Sonnet | C1 |
| C4 | `model-core` | `Element`、ID 规则、`Drawing` 容器与 build 上下文、视图、2D 几何、锚点、查询与候选、`@mutator` 钩子（空记录） | Opus | C2 C3 |
| C5 | `annotations` | 尺寸三类、注释、技术要求、标题栏字段与图框元素、剖视、剖面线（意图层）；suppress 依赖检查 | Opus | C4 |
| C6 | `layout-checks` | `text.py` 估算；§5 布局（视图内、视图摆放、图框标题栏技术要求、剖切符号与名称）；§10 检查；prims；`to_sheet / to_local` | Opus | C5 |
| C7 | `dxf-output` | §9.1 DXF、model.json、确定性测试 | Opus | C6 |
| C8 | `action-log` | §7 记录器、注册表、重放与失效、布局补全、move、set、suppress、accept、raw、raw_add、edit 编号作用域的自动名 | Opus | C7 |
| C9 | `txn-cli` | runtime 管线、§8 事务与 git、CLI 全部命令、JSON 输出与退出码、tmp 清理 | Opus | C8 C10 |
| C10 | `render-png` | §9.2 `render.py` | Sonnet | C7 |
| C11 | `examples` | 三个范例 + `init --from` 测试 + 零 warning | Sonnet | C9 |
| C12 | `skill` | `SKILL.md` | Sonnet | C11 |
| C13 | `acceptance-tests` | `tests/acceptance/`（§12 第 1~4 项的自动化部分，含请求清单的确定性脚本） | Sonnet | C11 |

- 并行：C2 ∥ C3；C8 ∥ C10（C10 只碰 `render.py`）；C12 ∥ C13。核心卡（C4–C9）由里程碑会话（Opus）顺序完成。C4 含查询：查询与模型、几何的测试共用夹具，拆开反而增加交接。
- **里程碑任务**（不设卡）：G5 演示与 `evidence/`、出图评审、HANDOVER、tag。

---

## 14. 风险

| 风险 | 缓解 |
|---|---|
| drawing.py 里无名边、中心线的编号随增删漂移，日志里的具体 ID 指向别的边 | 标注必须起名；脚本创建的元素用 edit 作用域的名字；SKILL 要求被引用的几何起名；M1 视评测情况考虑几何指纹 |
| TTF 字形与估算不一致，渲染出来仍有轻微压线 | 系数来自实测并有测试；`clearance` 余量；`lcad render --focus` 自检 |
| 自动居中使加一个尺寸就让整组视图平移几毫米 | 视图相对关系不变；需要钉住时 `V.front.place(at=…)` |
| Linux CI 无中文字体 | PNG 测试只断言产出与尺寸，不比像素 |
| 布局质量不足导致 Agent 多轮调布局 | §4.6 的立场：先给事实和余量，评测显示需要时再考虑求解器 |

---

## 15. 偏离记录（相对 DESIGN.md v1.0）

| DESIGN | M0 做法 | 理由 |
|---|---|---|
| §3.3 日常产出含渲染用 SVG | M0 只产出 DXF 和 model.json；带 `data-id` 的 SVG 随 Viewer 在 M2 | BRIEF §2 把 SVG 划给 M2；M0 没有消费者 |
| §3.1 `Drawing(template="templates/A3-GB.dxf")`，图纸目录有 `templates/` | 内置数据模板 `Drawing(sheet="A3")`；M0 的图纸目录没有 `templates/` | BRIEF 只要求最小图框标题栏；模板导入在 M1 |
| §7 CLI 含 `check / view / params / log / diff / template / export` | M0 只做 `init / build / edit / undo / context / render`；检查结果随 build / edit 输出 | BRIEF §2 的范围 |
| §4.2 `d.selection()` | M0 不提供（`lcad context @sel` 能读 selection.json） | Viewer 在 M2 |
| §6 “对 lcad edit，commit 的 diff 就是追加的那几条操作” | 同一轮里 Agent 若也改了 drawing.py，未提交的源文件改动并入这次 edit 的 commit | 保证“一轮修改恰好一个 commit”（BRIEF §3.3），也不限制 Agent 改哪一层（§3.2） |
| §6 `drawing.py` 的撤销用 `git revert`，冲突由 Agent 处理 | 用 `git apply -R` 只反向应用 drawing.py 部分；冲突时整体回滚并报告冲突内容，Agent 手改 drawing.py 后 `lcad build -m` | `git revert` 会连带日志行一起反转，与“按编号删行”冲突；回滚保持事务语义 |
| §6 撤销生成反向提交 | 撤销“一次撤销”在 M0 不支持，报错提示重做原修改 | 需要把删掉的行插回原位，M0 不为它加机制 |
| §4.6 线性 / 对齐尺寸 | 线性尺寸只做水平 / 竖直 | BRIEF 的“标注最小集”；对齐、角度尺寸在 M1 |

---

## 16. G1 评审处理记录

独立评审（新上下文 agent，2026-11-07）结论 “approve with changes”。major 项全部处理：B1 edit 可一并提交源文件改动（§8.2、§15）；B2 改用 matplotlib（§2）；D1 创建操作带 `view`（§7.1）；D2 多元素创建的主 ID 与派生顺序（§3.2）；D3 标注必须起名 + 脚本创建元素用 edit 作用域名（§3.2）；D4 `d.P`（§4.1）；D5 `move` 补全侧排（§4.5、§7.2）；D6 开区间（§5.1）；D7 raw 规则（§7.5）；D8 suppress 级联与依赖报错（§4.5）；E1 六视图轴映射（§3.1）；E2 轴不注封闭尺寸链（§11）；E3 中心线分段写出（§2）；E4 字形实测与 CJK 字高（§2、§6.2）；F1 坐标换算（§3.1）；F2 JSON + UTF-8（§2）。minor 项除下列外均已处理：C1 视图 `move` 保留（只沿不破坏对齐的方向，实现很小，且对应“微调”类请求）；G3 C4 不拆（理由见 §13）。
