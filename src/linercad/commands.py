"""Command implementations for `lcad` that are not transactions: context and render."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import InvalidArgument, NotFound
from .runtime import SRC, TMP_DIR, build

BRIEF_KINDS = ("view", "feature", "center", "dim", "note", "hatch", "section", "table.cell", "raw")
SNIPPETS = {
    "dim": [
        'd["{id}"].place(side="top")          # 换侧：top/bottom/left/right/inside',
        'd["{id}"].place(row=2)               # 换排',
        'd["{id}"].move(dy=3)                 # 沿外法向微调 3 mm',
        'd["{id}"].tol = "h7"                 # 改公差文字',
        'd["{id}"].suppress()                 # 删除',
    ],
    "note": ['d["{id}"].text = "新文字"', 'd["{id}"].place(dir=135)', 'd["{id}"].suppress()'],
    "edge": ['d["{id}"].role = "hidden"', 'd["{id}"].move(dx=1)'],
    "table.cell": ['d["{id}"].text = "新值"'],
    "view": ['d["{id}"].move(dy=-5)'],
}


def brief(e) -> dict:
    out = {"id": e.id, "view": e.view}
    i = e._intent
    if e.kind == "dim":
        out.update(text=i["text"], type=i["type"], role=i["role"], side=e.side, row=e.row)
    elif e.kind in ("note", "table.cell"):
        out["text"] = i.get("text")
    elif e.kind in ("feature", "center"):
        out["type"] = i.get("type")
        if e.kind == "feature":
            out["edges"] = len(i.get("edges", []))
    elif e.kind == "section":
        out.update(letter=i["letter"], cut_in=i["cut_in"])
    elif e.kind == "view":
        out.update(origin=e._resolved.get("origin"), bbox=e._resolved.get("bbox"))
    if e.status != "ok":
        out["status"] = e.status
    return out


def _source(dir, e):
    src = e.src or {}
    if src.get("file") == SRC and src.get("line"):
        lines = (Path(dir) / SRC).read_text(encoding="utf-8").splitlines()
        n = src["line"]
        lo, hi = max(1, n - 2), min(len(lines), n + 2)
        return [f"{k}: {lines[k - 1]}" for k in range(lo, hi + 1)]
    if src.get("edit"):
        log = (Path(dir) / "drawing.actions.jsonl").read_text(encoding="utf-8-sig").splitlines()
        n = src.get("line")
        if n and 0 < n <= len(log):
            return [f"drawing.actions.jsonl:{n}: {log[n - 1]}"]
    return []


def context(dir, ids=()):
    dir = Path(dir)
    res = build(dir)
    d = res.d
    if ids and ids[0] == "@sel":
        sel = dir / ".linercad" / "selection.json"
        if not sel.exists():
            raise InvalidArgument("还没有 selection.json（Viewer 在 M2 提供）")
        ids = json.loads(sel.read_text(encoding="utf-8")).get("ids", [])
    if not ids:
        groups = {}
        edges = {}
        for e in d._els.values():
            if e.kind == "edge":
                edges[e.view] = edges.get(e.view, 0) + 1
            elif e.kind in BRIEF_KINDS:
                groups.setdefault(e.kind, []).append(brief(e))
        from .txn import git_edits

        hist = [s for _, _, s, _ in git_edits(dir)[:10]]
        return {
            "ok": True,
            "drawing": {
                "sheet": d.sheet,
                "std": d.std_name,
                "scale": d.scale_text,
                "frame": list(d.template["frame"]),
            },
            "params": [d.P[n].to_dict(n) for n in d.P.names()],
            "elements": groups,
            "edges_per_view": edges,
            "findings": res.findings,
            "history": hist,
            "hint": "lcad context <ID> 看单个元素；查询无名几何用 d.q.lines(view=...).where(...).near(x, y)",
        }
    out = []
    for i in ids:
        e = d[i]
        b = e.bbox
        near = []
        if b:
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            r = max(b[2] - b[0], b[3] - b[1]) / 2 + 10
            near = [x.id for x in d.near(cx, cy, r=r) if x.id != e.id and x.kind not in ("frame",)][
                :12
            ]
        snip = [s.format(id=e.id) for s in SNIPPETS.get(e.kind, [])]
        out.append(
            {
                "element": e.to_dict(),
                "neighbors": near,
                "source": _source(dir, e),
                "snippet": ["def apply(d):", *("    " + s for s in snip)] if snip else [],
            }
        )
    return {"ok": True, "items": out}


def render(dir, focus=None, out=None, dpi=None):
    from .render import render_png

    dir = Path(dir)
    res = build(dir)
    d = res.d
    W, H = d.template["size"]
    bbox = None
    if focus:
        e = d.get(focus)
        if e is None:
            raise NotFound(f"找不到元素 {focus}", id=focus, candidates=d._close_ids(focus))
        if not e.bbox:
            raise InvalidArgument(f"{focus} 没有图形，不能局部渲染", id=focus)
        m = 15.0
        b = e.bbox
        bbox = (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
    tmp = dir / TMP_DIR
    tmp.mkdir(parents=True, exist_ok=True)
    name = f"render-{focus}.png" if focus else "render.png"
    path = Path(out) if out else tmp / name
    render_png(res.doc, (W, H), path, focus_bbox=bbox, focus_id=focus, dpi=dpi)
    from .txn import prune_tmp

    prune_tmp(dir)
    return {
        "ok": True,
        "png": str(path),
        "bbox": list(bbox) if bbox else [0, 0, W, H],
        "warnings": res.findings,
    }
