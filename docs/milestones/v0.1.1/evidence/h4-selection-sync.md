# H4 Viewer 选择同步到对话（证据）

卡 H4（issue #107，W3，P1 核心卡）· 分支 `m5/h4-selection-sync`（基于 main 5a0e4f2）· 热点 `viewer/` + `skill/`

## 两条路径的实现

1. **复制引用（所有 Agent）**：Viewer 点选 / Ctrl 多选后，检查器出现「复制引用」按钮（快捷键 **Ctrl+Shift+C**），把当前选择生成**一行**引用，例如
   `@D.d2（Φ30k6，主视图） @D.d1（M24×1.5-6g，主视图） @D.L（200，主视图）`
   （每个引用含 `@ID`、显示值/公差、所在视图；`ref_text` 生成语义）。复制成功在状态栏显示「已复制引用：…」。
2. **自然语言指代（所有 Agent）**：skill 明确规则——用户说「选中的 / 这个 / 那个 / 当前对象」而消息里**没有 @ID** 时，先 `lcad context "@sel"` 再动手；选择是唯一事实源，不猜。直读 `.linercad/selection.json` 时 Agent 必须自行比较 `version` 与当前 eN、并检查 `time` 在 TTL 内，否则同样按「当前没有有效选中」处理（skill 页已写明）。
   - `lcad context @sel` 现在校验新鲜度：选择版本必须与当前 `eN` 一致，且默认不超过 **15 分钟**（`LCAD_SELECTION_TTL` 可调）。
   - 无选择 / 版本落后 / 超时 → 返回 `error.code = "selection_stale"`，消息以「当前没有有效选中：…」开头，hint 明确「请在 Viewer 里重新点选，或直接把 @ID 贴进对话；不要猜用户选的是什么」。
   - 复制来的 `@D.d2（Φ30k6，主视图）` 也可以直接作为 `lcad context` 参数（自动去掉 @ 与括号里的说明；整行也可以作为一个带引号的参数传入）；PowerShell 里必须加引号，例如 `lcad context "@sel"`、`lcad context "@D.d2（Φ30k6，主视图）"`。

## dsh 现场验收（临时目录图纸仓库）

### 路径①：多选 3 元素 → 复制引用 → 一轮改对

截图 `h4-selection-copy.jpg`：Viewer 里 3 个元素高亮选中（D.d2 / D.d1 / D.L），检查器「3 个已写入 selection.json」+「复制引用」按钮（Ctrl+Shift+C）。

复制到的一行（实际 clipboard 内容，ego-browser 截获）：

```text
@D.d2（Φ30k6，主视图） @D.d1（M24×1.5-6g，主视图） @D.L（200，主视图）
```

把这一行贴给 Agent 后，用其中的引用直接查上下文：

```json
{"code": 0, "ids": ["D.d2", "D.d1", "D.L"], "refs_ok": true}
```

随后一轮修改成功（e1，只改了选中的 D.d2）：`{"ok": true, "edit": "e1", "changed": ["D.d2"], "errors": 0}`。

### 路径②：不复制，直接说「把选中的直径改成 k6」→ Agent 先读选择再改对

在 Viewer 里选中 D.d3（版本 e1），用户不复制；Agent 先 `lcad context @sel`：

```json
{"select_ok": true, "ids": ["D.d3"], "fresh": true}
```

确认 ID 后一轮修改成功（e2）：`{"ok": true, "edit": "e2", "changed": ["D.d3"], "errors": 0}`。

### 选择过期 / 没有选择：如实报告，不猜

版本落后（选择来自 e0，提交已被改成 e1）：

```json
{"code": 1, "error": {"code": "selection_stale",
 "message": "当前没有有效选中：选择来自 e0，当前是 e1",
 "hint": "请在 Viewer 里重新点选，或直接把 @ID 贴进对话；不要猜用户选的是什么"}}
```

没有 selection.json：

```json
{"code": 1, "error": {"code": "selection_stale",
 "message": "当前没有有效选中：还没有 selection.json",
 "hint": "请在 Viewer 里点选元素后重试，或直接把 @ID 贴进对话；不要猜"}}
```

超时：`tests/test_viewer.py::test_context_at_sel_refuses_an_expired_selection`（把 selection 时间改到 2000 年）断言 `selection_stale` +「超时/过期」。

## skill 写法

- `lcad skill viewer`（`src/linercad/skill/pages/viewer.md`）新写「选择同步到对话」一节：两条路径、复制格式与快捷键、`lcad context @sel` 规则、fresh 判定（版本 + 15 分钟 TTL）、`selection_stale` 时如实报告不猜。
- `src/linercad/skill/SKILL.md` 工作循环第 1 步加一句：用户说「这个 / 我选中的 / 当前对象」且没有 `@ID` 时先 `lcad context @sel`；`selection_stale` 时如实说「当前没有有效选中」，不要猜。

## 测试（G2 先失败：6 failed）

- 过期选择拒绝（版本落后、超时、无 selection.json）与 fresh metadata；
- 多选引用语义（`@D.d2（Φ30k6，主视图） …` 一行，值/公差/视图齐全，selection.json items 同步）；
- 粘贴的 `@ID（…）` 可直接用于 `lcad context`；
- Viewer「复制引用」UI / Ctrl+Shift+C / selectionRefs；
- skill 首页与 viewer 页包含指代规则和过期处理。

## 验证

- 全量 `uv run pytest` / `ruff check` / `ruff format --check` / `evals --baseline` / CI 四项：见 PR 评论。
- 本卡不动规则与布局，D 应保持 0.965724（2830, 97）。
- B2 的 Claude Code 钩子按 PLAN 转 v0.2，不在本卡。
