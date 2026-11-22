# H3 首次出图自动打开 Viewer（证据）

卡 H3（issue #106，W3，P1）· 分支 `m5/h3-auto-open`（基于 main 98b7be8）· 热点 `viewer/` + `cli.py`（build/edit 的 JSON 出口）。

## 做法

- `lcad build` / `lcad edit` 成功后，CLI 调 `viewer.autostart(dir)`：没有运行中的 Viewer 时，用 `python -m linercad.viewer --background --dir <图纸> --port 0 --idle-timeout <秒>` 起一个后台常驻进程，等它把 `.linercad/viewer.json`（pid / port / url）写好，再用 `webbrowser.open(url)` 打开一次；命令 JSON 带 `viewer: {url, opened}`。已在运行则复用（不新开标签），只返回 `{url, opened: false}`（页面自己轮询刷新）。
- 打不开浏览器时 `opened: false`、`url` 仍返回（远程/无浏览器会话的降级），后台 Viewer 照常可用。
- 开关：`--no-view`（build/edit）、`LCAD_NO_VIEW` 环境变量、`CI` 环境三者任一都是关；关掉时 JSON 不含 `viewer` 键。空闲超时默认 1800 s，`LCAD_VIEW_IDLE_TIMEOUT` 可调；超时进程自行退出并删除 `.linercad/viewer.json`。`.linercad/` 本来就在 `.gitignore`，端口/pid 不入库。仍只监听 127.0.0.1，令牌机制不变（v0.2 的令牌加固不在本卡）。
- 后台进程在 dsh 沙箱（workspace-write）里实测可以拉起并存活（见下），Windows 上 venv 的 `python.exe` 启动器会再起真实解释器，`autostart` 以状态文件里的活 pid + 可连通端口判断成功，不依赖启动器的 pid。

## dsh 现场验收（临时目录图纸仓库，产物不入库）

现场验收按 lead 2026-11-21 口径只做 dsh 侧：卡片 Goal 里「Claude Code 与 dsh 各出一张图」的 Claude Code 半句是旧措辞（Claude Code 不在本版本验收范围），Codex 侧由评审轮覆盖，不另设 Claude Code 验收。

环境：`LCAD_VIEW_IDLE_TIMEOUT` 按用例设为 12/30/60 s；`CI`、`LCAD_NO_VIEW` 未设置。

### ① 首次 build 自动起 Viewer 并打开一次

```json
{
 "ok": true, "edit": null, "commit": null, "changed": [], "errors": 0, "warnings": [],
 "note": "源文件没有改动，未提交",
 "dxf": ".linercad/build/drawing.dxf",
 "model": ".linercad/build/model.json",
 "viewer": {"url": "http://127.0.0.1:54919/", "opened": true}
}
```

`.linercad/viewer.json`（运行中）：

```json
{"pid": 67516, "port": 54919, "url": "http://127.0.0.1:54919/", "started": "2026-11-22T05:03:30+00:00"}
```

截图 `h3-auto-viewer.jpg`：自动启动的 Viewer 页面（打开返回的 url 后截取；dsh 里 `webbrowser.open` 返回 true）。

### ② 已在运行：第二次 build/edit 只刷新、不开新标签

```json
{"first_url": "http://127.0.0.1:49263/", "first_opened": false,
 "second_viewer": {"url": "http://127.0.0.1:49263/", "opened": false},
 "pid_before": 28716, "pid_after": 28716, "same_url": true}
```

（pid 与 url 都不变；`opened: false` 表示没有新开浏览器标签。上面首次验收里 first_opened 为 true，这次为了证据干净用 `open_browser=False` 复跑；后台进程那条 `first_opened: true` 见 ①。）

### ③ 空闲自退、无残留进程

```json
{"viewer": {"url": "http://127.0.0.1:53486/", "opened": false}, "pid": 52472,
 "alive_after_12s": false, "state_exists": false}
```

`running()` 返回 `None`；随后进程扫描：`Get-CimInstance ... CommandLine -like '*linercad.viewer*'` → **无残留**（`processes.txt` 为 `(none)`）。

说明：空闲自退用例用 `open_browser=False` 起 Viewer——被打开着的浏览器标签会每秒轮询 `/api/state`，按定义就是“有人看着”，不会误判空闲；关掉页面/标签后剩余空闲时间一到即退出。

### ④ CI / --no-view 默认关

```json
{"no_view_flag_has_viewer": false, "ci_env_has_viewer": false,
 "env_switch_has_viewer": false, "state_exists": false}
```

（三种关法都不产生 `viewer` 键、不写状态文件、不起进程；pytest 的 `tests/conftest.py` 全局设 `LCAD_NO_VIEW=1`，所以测试与 CI 永远不会自动开浏览器。）

## 自动化测试（G2 先失败：4 failed）

`tests/test_autoview.py`：
- `test_build_json_reports_the_background_viewer` / `test_edit_json_reports_the_background_viewer`：build/edit 成功时 JSON 带 `viewer`；`--no-view` 时无该键（stub 掉 autostart，不真起进程）。
- `test_autostart_is_off_by_default`：`LCAD_NO_VIEW`、`CI`、`disabled=True` 三种关法都返回 None 且不写状态。
- `test_autostart_spawns_reuses_opens_once_and_exits_idle`：真起后台进程 → 状态文件 pid/port 可用 → 第二次 autostart 复用同一 pid、`opened: false`、浏览器只被调用一次 → 空闲超时后进程退出、状态文件删除。

## 验证

- 全量 `uv run pytest` / `ruff check` / `ruff format --check` / `evals --baseline` / CI 四项：见 PR 评论。
- 本卡不动规则与布局，D 应保持 0.965724（2830, 97）。