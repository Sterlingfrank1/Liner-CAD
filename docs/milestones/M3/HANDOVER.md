# M3 HANDOVER：3D 来源与复杂零件

> SPEC：`docs/milestones/M3/SPEC.md`；证据：`docs/milestones/M3/evidence/`。

## 1. 交付

| PR | 卡 | 内容 |
|---|---|---|
| #55 | SPEC | 详细设计；G1 独立评审一轮（3 blocker、8 should-fix 并入） |
| #63 | S1 | 3D 来源：`d.model`、`V.project`（全剖 / 半剖 / 偏移面 / 局部剖 / 肋板）、曲线类型保留、`src3d` 来源与 `src3d_refs`、投影缓存、`missing_extra`；范例 `gear_cover`。G4 评审一轮（3 blocker 已修） |
| #64 | S3 | 装配：`Drawing(kind="assembly")`、`d.component`、`d.std_part`（6 个标准，带标准号）、`d.bom`（明细栏 + 序号）、按接触着色的剖面线、实心件不剖、接触面单线、配合代号 `H7/k6`；L3 三例 bearing / jack / vise。G4 评审一轮（8 should-fix 已修） |
| #65 | S2 + S4 + S5 | `lcad log` / `diff` / `export` 与 Viewer 版本对比、M2 遗留三项；DXF 导入（`init --from-dxf`、`import_dxf`、`inspect`）；SKILL 路由化（69 行 + 5 个分页）与 `lcad skill install --target claude|codex|opencode|generic` |
| #66 | S6 | 叉架、箱体族卡片；范例 `shift_fork`、`bearing_support`、`pump_body`；L2 各 5 例；箱体完整性对照 `evals/completeness.py`；投影修复（空内环、接缝分裂的圆弧合并）；评测中发现的多件丢失 bug |
| #67 | S7 | 跨 Agent 评测运行器与结果、出图评审、G5 证据、本交接；评审发现的“有间隙的相邻零件剖面线相同”已修 |
| 本 PR | S7 补 | 跨 Agent 评测加 DeepSeek Harness（dsh）与豆包工作（运行器支持，豆包未跑）；dsh 暴露的 `std_part` 不能写材料已修（`material=`）、skill 装配页螺栓朝向示例改正、export 只在用户要求时用 |

## 2. 怎么验证

```bash
git clone https://github.com/Sterlingfrank1/Liner-CAD && cd Liner-CAD && uv sync --extra 3d
uv run lcad init /tmp/gc --from gear_cover && uv run lcad -C /tmp/gc render      # 纯 3D 投影的箱体
cp -r evals/L3/bearing /tmp/brg && git -C /tmp/brg init -q && uv run lcad -C /tmp/brg render
uv run lcad init /tmp/imp --from-dxf tests/data/dxf/sample_part.dxf && uv run lcad -C /tmp/imp log
uv run pytest -q tests/test_source3d.py tests/test_assembly.py tests/test_import_dxf.py tests/test_versions.py
```

## 3. 验收（BRIEF §3）与证据

| 项 | 结果 | 证据 |
|---|---|---|
| 1 3D 来源 | 箱体纯由模型投影出三视图与全剖 / 半剖 / 局部剖，标注、PMI、检查照常；没装 `[3d]` 报 `missing_extra` | `tests/test_source3d.py`；范例 `gear_cover`、`pump_body` |
| 2 两族 | 叉架、箱体各 2–3 范例 + 各 5 个 L2，零 error 零 warning；叉架几何对照 1.00 / 1.00，箱体完整性对照缺失 0 | `tests/test_evals.py`、`evals/L2/{fork,box}` |
| 3 装配 | L3 三例零 error 零 warning，有明细栏、序号、逐件剖面线 | `tests/test_assembly.py`、`evals/L3` |
| 4 DXF 导入 | 导入 ezdxf 生成的带原生尺寸的图，两轮 `lcad edit`（一轮被清楚的错误拒绝后改对）、`log`、`diff`、`export rev-A` | `evidence/clean-clone.md`、`tests/test_import_dxf.py` |
| 5 版本 | `lcad log` / `diff` 与 Viewer 叠加对比可用 | `tests/test_versions.py`、`evidence/viewer-version-compare.jpg` |
| 6 跨 Agent | Claude 与 DeepSeek Harness（DeepSeek-V4.1-Flash high，只拿装好的 skill）与 ezdxf 基线：箱体、叉架、装配各首图 + 3 轮修改全部落实，两种 Agent 的图检查 0 error；**Codex 未运行，按用户决定换成 dsh 与豆包工作；豆包未运行**（见 §5） | `evidence/cross-agent.md`、`report-cross-agent.json`、`codex-403.log` |
| 7 出图评审 | 独立评审 1–3 分为主；1 条已修，其余列入 §4 | `evidence/render-review.md` |
| 8 | 干净 clone 946 测试通过、ruff 通过、评测 40 / 40；CI 绿（含 3d job）、本 HANDOVER、tag `v0.1-m3` | `evidence/clean-clone.md` |

## 4. 已知缺口

- 出图：尺寸排布（放射状直径引线、多层尺寸）避让弱，评审打 2 分；序号没有最小间距与对齐；装配图无螺纹啮合画法；3D / 装配视图不能出局部放大；明细栏不合并相同零件、文字不换行。
- 3D：不做阶梯 / 旋转剖与移出断面（用 2D 画法补）；`src3d` 的边号只是提示，哈希为准；组件必须在 `project()` 之前加。
- DXF 导入：TEXT 导入成带引线的注释、HATCH 跳过、原图框保留在新图幅里；验收只用了 ezdxf 生成的图，没有第三方 CAD 原生文件（需要下载许可）。
- Viewer：版本列表在轮询刷新时会自动折叠；`layout_changed` 在整视图移动时很长。
- 跨 Agent：每项 n = 1；修改轮次 harness 比基线慢；dsh 首图 12–21 分钟（箱体首图超 20 分钟上限，图已完整提交）；箱体任务与范例相近，对 harness 有利。
- 没有“试改不提交”：Agent 调布局用 `edit` + `undo` 试错，历史里留下成对的“测试 / 撤销” commit（dsh 叉架 26 个）；v0.2 候选 `lcad edit --dry-run`。

## 5. 偏离与决定

见 SPEC §4。另：
- **BRIEF §5 跨 Agent 条款的 Codex 换成 DeepSeek Harness 与豆包工作**：2026-11-09 本机 `codex exec`（0.147.0）每次调用都被所配置的服务商拒绝 `403 用户额度不足`（`evidence/codex-403.log`）；opencode 的 API key 无效。用户决定改用本机 DeepSeek Harness（`dsh` headless，DeepSeek-V4.1-Flash、推理 high）和豆包工作桌面版（云电脑、自动-高）。dsh 三项全部跑完；豆包只能靠 computer use 驱动界面，本次会话里没有该工具，未运行，运行器的 `prompt` / `record` 已备好。运行器保留 Codex 分支，充值后一条命令重跑：
  `python evals/cross_agent.py run --root <目录> --agent codex --task box`（再 `fork`、`asm`，然后 `score`）。
- `lcad log` 输出包成 `{ok, log}`（CLI 一律一个 JSON 对象）。
- 装配剖面线相邻判定用 0.5 mm（允许配合间隙）。

## 6. 待用户人工评审

- 豆包工作（云电脑、自动-高）三项评测：computer use 可用后由会话驱动，或人工按 `python evals/cross_agent.py prompt --agent doubao --task <box|fork|asm> --round <0-3>` 的文本逐轮粘贴，用 `record` 记时、把回传的 `drawing.zip` 解到 `<评测目录>/doubao/<任务>/drawing` 后 `score`。
- （可选）给 Codex 服务商充值或换服务商后，重跑 Codex 部分（命令见 §5）。
- 出图质量：评审指出的尺寸排布与装配图细节（`evidence/render-review.md`）是否作为 v0.2 第一优先级。
- 跨 Agent 结论：出图观感 harness 与裸 ezdxf 相当，优势在首图速度、检查、语义元素与版本；是否接受这个定位。
- 是否提供一份有明确许可的第三方 CAD DXF 作为导入验收样例。

## 7. 给下一步（v0.1.0 发布 / v0.2）的说明

- `src3d` / `src3d_refs` 与组件 ID 已就位，v0.2 写 STEP PMI 时从这里映射拓扑。
- 出图评审的 2 分项集中在布局：直径引线、尺寸分层、序号对齐——`layout.py` 的候选生成与代价函数是入口。
- 评测运行器 `evals/cross_agent.py` 可直接加任务（`evals/cross/tasks.toml`）。
