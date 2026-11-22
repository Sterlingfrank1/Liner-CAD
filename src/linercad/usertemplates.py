"""User parameterised drawing templates (H2): save / list / init --from.

A template is a directory under the user data area (never inside a drawing's git tree):

    <LCAD_TEMPLATES>/<name>/
        drawing.py        the build layer, with its Param(...) declarations
        model.py          optional (3D source / import helper)
        templates/        optional enterprise overlays used by the drawing
        template.json     manifest: name, description, params ranges, created, files

The default root is the per-user data directory (Windows %APPDATA%/linercad/templates,
else $XDG_DATA_HOME/linercad/templates or ~/.local/share/linercad/templates); the
LCAD_TEMPLATES environment variable overrides it (tests use a temp dir).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .errors import InvalidArgument, LinerError
from .runtime import SRC

MANIFEST = "template.json"
COPY_FILES = (SRC, "model.py")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def home() -> Path:
    """Directory that holds all user templates (LCAD_TEMPLATES overrides it)."""
    env = os.environ.get("LCAD_TEMPLATES")
    if env:
        return Path(env).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "linercad" / "templates"


def path(name) -> Path:
    name = str(name)
    if not NAME_RE.fullmatch(name):
        raise InvalidArgument(
            f"模板名 {name!r} 不合法",
            candidates=names(),
            hint="用字母/数字开头，只含字母、数字、_ . -，最长 64 字符",
        )
    return home() / name


def exists(name) -> bool:
    return (path(name) / MANIFEST).is_file() and (path(name) / SRC).is_file()


def names() -> list[str]:
    root = home()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if exists(p.name))


def _manifest_of(folder: Path) -> dict | None:
    try:
        doc = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def info(name) -> dict:
    folder = path(name)
    doc = _manifest_of(folder)
    if doc is None:
        raise InvalidArgument(f"没有用户模板 {name!r}", candidates=names())
    return doc


def list_all() -> list[dict]:
    """Manifests of all saved templates, sorted by name."""
    out = []
    for n in names():
        doc = _manifest_of(path(n))
        if doc is not None:
            out.append(doc)
    return out


def validate_name(name) -> str:
    name = str(name or "").strip()
    if not NAME_RE.fullmatch(name):
        raise InvalidArgument(
            f"模板名 {name!r} 不合法",
            hint="用字母/数字开头，只含字母、数字、_ . -，最长 64 字符",
        )
    from .txn import EXAMPLES

    if name in EXAMPLES:
        raise InvalidArgument(f"{name!r} 是内置范例名，请换一个模板名", candidates=list(EXAMPLES))
    return name


def _params_of(res) -> list[dict]:
    out = []
    for n in res.d.P.names():
        p = res.d.P[n].to_dict(n)
        out.append(
            {
                k: p.get(k)
                for k in ("name", "label", "value", "min", "max", "step", "unit", "tol", "rule")
                if p.get(k) is not None
            }
        )
    return out


def save(source_dir, name, description="", force=False, build_result=None) -> dict:
    """Copy the build layer of source_dir into the user template root.

    Only drawing.py / model.py / templates/ are copied: the revision layer
    (drawing.actions.jsonl) is deliberately not part of a template (the caller warns about it).
    """
    name = validate_name(name)
    source_dir = Path(source_dir)
    drawing = source_dir / SRC
    if not drawing.is_file():
        raise InvalidArgument(
            f"{source_dir} 里没有 {SRC}", hint="在图纸目录里运行 lcad template save"
        )
    target = path(name)
    if target.exists() and not force:
        raise InvalidArgument(
            f"用户模板 {name!r} 已存在", candidates=names(), hint="加 --force 覆盖，或换一个名字"
        )
    root = home()
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f".{name}.tmp-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        copied = [SRC]
        shutil.copyfile(drawing, tmp / SRC)
        for extra in COPY_FILES[1:]:
            if (source_dir / extra).is_file():
                shutil.copyfile(source_dir / extra, tmp / extra)
                copied.append(extra)
        overlay = source_dir / "templates"
        if overlay.is_dir():
            for f in sorted(overlay.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(source_dir).as_posix()
                    dst = tmp / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(f, dst)
                    copied.append(rel)
        manifest = {
            "name": name,
            "description": str(description or "").strip(),
            "created": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": str(source_dir.resolve()),
            "files": copied,
            "params": _params_of(build_result) if build_result is not None else [],
        }
        (tmp / MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        backup = None
        if target.exists():
            # move the old template aside first; restore it if publishing the new one fails
            backup = root / f".{name}.old-{os.getpid()}"
            shutil.rmtree(backup, ignore_errors=True)
            target.replace(backup)
        try:
            tmp.replace(target)
        except BaseException:
            if backup is not None:
                backup.replace(target)
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
        return manifest
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def init_files(name) -> list:
    """[(relative path, bytes)] of a saved template, for lcad init --from <name>."""
    folder = path(name)
    if not exists(name):
        raise InvalidArgument(
            f"没有用户模板 {name!r}", candidates=names(), hint="lcad template list 查看已保存模板"
        )
    files = []
    for rel in (SRC, "model.py"):
        p = folder / rel
        if p.is_file():
            files.append((rel, p.read_bytes()))
    overlay = folder / "templates"
    if overlay.is_dir():
        for f in sorted(overlay.rglob("*")):
            if f.is_file():
                files.append((f.relative_to(folder).as_posix(), f.read_bytes()))
    return files


def apply_sets(text: str, sets: dict, template_name=None) -> str:
    """Rewrite Param defaults of name=Param(<literal>, ...); fails before any build on typos."""
    if not sets:
        return text
    from .viewer import rewrite_param

    for name, value in sets.items():
        try:
            text = rewrite_param(text, name, value)
        except LinerError as e:
            candidates = []
            if template_name:
                try:
                    candidates = [p.get("name") for p in info(template_name).get("params", [])]
                except LinerError:
                    pass
            if not candidates:
                found = re.search(r"([A-Za-z_]\w*)=Param", e.message)
                candidates = [found.group(1)] if found else []
            raise InvalidArgument(
                f"--set {name}={value:g} 不能应用：{e.message}",
                candidates=[c for c in candidates if c],
                hint=e.hint,
            ) from e
    return text
