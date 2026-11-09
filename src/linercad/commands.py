"""Command implementations for `lcad` that are not transactions: context and render."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import InvalidArgument, LinerError, NotFound
from .model import check_name
from .runtime import SRC, TMP_DIR, build

BRIEF_KINDS = (
    "view",
    "feature",
    "center",
    "dim",
    "note",
    "hatch",
    "section",
    "table.cell",
    "raw",
    "import",
)
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
    elif e.kind == "import":
        out.update(path=i["path"], counts=i["counts"])
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
    seldoc = None
    if ids and ids[0] == "@sel":
        sel = dir / ".linercad" / "selection.json"
        if not sel.exists():
            raise InvalidArgument(
                "还没有 selection.json", hint="在 lcad view 里点选元素后再用 @sel"
            )
        seldoc = json.loads(sel.read_text(encoding="utf-8"))
        ids = seldoc.get("ids", []) + list(ids[1:])
        if not ids:
            raise InvalidArgument("selection.json 里没有选中的元素", hint="在 Viewer 里点选")
    try:
        res = build(dir)
    except (
        LinerError
    ) as e:  # fall back to the last good model.json (M2: context works while broken)
        mp = dir / ".linercad" / "build" / "model.json"
        if not mp.exists():
            raise
        m = json.loads(mp.read_text(encoding="utf-8"))
        els = {x["id"]: x for x in m["elements"]}
        items = [{"element": els[i]} for i in ids if i in els] if ids else []
        return {
            "ok": True,
            "stale": True,
            "build_error": e.to_dict(),
            "items": items,
            "elements": None if ids else sorted(els),
            "hint": "构建失败，以上是上一版 model.json；先修好 drawing.py / 脚本",
        }
    d = res.d
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
    warn = None
    if seldoc is not None:  # the selection may predate the latest edit
        gone = [i for i in ids if i not in d]
        ids = [i for i in ids if i in d]
        from .txn import git_edits

        edits = git_edits(dir)
        head = f"e{edits[0][0]}" if edits else None
        if gone or (seldoc.get("version") and head and seldoc["version"] != head):
            warn = f"选择来自 {seldoc.get('version')}，当前是 {head}" + (
                f"；已不存在：{', '.join(gone)}" if gone else ""
            )
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
    res_ = {"ok": True, "items": out}
    if warn:
        res_["warning"] = warn
    return res_


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


def check(dir):
    """All findings of a fresh build, grouped by rule pack."""
    from .checks import RULES
    from .runtime import build

    res = build(dir)
    packs = {p: [] for p in ("drafting", "dimensioning", "tolerancing", "surface", "layout")}
    for f in res.findings:
        packs.setdefault(f.get("pack") or RULES.get(f["rule"], "layout"), []).append(f)
    errors = sum(1 for f in res.findings if f.get("severity") == "error")
    return {"ok": True, "errors": errors, "warnings": len(res.findings) - errors, "packs": packs}


def inspect_dxf(dir, file):
    """Survey a DXF (layers, entity statistics, extents, how it would import) plus a temporary PNG
    in ``<dir>/.linercad/tmp`` when ``dir`` is a drawing directory, else in the system temp dir."""
    from . import importdxf

    tmp = Path(dir) / TMP_DIR
    return importdxf.inspect(file, tmp if (Path(dir) / ".linercad").is_dir() else None)


def _skill_files():
    """{relative path: text} of the packaged skill: SKILL.md, pages/*.md, families/*.md."""
    from importlib import resources

    base = resources.files("linercad") / "skill"
    out = {"SKILL.md": (base / "SKILL.md").read_text(encoding="utf-8")}
    for sub in ("pages", "families"):
        d = base / sub
        if d.is_dir():
            for f in sorted(d.iterdir(), key=lambda x: x.name):
                if f.name.endswith(".md"):
                    out[f"{sub}/{f.name}"] = f.read_text(encoding="utf-8")
    return out


def skill(family=None):
    """SKILL.md, a page (skill/pages/<name>.md) or a part-family card (skill/families/<name>.md)."""
    from .errors import NotFound

    files = _skill_files()
    if family is None:
        return {"ok": True, "path": "SKILL.md", "text": files["SKILL.md"]}
    for sub in ("families", "pages"):
        key = f"{sub}/{family}.md"
        if key in files:
            return {"ok": True, "path": key, "text": files[key]}
    names = sorted(k.split("/", 1)[1][:-3] for k in files if "/" in k)
    raise NotFound(f"没有分页或零件族卡片 {family!r}", candidates=names + ["install"])


MARK_BEGIN = "<!-- linercad:begin (lcad skill install) -->"
MARK_END = "<!-- linercad:end -->"
TARGETS = ("claude", "codex", "opencode", "generic")


def _body(text):
    """SKILL.md without its YAML front matter."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def skill_install(target, dir="."):
    """Install the skill where an agent finds it (SPEC M3 §1.7): claude → .claude/skills/linercad/,
    opencode → .opencode/skills/linercad/, codex → a marked section of AGENTS.md, generic →
    LINERCAD.md. Pages stay reachable with ``lcad skill <page>``."""
    from .errors import InvalidArgument

    if target not in TARGETS:
        raise InvalidArgument(
            f"--target {target!r} 不对", candidates=list(TARGETS), values={"target": target}
        )
    root = Path(dir)
    files = _skill_files()
    written = []

    def put(rel, text):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        written.append(Path(rel).as_posix())

    if target in ("claude", "opencode"):
        base = ".claude/skills/linercad" if target == "claude" else ".opencode/skills/linercad"
        for rel, text in files.items():
            put(f"{base}/{rel}", text)
    elif target == "generic":
        put("LINERCAD.md", _body(files["SKILL.md"]))
    else:
        p = root / "AGENTS.md"
        old = p.read_text(encoding="utf-8") if p.is_file() else ""
        block = MARK_BEGIN + "\n" + _body(files["SKILL.md"]).rstrip() + "\n" + MARK_END
        if MARK_BEGIN in old and MARK_END in old:
            i = old.index(MARK_BEGIN)
            j = old.index(MARK_END) + len(MARK_END)
            new = old[:i] + block + old[j:]
        else:
            new = (old.rstrip("\n") + "\n\n" if old.strip() else "") + block + "\n"
        put("AGENTS.md", new)
    return {
        "ok": True,
        "target": target,
        "dir": str(root),
        "files": written,
        "hint": "分页与零件族卡片用 lcad skill <页> 读取",
    }


def template_import(dir, file, name):
    """Company DXF → ``templates/<name>.toml`` (enterprise overlay, SPEC M1 §6)."""
    from .dxfout import write_text_atomic
    from .std.importer import dump_toml, import_dxf

    check_name(name, "企业档名")
    data, notes = import_dxf(file)
    rel = f"templates/{name}.toml"
    head = f"# lcad template import {Path(file).name}\n"
    write_text_atomic(Path(dir) / rel, head + dump_toml(data))
    tb = data.get("title_block", {})
    return {
        "ok": True,
        "path": rel,
        "std": {k: sorted(v) for k, v in data.get("std", {}).items()},
        "title_block": {"size": tb.get("size"), "fields": sorted(tb.get("fields", {}))},
        "notes": notes,
        "hint": f'Drawing(..., overlay="{name}")；下一次 lcad build -m 会连同图纸源一起提交',
    }
