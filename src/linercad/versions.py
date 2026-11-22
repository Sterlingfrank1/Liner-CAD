"""Versions (M3 SPEC §1.6): ``lcad log`` / ``lcad diff A B`` / ``lcad export``.

A version is a commit that touches the drawing directory. ``diff`` checks the whole drawing
repository out at each revision with ``git worktree add --detach`` (so relative paths such as
``../part`` in an assembly resolve), rebuilds the same relative drawing directory there and compares
the elements by ID. The worktrees are always removed again.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import tempfile
from html import escape
from pathlib import Path

from . import runtime, svgout, txn
from .errors import DirtySource, GitError, InvalidArgument, LinerError, NotFound
from .runtime import TMP_DIR
from .txn import EDIT_RE, git

EDIT_ID = re.compile(r"e\d+")
FORMATS = ("dxf", "pdf")
BBOX_EPS = 0.01  # mm: a resolved bounding box moving more than this counts as a layout change
REV_TAG = re.compile(r"rev-([A-Z]+)")

# overlay classes: A grey, B black, then added / removed / changed
COLORS = {
    "df-a": "#b9b9b9",
    "df-b": "#111111",
    "df-add": "#1a9a3c",
    "df-del": "#d62728",
    "df-chg": "#1565c0",
}


# ---- log ------------------------------------------------------------------------------------------


def log(dir) -> list[dict]:
    """``[{edit, commit, message, time}]`` of the commits touching ``dir``, newest first."""
    r = git(dir, "log", "--format=%h%x1f%aI%x1f%s%x1e", "--", ".")
    out = []
    for chunk in r.stdout.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        h, t, s = (chunk.split("\x1f") + ["", ""])[:3]
        m = EDIT_RE.match(s)
        out.append(
            {
                "edit": f"e{m.group(1)}" if m else None,
                "commit": h,
                "message": s[m.end() :] if m else s,
                "time": t,
            }
        )
    return out


def resolve(dir, ref) -> str:
    """Full commit hash of an edit id (``e2``), a commit, ``HEAD`` or a tag (``rev-A``)."""
    ref = str(ref).strip()
    if not ref or ref.startswith("-"):
        raise InvalidArgument(f"版本 {ref!r} 不合法", hint="写 e2、提交号、HEAD 或标签 rev-A")
    if EDIT_ID.fullmatch(ref):
        for n, h, *_ in txn.git_edits(dir):
            if f"e{n}" == ref:
                return h
    # not an edit number (or none by that number): a commit, HEAD or a tag; a short hash such as
    # e123456 looks like an edit number too
    r = git(dir, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    edits = [f"e{n}" for n, *_ in txn.git_edits(dir)]
    tags = git(dir, "tag", "-l", "rev-*", check=False).stdout.split()
    raise NotFound(
        f"找不到版本 {ref}",
        id=ref,
        candidates=edits[:12] + tags,
        hint="lcad log 列出全部版本",
    )


def _short(dir, full) -> str:
    return git(dir, "rev-parse", "--short", full).stdout.strip()


# ---- worktrees ------------------------------------------------------------------------------------


@contextlib.contextmanager
def checkouts(dir, commits):
    """Check the repository out at ``commits`` (detached worktrees in a temp dir); yields
    ``{commit: drawing directory}``. The worktrees are removed on exit, also after an error."""
    root = txn.repo_root(dir)
    if root is None:
        raise GitError(f"{dir} 不在 git 仓库里", hint="lcad init 会建仓库")
    rel = os.path.relpath(Path(dir).resolve(), Path(root).resolve())
    tmp = Path(tempfile.mkdtemp(prefix="lcad-diff-"))
    made = []
    try:
        out = {}
        for k, c in enumerate(dict.fromkeys(commits)):
            wt = tmp / f"w{k}"
            git(root, "worktree", "add", "--detach", "-q", str(wt), c)
            made.append(wt)
            out[c] = wt if rel == "." else wt / rel
        yield out
    finally:
        for wt in made:
            git(root, "worktree", "remove", "--force", str(wt), check=False)
        shutil.rmtree(tmp, ignore_errors=True)
        git(root, "worktree", "prune", check=False)


def _build_at(drawing_dir, ref):
    try:
        return runtime.build(drawing_dir, dxf=False)
    except LinerError as e:
        raise type(e)(
            f"重建版本 {ref} 失败：{e.message}",
            id=e.id,
            candidates=e.candidates,
            values=e.values,
            hint=e.hint,
        ) from e


# ---- comparing -----------------------------------------------------------------------------------


def _norm(x):
    return json.loads(json.dumps(x, sort_keys=True, default=str))


def snapshot(d) -> dict:
    """``{id: {kind, intent, bbox}}`` of a built drawing (intent and bbox are what ``diff`` compares)."""
    out = {}
    for e in d._els.values():
        bbox = e._resolved.get("bbox")
        out[e.id] = {
            "kind": e.kind,
            "intent": _norm(e.to_dict()["intent"]),
            "bbox": [float(v) for v in bbox] if bbox else None,
            "view": e._intent.get("view"),
        }
    return out


def _moved(a, b):
    """Largest coordinate shift between two boxes (mm); ``None`` if only one of them exists."""
    if a is None and b is None:
        return 0.0
    if a is None or b is None:
        return None
    return max(abs(x - y) for x, y in zip(a, b, strict=True))


def _delta(a, b):
    """Per-coordinate box shift (x0, y0, x1, y1): equal values on a pure translation."""
    return tuple(round(y - x, 6) for x, y in zip(a, b, strict=True))


def _element_view(i, entry):
    """The view an element belongs to; the view element V.<name> itself belongs to <name>."""
    if entry.get("view"):
        return entry["view"]
    return i[2:] if isinstance(i, str) and i.startswith("V.") else None


def compare(sa: dict, sb: dict) -> dict:
    """Semantic diff by element ID: ``added / removed / intent_changed / layout_changed`` plus
    ``details`` (the changed intent fields as ``[a, b]`` and how far a box moved) and
    ``view_moves``.

    A whole-view translation (the layout re-centres the view group, or the user moved the view)
    becomes one ``view_moves`` entry ``{view, dx, dy, elements}``; the elements that share it leave
    ``layout_changed``, which keeps only elements moving differently from their view."""
    added = sorted(set(sb) - set(sa))
    removed = sorted(set(sa) - set(sb))
    intent_changed, layout_changed, details = [], [], {}
    deltas = {}  # id -> per-coordinate shift, for elements present in both with a box in both
    for i in sorted(set(sa) & set(sb)):
        a, b = sa[i], sb[i]
        if a["intent"] != b["intent"]:
            intent_changed.append(i)
            fields = {
                k: [a["intent"].get(k), b["intent"].get(k)]
                for k in sorted(set(a["intent"]) | set(b["intent"]))
                if a["intent"].get(k) != b["intent"].get(k)
            }
            details.setdefault(i, {"kind": b["kind"]})["intent"] = fields
        mv = _moved(a["bbox"], b["bbox"])
        if mv is None or mv > BBOX_EPS:
            layout_changed.append(i)
            details.setdefault(i, {"kind": b["kind"]})["moved"] = (
                None if mv is None else round(mv, 3)
            )
        if a["bbox"] is not None and b["bbox"] is not None:
            deltas[i] = _delta(a["bbox"], b["bbox"])
    view_moves, absorbed = [], set()
    groups = {}
    for i, delta in deltas.items():
        if max(abs(x) for x in delta) <= BBOX_EPS:
            continue
        view = _element_view(i, sb[i])
        if view:
            groups.setdefault(view, []).append((i, delta))
    for view in sorted(groups):
        rows = groups[view]
        # the view element V.<name> is the explicit anchor: when it moved, that translation is the
        # view move even if only one child shares it (the other children are the extra movements)
        anchor_delta = next((d for i, d in rows if i == f"V.{view}"), None)
        if anchor_delta is not None:
            if max(abs(x) for x in anchor_delta) <= BBOX_EPS:
                continue  # the view itself did not move: children moved on their own
            absorbed |= {i for i, d in rows if d == anchor_delta}
            n = sum(1 for _i, d in rows if d == anchor_delta)
            view_moves.append(
                {"view": view, "dx": anchor_delta[0], "dy": anchor_delta[1], "elements": n}
            )
            continue
        counts = {}
        for _i, delta in rows:
            counts[delta] = counts.get(delta, 0) + 1
        top = max(counts.values())
        tied = [delta for delta, n in counts.items() if n == top]
        if len(tied) != 1:
            continue  # no single common translation: report no view move
        delta, n = tied[0], top
        total = sum(
            1
            for i in set(sa) & set(sb)
            if _element_view(i, sb[i]) == view
            and sa[i]["bbox"] is not None
            and sb[i]["bbox"] is not None
        )
        # without an anchor a translation needs at least two elements moving together and a
        # strict majority: the remaining elements are the real extra layout changes
        if n >= 2 and 2 * n > total:
            absorbed |= {i for i, d in rows if d == delta}
            view_moves.append({"view": view, "dx": delta[0], "dy": delta[1], "elements": n})
    layout_changed = [i for i in layout_changed if i not in absorbed]
    for i in absorbed:
        d = details.get(i)
        if d:
            d.pop("moved", None)
            if set(d) <= {"kind"}:
                details.pop(i)
    return {
        "added": added,
        "removed": removed,
        "intent_changed": intent_changed,
        "layout_changed": layout_changed,
        "view_moves": view_moves,
        "details": details,
        "_view_moved_ids": sorted(absorbed),  # kept out of the public summary, used by the overlay
    }


# ---- overlay SVG ------------------------------------------------------------------------------------

STANDALONE_CSS = (
    "g line,g path,g circle,g polyline{stroke:currentColor}"
    'g text{fill:currentColor;font-family:FangSong,STFangsong,SimFang,"仿宋",serif}'
    "g polygon.solid{fill:currentColor}g path.hatch{stroke:none}"
    + "".join(f".{c}{{color:{v}}}" for c, v in COLORS.items())
)


def overlay_svg(da, db, comparison: dict) -> str:
    """A (grey) under B (black); added green, removed red, changed blue (A's version stays grey).
    No stylesheet inside: the Viewer's page CSP forbids inline styles and its own stylesheet has the
    same rules; the file written by ``diff`` embeds ``STANDALONE_CSS``."""
    added, removed = set(comparison["added"]), set(comparison["removed"])
    changed = (
        set(comparison["intent_changed"])
        | set(comparison["layout_changed"])
        | set(comparison.get("_view_moved_ids", []))
    )
    (Wa, Ha), (Wb, Hb) = da.template["size"], db.template["size"]
    W, H = max(Wa, Wb), max(Ha, Hb)
    f = svgout._f
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(W)} {f(H)}" '
        f'width="{f(W)}mm" height="{f(H)}mm" data-sheet="{escape(db.sheet)}" data-compare="1">',
        "<defs>",
        *[svgout.hatch_pattern(db, f"hatch-{c}", v) for c, v in COLORS.items()],
    ]
    out += [
        "</defs>",
        f'<rect x="0" y="0" width="{f(W)}" height="{f(H)}" fill="white" class="paper"/>',
    ]

    def layer(d, dy, klass):
        out.append(f'<g transform="translate(0,{f(dy)})">' if dy else "<g>")
        for i, _kind, html in svgout.svg_groups(d):
            c = klass(i)
            html = html.replace("<g data-id=", f'<g class="{c}" data-id=', 1)
            out.append(html.replace("url(#hatch)", f"url(#hatch-{c})"))
        out.append("</g>")

    layer(da, H - Ha, lambda i: "df-del" if i in removed else "df-a")
    layer(db, H - Hb, lambda i: "df-add" if i in added else "df-chg" if i in changed else "df-b")
    out.append("</svg>")
    return "\n".join(out)


# ---- diff ---------------------------------------------------------------------------------------------


def compare_revisions(dir, a, b=None):
    """Rebuild ``a`` (and ``b``, default the working tree) and compare. Returns ``(summary, svg)``
    where ``svg`` is the overlay without an embedded stylesheet."""
    dir = Path(dir)
    ca = resolve(dir, a)
    cb = resolve(dir, b) if b is not None else None
    wanted = [ca] + ([cb] if cb else [])
    with checkouts(dir, wanted) as wt:
        ra = _build_at(wt[ca], a)
        rb = _build_at(wt[cb], b) if cb else runtime.build(dir, dxf=False)
        comparison = compare(snapshot(ra.d), snapshot(rb.d))
        svg = overlay_svg(ra.d, rb.d, comparison)
    comparison.pop("_view_moved_ids", None)
    summary = {
        "a": {"ref": str(a), "commit": _short(dir, ca)},
        "b": {
            "ref": str(b) if b is not None else "working",
            "commit": _short(dir, cb) if cb else None,
        },
        **comparison,
        "counts": {
            k: len(comparison[k])
            for k in ("added", "removed", "intent_changed", "layout_changed", "view_moves")
        },
    }
    return summary, svg


def _safe(ref) -> str:
    return re.sub(r"[^\w.\-]", "_", str(ref))


def diff(dir, a, b=None) -> dict:
    """``compare_revisions`` plus a stand-alone overlay file ``.linercad/tmp/diff-<A>-<B>.svg``."""
    dir = Path(dir)
    summary, svg = compare_revisions(dir, a, b)
    name = f"diff-{_safe(a)}-{_safe(b) if b is not None else 'working'}.svg"
    path = dir / TMP_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    stand = svg.replace("<defs>", f"<defs><style>{STANDALONE_CSS}</style>", 1)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(stand)
    txn.prune_tmp(dir)
    return {"ok": True, **summary, "svg": str(path)}


# ---- export -------------------------------------------------------------------------------------------


def rev_letter(n: int) -> str:
    """0 → A, 25 → Z, 26 → AA (revision letters, GB/T 10609.1 style)."""
    s, m = "", n + 1
    while m:
        m, r = divmod(m - 1, 26)
        s = chr(65 + r) + s
    return s


def _rev_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def next_rev(dir) -> str:
    """The first revision letter without a ``rev-<letter>`` tag."""
    used = set()
    for t in git(dir, "tag", "-l", "rev-*", check=False).stdout.split():
        m = REV_TAG.fullmatch(t)
        if m:
            used.add(_rev_index(m.group(1)))
    n = 0
    while n in used:
        n += 1
    return rev_letter(n)


def _has_revision_field(d) -> bool:
    return "revision" in d.template["title_block"]["fields"]


def _formats(formats) -> list[str]:
    if formats is None:
        return list(FORMATS)
    items = [formats] if isinstance(formats, str) else list(formats)
    out = []
    for f in items:
        for part in str(f).split(","):
            part = part.strip().lower()
            if not part:
                continue
            if part not in FORMATS:
                raise InvalidArgument(
                    f"不支持的导出格式 {part!r}", candidates=list(FORMATS), hint="--formats dxf,pdf"
                )
            if part not in out:
                out.append(part)
    if not out:
        raise InvalidArgument("--formats 是空的", candidates=list(FORMATS))
    return out


def _write_files(res, to: Path, formats) -> list[str]:
    """Write the requested files into ``to``; a failure leaves no half-written file behind."""
    from .dxfout import save_doc
    from .render import render_pdf

    to.mkdir(parents=True, exist_ok=True)
    W, H = res.d.template["size"]
    made, tmps = [], []
    try:
        for fmt in formats:
            final = to / f"drawing.{fmt}"
            part = to / f".lcad-partial-drawing.{fmt}"
            tmps.append(part)
            if fmt == "dxf":
                save_doc(res.doc, part)
            else:
                render_pdf(res.doc, (W, H), part)
            os.replace(part, final)
            made.append(str(final))
    finally:
        for p in tmps:
            p.unlink(missing_ok=True)
    return made


def export(dir, to, formats=None) -> dict:
    """Release: write ``drawing.dxf`` / ``drawing.pdf`` into ``to``, put the new revision letter in
    the title block's revision field, commit it as ``eN · 发布 rev-X`` and tag that commit ``rev-X``."""
    dir = Path(dir)
    fmts = _formats(formats)
    dirty = txn.dirty_sources(dir)
    if dirty:
        raise DirtySource(
            f"有未提交的源文件改动：{', '.join(dirty)}；发布的应是已提交的版本",
            candidates=dirty,
            hint='先 lcad build -m "<原话>" 提交，再 lcad export',
        )
    d0 = runtime.run_drawing(dir)
    letter = next_rev(dir)
    tag = f"rev-{letter}"
    to = Path(to)
    note = None
    if _has_revision_field(d0):
        ops = runtime.load_log(dir)
        edit_id = txn.next_edit(dir, ops)
        op = {
            "edit": edit_id,
            "op": "set",
            "id": "T.title.revision",
            "args": {"text": letter},
            "_line": len(ops) + 1,
        }
        # files first, from a build that already carries the revision: a locked or full target
        # fails here, before anything is committed
        pre = runtime.build(dir, [op], current_edit=edit_id)
        files = _write_files(pre, to, fmts)
        script = dir / TMP_DIR / f"export-{tag}.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            f'def apply(d):\n    d["T.title.revision"].set(text="{letter}")\n', encoding="utf-8"
        )
        out, res = txn.edit_full(dir, script, f"发布 {tag}")
        edit, commit = out["edit"], out["commit"]
    else:
        res = runtime.build(dir)
        files = _write_files(res, to, fmts)
        edit = None
        commit = _short(dir, "HEAD")
        note = "模板没有修订栏（revision），标题栏未改动，也没有新提交；标签打在当前提交上"
    try:
        git(dir, "tag", tag, "HEAD")
    except GitError as e:
        raise GitError(
            f"{edit or commit} 已提交并导出，但打标签 {tag} 失败：{e.message}",
            hint=f"手动 git tag {tag} {commit}",
        ) from e
    return {
        "ok": True,
        "tag": tag,
        "edit": edit,
        "commit": commit,
        "files": files,
        "errors": txn._errors(res.findings),
        "warnings": txn._warnings(res.findings),
        **({"note": note} if note else {}),
    }
