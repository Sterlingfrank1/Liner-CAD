"""Project root resolution and ``linercad.project.toml`` marker management (v0.1.3 R9)."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .errors import InvalidArgument

MARKER = "linercad.project.toml"
DEFAULT_TEMPLATES_DIR = "lcad-templates"
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$")


@dataclass(frozen=True)
class ProjectRoot:
    """Resolved project root containing (or ready to host) ``linercad.project.toml``."""

    root: Path
    templates_dir: Path
    marker_path: Path
    marker_exists: bool
    resolved_by: str


def is_drawing_dir(path: Path) -> bool:
    """True when ``path`` looks like a drawing directory (``drawing.py`` or ``.linercad/``)."""
    p = Path(path)
    return (p / "drawing.py").is_file() or (p / ".linercad").is_dir()


def is_inside_drawing_dir(path: Path) -> bool:
    """True when ``path`` is a drawing dir or sits beneath a drawing root (with ``drawing.py``)."""
    p = Path(path).resolve()
    if is_drawing_dir(p):
        return True
    for anc in p.parents:
        if is_drive_root(anc):
            break
        if (anc / "drawing.py").is_file() or (anc / "drawing.actions.jsonl").is_file():
            return True
        if (anc / ".git").exists() or (anc / MARKER).is_file():
            break
    return False


def is_drive_root(path: Path) -> bool:
    """True when ``path`` is the filesystem / drive root."""
    r = Path(path).resolve()
    return r.parent == r


def validate_tag(tag) -> str | None:
    """Validate optional template tag string; returns ``None`` if omitted or blank."""
    if tag is None:
        return None
    s = str(tag).strip()
    if not s:
        return None
    if not TAG_RE.fullmatch(s):
        raise InvalidArgument(
            f"模板标签 {tag!r} 不合法",
            hint="标签须以字母或数字开头，只含字母、数字、_ . -，最长 32 字符",
        )
    return s


def _read_marker(root: Path) -> tuple[Path, str]:
    marker = root / MARKER
    try:
        data = tomllib.loads(marker.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise InvalidArgument(f"读取 {marker} 失败：{e}") from e
    tpl = data.get("templates") if isinstance(data, dict) else None
    rel = DEFAULT_TEMPLATES_DIR
    if isinstance(tpl, dict) and "dir" in tpl:
        rel = str(tpl["dir"] or "").strip()
    if not rel:
        raise InvalidArgument(f"{marker} 中的 [templates].dir 不能为空")
    rel_path = Path(rel)
    if rel_path.is_absolute():
        raise InvalidArgument(f"{marker} 中的 [templates].dir 必须是相对路径：{rel}")
    root_res = root.resolve()
    tdir = (root_res / rel_path).resolve()
    try:
        sub = tdir.relative_to(root_res)
    except ValueError as e:
        raise InvalidArgument(f"{marker} 中的模板目录越出项目根：{rel}") from e
    if sub == Path(".") or is_inside_drawing_dir(tdir):
        raise InvalidArgument(f"{marker} 中的模板目录不合法：{rel}")
    return tdir, sub.as_posix()


def _can_write_target(cand: Path) -> bool:
    cur = cand
    while not cur.exists():
        if cur.parent == cur:
            return False
        cur = cur.parent
    return cur.is_dir() and os.access(cur, os.W_OK)


def _from_explicit(raw: str | Path, *, source_name: str, allow_create: bool) -> ProjectRoot | None:
    p = Path(raw).expanduser().resolve()
    if is_inside_drawing_dir(p):
        raise InvalidArgument(
            f"项目根不能在图纸目录内：{p}",
            hint="请传入图纸所在的项目根目录（例如图纸目录的父目录）",
        )
    marker = p / MARKER
    if marker.is_file():
        tdir, _ = _read_marker(p)
        return ProjectRoot(p, tdir, marker, True, source_name)
    if is_drive_root(p):
        raise InvalidArgument(
            f"项目根不能是磁盘根目录：{p}",
            hint="请显式指定工作区下的项目目录，如 --project ./my-project",
        )
    if not allow_create:
        return None
    if not _can_write_target(p):
        raise InvalidArgument(
            f"项目根目录不可写：{p}",
            hint="请通过 --project <root> 指定可写的项目根目录",
        )
    return ProjectRoot(p, p / DEFAULT_TEMPLATES_DIR, marker, False, source_name)


def resolve_project(
    anchor: Path | None = None,
    *,
    project: str | Path | None = None,
    allow_create: bool = False,
) -> ProjectRoot | None:
    """Resolve the project root in priority order:

    1. explicit ``project`` (``--project``)
    2. env ``LCAD_PROJECT_ROOT``
    3. upward walk for ``linercad.project.toml`` (skipping anchor's own ``.git``, stopping AFTER checking ancestor ``.git``)
    4. only when ``allow_create=True``: ``anchor.parent`` if ``anchor`` is a drawing dir, else ``anchor``.
    """
    if project is not None and str(project).strip():
        return _from_explicit(project, source_name="cli", allow_create=allow_create)

    env_root = os.environ.get("LCAD_PROJECT_ROOT")
    if env_root and env_root.strip():
        return _from_explicit(env_root, source_name="env", allow_create=allow_create)

    start = (Path(anchor) if anchor is not None else Path.cwd()).resolve()
    cur = start
    idx = 0
    while True:
        if not is_inside_drawing_dir(cur) and (cur / MARKER).is_file():
            tdir, _ = _read_marker(cur)
            return ProjectRoot(cur, tdir, cur / MARKER, True, "marker")
        if idx > 0 and (cur / ".git").exists():
            break
        if is_drive_root(cur):
            break
        cur = cur.parent
        idx += 1

    if not allow_create:
        return None

    cand = start.parent if is_drawing_dir(start) else start
    while is_inside_drawing_dir(cand) and not is_drive_root(cand):
        cand = cand.parent
    if is_inside_drawing_dir(cand):
        raise InvalidArgument(
            f"项目根不能在图纸目录内：{cand}",
            hint="请显式传入 --project <项目根目录>",
        )
    if is_drive_root(cand):
        raise InvalidArgument(
            f"解析到的项目根是磁盘根目录 {cand}，请显式传入 --project",
            hint="请传入 --project <项目根目录>",
        )
    if not _can_write_target(cand):
        raise InvalidArgument(
            f"项目根目录不可写：{cand}",
            hint="请显式传入 --project <项目根目录>",
        )
    return ProjectRoot(cand, cand / DEFAULT_TEMPLATES_DIR, cand / MARKER, False, "fallback")


def ensure_project_dir(proj: ProjectRoot) -> bool:
    """Create ``linercad.project.toml`` (if absent) and the templates dir; returns True if marker created."""
    if is_inside_drawing_dir(proj.root):
        raise InvalidArgument(f"铁律禁止在图纸目录内写入项目标记：{proj.root}")
    proj.root.mkdir(parents=True, exist_ok=True)
    created_marker = False
    if not proj.marker_path.is_file():
        now = datetime.now(UTC).isoformat(timespec="seconds")
        proj_name = proj.root.name.replace('"', "")
        rel_dir = proj.templates_dir.resolve().relative_to(proj.root.resolve()).as_posix()
        rel_dir = rel_dir.replace('"', "")
        text = (
            "version = 1\n"
            f'name = "{proj_name}"\n'
            f'created = "{now}"\n'
            "[templates]\n"
            f'dir = "{rel_dir}"\n'
        )
        tmp = proj.marker_path.with_name(f".{MARKER}.tmp-{os.getpid()}")
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(tmp, proj.marker_path)
        finally:
            tmp.unlink(missing_ok=True)
        created_marker = True
    proj.templates_dir.mkdir(parents=True, exist_ok=True)
    return created_marker
