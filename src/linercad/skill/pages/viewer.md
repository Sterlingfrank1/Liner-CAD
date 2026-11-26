# Viewer：用户在浏览器里看图、点选、试参数

用户可能开着 `lcad view`（浏览器里看图、点选、拖参数滑块）；画完后 Viewer 也会被自动打开。

## 自动打开与关闭（H3 / R1 / R2）

- 图纸目录**第一次** `build` / `edit` 成功后，若没有运行中的 Viewer，harness 会在后台起一个并打开浏览器一次；命令 JSON 带 `viewer: {url, pid, started, opened, reused}`，打不开浏览器时把 `url` 告诉用户即可。已在运行则只刷新页面、不新开标签（`reused: true`、`opened: false`）。
- **静默拉起（推荐）**：`lcad build --ensure-viewer` / `lcad edit ... --ensure-viewer` 静默起后台守护进程、**不弹系统浏览器**（`opened: false`），且显式覆盖 `LCAD_NO_VIEW=1`、`LCAD_NO_VIEWER=1` 与 `CI`；把返回的 `viewer.url` 放进回复里即可。
- **关闭**：本次命令加 `--no-viewer` / `--no-view`（与 `--ensure-viewer` 互斥），或设置 `LCAD_NO_VIEW=1` / `LCAD_NO_VIEWER=1`，CI 环境默认关。后台 Viewer 在空闲超时（默认 30 分钟，`LCAD_VIEW_IDLE_TIMEOUT` 秒）后自退，并删除状态文件。
- **端口回退**：`lcad view` 默认绑定 `8765`，若被占用自动回退到随机空闲端口并把真实端口写入 `.linercad/viewer.json`；显式传 `--port <N>` 且被占用时直接报错退出（`error.code == "viewer_bind"`）。
- 状态在 `.linercad/viewer.json`（pid / port / url / started），只是本地状态，不要提交或手改。

## 选择同步到对话（H4）

Viewer 的选择是唯一事实源：`.linercad/selection.json`（`ids` + 每个元素的 `ref` / 时间 / 版本）。两条路都支持，任何 Agent 通用：

1. **复制引用（推荐，用户点了按钮 / 快捷键）：** 用户在 Viewer 里单击点选、Ctrl 多选，点「复制引用」或按 Ctrl+Alt+C（Ctrl+Shift+C 是浏览器 DevTools 快捷键，页面拦不住），得到一行引用，例如
   `@D.d1（Φ25k6，主视图） @D.d2（Φ30k6，主视图） @D.L（200，主视图）`。
   用户把它粘进对话后，把每个 `@ID` 当作该元素——可以直接 `lcad context "@D.d1（Φ25k6，主视图）" "@D.d2（Φ30k6，主视图）"`（PowerShell 里参数要用双引号包住整条引用），或按 ID 写临时脚本；不要要求用户再解释一遍。
2. **自然语言指代（用户没复制）：** 用户说「选中的 / 这个 / 那个 / 当前对象 / 我选的」而消息里**没有 `@ID`** 时，先读当前选中再动手：
   ```powershell
   lcad context "@sel"      # PowerShell 里 @sel 要加引号
   ```
   确认 `items` 里的 ID 后再写脚本 / 改参数；不要凭聊天上下文猜用户指的是哪个元素。
   优先用 `lcad context`（它校验版本与 TTL）。**若直读 `.linercad/selection.json`：** 必须自己用 `lcad log` 的当前 `eN` 比较文件里的 `version`，并检查 `time` 不超过 15 分钟（默认 TTL）；版本不一致或超时就按「当前没有有效选中」处理，不要用旧选择。

**选择过期时如实报告，不要猜：** `lcad context "@sel"` 会校验选择的新鲜度——版本必须与当前 `eN` 一致，且默认不超过 15 分钟（`LCAD_SELECTION_TTL` 秒数可调；**设为 0 或负值表示永不过期**，版本校验仍然生效，不要把它当成“立即过期”）。失败时返回的 `error.code` 是 `selection_stale`，消息形如「当前没有有效选中：选择来自 e0，当前是 e1」/「当前没有有效选中：选择已超过 900 秒（超时）」/「当前没有有效选中：还没有 selection.json」。这时**明确告诉用户当前没有有效选中**，请他在 Viewer 里重新点选或把 `@ID` 贴进对话；不要用旧选择硬改，也不要猜。

## 参数与刷新

- 用户在试的参数值在 `.linercad/snapshot.json` 的 `params`（只是预览，没写进 drawing.py）；用户要定下来时，改 drawing.py 里那个 `Param` 的默认值再 `lcad build -m`，或请用户点 Viewer 的「写回源码」。
- 你提交后 Viewer 会自动刷新，状态栏显示新的编号。
- 命令是 `lcad -C <图纸目录> view`（目录用全局 `-C`，不是位置参数）。Viewer 只面向本机单用户：只监听 127.0.0.1，令牌随首页下发，不防同机其他用户 / 进程。共享主机上不要替用户开，也不要把端口暴露给他人。
