"""Command implementations for `lcad` that are not transactions: context and render."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .errors import InvalidArgument, LinerError, NotFound
from .model import check_name
from .runtime import SRC, TMP_DIR, build

SELECTION_TTL = 900.0  # seconds a Viewer selection stays actionable (H4); env override for tests

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


def _selection_ttl() -> float:
    raw = os.environ.get("LCAD_SELECTION_TTL")
    if not raw:
        return SELECTION_TTL
    try:
        return max(0.0, float(raw))
    except ValueError:
        return SELECTION_TTL


def _selection_age(seldoc):
    """Seconds since the Viewer wrote the selection, or None when the timestamp is unusable."""
    try:
        when = datetime.fromisoformat(str(seldoc.get("time")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - when).total_seconds())


def _fresh_selection(dir, seldoc):
    """The ids of an actionable selection; refuses (selection_stale) when it is gone or outdated."""
    ids = list(seldoc.get("ids") or [])
    hint = "请在 Viewer 里重新点选，或直接把 @ID 贴进对话；不要猜用户选的是什么"
    if not ids:
        raise InvalidArgument(
            "当前没有有效选中：selection.json 里没有元素", code="selection_stale", hint=hint
        )
    from .txn import git_edits

    selver = seldoc.get("version")
    edits = git_edits(Path(dir))
    head = f"e{edits[0][0]}" if edits else None
    if not selver or not head or selver != head:
        raise InvalidArgument(
            f"当前没有有效选中：选择来自 {selver or '未知版本'}，当前是 {head or '未知版本'}",
            code="selection_stale",
            hint=hint,
        )
    age = _selection_age(seldoc)
    ttl = _selection_ttl()
    if age is None:
        raise InvalidArgument(
            "当前没有有效选中：selection.json 缺少可用的选择时间",
            code="selection_stale",
            hint=hint,
        )
    if ttl and age > ttl:
        raise InvalidArgument(
            f"当前没有有效选中：选择已超过 {int(ttl)} 秒（超时）",
            code="selection_stale",
            hint=hint,
        )
    return ids, {"version": selver, "time": seldoc.get("time"), "ids": ids, "fresh": True}


def _refs_in(text):
    """@IDs of a pasted reference line, ignoring @ inside the （...） description."""
    out = []
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == "（":
            depth += 1
        elif c == "）":
            depth = max(0, depth - 1)
        elif c == "@" and depth == 0:
            j = i + 1
            while j < len(text) and not text[j].isspace() and text[j] not in "（）":
                j += 1
            if j > i + 1:
                out.append(text[i + 1 : j])
            i = j - 1
        i += 1
    return out


def _clean_ids(items):
    """Element ids of copied references.

    Accepts one reference per argument, a pasted whole line ("@D.d1（...） @D.d2（...）"), or plain
    ids: Windows PowerShell needs the argument quoted, e.g. lcad context "@D.d1（Φ30k6，主视图）".
    """
    out = []
    for item in items:
        s = str(item).strip()
        refs = _refs_in(s)
        if refs:
            out.extend(refs)
            continue
        s = s.split("（", 1)[0].strip()
        if s:
            out.append(s)
    return out


def context(dir, ids=()):
    dir = Path(dir)
    seldoc = None
    selection = None
    want_sel = bool(ids) and str(ids[0]).strip() == "@sel"
    ids = _clean_ids(ids[1:]) if want_sel else _clean_ids(ids)
    if want_sel:
        sel = dir / ".linercad" / "selection.json"
        hint = "请在 Viewer 里点选元素后重试，或直接把 @ID 贴进对话；不要猜"
        if not sel.exists():
            raise InvalidArgument(
                "当前没有有效选中：还没有 selection.json", code="selection_stale", hint=hint
            )
        seldoc = json.loads(sel.read_text(encoding="utf-8"))
        selected, selection = _fresh_selection(dir, seldoc)
        ids = selected + ids
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
        if seldoc is not None and ids and not items:
            gone = [i for i in ids if i not in els]
            raise InvalidArgument(
                "当前没有有效选中：选中的元素在当前图中都已不存在"
                + (f"（{', '.join(gone)}）" if gone else ""),
                code="selection_stale",
                hint="请在 Viewer 里重新点选，或直接把 @ID 贴进对话；不要猜",
            )
        out = {
            "ok": True,
            "stale": True,
            "build_error": e.to_dict(),
            "items": items,
            "elements": None if ids else sorted(els),
            "hint": "构建失败，以上是上一版 model.json；先修好 drawing.py / 脚本",
        }
        if selection is not None:
            out["selection"] = selection
        return out
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
    if seldoc is not None:  # the elements themselves may have been removed by an uncommitted edit
        gone = [i for i in ids if i not in d]
        ids = [i for i in ids if i in d]
        if not ids:
            raise InvalidArgument(
                "当前没有有效选中：选中的元素在当前图中都已不存在"
                + (f"（{', '.join(gone)}）" if gone else ""),
                code="selection_stale",
                hint="请在 Viewer 里重新点选，或直接把 @ID 贴进对话；不要猜",
            )
        if gone:
            warn = f"已不存在：{', '.join(gone)}"
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
    if selection is not None:
        res_["selection"] = selection
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
    packs = {
        p: [] for p in ("drafting", "dimensioning", "tolerancing", "surface", "layout", "placement")
    }
    for f in res.findings:
        packs.setdefault(f.get("pack") or RULES.get(f["rule"], "layout"), []).append(f)
    errors = sum(1 for f in res.findings if f.get("severity") == "error")
    return {
        "ok": True,
        "errors": errors,
        "warnings": len(res.findings) - errors,
        "packs": packs,
        "opportunities": res.opportunities,
    }


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
