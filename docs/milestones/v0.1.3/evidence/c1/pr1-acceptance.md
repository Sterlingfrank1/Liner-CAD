# PR-1 验收证据（C1 · Viewer 全量，R1–R8）

- 分支：`v013/viewer`
- Issue：`#164`（`[v0.1.3/C1] Viewer 全量`）
- 临时目录验收环境：`%TEMP%\lcad-pr1-verify`（运行结束后已清理，未在仓库产生图纸 commit）

## 四场景实测结果

```json
{
  "s1_ensure_viewer": {
    "first": {
      "url": "http://127.0.0.1:61526/",
      "pid": 35648,
      "started": "2026-11-26T15:03:33+00:00",
      "opened": false,
      "reused": false
    },
    "second": {
      "url": "http://127.0.0.1:61526/",
      "pid": 35648,
      "started": "2026-11-26T15:03:33+00:00",
      "opened": false,
      "reused": true
    }
  },
  "s1_no_viewer_has_key": false,
  "s1_explicit_port_occupied": {
    "rc": 1,
    "error": "viewer_bind"
  },
  "s1_default_fallback": {
    "occupied": 54177,
    "bound": 54178,
    "url": "http://127.0.0.1:54178/"
  },
  "s2_selection": {
    "select_count": 50,
    "select_total": 60,
    "truncated": true,
    "context_summary": true,
    "context_items_len": 0,
    "context_kinds": {
      "edge": 50
    }
  },
  "s3_title_cells": {
    "count_in_model": 16,
    "empty_company_ref": "@T.title.company",
    "context_sel_id": "T.title.company"
  },
  "s4_download": {
    "formats": {
      "dxf": {
        "status": 200,
        "ctype": "application/dxf",
        "archive": "single",
        "disp": "attachment; filename=\"LC-SH-01-e0.dxf\"; filename*=UTF-8''LC-SH-01-e0.dxf",
        "bytes": 109574
      },
      "pdf": {
        "status": 200,
        "ctype": "application/pdf",
        "archive": "single",
        "disp": "attachment; filename=\"LC-SH-01-e0.pdf\"; filename*=UTF-8''LC-SH-01-e0.pdf",
        "bytes": 158101
      },
      "png": {
        "status": 200,
        "ctype": "image/png",
        "archive": "single",
        "disp": "attachment; filename=\"LC-SH-01-e0.png\"; filename*=UTF-8''LC-SH-01-e0.png",
        "bytes": 52535
      },
      "dxf_preview": {
        "status": 200,
        "disp": "attachment; filename=\"LC-SH-01-e0-preview.dxf\"; filename*=UTF-8''LC-SH-01-e0-preview.dxf",
        "bytes": 109562
      }
    },
    "git_status_empty": true,
    "git_tag_empty": true
  }
}
```

## 覆盖说明

1. **R1/R2**：在 `LCAD_NO_VIEW=1` 且 `CI=1` 下 `lcad build --ensure-viewer` 静默起守护进程（`opened=false`、`reused=false`），第二次 `lcad edit --ensure-viewer` 复用同进程（`reused=true`）；`--no-viewer` 不输出 `viewer` 键；默认端口占用回退空闲端口，显式 `--port` 被占报错 `viewer_bind`。
2. **R3/R6**：`index.html` / `viewer.css` / `viewer.js` 实现 `--left-w`/`--right-w` 拖拽调宽、`localStorage`（`lcad.leftW`/`lcad.rightW`）持久化、双击复位、双侧折叠及 `<=1100` / `<=820` 窄屏两档适配；检查器状态文案改为「已选中 N 个元素」，已移除 `selection.json` 字样并保留 `Ctrl+Alt+C`。
3. **R4/R5**：画布实现左键框选（L→R 蓝实线全包含 / R→L 绿虚线相交，容差 `0.75 * sc`）、右/中键/Space+左键平移与右键菜单抑制；`Viewer.select` 默认截断上限 50（`LCAD_SELECTION_CAP`），`lcad context "@sel"` 超 10 返回摘要（保留 `items: []`）。
4. **R7**：GB/ISO 标题栏全部 16 格（含空字段如 `T.title.company`）均输出 `cell_box` 与 SVG `cell-hit` 命中矩形并可点选/读取 `@sel`。
5. **R8**：`GET /api/download?fmt=dxf|pdf|png[&preview=1]` 经临时目录出图后即删，无 git / 源码 / `.linercad/build` 副作用；带内部 `assets/logo.png` 的 DXF 自动打 `.zip`（`X-LCAD-Archive: zip`），越界外部图片路径拒绝（409）。
6. 浏览器交互视觉手感（拖拽宽度、框选两态拖拽）待用户合入后试用确认。
