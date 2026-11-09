"""Viewer v0 (M2 SPEC §2): a tiny local HTTP service (standard library only, bound to
127.0.0.1) plus a static page. The page polls ``/api/state``; the service rebuilds when
``drawing.py``, the action log or git HEAD change. Selection and snapshot are written to
``.linercad/selection.json`` / ``snapshot.json`` for agents (``lcad context @sel``)."""

from __future__ import annotations

import ast
import io
import json
import re
import secrets
import subprocess
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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
    return i.get("type") or i.get("shape") or ""


def view_label(e) -> str:
    v = e._intent.get("view")
    if not v:
        return ""
    return VIEW_NAMES.get(v, f"{v} 向视图")


def ref_text(e) -> str:
    parts = [p for p in (label(e), view_label(e)) if p]
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
            self.version += 1
            self._write_snapshot()
            return True

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
                "edit": edit,
                "status": status,
                "errors": errors,
                "warnings": warns,
                "build_error": self.error,
                "preview": bool(self.preview),
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
            issues = {}
            for f in r.findings:
                issues.setdefault(f.get("id"), []).append(
                    {k: f.get(k) for k in ("rule", "pack", "severity", "message", "std")}
                )
            out = []
            for e in r.d._els.values():
                if not e._prims:
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
            return {
                "ok": True,
                "version": self.version,
                "content_bbox": _content_bbox(r.d),
                "title_bbox": _title_bbox(r.d),
                "elements": out,
                "issues": [
                    {k: f.get(k) for k in ("rule", "id", "severity", "message")} for f in r.findings
                ],
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
                out.append(p)
            return {"ok": True, "params": out}

    # ---- selection / snapshot -----------------------------------------------------------------
    def select(self, ids):
        with self.lock:
            r = self._current()
            items = []
            for i in ids:
                e = r.d.get(i) if r else None
                if e is None:
                    continue
                items.append(
                    {
                        "id": e.id,
                        "kind": e.kind,
                        "label": label(e),
                        "view": e._intent.get("view"),
                        "ref": ref_text(e),
                        "selector": svgout.selector(e),
                    }
                )
            self.selection = items
            edit, _, _ = self.edit_no()
            doc = {
                "version": edit,
                "ids": [x["id"] for x in items],
                "items": items,
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
            "issues": [
                {k: f.get(k) for k in ("rule", "id", "severity", "message")}
                for f in (r.findings if r else [])
            ],
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
            if seq is not None:
                if seq < self.preview_seq:  # an older drag arrived late
                    return {
                        "ok": False,
                        "superseded": True,
                        "error": {"code": "superseded", "message": ""},
                    }
                self.preview_seq = seq
            if not values:
                self.preview = None
                self.version += 1
                self._write_snapshot()
                return {"ok": True, "version": self.version}
            try:
                res = build(self.dir, params=values)
            except LinerError as e:
                self.param_errors = {"values": dict(values), "error": e.to_dict()}
                self._write_snapshot()
                return {"ok": False, "error": e.to_dict()}
            self.param_errors = {}
            svg = svgout.svg(res.d)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            self.preview = {"values": dict(values), "svg": svg, "res": res, "timing_ms": ms}
            self.version += 1
            self._write_snapshot()
            stale = [{k: s.get(k) for k in ("edit", "op", "id", "reason")} for s in res.stale]
            return {"ok": True, "version": self.version, "timing_ms": ms, "stale_ops": stale}

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
    )
    return {k: v for k, v in e.to_dict()["intent"].items() if k in keep}


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

        def do_GET(self):  # noqa: N802
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
                if path == "/api/state":
                    return self._json(viewer.state())
                if path == "/api/model":
                    return self._json(viewer.model())
                if path == "/api/params":
                    return self._json(viewer.params())
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


def serve(dir, port=8765, open_browser=True):
    """Start the Viewer on 127.0.0.1:<port> (blocks). Returns after Ctrl+C."""
    v = Viewer(dir)
    httpd = _Server(("127.0.0.1", int(port)), make_handler(v))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(json.dumps({"ok": True, "url": url, "dir": str(v.dir)}, ensure_ascii=False), flush=True)
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
