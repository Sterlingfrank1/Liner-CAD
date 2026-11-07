# M0 BRIEF：骨架 + 索引

> 写给 M0 里程碑会话。流程和门禁见 `docs/ROADMAP.md`；设计依据见 `DESIGN.md`（下文的 § 均指它）。

## 1. 目标

搭好 Harness 的骨架，让“构建层 + 临时脚本 + 动作日志 + 事务 + git”这条主链路跑通，并且能画出三类零件的、看得过去的图。后续里程碑都在这副骨架上加东西，所以 M0 的重点是**数据模型和主链路设计对**，而不是功能多。

## 2. 范围

**必须做：**

| 模块 | 内容 | 依据 |
|---|---|---|
| 工程骨架 | `pyproject.toml`（uv）、包 `linercad`、`python -m linercad` 与 `lcad` 等价、pytest + ruff、GitHub Actions（PR 上跑 lint 和测试） | §7 |
| 图纸模型 | 元素 = 意图 + 布局；字段 `id / kind / intent / placement / refs / covers / tags / src / history / status`；`model.json` | §4.2 |
| 三级索引 | DXF 图元的 XDATA 写元素 ID；元素记录 `src`（drawing.py 行号或日志操作）和 `history`（edit 编号） | §4.1 |
| 引用与查询 | `d["ID"]`、`d.q.<kind>(...)`、带数量断言的几何选择器、`d.near(x, y)`；找不到时列出候选 | §4.3 |
| 参数 | `Param(值, min, max, step, unit, label, tol, rule)`，参数表达式，记录自己的源码位置（M2 写回源码要用） | §4.4、§5.2 |
| 2D 原生几何 | 视图、带线型角色的几何（粗实线、细实线、虚线、点画线…）、命名特征；视图按投影关系摆放并对齐 | §3.4 |
| 标注最小集 | 线性尺寸、直径、半径、中心线、注释、最小图框和标题栏；尺寸角色 size / position / overall | §4.2、§4.4 |
| 标注布局 | 确定性的语义放置 + 局部外推 + 冲突报告；写了的固定、没写的自动；数值来自标准档 | §4.6 |
| 标准档 | GB 档（数据化，不写死在代码里），结构上能叠加 ISO 档和企业档（这两者 M1 做） | §4.7 |
| 全剖视 | 剖面轮廓由 Agent 画；剖面线、剖切符号、剖视标注由 Harness 负责 | §3.4 |
| 修订层 | 修改类 API 调用自动记录为动作日志；按顺序重放；失效操作跳过并报告；`d.raw` 逃生口的改动也记录 | §3.2 |
| 事务与 CLI | `lcad init / build / edit / undo / context`；失败整体回滚，返回错误、相关元素和候选 | §3.2、§7 |
| 版本管理 | 一次成功修改一个 commit，提交信息 `eN · 用户原话`；只提交本图源文件；不 push；`.gitattributes` 固定 LF | §6 |
| 最小检查 | 重叠、越出图框、失效操作（完整 Checks v1 在 M1） | §4.5 |
| 渲染自检 | Agent 自检用的整图 / 局部 PNG（`lcad render [--focus ID]`），临时文件 | §3.3、§5.3 |
| 最小 Skill | 一份简短的 `SKILL.md`，让宿主 Agent 只看它就能用 CLI 完成出图和修改（M3 再完善、做安装器） | §7 |
| 三个范例 | 轴、法兰盘（全剖主视图）、支架，各一个图纸目录 | §10 |

**不做（留给后续）：** 形位公差 / 粗糙度 / 尺寸链 / 配合查表的完整实现（M1）、ISO 档和企业模板（M1）、其它剖视（M1）、Viewer 和带 `data-id` 的 SVG（M2）、`diff / log / export`（M2–M3 视需要）、3D 来源（M1 对照工具、M3 正式来源）。

## 3. 验收（G5）

1. 从干净 clone 安装后，轴、法兰盘、支架三张图都能 `lcad build` 出 DXF；法兰盘主视图为全剖，剖面线、剖切符号、剖视标注齐全。
2. 每张图完成 **5 轮以上**对话修改，覆盖不同类别：改布局（换侧 / 换排 / 微调）、改意图（值 / 公差文字）、加删元素、改参数后日志重放、`lcad undo` 撤销较早的一轮、失败事务回滚。
   - 由一个**独立 agent**扮演宿主 Coding Agent 完成：它只拿到 `SKILL.md` 和用户的修改请求，自己写临时脚本、调用 CLI。记录放进 `evidence/`。
   - 同样的修改脚本另做成确定性的自动化测试。
3. 每个图纸仓库里 `git ls-files` 只有源文件（`drawing.py`、`drawing.actions.jsonl`、模板、`.gitignore`、`.gitattributes`）；每轮修改恰好一个 commit，失败事务不产生 commit。
4. 确定性：同样的输入重建两次，DXF 实体和 `model.json` 一致。
5. 出图质量：三张图的渲染 PNG 由一个独立的多模态 agent 按评分表评审（视图、线型、尺寸是否重叠或越界、剖视表达），结论写进 HANDOVER。
6. CI 通过，HANDOVER 已合并，tag `v0.1-m0` 已推送。

## 4. 留给 SPEC 决定的问题

1. 2D 几何 API 的形状：轴类回转体怎么画（半轮廓镜像？）、圆和孔、线型角色的取值。
2. ID 的命名和自动生成规则；XDATA 的 appid。
3. 修改类调用怎么被记录（代理 / 记录器）、操作的 schema、相对操作的重放语义。
4. 范例放在哪里；验收和测试时图纸仓库建在临时目录，不能在开发仓库里产生图纸 commit。
5. PNG 渲染用什么依赖（ezdxf drawing add-on 配 matplotlib 或 PyMuPDF；本机两者都有）。
6. 给 Agent 的错误格式（异常类型、CLI 输出 JSON 还是文本）。

每个决定写进 SPEC，附一句理由。保持简洁：不加 DESIGN 没要求的规则和机制。

## 5. 参考（只取思想，不抄实现）

- SimpleCADAPI：`D:\Industry\Claude-Code\SimpleCADAPI\src\simplecadapi\`，重点看 `dxf_engine/`（DimDecl / Resolved / report、排号槽位、evaluate）、`ql.py`、`params/`、`recording/`、`editor/`。
- 旧项目 `D:\Industry\Claude-Code\projects\tool-cad-agent-v0.1`：只看教训，不看实现（`DESIGN.md` §1 的“旧坑”）。

## 6. Goal 条件

> M0 done when: SPEC and cards are merged; every M0 card PR is merged to main with CI green; from a clean clone, shaft, flange (full-section front view) and bracket each build to DXF and pass ≥5 rounds of lcad edit/undo driven by an independent agent using only SKILL.md; each drawing repo tracks only source files; render review is recorded; HANDOVER.md is merged and tag v0.1-m0 is pushed.
