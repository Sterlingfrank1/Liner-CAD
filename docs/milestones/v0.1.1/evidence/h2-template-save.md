# H2 用户参数化模板（save / list / init --from --set）证据

卡 H2（issue #105，W3，P2 非核心）· 分支 `m5/h2-template-save`（基于 main 9300fd7 之后的 H4 合并点）· 热点 `commands.py`、模板清单/存放、`skill/pages/api.md`

## 实现

- **`lcad template save <名> --description "…" [--force]`**：在图纸目录里运行。
  - 前提：该图 `check` 0 error（build 的 error finding 数 = 0；warning 可保留）；有 error 时返回 `invalid_arg` 并列出出错 ID，不写模板。
  - 只保存**构建层**：`drawing.py` + 可选 `model.py` + `templates/`（企业档 overlay）；清单 `template.json` 含 名称 / 描述 / 参数（value、min、max、step、unit、tol、rule）/ 创建时间 / 文件列表 / 来源。
  - **修订层存在时提示**：`drawing.actions.jsonl` 非空时输出 warning「修订层有 N 条操作：模板只保存构建层 drawing.py，修订层不保存；需要保留请先并入 drawing.py」。
  - 有未提交源文件时 warning「按当前文件保存」。
  - 名字校验：字母/数字开头，只含字母数字 `_.-`，不得与内置范例名冲突；已存在需 `--force`（旧模板在 staged 校验通过前不动）。
- **存放位置（用户级，不进图纸 git；DESIGN §3.1 的 .linercad 语义）：** ```LCAD_TEMPLATES``` 覆盖；默认 Windows `%APPDATA%/linercad/templates`，其他系统 `$XDG_DATA_HOME/linercad/templates` 或 `~/.local/share/linercad/templates`。每个模板一个目录（drawing.py / 可选 model.py / templates/ / template.json），原子写入（临时目录 + rename）。
- **`lcad template list`**：输出 `{home, templates:[清单…]}`，空目录也 `ok:true`。
- **`lcad init <目录> --from <用户模板> [--set K=V …]`**：复制模板源文件（含 model.py / templates/）→ 按 `K=V` 重写 `name=Param(<数字字面量>, …)` 默认值 → 正常 build / e0 commit；`--set` 找不到参数或值非数字时在写目录前失败并回滚（不留半成品）。用户模板自带图幅，`--sheet` 会被拒绝而不是静默忽略。内置范例 `--from` 行为不变，且 `--set` 对范例同样可用。
- **skill**：`skill/pages/api.md` 新增「用户模板」一节（save / list / init --set 示例、存放位置与环境变量、只存构建层与修订层提示、**匹配即从模板起步**规则）；`SKILL.md` 路由表增加一行指向该节。`lcad skill`（主文件与 api 页）还会**动态追加「当前用户模板」节**，列出已保存模板的名称、描述、参数值与范围（无模板时提示 save）。

## 测试（G2 先失败：14 failed）

`tests/test_templates.py`（24 个）：save 清单/参数范围、list、check error 拒绝（conv_dim）、修订层 warning、内置名/重名/--force、init --from --set 一步出图（参数生效 + 0 error）、未知模板候选、未知参数回滚、model.py 复制、list CLI、--sheet 拒绝、非 git 目录、模板单跑校验（修订层补尺寸 / 缺 ref.dxf）、新进程校验、--force 失败保留旧模板、junk 条目、skill 动态列出模板、开区间参数显示；`tests/test_skill.py`：api.md 含模板命令/--set/LCAD_TEMPLATES/修订层/「从模板起步」规则。H2 定向共 25 passed（G2 首笔 14 failed）。

## 牛鼻刀基线（换规格提速实测）

方法：临时目录 + Python 驱动，`time.perf_counter` 包住 lcad 进程；数字为**本机 lcad 侧墙钟**（含进程启动；Agent/模型耗时不在 lcad 内，按 PLAN 由 C4/E7 统计）。图纸为参数化牛鼻刀（参数 D=切削直径、R=刀尖圆角、L=总长、Lc=刃长，前视 + 左视 + 4 个尺寸）。两边均 `errors: 0`。

| 流程 | lcad 命令 | 实测 |
|---|---|---|
| 首次出图（空目录 → `init` 2.94s + 手写 drawing.py + `build` 2.98s） | 2 | **5.92 s** |
| `template save bull-nose` | 1 | 1.79 s |
| 换规格（模板）：`init 新目录 --from bull-nose --set D=6 R=0.5` | **1** | **2.21 s** |
| 对照（不用模板）：手改 2 处 Param + `build` | 1 | 3.44 s |

模板换规格结果：`init` 一条命令 0 error，参数确认 `{D:6, R:0.5, L:65, Lc:18}`；无需重写 drawing.py。首次出图 5.92 s 中最费时的是从零写图纸（本表只计 lcad 侧，实际模型设计/迭代由 C4/E7 度量）。

## 验证

- 全量 `uv run pytest` / `ruff check` / `ruff format --check` / `evals --baseline` / CI 四项：见 PR 评论。
- 未动规则/布局/基线；D 应保持 0.965724（2830, 97）。