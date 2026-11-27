"""Parameterised drawing templates (H2 + v0.1.3 R9–R12): project & user scopes.

A template directory never carries a ``kind`` field and never enters a drawing's own ``.git`` tree:

    <root>/<name>/
        drawing.py               the build layer, with Param(...) declarations
        baseline.actions.jsonl   optional solidified semantic revision ops (edit="e0")
        model.py                 optional (3D source / import helper)
        templates/               optional enterprise overlays
        template.json            manifest (schema=2)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .errors import InvalidArgument, LinerError
from .runtime import SRC

MANIFEST = "template.json"
BASELINE_LOG = "baseline.actions.jsonl"
COPY_FILES = (SRC, "model.py")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
TRUST_EXTERNAL_WARNING = "模板含可执行 drawing.py，确认后再用"
SEMANTIC_OPS = frozenset({"accept", "general_tol", "rough_default"})
SEMANTIC_PREFIXES = ("D.", "N.", "G.", "R.", "DT.", "T.", "A.", "B.", "K.", "V.")


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


def path(name, root: Path | None = None) -> Path:
    name = str(name)
    if not NAME_RE.fullmatch(name):
        raise InvalidArgument(
            f"模板名 {name!r} 不合法",
            candidates=names(root=root),
            hint="用字母/数字开头，只含字母、数字、_ . -，最长 64 字符",
        )
    base = Path(root) if root is not None else home()
    return base / name


def exists(name, root: Path | None = None) -> bool:
    if not NAME_RE.fullmatch(str(name)):
        return False
    p = path(name, root=root)
    return (p / MANIFEST).is_file() and (p / SRC).is_file()


def names(root: Path | None = None) -> list[str]:
    base = Path(root) if root is not None else home()
    if not base.is_dir():
        return []
    out = []
    for p in base.iterdir():
        if not NAME_RE.fullmatch(p.name):
            continue  # .tmp-* / .old-* / .DS_Store: never let junk entries break list / init
        if exists(p.name, root=base):
            out.append(p.name)
    return sorted(out)


def _manifest_of(folder: Path) -> dict | None:
    try:
        doc = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def source_dir_of(doc: dict | None) -> str | None:
    """Read source directory string from either schema 1 (str) or schema 2 (dict) manifests."""
    if not isinstance(doc, dict):
        return None
    src = doc.get("source")
    if isinstance(src, dict):
        val = src.get("dir")
        return str(val) if val else None
    if isinstance(src, str) and src.strip():
        return src.strip()
    return None


def trust_info(
    doc: dict | None, *, scope: str, project_root: Path | None = None
) -> tuple[str, str | None]:
    """Classify template source trust: ``builtin`` / ``local`` / ``external`` + warning."""
    if scope == "example":
        return "builtin", None
    src_str = source_dir_of(doc)
    if not src_str:
        return "external", TRUST_EXTERNAL_WARNING
    try:
        src_p = Path(src_str).resolve()
    except OSError:
        return "external", TRUST_EXTERNAL_WARNING
    if project_root is not None:
        try:
            src_p.relative_to(Path(project_root).resolve())
            return "local", None
        except ValueError:
            return "external", TRUST_EXTERNAL_WARNING
    if src_p.exists():
        return "local", None
    return "external", TRUST_EXTERNAL_WARNING


def remove(name, root: Path | None = None) -> None:
    """Drop one template (used when save-time validation finds it is not self-contained)."""
    target = path(name, root=root) if NAME_RE.fullmatch(str(name)) else None
    if target is not None:
        shutil.rmtree(target, ignore_errors=True)


def info(name, root: Path | None = None) -> dict:
    folder = path(name, root=root)
    doc = _manifest_of(folder)
    if doc is None:
        raise InvalidArgument(f"没有模板 {name!r}", candidates=names(root=root))
    return doc


def list_all(
    root: Path | None = None,
    *,
    scope: str = "user",
    project_root: Path | None = None,
) -> list[dict]:
    """Manifests of saved templates under ``root`` (or user home), enriched for list display."""
    base = Path(root) if root is not None else home()
    out = []
    for n in names(root=base):
        folder = base / n
        doc = _manifest_of(folder)
        if doc is None:
            continue
        item = dict(doc)
        item.pop("kind", None)
        params = item.get("params") or []
        files = item.get("files") or []
        trust, warn = trust_info(item, scope=scope, project_root=project_root)
        item["scope"] = scope
        item.setdefault("tag", None)
        item["path"] = str(folder.resolve())
        item["param_count"] = len(params)
        item["has_baseline"] = (folder / BASELINE_LOG).is_file() or (BASELINE_LOG in files)
        item["trust"] = trust
        if warn:
            item["trust_warning"] = warn
        out.append(item)
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


def resolve_template(
    name: str,
    project_templates_dir: Path | None = None,
    *,
    allow_example: bool = True,
) -> tuple[str, Path | None]:
    """Resolve template by precedence: project > user > built-in example."""
    from .txn import EXAMPLES

    key = str(name)
    if NAME_RE.fullmatch(key):
        if project_templates_dir is not None and exists(key, root=project_templates_dir):
            return "project", path(key, root=project_templates_dir)
        if exists(key):
            return "user", path(key)
    if allow_example and key in EXAMPLES:
        return "example", None
    cands = []
    if project_templates_dir is not None:
        cands.extend(names(root=project_templates_dir))
    for n in names():
        if n not in cands:
            cands.append(n)
    for n in EXAMPLES:
        if n not in cands:
            cands.append(n)
    raise InvalidArgument(f"没有范例或用户模板（含项目模板）{name!r}", candidates=cands)


def is_semantic_op(rec: dict) -> bool:
    """True if a log op operates on policies or semantic IDs (safe to preserve across param changes)."""
    if rec.get("op") in SEMANTIC_OPS:
        return True
    rid = rec.get("id")
    return isinstance(rid, str) and rid.startswith(SEMANTIC_PREFIXES)


def filter_baseline_ops(ops: list[dict]) -> tuple[list[dict], list[str], dict]:
    """Keep semantic ops rewritten to ``edit="e0"``; return ``(kept_ops, lines, stats)``."""
    from . import record

    kept: list[dict] = []
    lines: list[str] = []
    dropped_samples: list[dict] = []
    dropped = 0
    for rec in ops:
        if is_semantic_op(rec):
            item = {
                "edit": "e0",
                "op": rec["op"],
                "id": rec.get("id"),
                "args": rec.get("args", {}),
                "_line": len(kept) + 1,
            }
            kept.append(item)
            lines.append(record.dumps(item))
        else:
            dropped += 1
            if len(dropped_samples) < 5:
                dropped_samples.append(
                    {
                        "line": rec.get("_line"),
                        "edit": rec.get("edit"),
                        "op": rec.get("op"),
                        "id": rec.get("id"),
                    }
                )
    return kept, lines, {"kept": len(kept), "dropped": dropped, "dropped_samples": dropped_samples}


def _norm_hash_val(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        r = round(float(v), 3)
        return 0.0 if r == 0 else r
    if isinstance(v, dict):
        return {str(k): _norm_hash_val(x) for k, x in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [_norm_hash_val(x) for x in v]
    return v


def model_hash(d) -> str:
    """Canonical sha256 over sorted ``d._els`` (intent/resolved/refs/status, floats to 3 decimals)."""
    elements = [
        _norm_hash_val(
            {
                "id": e._id,
                "kind": e.kind,
                "intent": e._intent,
                "resolved": e.placement["resolved"],
                "refs": e._refs,
                "status": e._status,
            }
        )
        for e in sorted(d._els.values(), key=lambda x: x._id)
    ]
    payload = json.dumps(elements, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_staged_model_hash(staged_dir: Path) -> str:
    from . import runtime

    with tempfile.TemporaryDirectory(prefix="lcad-hash-") as td:
        work = Path(td) / "tpl"
        shutil.copytree(staged_dir, work)
        base = work / BASELINE_LOG
        if base.is_file():
            (work / runtime.LOG).write_bytes(base.read_bytes())
        res = runtime.build(work, dxf=True)
        return model_hash(res.d)


def probe_template(work_dir: Path, params: list[dict], max_builds: int = 16) -> dict:
    """Evaluate each param's non-None min/max bounds (if min != max) up to ``max_builds``."""
    from . import runtime

    work_src = Path(work_dir)
    with tempfile.TemporaryDirectory(prefix="lcad-probe-") as td:
        work = Path(td) / "tpl"
        shutil.copytree(work_src, work)
        base = work / BASELINE_LOG
        log_file = work / runtime.LOG
        if base.is_file() and not log_file.exists():
            log_file.write_bytes(base.read_bytes())
        candidates: list[tuple[str, str, float]] = []
        for p in params or ():
            name = p.get("name")
            lo, hi = p.get("min"), p.get("max")
            if not name:
                continue
            if lo is not None and hi is not None and lo == hi:
                continue
            if lo is not None:
                candidates.append((str(name), "min", float(lo)))
            if hi is not None:
                candidates.append((str(name), "max", float(hi)))
        builds = 0
        failed: list[dict] = []
        stale_semantic: list[dict] = []
        skipped: list[dict] = []
        for name, bound, val in candidates:
            if builds >= max_builds:
                skipped.append({"param": name, "bound": bound, "value": val})
                continue
            builds += 1
            try:
                res = runtime.build(work, params={name: val}, dxf=True)
            except Exception as e:  # noqa: BLE001
                failed.append(
                    {
                        "param": name,
                        "bound": bound,
                        "value": val,
                        "reason": f"{type(e).__name__}: {e}",
                    }
                )
                continue
            errs = [f for f in res.findings if f.get("severity") == "error"]
            if errs:
                failed.append(
                    {
                        "param": name,
                        "bound": bound,
                        "value": val,
                        "reason": f"check 有 {len(errs)} 个 error",
                        "rules": [f.get("rule") for f in errs[:5]],
                    }
                )
            for s in res.stale:
                if is_semantic_op(s):
                    stale_semantic.append(
                        {
                            "param": name,
                            "bound": bound,
                            "value": val,
                            "id": s.get("id"),
                            "op": s.get("op"),
                            "reason": s.get("reason"),
                        }
                    )
        return {
            "builds": builds,
            "failed": failed,
            "stale_semantic": stale_semantic,
            "skipped": skipped,
        }


def save(
    source_dir,
    name,
    description="",
    force=False,
    build_result=None,
    validate=None,
    *,
    root: Path | None = None,
    tag: str | None = None,
    baseline_lines: list[str] | None = None,
    extra_files: list[tuple[str, Path]] = (),
    probe: dict | None = None,
    model_hash: str | None = None,
    compute_hash: bool = False,
    run_probe: bool = False,
    force_probe_fail: bool = False,
    dry_run: bool = False,
    on_ready=None,
) -> dict:
    """Package ``source_dir`` build layer (+ optional baseline / assets) into ``root / name``."""
    name = validate_name(name)
    source_dir = Path(source_dir)
    drawing = source_dir / SRC
    if not drawing.is_file():
        raise InvalidArgument(
            f"{source_dir} 里没有 {SRC}", hint="在图纸目录里运行 lcad template save"
        )
    dest_root = Path(root) if root is not None else home()
    target = path(name, root=dest_root)
    if target.exists() and not force and not dry_run:
        raise InvalidArgument(
            f"模板 {name!r} 已存在",
            candidates=names(root=dest_root),
            hint="加 --force 覆盖，或换一个名字",
        )
    with tempfile.TemporaryDirectory(prefix=f"lcad-tpl-{name}-") as td:
        tmp = Path(td)
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
        for rel, src_path in extra_files:
            rel_posix = Path(rel).as_posix()
            dst = (tmp / rel_posix).resolve()
            dst.relative_to(tmp.resolve())
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_path, dst)
            if rel_posix not in copied:
                copied.append(rel_posix)
        if baseline_lines:
            text = "".join(ln + "\n" for ln in baseline_lines)
            (tmp / BASELINE_LOG).write_text(text, encoding="utf-8", newline="\n")
            copied.append(BASELINE_LOG)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        manifest = {
            "schema": 2,
            "name": name,
            "tag": tag,
            "description": str(description or "").strip(),
            "created": now,
            "source": {"dir": str(source_dir.resolve()), "created": now},
            "files": copied,
            "params": _params_of(build_result) if build_result is not None else [],
            "model_hash": model_hash,
            "probe": probe,
        }
        (tmp / MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        if validate is not None:
            validate(tmp, manifest)
        if compute_hash and manifest.get("model_hash") is None:
            manifest["model_hash"] = _compute_staged_model_hash(tmp)
        if run_probe and manifest.get("probe") is None:
            probe_res = probe_template(tmp, manifest["params"])
            manifest["probe"] = probe_res
            if (probe_res["failed"] or probe_res["stale_semantic"]) and not force_probe_fail:
                raise InvalidArgument(
                    f"保存前参数边界自检失败（{len(probe_res['failed'])} 项构建/检查失败，"
                    f"{len(probe_res['stale_semantic'])} 项语义基线失效）",
                    values={"probe": probe_res},
                    hint="修复参数范围 / Param.rule / 基线引用，或使用 --force-probe-fail 强制保存",
                )
        (tmp / MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        if dry_run:
            return manifest
        if callable(on_ready):
            on_ready()
        dest_root.mkdir(parents=True, exist_ok=True)
        staged = dest_root / f".{name}.tmp-{os.getpid()}"
        shutil.rmtree(staged, ignore_errors=True)
        shutil.copytree(tmp, staged)
        backup = None
        if target.exists():
            backup = dest_root / f".{name}.old-{os.getpid()}"
            shutil.rmtree(backup, ignore_errors=True)
            target.replace(backup)
        try:
            staged.replace(target)
        except BaseException:
            if backup is not None and not target.exists():
                backup.replace(target)
            shutil.rmtree(staged, ignore_errors=True)
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
        return manifest


def init_files(name, *, folder: Path | None = None) -> list[tuple[str, bytes]]:
    """[(relative path, bytes)] of a saved template (excluding ``template.json`` and baseline)."""
    if folder is None:
        if not exists(name):
            raise InvalidArgument(
                f"没有用户模板 {name!r}",
                candidates=names(),
                hint="lcad template list 查看已保存模板",
            )
        folder = path(name)
    else:
        folder = Path(folder)
    files: list[tuple[str, bytes]] = []
    folder_res = folder.resolve()
    manifest = _manifest_of(folder)
    if manifest and isinstance(manifest.get("files"), list):
        for rel in manifest["files"]:
            if rel in (MANIFEST, BASELINE_LOG):
                continue
            p = (folder / rel).resolve()
            try:
                p.relative_to(folder_res)
            except ValueError as e:
                raise InvalidArgument(f"模板文件越界：{rel}") from e
            if p.is_file():
                files.append((Path(rel).as_posix(), p.read_bytes()))
        return files
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


def apply_sets(text: str, sets: dict, template_name=None, *, folder: Path | None = None) -> str:
    """Rewrite Param defaults of name=Param(<literal>, ...); fails before any build on typos."""
    if not sets:
        return text
    from .viewer import rewrite_param

    for name, value in sets.items():
        try:
            text = rewrite_param(text, name, value)
        except LinerError as e:
            candidates = []
            if folder is not None:
                doc = _manifest_of(Path(folder))
                if doc:
                    candidates = [p.get("name") for p in doc.get("params", [])]
            elif template_name:
                try:
                    candidates = [p.get("name") for p in info(template_name).get("params", [])]
                except LinerError:
                    pass
            if not candidates:
                candidates = re.findall(r"([A-Za-z_]\w*)\s*=\s*Param\s*\(", text)
            raise InvalidArgument(
                f"--set {name}={value:g} 不能应用：{e.message}",
                candidates=[c for c in candidates if c],
                hint=e.hint,
            ) from e
    return text
