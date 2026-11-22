"""Transactions and git (SPEC §8): init / build / edit / undo.

One successful modification = one commit ``eN · <user words>``; only this drawing's source
files are committed; nothing is pushed. Any failure rolls back: the log is unchanged, there is
no commit and the previous artifacts stay.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from importlib import resources
from pathlib import Path

from . import record
from .errors import DirtySource, GitError, InvalidArgument, NoOps, UndoError
from .runtime import BUILD_DIR, LOG, SRC, TMP_DIR, build, edit_number, run_script, write_artifacts

REF_DXF = "ref.dxf"  # what `lcad init --from-dxf` copies in
SOURCES = (SRC, LOG, ".gitignore", ".gitattributes", "templates")
GITIGNORE = ".linercad/\n"
GITATTRIBUTES = "* text=auto eol=lf\n"
EXAMPLES = tuple(  # every package example directory with a drawing.py (adding one needs no code)
    sorted(
        p.name
        for p in resources.files("linercad").joinpath("examples").iterdir()
        if p.is_dir() and (p / "drawing.py").is_file()
    )
)
EDIT_RE = re.compile(r"^e(\d+) · ")
KEEP_TMP = 20

STARTER = '''"""Liner-CAD 图纸构建层。改完运行 `lcad build -m "<说明>"`。"""

from linercad import Drawing, Param

d = Drawing(sheet="{sheet}", std="GB", scale="1:1")
P = d.params(
    L=Param(100, min=10, max=400, unit="mm", label="长度"),
    H=Param(50, min=5, max=200, unit="mm", label="高度"),
)
front = d.view("front")
front.rect((0, 0), P.L, P.H, name="body")
front.dim.linear("L", (0, 0), (P.L, 0), value=P.L, side="bottom")
front.dim.linear("H", (0, 0), (0, P.H), value=P.H, side="left")
d.title(name="未命名零件", material="")
'''

DXF_STARTER = '''"""Liner-CAD 图纸构建层：导入 {ref}。改完运行 `lcad build -m "<说明>"`。"""

from linercad import Drawing

d = Drawing(sheet="{sheet}", std="GB", scale="{scale}")
d.import_dxf("{ref}")
'''


# ---- git ----------------------------------------------------------------------------------------------


def git(dir, *args, check=True, input=None):
    """Run git; stdin/stdout as raw UTF-8 bytes (text mode would turn LF into CRLF on Windows)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(dir), *args],
            capture_output=True,
            input=None if input is None else input.encode("utf-8"),
        )
    except FileNotFoundError as e:
        raise GitError("找不到 git 命令", hint="安装 git 并放进 PATH") from e
    r.stdout = r.stdout.decode("utf-8", errors="replace")
    r.stderr = r.stderr.decode("utf-8", errors="replace")
    if check and r.returncode != 0:
        raise GitError(
            f"git {' '.join(args[:2])} 失败：{(r.stderr or r.stdout).strip()}",
            values={"args": list(args)},
        )
    return r


def repo_root(dir):
    r = git(dir, "rev-parse", "--show-toplevel", check=False)
    return Path(r.stdout.strip()) if r.returncode == 0 else None


def _ident(dir):
    name = git(dir, "config", "user.name", check=False).stdout.strip()
    email = git(dir, "config", "user.email", check=False).stdout.strip()
    out = []
    if not name:
        out += ["-c", "user.name=linercad"]
    if not email:
        out += ["-c", "user.email=linercad@localhost"]
    return out


def source_paths(dir):
    """Tracked sources: drawing.py, the log, templates, plus 3D models next to drawing.py (other
    ``*.py``, ``*.step``/``*.stp``), imported ``*.dxf`` and sub-directories holding component
    models (M3)."""
    dir = Path(dir)
    out = [p for p in SOURCES if (dir / p).exists()]
    for f in sorted(dir.iterdir()) if dir.is_dir() else []:
        if f.name.startswith(".") or f.name in out:
            continue
        if f.is_file() and f.suffix.lower() in (".py", ".step", ".stp", ".dxf"):
            out.append(f.name)
        elif (
            f.is_dir()
            and f.name not in ("templates", "__pycache__")
            and any(f.glob("model.py")) | any(f.glob("*/model.py"))
        ):
            out.append(f.name)
    return out


def dirty_sources(dir):
    paths = source_paths(dir)
    r = git(
        dir,
        "-c",
        "core.quotePath=false",
        "status",
        "--porcelain",
        "-z",
        "--untracked-files=all",
        "--",
        *paths,
    )
    root = repo_root(dir)
    out = []
    for item in r.stdout.split("\0"):
        if len(item) > 3:
            full = (root / item[3:]).resolve() if root else Path(dir) / item[3:]
            out.append(Path(os.path.relpath(full, Path(dir).resolve())).as_posix())
    return out


def _unstage(dir):
    git(dir, "reset", "-q", "--", *source_paths(dir), check=False)


def commit(dir, subject, body=None):
    """Commit only this drawing's source files. Returns the short hash, or None if nothing changed."""
    paths = source_paths(dir)
    git(dir, "add", "--", *paths)
    staged = git(dir, "diff", "--cached", "--name-only", "--", *paths).stdout.strip()
    if not staged:
        return None
    msg = ["-m", subject] + (["-m", body] if body else [])
    git(dir, *_ident(dir), "commit", "-q", *msg, "--", *paths)
    return git(dir, "rev-parse", "--short", "HEAD").stdout.strip()


def git_edits(dir):
    """[(number, hash, subject, body)] of commits touching this drawing, newest first."""
    r = git(dir, "log", "--format=%H%x1f%s%x1f%b%x1e", "--", ".", check=False)
    out = []
    for chunk in r.stdout.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        h, s, b = (chunk.split("\x1f") + ["", ""])[:3]
        m = EDIT_RE.match(s)
        if m:
            out.append((int(m.group(1)), h, s, b))
    return out


def next_edit(dir, log_ops):
    nums = [edit_number(r["edit"]) for r in log_ops] + [n for n, *_ in git_edits(dir)]
    return f"e{max(nums + [-1]) + 1}"


# ---- helpers ------------------------------------------------------------------------------------------


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def prune_tmp(dir, keep=KEEP_TMP):
    tmp = Path(dir) / TMP_DIR
    if not tmp.is_dir():
        return
    files = sorted(
        (p for p in tmp.iterdir() if p.is_file()),
        key=lambda p: (p.stat().st_mtime, p.name),
        reverse=True,
    )
    for p in files[keep:]:
        try:
            p.unlink()
        except OSError:
            pass


def _errors(findings):
    return sum(1 for f in findings if f.get("severity") == "error")


def _warnings(findings, base=None):
    seen = {(f["rule"], f.get("id")) for f in base} if base is not None else None
    out = []
    for f in findings:
        f = dict(f)
        if seen is not None and (f["rule"], f.get("id")) not in seen:
            f["new"] = True
        out.append(f)
    return out


# ---- commands -----------------------------------------------------------------------------------------


def _artifacts(dir, res, edit):
    """Write artifacts after a successful commit; a failure here is reported, not raised."""
    try:
        return write_artifacts(dir, res, edit)
    except OSError as e:
        return {
            "artifacts_error": f"{type(e).__name__}: {e}",
            "hint": "关闭占用产物的程序后 lcad build",
        }


def _example_extras(from_):
    """Other source files of an example (``model.py``, STEP …) copied next to ``drawing.py``."""
    if not from_:
        return []
    root = resources.files("linercad") / "examples" / from_
    return [
        (f.name, f.read_text(encoding="utf-8"))
        for f in root.iterdir()
        if f.is_file()
        and f.name != SRC
        and f.name.endswith((".py", ".step", ".stp"))
        and not f.name.startswith("_")
    ]


def needs_3d(name) -> bool:
    """An example whose drawing projects a 3D model (needs ``linercad[3d]``)."""
    return (resources.files("linercad") / "examples" / name / "model.py").is_file()


def init(dir, from_=None, sheet=None, from_dxf=None, sets=None):
    """New drawing directory: the starter, a package example (``from_``) or an imported DXF
    (``from_dxf`` is copied to ``ref.dxf``; the sheet is guessed from its extents unless given)."""
    dir = Path(dir)
    if (dir / SRC).exists() or (dir / LOG).exists():
        raise InvalidArgument(f"{dir} 里已经有图纸（{SRC} 或 {LOG}）", hint="换一个空目录")
    from . import usertemplates

    user_template = None
    if from_ is not None and from_ not in EXAMPLES:
        known = usertemplates.names()
        if from_ in known:
            user_template = str(from_)  # a saved user template shadows nothing: examples win
        else:
            raise InvalidArgument(
                f"没有范例或用户模板 {from_!r}",
                candidates=list(EXAMPLES) + known,
            )
    if from_ is not None and from_dxf is not None:
        raise InvalidArgument("--from 和 --from-dxf 只能用一个")
    if user_template is not None and sheet:
        raise InvalidArgument(
            "用户模板自带图幅，不能再用 --sheet",
            hint="需要别的图幅：改模板 drawing.py 的 Drawing(sheet=...) 后重新 template save",
        )
    dxf_src, guess = None, None
    if from_dxf is not None:
        from . import importdxf

        dxf_src = Path(from_dxf)
        guess = importdxf.prepare_init(
            dxf_src
        )  # an unreadable file fails here, before anything is made
        sheet = sheet or guess["sheet"]
    sheet = sheet or "A3"
    existed = dir.exists()
    dir.mkdir(parents=True, exist_ok=True)
    created = []
    had_repo = repo_root(dir) is not None
    try:
        extras = []
        if dxf_src is not None:
            text0 = DXF_STARTER.format(ref=REF_DXF, sheet=sheet, scale=guess["scale"])
            if not (dir / REF_DXF).exists():
                shutil.copyfile(dxf_src, dir / REF_DXF)
                created.append(dir / REF_DXF)
        elif user_template:
            files = usertemplates.init_files(user_template)
            text0 = dict(files)[SRC].decode("utf-8")
            extras = [(n, b) for n, b in files if n != SRC]
        elif from_:
            text0 = (resources.files("linercad") / "examples" / from_ / SRC).read_text(
                encoding="utf-8"
            )
            extras = _example_extras(from_)
        else:
            text0 = STARTER.format(sheet=sheet)
            extras = []
        if sets:
            text0 = usertemplates.apply_sets(text0, sets, template_name=user_template)
        for name, text in (
            (SRC, text0),
            *extras,
            (LOG, ""),
            (".gitignore", GITIGNORE),
            (".gitattributes", GITATTRIBUTES),
        ):
            if not (dir / name).exists():
                p = dir / name
                p.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(text, bytes):
                    p.write_bytes(text)
                else:
                    _write(p, text)
                created.append(p)
        if not had_repo:
            git(dir, "init", "-q")
        res = build(dir)
    except BaseException:
        for p in created:
            p.unlink(missing_ok=True)
        if not had_repo:
            shutil.rmtree(dir / ".git", ignore_errors=True)
        shutil.rmtree(dir / ".linercad", ignore_errors=True)
        if not existed:
            shutil.rmtree(dir, ignore_errors=True)
        raise
    (dir / TMP_DIR).mkdir(parents=True, exist_ok=True)
    arts = write_artifacts(dir, res, "e0")
    h = commit(dir, "e0 · init")
    out = {
        "ok": True,
        "edit": "e0",
        "commit": h,
        "dir": str(dir),
        **arts,
        "errors": _errors(res.findings),
        "warnings": _warnings(res.findings),
    }
    if user_template:
        out["template"] = user_template
    if sets:
        out["sets"] = dict(sets)
    if dxf_src is not None:
        out["import"] = {
            "sheet": sheet,
            "scale": guess["scale"],
            "elements": {e.id: e.counts for e in res.d.elements if e.kind == "import"},
        }
    return out


def _model_sig(dir):
    """{id: intent+refs} of the last written model.json (empty when there is none)."""
    p = Path(dir) / BUILD_DIR / "model.json"
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        e["id"]: json.dumps([e.get("intent"), e.get("refs")], sort_keys=True)
        for e in m.get("elements", [])
    }


def changed_ids(before, d):
    """Element IDs added, removed or whose intent / refs changed since ``before``."""
    after = {}
    for e in d._els.values():
        x = e.to_dict()
        after[e.id] = json.dumps([x["intent"], x["refs"]], sort_keys=True)
    return sorted(i for i in set(before) | set(after) if before.get(i) != after.get(i))


def build_commit(dir, msg=None):
    dir = Path(dir)
    before = _model_sig(dir)
    res = build(dir)
    edit = next_edit(dir, res.log_ops)
    out = {
        "ok": True,
        "edit": None,
        "commit": None,
        "changed": changed_ids(before, res.d) if before else [],
        "errors": _errors(res.findings),
        "warnings": _warnings(res.findings),
    }
    dirty = dirty_sources(dir)
    if msg:
        if dirty:
            out["commit"] = commit(dir, f"{edit} · {msg}")
            out["edit"] = edit
        else:
            out["note"] = "源文件没有改动，未提交"
    elif dirty:
        out["uncommitted"] = dirty
        out["hint"] = '源文件有未提交改动；用 lcad build -m "<原话>" 提交'
    current = out["edit"] or f"e{int(edit[1:]) - 1}"  # model.json records the version it shows
    out.update(write_artifacts(dir, res, current))
    return out


def edit(dir, script, msg):
    return edit_full(dir, script, msg)[0]


def edit_full(dir, script, msg):
    """``edit`` plus the final ``BuildResult`` (``lcad export`` writes its files from it)."""
    dir = Path(dir)
    if not msg:
        raise InvalidArgument('lcad edit 需要 -m "<用户原话>"')
    log_path = dir / LOG
    script = Path(script)
    if not script.is_absolute() and not script.exists() and (dir / script).exists():
        script = dir / script  # relative to the drawing directory given with -C
    base = build(dir)
    edit_id = next_edit(dir, base.log_ops)
    ops = run_script(base.d, script, edit_id)
    if not ops:
        raise NoOps(
            "脚本没有产生任何修改操作",
            hint="确认 apply(d) 里调用了修改类 API（place/set/move/suppress/建图/标注）",
        )
    n0 = len(log_path.read_text(encoding="utf-8").splitlines()) if log_path.exists() else 0
    numbered = [dict(op, _line=n0 + k + 1) for k, op in enumerate(ops)]
    r1 = build(dir, numbered, current_edit=edit_id)
    filled = record.fill_layout(numbered, r1.d)
    r2 = build(dir, filled, current_edit=edit_id)
    old = log_path.read_bytes() if log_path.exists() else b""
    lines = "".join(record.dumps(op) + "\n" for op in filled)
    prefix = old.decode("utf-8")
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    _write(log_path, prefix + lines)
    try:
        h = commit(dir, f"{edit_id} · {msg}")
    except Exception:
        log_path.write_bytes(old)
        _unstage(dir)
        raise
    arts = _artifacts(dir, r2, edit_id)
    prune_tmp(dir)
    changed = []
    for op in filled:
        if op.get("id") and op["id"] not in changed:
            changed.append(op["id"])
    out = {
        "ok": True,
        "edit": edit_id,
        "commit": h,
        "ops": [{k: v for k, v in op.items() if k != "_line"} for op in filled],
        "changed": changed,
        "errors": _errors(r2.findings),
        "warnings": _warnings(r2.findings, base.findings),
        **arts,
    }
    return out, r2


def undo(dir, target, msg=None):
    dir = Path(dir)
    if not re.fullmatch(r"e\d+", str(target)):
        raise UndoError(f"编号 {target!r} 不合法，应写成 e7 这样")
    if target == "e0":
        raise UndoError("e0（init）不能撤销")
    dirty = dirty_sources(dir)
    if dirty:
        raise DirtySource(
            f"有未提交的源文件改动：{', '.join(dirty)}",
            candidates=dirty,
            hint='先 lcad build -m "<原话>" 提交，或手动还原',
        )
    edits = git_edits(dir)
    undone = {m.strip() for *_, b in edits for m in re.findall(r"Undo-Of:\s*(e\d+)", b)}
    if target in undone:
        raise UndoError(f"{target} 已经撤销过了", hint="重新做一次原来的修改")
    hit = [e for e in edits if f"e{e[0]}" == target]
    if not hit:
        cands = [
            f"e{n}"
            for n, _, s, b in edits
            if n != 0 and "Undo-Of:" not in b and f"e{n}" not in undone
        ]
        raise UndoError(f"找不到修改 {target}", candidates=cands)
    _, h, subject, body = hit[0]
    if "Undo-Of:" in body:
        raise UndoError(f"{target} 本身是一次撤销，M0 不支持撤销撤销", hint="重新做一次原来的修改")
    log_path = dir / LOG
    old_log = log_path.read_bytes() if log_path.exists() else b""
    old_src = (dir / SRC).read_bytes()
    keep = [
        ln for ln in old_log.decode("utf-8").splitlines() if ln.strip() and not _is_edit(ln, target)
    ]
    removed = len([ln for ln in old_log.decode("utf-8").splitlines() if ln.strip()]) - len(keep)
    root = repo_root(dir)
    rel = Path(os.path.relpath(dir.resolve(), root.resolve())).as_posix()
    srcs = [f"{rel}/{p}" if rel != "." else p for p in (SRC, "templates")]
    patch = (
        git(root, "diff", f"{h}^", h, "--", *srcs, check=False).stdout
        if _has_parent(root, h)
        else ""
    )
    try:
        if patch.strip():
            chk = git(root, "apply", "-R", "--check", "-", check=False, input=patch)
            if chk.returncode != 0:
                raise UndoError(
                    f"撤销 {target} 对 drawing.py 的改动有冲突",
                    values={"conflict": chk.stderr.strip()},
                    hint="手动改 drawing.py 后 lcad build -m，或先撤销更晚的修改",
                )
            git(root, "apply", "-R", "-", input=patch)
        _write(log_path, "".join(ln + "\n" for ln in keep))
        res = build(dir)
        new_id = next_edit(dir, res.log_ops)
        c = commit(dir, f"{new_id} · {msg or 'undo ' + target}", body=f"Undo-Of: {target}")
        if c is None:
            raise UndoError(f"撤销 {target} 没有产生任何改动")
    except Exception:
        log_path.write_bytes(old_log)
        (dir / SRC).write_bytes(old_src)
        _unstage(dir)
        raise
    arts = _artifacts(dir, res, new_id)
    return {
        "ok": True,
        "edit": new_id,
        "commit": c,
        "undone": target,
        "removed_ops": removed,
        "errors": _errors(res.findings),
        "warnings": _warnings(res.findings),
        **arts,
    }


def _is_edit(line, target):
    import json

    try:
        return json.loads(line).get("edit") == target
    except json.JSONDecodeError:
        return False


def _has_parent(root, h):
    return git(root, "rev-parse", "-q", "--verify", f"{h}^", check=False).returncode == 0


def clean_tmp(dir):
    shutil.rmtree(Path(dir) / TMP_DIR, ignore_errors=True)
