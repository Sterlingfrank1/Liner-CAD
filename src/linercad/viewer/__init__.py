"""Viewer v0 (M2 SPEC §2): a tiny local HTTP service (standard library only, bound to
127.0.0.1) plus a static page. The page polls ``/api/state``; the service rebuilds when
``drawing.py``, the action log or git HEAD change. Selection and snapshot are written to
``.linercad/selection.json`` / ``snapshot.json`` for agents (``lcad context @sel``)."""

from __future__ import annotations

import ast
import contextlib
import errno
import io
import json
import math
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request as URLRequest
from urllib.request import urlopen

from .. import svgout
from ..errors import InvalidArgument, LinerError
from ..runtime import LOG, SRC, build

STATIC = {
    "/": ("index.html", "text/html"),
    "/viewer.js": ("viewer.js", "text/javascript"),
    "/viewer.css": ("viewer.css", "text/css"),
}
VIEW_NAMES = {
    "front": "主视图",
    "top": "俯视图",
    "left": "左视图",
    "right": "右视图",
    "bottom": "仰视图",
    "rear": "后视图",
}


def label(e) -> str:
    """Short human label: dimension text, tolerance frame, symbol value, or the ID."""
    i = e._intent
    if e.kind == "dim":
        return i.get("text", "") + (i.get("tail") or "")
    if e.kind == "gtol":
        return f"{i['char']} {i['value']:g}"
    if e.kind == "rough":
        return f"{i['param']} {i['value']:g}"
    if e.kind in ("datum", "section", "mark"):
        return i.get("letter", "")
    if e.kind in ("note", "table.cell"):
        return i.get("text", "")
    if e.kind == "table":
        return i.get("title") or i.get("name", "")
    return i.get("type") or i.get("shape") or ""


def view_label(e) -> str:
    v = e._intent.get("view")
    if not v:
        return ""
    return VIEW_NAMES.get(v, f"{v} 向视图")


def ref_text(e) -> str:
    # a copied reference must stay one line even when a note / dimension text contains newlines
    parts = [" ".join(str(p).split()) for p in (label(e), view_label(e)) if p]
    return f"@{e.id}（{'，'.join(parts)}）" if parts else f"@{e.id}"


class Viewer:
    """Build state of one drawing directory, shared by the request threads."""

    def __init__(self, dir):
        self.dir = Path(dir).resolve()
        self.lock = threading.RLock()
        self.sig = None
        self.version = 0
        self.res = None
        self.svg = ""
        self.error = None
        self.preview = None  # {"values", "svg", "res", "timing_ms"}
        self.selection = []
        self.viewport = None
        self.preview_seq = -1
        self.param_errors = {}
        self.token = secrets.token_hex(16)  # per run; the served page carries it (SPEC §2 安全)
        self.retried = None
        self.refresh()
        # H3: the idle clock starts after the initial build, so a slow drawing is not born expired
        self.last_active = time.monotonic()

    # ---- build state ------------------------------------------------------------------------
    def _head(self):
        try:
            r = subprocess.run(
                ["git", "-C", str(self.dir), "log", "-1", "--format=%h%x00%s", "--"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5,
            )
            h, _, s = r.stdout.strip().partition("\0")
            return h, s
        except (OSError, subprocess.SubprocessError):
            return "", ""

    def _signature(self):
        m = []
        for p in (self.dir / SRC, self.dir / LOG):
            st = p.stat() if p.exists() else None
            m.append((st.st_mtime_ns, st.st_size) if st else None)
        return (*m, self._head()[0])

    def refresh(self, force=False):
        """Rebuild if the sources or HEAD changed. Keeps the last good build on failure."""
        with self.lock:
            sig = self._signature()
            if sig == self.sig and not force:
                return False
            self.sig = sig
            try:
                res = build(self.dir)
            except Exception as e:  # noqa: BLE001 - shown in the page, never kills the service
                self.error = (
                    e.to_dict()
                    if isinstance(e, LinerError)
                    else {"code": "internal", "message": f"{type(e).__name__}: {e}"}
                )
                if self.retried != sig:  # maybe a half-written file: try this version once more
                    self.retried, self.sig = sig, None
            else:
                self.res, self.svg, self.error = res, svgout.svg(res.d), None
                self.preview = None
                self.param_errors = {}
            self.version += 1
            self._write_snapshot()
            return True

    def _drawing_edit(self):
        """Latest eN commit that touched this drawing (the version selection.json records).

        The repository may have newer commits for other drawings; only git_edits(dir) knows the
        drawing's own eN, and lcad context validates against exactly that value.
        """
        from ..txn import git_edits

        edits = git_edits(self.dir)
        return f"e{edits[0][0]}" if edits else None

    def edit_no(self):
        h, s = self._head()
        m = re.match(r"(e\d+) · (.*)", s)
        return (m.group(1), m.group(2), h) if m else ("", s, h)

    def state(self):
        self.refresh()
        with self.lock:
            edit, msg, _ = self.edit_no()
            f = self._findings()
            errors = sum(1 for x in f if x.get("severity") == "error")
            warns = len(f) - errors
            status = " · ".join(
                p
                for p in (
                    edit,
                    f"{errors} 个错误" if errors else "",
                    f"{warns} 个警告",
                    f"“{msg}”" if msg else "",
                )
                if p
            )
            return {
                "ok": True,
                "version": self.version,
                "pid": os.getpid(),
                "dir": str(self.dir),
                "edit": edit,
                "status": status,
                "message": msg,
                "errors": errors,
                "warnings": warns,
                "build_error": self.error,
                "preview": bool(self.preview),
                "preview_seq": self.preview_seq,
                "param_errors": bool(self.param_errors),
            }

    def _current(self):
        return self.preview["res"] if self.preview else self.res

    def _findings(self):
        r = self._current()
        return list(r.findings) if r else []

    # ---- model summary --------------------------------------------------------------------------
    def model(self):
        with self.lock:
            r = self._current()
            if r is None:
                return {"ok": False, "error": self.error}
            issues = self._issues_by_element(r)
            out = []
            for e in r.d._els.values():
                if not e._prims and not (e.kind == "table.cell" and "cell_box" in e._resolved):
                    continue
                src = e.src
                link = None
                if src and src.get("file") == Path(SRC).name:
                    from urllib.parse import quote

                    link = f"vscode://file/{quote((self.dir / SRC).as_posix())}:{src['line']}"
                out.append(
                    {
                        "id": e.id,
                        "kind": e.kind,
                        "label": label(e),
                        "view": e._intent.get("view"),
                        "ref": ref_text(e),
                        "intent": _brief_intent(e),
                        "refs": e.refs,
                        "src": src,
                        "src_link": link,
                        "history": e.history,
                        "status": e.status,
                        "issues": issues.get(e.id, []),
                        "selector": svgout.selector(e),
                    }
                )
            errors = sum(1 for f in r.findings if f.get("severity") == "error")
            return {
                "ok": True,
                "version": self.version,
                "summary": {
                    "elements": len(out),
                    "errors": errors,
                    "warnings": len(r.findings) - errors,
                },
                "resolved": self._resolved(r),
                "unplaced": self._unplaced(r),
                "content_bbox": _content_bbox(r.d),
                "title_bbox": _title_bbox(r.d),
                "elements": out,
                "issues": [_finding(f) for f in r.findings],
            }

    def params(self):
        with self.lock:
            r = self.res
            if r is None:
                return {"ok": False, "error": self.error}
            P = r.d.P
            out = []
            for n in P.names():
                p = P[n].to_dict(n)
                p["default"] = p["value"]
                if self.preview and n in self.preview["values"]:
                    p["value"] = self.preview["values"][n]
                lo, hi = p.get("min"), p.get("max")
                base = p["default"]
                declared = lo is not None and hi is not None
                if not declared:
                    # fallback range: 0.5–1.5 × default, aligned to the step grid so the default
                    # value is reachable on the slider (Param(11) must not become 5.5–16.5 with step 1)
                    step = p.get("step")
                    if step is None:
                        step = 1 if abs(base) >= 10 else 0.1
                    if lo is None:
                        lo = math.floor((base * 0.5) / step) * step
                    if hi is None:
                        hi = math.ceil((base * 1.5) / step) * step
                    if not hi > lo:  # a default of 0 must still give a usable slider
                        lo, hi = base - 1, base + 1
                p["range"] = {"min": round(float(lo), 6), "max": round(float(hi), 6)}
                out.append(p)
            return {"ok": True, "params": out}

    # ---- selection / snapshot -----------------------------------------------------------------
    def select(self, ids):
        with self.lock:
            r = self._current()
            valid = []
            seen = set()
            for i in ids:
                if i in seen:
                    continue
                seen.add(i)
                e = r.d.get(i) if r else None
                if e is None:
                    continue
                valid.append(
                    {
                        "id": e.id,
                        "kind": e.kind,
                        "label": label(e),
                        "view": e._intent.get("view"),
                        "ref": ref_text(e),
                        "selector": svgout.selector(e),
                    }
                )
            total = len(valid)
            cap = _selection_cap()
            truncated = cap > 0 and total > cap
            items = valid[:cap] if truncated else valid
            kinds: dict[str, int] = {}
            for x in items:
                k = x["kind"]
                kinds[k] = kinds.get(k, 0) + 1
            self.selection = items
            doc = {
                "version": self._drawing_edit(),
                "ids": [x["id"] for x in items],
                "items": items,
                "count": len(items),
                "total": total,
                "truncated": truncated,
                "kinds": kinds,
                "time": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            _write_json(self.dir / ".linercad" / "selection.json", doc)
            self._write_snapshot()
            return {"ok": True, **doc}

    def set_viewport(self, vp):
        with self.lock:
            self.viewport = [float(x) for x in vp][:4]
            self._write_snapshot()
            return {"ok": True}

    def _write_snapshot(self):
        edit, _, h = self.edit_no()
        r = self._current()
        doc = {
            "version": edit,
            "commit": h,
            "selection": self.selection,
            "issues": [_finding(f) for f in (r.findings if r else [])],
            "viewport": self.viewport,
            "params": dict(self.preview["values"]) if self.preview else {},
            "param_errors": self.param_errors,
            "stale_ops": [
                {k: s.get(k) for k in ("edit", "op", "id", "reason")}
                for s in (r.stale if r else [])
            ],
            "build_error": self.error,
        }
        _write_json(self.dir / ".linercad" / "snapshot.json", doc)

    # ---- sliders ----------------------------------------------------------------------------------
    def do_preview(self, values, seq=None):
        t0 = time.perf_counter()
        with self.lock:
            if not values:  # a withdrawal always wins, even with a stale client seq (page reload)
                if seq is not None:
                    self.preview_seq = max(self.preview_seq, seq) + 1
                self.preview = None
                self.param_errors = {}
                self.version += 1
                self._write_snapshot()
                findings = [_finding(f) for f in (self.res.findings if self.res else [])]
                return {
                    "ok": True,
                    "version": self.version,
                    "findings": findings,
                    "affected": [],
                    "resolved": self._resolved(self.res) if self.res else {},
                    "element_issues": self._issues_by_element(self.res) if self.res else {},
                    "unplaced": self._unplaced(self.res) if self.res else [],
                }
            if seq is not None:
                if seq < self.preview_seq:  # an older drag arrived late
                    return {
                        "ok": False,
                        "superseded": True,
                        "error": {"code": "superseded", "message": ""},
                    }
                self.preview_seq = seq
            try:
                res = build(self.dir, params=values)
            except LinerError as e:
                info = e.to_dict()
                affected = self._affected_ids(info.get("id"))
                self.param_errors = {
                    "values": dict(values),
                    "error": info,
                    "affected": affected,
                }
                self._write_snapshot()
                return {"ok": False, "error": info, "affected": affected}
            self.param_errors = {}
            svg = svgout.svg(res.d)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            self.preview = {"values": dict(values), "svg": svg, "res": res, "timing_ms": ms}
            self.version += 1
            self._write_snapshot()
            stale = [{k: s.get(k) for k in ("edit", "op", "id", "reason")} for s in res.stale]
            return {
                "ok": True,
                "version": self.version,
                "timing_ms": ms,
                "findings": [_finding(f) for f in res.findings],
                "affected": [],
                "resolved": self._resolved(res),
                "element_issues": self._issues_by_element(res),
                "unplaced": self._unplaced(res),
                "stale_ops": stale,
            }

    def _affected_ids(self, name):
        """Drawn elements that cover parameter name: a param-rule error has no element finding,
        so the canvas marks the elements that display / depend on that parameter."""
        r = self.res
        if r is None or not name:
            return []
        return [e.id for e in r.d._els.values() if e._prims and name in (e._covers or [])]

    def _finding_targets(self, f, r):
        """Drawn element ids a finding stands for. A finding whose id is not drawn itself (a view
        such as V.top, or a parameter) is mapped to the elements that can be marked on the canvas."""
        eid = f.get("id")
        el = r.d._els.get(eid)
        if el is not None and (el._prims or "cell_box" in el._resolved):
            return [eid]
        if isinstance(eid, str) and eid.startswith("V."):
            view = eid[2:]
            return [e.id for e in r.d._els.values() if e._prims and e._intent.get("view") == view]
        if isinstance(eid, str) and eid.startswith("P."):
            name = eid[2:]
            return [e.id for e in r.d._els.values() if e._prims and name in (e._covers or [])]
        return []

    def _resolved(self, r):
        """element id → severity for findings whose own id is not a drawn element (canvas marks)."""
        out = {}
        if r is None:
            return out
        for f in r.findings:
            for eid in self._finding_targets(f, r):
                if eid == f.get("id"):
                    continue
                sev = f.get("severity") or "warn"
                if out.get(eid) != "error":
                    out[eid] = "error" if sev == "error" else "warn"
        return out

    def _issues_by_element(self, r):
        """element id → [finding] for the inspector: a view / parameter level finding is listed
        under the elements it is resolved to, so selecting one shows the E1 fields too."""
        out = {}
        if r is None:
            return out
        for f in r.findings:
            item = _finding(f)
            for eid in self._finding_targets(f, r) or [f.get("id")]:
                out.setdefault(eid, []).append(item)
        return out

    def _unplaced(self, r):
        """findings the canvas cannot mark (no drawn element: e.g. a parameter nothing displays);
        the inspector still lists them with the E1 fields."""
        if r is None:
            return []
        return [_finding(f) for f in r.findings if not self._finding_targets(f, r)]

    def writeback(self, name, value):
        from .. import txn
        from ..errors import DirtySource

        with self.lock:
            dirty = txn.dirty_sources(self.dir)
            if dirty:
                raise DirtySource(
                    f"源文件有未提交的改动：{', '.join(dirty)}；写回会把它们一起提交",
                    candidates=list(dirty),
                    hint="先让 Agent 提交（lcad build -m ...），再写回",
                )
            build(self.dir, params={name: value})  # rule / range checked before touching the file
            path = self.dir / SRC
            raw = path.read_bytes()
            new = rewrite_param(raw.decode("utf-8"), name, value)
            head = self._head()[0]
            path.write_bytes(new.encode("utf-8"))
            try:
                out = txn.build_commit(self.dir, f"参数 {name}={_num(value)}（Viewer 写回）")
            except Exception:
                if self._head()[0] == head:  # nothing committed: put the file back exactly
                    txn._unstage(self.dir)
                    path.write_bytes(raw)
                raise
            self.preview = None
            self.refresh(force=True)
            return out

    # ---- versions (M3 S2) -------------------------------------------------------------------------
    def versions(self):
        from .. import versions

        return {"ok": True, "versions": versions.log(self.dir)}

    def diff(self, a, b=None):
        """Overlay of two versions (``b`` empty = the working tree). Builds run under the viewer
        lock: ``redirect_stdout`` in the build pipeline is process-wide."""
        from .. import versions

        if not a:
            raise InvalidArgument("缺少版本 a", hint="/api/diff?a=e1&b=e2")
        with self.lock:
            summary, svg = versions.compare_revisions(self.dir, a, b or None)
        return {"ok": True, "summary": summary, "svg": svg}

    def current_svg(self):
        with self.lock:
            return self.preview["svg"] if self.preview else self.svg

    def download(self, fmt: str, preview: bool = False) -> tuple[bytes, str, str, str]:
        """Render DXF/PDF/PNG (or zip when DXF references external images) in a temp dir
        without touching git, drawing sources, or ``.linercad/build``.
        """
        fmt = (fmt or "").strip().lower()
        if fmt not in ("dxf", "pdf", "png"):
            raise InvalidArgument(
                f"不支持的下载格式 {fmt!r}",
                candidates=["dxf", "pdf", "png"],
                values={"fmt": fmt},
            )
        with self.lock:
            use_preview = bool(preview and self.preview)
            params = dict(self.preview["values"]) if use_preview else None
            try:
                res = build(self.dir, params=params, dxf=True)
            except LinerError as e:
                raise _DownloadBuildError(
                    e.message,
                    code=e.code,
                    id=e.id,
                    candidates=e.candidates,
                    values=e.values,
                    hint=e.hint,
                ) from e
            except Exception as e:  # noqa: BLE001
                raise _DownloadBuildError(f"{type(e).__name__}: {e}", code="build") from e

            no_el = res.d.get("T.title.drawing_no")
            raw_base = (
                no_el.text.strip()
                if no_el is not None and str(getattr(no_el, "text", "") or "").strip()
                else self.dir.name
            )
            base = _sanitize_filename(raw_base) or _sanitize_filename(self.dir.name) or "drawing"
            edit = self._drawing_edit() or self.edit_no()[0] or "e0"
            suffix = "-preview" if use_preview else ""

            tmpdir = Path(tempfile.mkdtemp(prefix="lcad-dl-"))
            try:
                if fmt == "dxf":
                    from .. import dxfout

                    dxf_path = tmpdir / "drawing.dxf"
                    dxfout.save_doc(res.doc, dxf_path)
                    imgs = _dxf_external_images(res.doc, self.dir)
                    if imgs:
                        zip_path = tmpdir / "bundle.zip"
                        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                            zf.write(dxf_path, "drawing.dxf")
                            for arc_rel, src_path in imgs:
                                zf.write(src_path, arc_rel)
                        return (
                            zip_path.read_bytes(),
                            "application/zip",
                            f"{base}-{edit}{suffix}.zip",
                            "zip",
                        )
                    return (
                        dxf_path.read_bytes(),
                        "application/dxf",
                        f"{base}-{edit}{suffix}.dxf",
                        "single",
                    )
                if fmt == "pdf":
                    from ..render import render_pdf

                    pdf_path = tmpdir / "drawing.pdf"
                    render_pdf(res.doc, res.d.template["size"], pdf_path)
                    return (
                        pdf_path.read_bytes(),
                        "application/pdf",
                        f"{base}-{edit}{suffix}.pdf",
                        "single",
                    )
                from ..render import render_png

                png_path = tmpdir / "drawing.png"
                render_png(res.doc, res.d.template["size"], png_path)
                return (
                    png_path.read_bytes(),
                    "image/png",
                    f"{base}-{edit}{suffix}.png",
                    "single",
                )
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)


class _DownloadBuildError(LinerError):
    code = "build"


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", str(name or "")).strip("._")


def _dxf_external_images(doc, base_dir: Path) -> list[tuple[str, Path]]:
    """Collect ``IMAGEDEF`` external image files relative to ``base_dir``."""
    out = []
    seen = set()
    base_resolved = base_dir.resolve()
    for idef in doc.objects.query("IMAGEDEF"):
        raw = str(getattr(idef.dxf, "filename", "") or "").strip()
        if not raw:
            continue
        rel_path = Path(raw)
        src = (base_dir / rel_path).resolve() if not rel_path.is_absolute() else rel_path.resolve()
        try:
            arc_rel = src.relative_to(base_resolved).as_posix()
        except ValueError as e:
            raise _DownloadBuildError(
                f"DXF 引用的外部图片不在图纸目录内：{raw}",
                code="build",
                values={"path": str(src)},
            ) from e
        if not src.is_file():
            raise _DownloadBuildError(
                f"DXF 引用的外部图片不存在：{raw}",
                code="build",
                values={"path": str(src)},
            )
        if arc_rel not in seen:
            seen.add(arc_rel)
            out.append((arc_rel, src))
    return out


def _content_bbox(d):
    """Union of the drawn elements' boxes (sheet coordinates) without the sheet frame and the
    title-block cells: what the initial view fits to. ``None`` for an empty drawing."""
    boxes = [
        e.bbox
        for e in d._els.values()
        if e._prims and e.bbox and e.kind not in ("frame", "table.cell")
    ]
    if not boxes:
        return None
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def _title_bbox(d):
    """The title block's box (sheet coordinates); the initial view keeps it in sight."""
    tb = d.template["title_block"]
    ox, oy = tb["origin"]
    return [ox, oy, ox + tb["size"][0], oy + tb["size"][1]]


def _num(v):
    v = float(v)
    return str(int(v)) if v.is_integer() else repr(v)


def rewrite_param(text: str, name: str, value) -> str:
    """Replace the literal default of ``name=Param(<literal>, ...)`` and nothing else."""
    from ..errors import ParamError

    tree = ast.parse(text)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == name and isinstance(node.value, ast.Call):
            call = node.value
            fn = call.func
            if (isinstance(fn, ast.Name) and fn.id == "Param") or (
                isinstance(fn, ast.Attribute) and fn.attr == "Param"
            ):
                hits.append(call)
    if len(hits) != 1:
        raise ParamError(f"drawing.py 里找不到唯一的 {name}=Param(...)（找到 {len(hits)} 个）")
    call = hits[0]
    if not call.args:
        raise ParamError(f"{name} 的默认值不是第一个位置参数，不能自动写回")
    lit = call.args[0]
    neg = (
        isinstance(lit, ast.UnaryOp)
        and isinstance(lit.op, ast.USub)
        and isinstance(lit.operand, ast.Constant)
    )
    if not (
        (
            isinstance(lit, ast.Constant)
            and isinstance(lit.value, (int, float))
            and not isinstance(lit.value, bool)
        )
        or neg
    ):
        raise ParamError(
            f"{name} 的默认值是表达式（{ast.unparse(lit)}），不能自动写回；请改 drawing.py",
            hint="Viewer 只改数字字面量",
        )
    lines = io.StringIO(text, newline="").readlines()  # same line breaks as ast
    if lit.lineno != lit.end_lineno:
        raise ParamError(f"{name} 的默认值跨行，不能自动写回")
    ln = lines[lit.lineno - 1]
    b = len(ln.encode("utf-8")[: lit.col_offset].decode("utf-8"))
    e = len(ln.encode("utf-8")[: lit.end_col_offset].decode("utf-8"))
    lines[lit.lineno - 1] = ln[:b] + _num(value) + ln[e:]
    return "".join(lines)


def _brief_intent(e):
    keep = (
        "type",
        "shape",
        "text",
        "value",
        "tol",
        "tolerance",
        "tol_show",
        "role",
        "datum",
        "char",
        "zone",
        "datums",
        "modifiers",
        "param",
        "removal",
        "process",
        "letter",
        "target",
        "ref",
        "spec",
        "designation",
        "r",
        "c",
        "p1",
        "p2",
        "measured",
        "expr",
        "table",
        "field",
        "label",
        "row",
        "col",
        "header",
        "title",
        "cols",
        "nrows",
        "ncols",
        "wrap",
        "text_height",
        "align",
        "bold",
        "border_width",
    )
    return {k: v for k, v in e.to_dict()["intent"].items() if k in keep}


#: fields of one check finding as the Viewer, the inspector and snapshot.json show them. E1 added
#: clause / measured / expected / candidates next to the old rule / id / severity / message.
FINDING_KEYS = (
    "rule",
    "id",
    "severity",
    "message",
    "clause",
    "measured",
    "expected",
    "candidates",
    "pack",
    "std",
)


def _finding(f) -> dict:
    """One finding with the fields of the E1 finding protocol (missing containers become empty)."""
    out = {k: f.get(k) for k in FINDING_KEYS}
    out["measured"] = dict(out["measured"] or {})
    out["expected"] = dict(out["expected"] or {})
    out["candidates"] = list(out["candidates"] or [])
    return out


def _write_json(path: Path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in range(5):  # Windows: a reader may hold the target open for a moment
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.05 * (k + 1))
    tmp.replace(path)


# ---- HTTP ------------------------------------------------------------------------------------------


def make_handler(viewer: Viewer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body: bytes, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(
                code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json"
            )

        def _send_file(self, body: bytes, ctype: str, filename: str, archive: str):
            ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "download"
            disp = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Disposition", disp)
            self.send_header("X-LCAD-Archive", archive)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            viewer.last_active = time.monotonic()
            path = self.path.split("?")[0]
            try:
                if not self._host_ok():
                    return self._json(
                        {"ok": False, "error": {"code": "forbidden", "message": "host"}}, 403
                    )
                if path in STATIC:
                    name, ctype = STATIC[path]
                    body = (resources.files(__package__) / name).read_bytes()
                    if name == "index.html":
                        body = body.replace(b"__LCAD_TOKEN__", viewer.token.encode())
                    return self._send(200, body, ctype)
                if path == "/svg":
                    svg = viewer.current_svg()
                    if not svg:
                        return self._json({"ok": False, "error": viewer.error}, 503)
                    return self._send(200, svg.encode("utf-8"), "image/svg+xml")
                if path == "/api/ping":  # H3 identity probe: lightweight, never rebuilds
                    return self._json({"ok": True, "pid": os.getpid(), "dir": str(viewer.dir)})
                if path == "/api/state":
                    return self._json(viewer.state())
                if path == "/api/model":
                    return self._json(viewer.model())
                if path == "/api/params":
                    return self._json(viewer.params())
                if path == "/api/download":
                    if not self._authorized():
                        return self._json(
                            {
                                "ok": False,
                                "error": {"code": "forbidden", "message": "origin / token"},
                            },
                            403,
                        )
                    q = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                    fmt = q.get("fmt", "")
                    prev_raw = q.get("preview")
                    if prev_raw not in (None, "", "0", "1"):
                        raise InvalidArgument(
                            f"preview 参数非法：{prev_raw!r}", values={"preview": prev_raw}
                        )
                    try:
                        body, ctype, fname, archive = viewer.download(
                            fmt, preview=(prev_raw == "1")
                        )
                    except _DownloadBuildError as e:
                        return self._json({"ok": False, "error": e.to_dict()}, 409)
                    return self._send_file(body, ctype, fname, archive)
                if path in ("/api/versions", "/api/diff"):  # git work: same guards as POST
                    if not self._authorized():
                        return self._json(
                            {
                                "ok": False,
                                "error": {"code": "forbidden", "message": "origin / token"},
                            },
                            403,
                        )
                    if path == "/api/versions":
                        return self._json(viewer.versions())
                    q = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                    return self._json(viewer.diff(q.get("a", ""), q.get("b", "")))
                self._json({"ok": False, "error": {"code": "not_found", "message": path}}, 404)
            except LinerError as e:
                self._json({"ok": False, "error": e.to_dict()}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"ok": False, "error": {"code": "internal", "message": str(e)}}, 500)

        def _host_ok(self):  # DNS rebinding: only our own loopback names
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _authorized(self):  # own Host + same Origin (when sent) + the per-run token
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            tok = self.headers.get("X-LCAD-Token", "")
            return (
                tok.isascii()
                and self._host_ok()
                and not (origin and origin.split("//", 1)[-1] != host)
                and secrets.compare_digest(tok, viewer.token)
            )

        def do_POST(self):  # noqa: N802
            viewer.last_active = time.monotonic()
            # same origin + per-run token: another local page cannot drive the service
            tok = self.headers.get("X-LCAD-Token", "")
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if not tok.isascii() or not 0 <= n <= 1_000_000:
                return self._json(
                    {"ok": False, "error": {"code": "bad_request", "message": "header"}}, 400
                )
            if not self._authorized():
                return self._json(
                    {"ok": False, "error": {"code": "forbidden", "message": "origin / token"}}, 403
                )
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self._json(
                    {"ok": False, "error": {"code": "bad_request", "message": "JSON only"}}, 415
                )
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
                path = self.path.split("?")[0]
                if path == "/api/select":
                    return self._json(viewer.select(list(body.get("ids", []))))
                if path == "/api/preview":
                    return self._json(
                        viewer.do_preview(dict(body.get("values") or {}), body.get("seq"))
                    )
                if path == "/api/writeback":
                    return self._json(viewer.writeback(body["name"], body["value"]))
                if path == "/api/view":
                    return self._json(viewer.set_viewport(body.get("viewport") or []))
                self._json({"ok": False, "error": {"code": "not_found", "message": path}}, 404)
            except LinerError as e:
                self._json({"ok": False, "error": e.to_dict()}, 400)
            except Exception as e:  # noqa: BLE001
                self._json(
                    {
                        "ok": False,
                        "error": {"code": "internal", "message": f"{type(e).__name__}: {e}"},
                    },
                    500,
                )

    return Handler


class _Server(ThreadingHTTPServer):
    """A taken port must fail, not be shared (Windows SO_REUSEADDR semantics)."""

    allow_reuse_address = False

    def server_bind(self):
        import socket

        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


# ---- H3: background Viewer lifecycle ---------------------------------------------------------------

STATE_PATH = Path(".linercad") / "viewer.json"
LOG_PATH = Path(".linercad") / "viewer.log"
DEFAULT_PORT = 8765
DEFAULT_SELECTION_CAP = 50
DEFAULT_IDLE_TIMEOUT = 1800.0  # seconds without a request before the background Viewer exits


def _selection_cap() -> int:
    """Maximum elements stored in selection.json (<=0 disables the cap, for tests)."""
    raw = os.environ.get("LCAD_SELECTION_CAP")
    if not raw:
        return DEFAULT_SELECTION_CAP
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_SELECTION_CAP


def _state_path(dir):
    return Path(dir) / STATE_PATH


def _log_path(dir):
    return Path(dir) / LOG_PATH


def _pid_alive(pid) -> bool:
    """Is the process still running? (the Windows branch also works for a detached child)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(
            SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            return bool(ok) and code.value == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    # a detached child that exited but was not reaped is a zombie: it is not a running Viewer
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        if stat.rsplit(")", 1)[1].split()[0] == "Z":
            return False
    except (OSError, IndexError):
        pass
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OSError):
        return False
    except PermissionError:
        return True
    return True


def _port_open(port) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.4):
            return True
    except OSError:
        return False


def _read_state(dir):
    try:
        doc = json.loads(_state_path(dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _clear_state(dir, pid=None):
    p = _state_path(dir)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None
    if pid is not None and doc is not None and doc.get("pid") != pid:
        return
    try:
        p.unlink()
    except OSError:
        pass


def _idle_timeout(value=None) -> float:
    """Seconds of inactivity after which the background Viewer exits."""
    if value is not None:
        return max(1.0, float(value))
    raw = os.environ.get("LCAD_VIEW_IDLE_TIMEOUT")
    if not raw:
        return DEFAULT_IDLE_TIMEOUT
    try:
        return max(1.0, float(raw))
    except ValueError:
        return DEFAULT_IDLE_TIMEOUT


def _suppressed(disabled=False, *, ensure=False) -> bool:
    """--no-view / --no-viewer, env switches and CI keep auto-start off; --ensure-viewer wins."""
    if disabled:
        return True
    if ensure:
        return False
    return bool(
        os.environ.get("LCAD_NO_VIEW") or os.environ.get("LCAD_NO_VIEWER") or os.environ.get("CI")
    )


def _viewer_identity(doc, dir):
    """Does this state document describe a live Viewer of *this* drawing?

    A stale pid/port can be reused by an unrelated process after a crash; ask the service who it is
    (any loopback HTTP service answers, but only a Liner-CAD Viewer for this dir has the pid + dir).
    """
    try:
        port = int(doc["port"])
        req = URLRequest(f"http://127.0.0.1:{port}/api/ping", headers={"Host": f"127.0.0.1:{port}"})
        with urlopen(req, timeout=0.6) as resp:  # noqa: S310 - loopback only
            st = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError, KeyError):
        return False
    try:
        return (
            st.get("ok") is True
            and int(st.get("pid", 0)) == int(doc.get("pid", -1))
            and Path(str(st.get("dir", ""))).resolve() == Path(dir).resolve()
        )
    except (TypeError, ValueError, OSError):
        return False


def _running(dir):
    """The state document of a live Viewer for this drawing, or None (stale files removed)."""
    doc = _read_state(dir)
    if not doc:
        return None
    try:
        pid, port = int(doc["pid"]), int(doc["port"])
    except (KeyError, TypeError, ValueError):
        _clear_state(dir)
        return None
    if _pid_alive(pid) and _port_open(port) and _viewer_identity(doc, dir):
        return doc
    _clear_state(dir, pid)
    return None


def _log_tail(dir, limit=400) -> str:
    try:
        data = _log_path(dir).read_bytes()[-limit:]
    except OSError:
        return ""
    return data.decode("utf-8", "replace").strip()


#: Popen objects of spawned viewers; polled so exited children are reaped (no zombies).
_CHILDREN = []
_CHILDREN_LOCK = threading.Lock()
_LOCK = ".linercad/viewer.lock"
_LOCK_WAIT = 30.0  # seconds one build may wait for another one's spawn decision
_START_TIMEOUT = 15.0  # seconds to wait for the child's state file (CI can be slow)


def _reap_children():
    with _CHILDREN_LOCK:
        for proc in list(_CHILDREN):
            if proc.poll() is not None:
                _CHILDREN.remove(proc)


def _kill_tree(pid):
    """Terminate the background child (and its process tree) after a startup timeout."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return
    if pid <= 0 or pid == os.getpid():
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
        return
    try:
        os.kill(pid, 15)
    except OSError:
        return
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and _pid_alive(pid):
        time.sleep(0.1)
    if _pid_alive(pid):
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def _lock_owner(path):
    """pid recorded in the lock file, or None when it cannot be read (mid-creation)."""
    try:
        return int(path.read_text(encoding="utf-8").strip() or 0) or None
    except (OSError, ValueError):
        return None


@contextlib.contextmanager
def _viewer_lock(dir):
    """A cross-process lock: only one build/edit may decide to spawn the background Viewer."""
    path = Path(dir) / _LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    deadline = time.monotonic() + _LOCK_WAIT
    while time.monotonic() < deadline:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            owner = _lock_owner(path)
            stale = False
            if owner is not None:
                stale = not _pid_alive(owner)  # only a dead owner's lock may be taken over
            else:
                try:  # the file exists but has no owner yet: a live owner may be writing it
                    stale = time.time() - path.stat().st_mtime > 300
                except OSError:
                    stale = False
            if stale:
                try:
                    path.unlink()
                except OSError:
                    pass
            time.sleep(0.05)
    if fd is None:
        raise TimeoutError("另一个 lcad 进程正在启动 Viewer，请稍后重试")
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        fd = None
        yield
    finally:
        if fd is not None:
            os.close(fd)
        owner = _lock_owner(path)
        if owner == os.getpid():  # never remove a lock a newer owner already took over
            try:
                path.unlink()
            except OSError:
                pass


def autostart(dir, disabled=False, open_browser=None, *, ensure=False):
    """After a successful build / edit: make sure a Viewer runs and open it once.

    Returns ``{"url", "pid", "started", "opened", "reused"}``; None when suppressed.
    ``ensure=True`` (--ensure-viewer) overrides ``LCAD_NO_VIEW`` / ``LCAD_NO_VIEWER`` / ``CI`` and
    keeps browser auto-open off by default. An already running Viewer is reused without a new tab.
    """
    if open_browser is None:
        open_browser = not ensure
    if _suppressed(disabled, ensure=ensure):
        return None
    dir = Path(dir).resolve()  # --dir and the child cwd must agree for lcad -C <relative>
    _reap_children()
    try:
        with _viewer_lock(dir):
            running = _running(dir)
            if running is not None:
                return {
                    "url": running["url"],
                    "pid": int(running["pid"]),
                    "started": running.get("started"),
                    "opened": False,
                    "reused": True,
                }
            log = _log_path(dir)
            log.parent.mkdir(parents=True, exist_ok=True)
            args = [
                sys.executable,
                "-m",
                "linercad.viewer",
                "--background",
                "--dir",
                str(dir),
                "--port",
                "0",
                "--idle-timeout",
                str(_idle_timeout()),
            ]
            kwargs = dict(
                stdin=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                cwd=str(dir),
                close_fds=True,
            )
            if os.name == "nt":
                kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                )
            else:
                kwargs["start_new_session"] = True
            with open(log, "ab") as handle:
                proc = subprocess.Popen(args, stdout=handle, **kwargs)
            with _CHILDREN_LOCK:
                _CHILDREN.append(proc)
            # the Windows venv launcher may exit after starting the real interpreter, so accept
            # the state file written by the child (any live pid + open port)
            state = None
            deadline = time.monotonic() + _START_TIMEOUT
            while time.monotonic() < deadline:
                candidate = _read_state(dir)
                if (
                    candidate
                    and candidate.get("pid")
                    and candidate.get("port")
                    and _pid_alive(candidate["pid"])
                    and _port_open(candidate["port"])
                ):
                    state = candidate
                    break
                time.sleep(0.05)
            if not state or not state.get("port"):
                # do not leave a half-started child behind (it may bind later and become an
                # unregistered viewer); kill the tree and any state it managed to publish
                _kill_tree(proc.pid)
                late = _read_state(dir)
                if late and late.get("pid"):
                    _kill_tree(late["pid"])
                _clear_state(dir)
                return {
                    "url": None,
                    "opened": False,
                    "error": _log_tail(dir) or "Viewer 后台进程启动失败",
                }
            url = state["url"]
    except Exception as e:  # noqa: BLE001 - a Viewer failure must not fail the build/edit
        return {"url": None, "opened": False, "error": f"{type(e).__name__}: {e}"}
    opened = False
    if open_browser:
        try:
            import webbrowser

            opened = bool(webbrowser.open(url))
        except Exception:  # noqa: BLE001 - no browser is a supported degradation
            opened = False
    return {
        "url": url,
        "pid": int(state["pid"]),
        "started": state.get("started"),
        "opened": opened,
        "reused": False,
    }


def _serve_until_idle(httpd, v, idle_timeout):
    """Serve one request at a time and exit after idle_timeout seconds without any request."""
    httpd.timeout = min(1.0, max(idle_timeout / 4, 0.05))
    while True:
        httpd.handle_request()
        if time.monotonic() - v.last_active > idle_timeout:
            return


def _is_addr_in_use(err: OSError) -> bool:
    """Detect port-in-use errors cross-platform (Windows SO_EXCLUSIVEADDRUSE may raise 10013)."""
    return err.errno in (errno.EADDRINUSE, 10048, 98, 48) or getattr(err, "winerror", None) in (
        10048,
        10013,
    )


def _start_server(dir, port, *, allow_fallback=False):
    """Bind the Viewer server and publish its state; the caller owns the lock/idle loop."""
    target = int(port)
    if not 0 <= target <= 65535:
        raise InvalidArgument(f"端口号 {target} 超出范围（0..65535）", values={"port": target})
    v = Viewer(dir)
    v.last_active = time.monotonic()  # the idle clock starts when the service is ready
    handler = make_handler(v)
    try:
        httpd = _Server(("127.0.0.1", target), handler)
    except OSError as e:
        if allow_fallback and target != 0 and _is_addr_in_use(e):
            try:
                httpd = _Server(("127.0.0.1", 0), handler)
            except OSError as e2:
                raise LinerError(
                    f"无法绑定端口（默认 {target} 被占用且自动回退失败）：{e2}",
                    code="viewer_bind",
                    values={"port": target},
                ) from e2
        else:
            raise LinerError(
                f"无法绑定端口 127.0.0.1:{target}：{e}",
                code="viewer_bind",
                values={"port": target},
                hint="改用其他 --port 或省略 --port 自动分配空闲端口",
            ) from e
    actual_port = int(httpd.server_address[1])
    url = f"http://127.0.0.1:{actual_port}/"
    _write_json(
        _state_path(dir),
        {
            "pid": os.getpid(),
            "port": actual_port,
            "url": url,
            "started": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )
    return v, httpd, url


def _open(url):
    try:
        import webbrowser

        return bool(webbrowser.open(url))
    except Exception:  # noqa: BLE001 - no browser is a supported degradation
        return False


def serve(dir, port=None, open_browser=True, idle_timeout=None, background=False):
    """Start the Viewer on 127.0.0.1:<port> (blocks). Writes .linercad/viewer.json for H3.

    When ``port`` is omitted (``None``) and not ``background``, binds ``DEFAULT_PORT`` (8765) and
    falls back once to port 0 if occupied. An explicit ``--port`` fails with ``viewer_bind``.
    """
    dir = Path(dir).resolve()
    allow_fallback = (port is None) and not background
    target = DEFAULT_PORT if port is None else int(port)
    if background:
        v, httpd, url = _start_server(dir, target)
    else:
        with _viewer_lock(dir):
            existing = _running(dir)
            if existing is not None and int(existing.get("pid", 0)) != os.getpid():
                # another Viewer already serves this drawing: report it instead of writing a
                # state file that would orphan the running process (lcad view + auto-open)
                print(
                    json.dumps(
                        {"ok": True, "url": existing["url"], "dir": str(dir), "existing": True},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if open_browser:
                    _open(existing["url"])
                return
            v, httpd, url = _start_server(dir, target, allow_fallback=allow_fallback)
    print(json.dumps({"ok": True, "url": url, "dir": str(v.dir)}, ensure_ascii=False), flush=True)
    if open_browser:
        _open(url)
    try:
        if idle_timeout:
            _serve_until_idle(httpd, v, float(idle_timeout))
        else:
            httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        _clear_state(dir, os.getpid())
