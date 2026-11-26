"""H3: the first successful build / edit starts the background Viewer (and only once).

The JSON of lcad build / lcad edit carries viewer: {url, opened}; a running Viewer is reused
without opening a new tab; the background process exits when idle and removes its state file.
"""

from __future__ import annotations

import errno
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from linercad import cli, txn, viewer


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "d"
    txn.init(p)
    return p


def _kill(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        os.kill(pid, 9)


def test_build_json_reports_the_background_viewer(repo, monkeypatch, capsys):
    calls = []

    def fake(dir, disabled=False, open_browser=True):
        calls.append((Path(dir), disabled, open_browser))
        return {"url": "http://127.0.0.1:8765/", "opened": True}

    monkeypatch.setattr(viewer, "autostart", fake)
    code = cli.main(["-C", str(repo), "build"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"]
    assert out["viewer"] == {"url": "http://127.0.0.1:8765/", "opened": True}
    assert calls == [(repo, False, True)]

    # --no-view turns it off: the CLI must pass disabled=True and leave the key out
    def disabled_fake(dir, disabled=False, open_browser=True):
        calls.append((Path(dir), disabled, open_browser))
        return None if disabled else {"url": "http://127.0.0.1:8765/", "opened": True}

    monkeypatch.setattr(viewer, "autostart", disabled_fake)
    code = cli.main(["-C", str(repo), "build", "--no-view"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] and "viewer" not in out
    assert calls[-1][1] is True


def test_edit_json_reports_the_background_viewer(repo, monkeypatch, capsys):
    s = repo / ".linercad" / "tmp" / "h3.py"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text('def apply(d):\n    d.notes.tech("H3")\n', encoding="utf-8")
    monkeypatch.setattr(
        viewer, "autostart", lambda *a, **k: {"url": "http://127.0.0.1:1/", "opened": False}
    )
    code = cli.main(["-C", str(repo), "edit", str(s), "-m", "加技术要求"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["viewer"] == {"url": "http://127.0.0.1:1/", "opened": False}


def test_autostart_failure_does_not_fail_the_build(repo, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("no process for you")

    monkeypatch.setattr(viewer, "autostart", boom)
    code = cli.main(["-C", str(repo), "build"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"]  # the transaction succeeded; the Viewer is a side effect
    assert out["viewer"]["url"] is None and out["viewer"]["opened"] is False
    assert "no process for you" in out["viewer"]["error"]


def test_autostart_is_off_by_default(repo, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("LCAD_NO_VIEW", "1")
    assert viewer.autostart(repo, open_browser=False) is None
    monkeypatch.delenv("LCAD_NO_VIEW")
    monkeypatch.setenv("CI", "true")
    assert viewer.autostart(repo, open_browser=False) is None
    monkeypatch.delenv("CI")
    assert viewer.autostart(repo, disabled=True, open_browser=False) is None
    assert not (repo / ".linercad" / "viewer.json").exists()


def test_autostart_spawns_reuses_opens_once_and_exits_idle(repo, monkeypatch):
    monkeypatch.delenv("LCAD_NO_VIEW", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("LCAD_VIEW_IDLE_TIMEOUT", "3")
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    state = repo / ".linercad" / "viewer.json"
    pid = None
    monkeypatch.chdir(repo.parent)  # lcad -C <relative> must still start the Viewer
    try:
        first = viewer.autostart(Path("d"))
        assert first["url"].startswith("http://127.0.0.1:") and first["opened"] is True
        doc = json.loads(state.read_text(encoding="utf-8"))
        pid = doc["pid"]
        assert doc["port"] > 0 and viewer._pid_alive(pid) and viewer._port_open(doc["port"])

        second = viewer.autostart(Path("d"))  # already running: refresh only, no new tab
        assert second["url"] == first["url"] and second["opened"] is False
        assert json.loads(state.read_text(encoding="utf-8"))["pid"] == pid
        assert opened == [first["url"]]
    finally:
        deadline = time.monotonic() + 30
        while pid and time.monotonic() < deadline and viewer._pid_alive(pid):
            time.sleep(0.2)
        if pid and viewer._pid_alive(pid):
            _kill(pid)
    # idle timeout: the background process exits and removes its state file
    assert not viewer._pid_alive(pid)
    assert not state.exists()


def _stop(state_file):
    try:
        pid = json.loads(state_file.read_text(encoding="utf-8"))["pid"]
    except (OSError, ValueError, KeyError):
        return
    if viewer._pid_alive(pid):
        _kill(pid)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and viewer._pid_alive(pid):
        time.sleep(0.1)


def test_serve_reuses_an_already_running_viewer(repo, monkeypatch):
    monkeypatch.delenv("LCAD_NO_VIEW", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("LCAD_VIEW_IDLE_TIMEOUT", "20")
    state = repo / ".linercad" / "viewer.json"
    try:
        first = viewer.autostart(repo, open_browser=False)
        assert first.get("url"), first
        pid = json.loads(state.read_text(encoding="utf-8"))["pid"]
        opened = []
        monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
        viewer.serve(repo)  # `lcad view` while it already runs: report it, open it, no 2nd server
        assert opened == [first["url"]]  # the explicit command reopens the browser
        assert json.loads(state.read_text(encoding="utf-8"))["pid"] == pid  # not overwritten
    finally:
        _stop(state)


def test_concurrent_autostart_starts_one_viewer(repo, monkeypatch):
    import threading

    monkeypatch.delenv("LCAD_NO_VIEW", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("LCAD_VIEW_IDLE_TIMEOUT", "10")
    state = repo / ".linercad" / "viewer.json"
    results, errors = [], []
    try:

        def call():
            try:
                results.append(viewer.autostart(repo, open_browser=False))
            except Exception as e:  # noqa: BLE001 - reported below
                errors.append(e)

        threads = [threading.Thread(target=call) for _ in range(3)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(30)
        assert not errors, errors
        assert all(not th.is_alive() for th in threads), "an autostart call hung"
        assert len(results) == 3 and all(r and r.get("url") for r in results), results
        assert len({r["url"] for r in results}) == 1  # one viewer, the others reuse it
        doc = json.loads(state.read_text(encoding="utf-8"))
        assert doc["pid"] > 0 and viewer._pid_alive(doc["pid"])
        assert len(viewer._CHILDREN) == 1, "the lock must allow exactly one spawned viewer"
    finally:
        _stop(state)


def test_active_lock_is_not_stolen(repo, monkeypatch):
    lock = repo / ".linercad" / "viewer.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()), encoding="utf-8")  # a live owner
    monkeypatch.setattr(viewer, "_LOCK_WAIT", 0.2)
    try:
        with pytest.raises(TimeoutError):
            with viewer._viewer_lock(repo):
                pass
        assert lock.exists()  # a live lock must never be removed by a waiter
    finally:
        lock.unlink(missing_ok=True)


def test_startup_timeout_kills_the_half_started_child(repo, monkeypatch):
    monkeypatch.delenv("LCAD_NO_VIEW", raising=False)
    monkeypatch.delenv("CI", raising=False)

    class FakeProc:
        pid = 424242

        def poll(self):
            return None

    killed = []
    monkeypatch.setattr(viewer, "_kill_tree", lambda pid: killed.append(pid))
    monkeypatch.setattr(viewer, "_START_TIMEOUT", 0.2)
    monkeypatch.setattr(viewer.subprocess, "Popen", lambda *a, **k: FakeProc())
    try:
        res = viewer.autostart(repo, open_browser=False)
        assert res["url"] is None and res["opened"] is False
        assert killed == [424242], killed  # the orphan-to-be is terminated
    finally:
        viewer._CHILDREN.clear()  # drop the fake process from the shared reaper list


def test_identity_probe_rejects_a_foreign_service(repo, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):  # noqa: N802
            body = json.dumps({"ok": True, "pid": os.getpid(), "dir": "elsewhere"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state = repo / ".linercad" / "viewer.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "port": httpd.server_address[1],
                "url": f"http://127.0.0.1:{httpd.server_address[1]}/",
            }
        ),
        encoding="utf-8",
    )
    try:
        assert viewer._running(repo) is None  # foreign service: not our Viewer
        assert not state.exists()
    finally:
        httpd.shutdown()


def test_cli_survives_a_viewer_import_failure(repo, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "linercad.viewer", None)
    code = cli.main(["-C", str(repo), "build"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"]
    assert out["viewer"]["url"] is None and "halted" in out["viewer"]["error"]


# ---- v0.1.3 PR-1 R1/R2: --ensure-viewer / --no-viewer precedence & port fallback ------------------


def test_ensure_viewer_overrides_env_and_ci_without_opening_browser(repo, monkeypatch, capsys):
    monkeypatch.setenv("LCAD_NO_VIEW", "1")
    monkeypatch.setenv("LCAD_NO_VIEWER", "1")
    monkeypatch.setenv("CI", "1")
    monkeypatch.setenv("LCAD_VIEW_IDLE_TIMEOUT", "15")
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    state = repo / ".linercad" / "viewer.json"
    try:
        code = cli.main(["-C", str(repo), "build", "--ensure-viewer"])
        out = json.loads(capsys.readouterr().out)
        assert code == 0 and out["ok"]
        v = out["viewer"]
        assert v["url"].startswith("http://127.0.0.1:")
        assert isinstance(v["pid"], int) and v["pid"] > 0
        assert isinstance(v["started"], str) and v["started"]
        assert v["opened"] is False
        assert v["reused"] is False
        assert opened == []
        assert state.is_file()

        script = repo / ".linercad" / "tmp" / "r1.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text('def apply(d):\n    d.notes.tech("R1")\n', encoding="utf-8")
        code2 = cli.main(
            ["-C", str(repo), "edit", str(script), "-m", "R1 ensure", "--ensure-viewer"]
        )
        out2 = json.loads(capsys.readouterr().out)
        assert code2 == 0 and out2["ok"]
        v2 = out2["viewer"]
        assert v2["url"] == v["url"]
        assert v2["pid"] == v["pid"]
        assert v2["opened"] is False
        assert v2["reused"] is True
        assert opened == []
    finally:
        _stop(state)


def test_no_viewer_flag_and_env_suppress_and_reject_conflict(repo, monkeypatch, capsys):
    monkeypatch.delenv("LCAD_NO_VIEW", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("LCAD_NO_VIEWER", raising=False)
    state = repo / ".linercad" / "viewer.json"

    code = cli.main(["-C", str(repo), "build", "--no-viewer"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] and "viewer" not in out
    assert not state.exists()

    monkeypatch.setenv("LCAD_NO_VIEWER", "1")
    code = cli.main(["-C", str(repo), "build"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] and "viewer" not in out
    assert not state.exists()

    script = repo / ".linercad" / "tmp" / "conflict.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text('def apply(d):\n    d.notes.tech("conflict")\n', encoding="utf-8")
    for args in (
        ["-C", str(repo), "build", "--ensure-viewer", "--no-viewer"],
        ["-C", str(repo), "build", "--ensure-viewer", "--no-view"],
        ["-C", str(repo), "edit", str(script), "-m", "conflict", "--ensure-viewer", "--no-viewer"],
    ):
        code = cli.main(args)
        err = json.loads(capsys.readouterr().out)
        assert code == 2 and not err["ok"] and err["error"]["code"] == "usage"
    assert not state.exists()


def test_view_default_port_falls_back_when_occupied(repo, monkeypatch, capsys):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    occupied = sock.getsockname()[1]
    monkeypatch.setattr(viewer, "DEFAULT_PORT", occupied)
    state = repo / ".linercad" / "viewer.json"

    seen_calls = []
    monkeypatch.setattr(
        viewer,
        "serve",
        lambda d, port=None, open_browser=True, **kw: seen_calls.append((d, port, open_browser)),
    )
    assert cli.main(["-C", str(repo), "view", "--no-open"]) == 0
    assert seen_calls[-1][1] is None  # CLI leaves default port as sentinel None

    monkeypatch.undo()
    monkeypatch.setattr(viewer, "DEFAULT_PORT", occupied)
    err_box = []
    th = threading.Thread(
        target=lambda: _run_serve(repo, None, 1.0, err_box),
        daemon=True,
    )
    try:
        th.start()
        deadline = time.monotonic() + 10
        doc = None
        while time.monotonic() < deadline:
            if state.is_file():
                try:
                    doc = json.loads(state.read_text(encoding="utf-8"))
                    if doc.get("port") and viewer._port_open(doc["port"]):
                        break
                except (OSError, ValueError):
                    pass
            time.sleep(0.05)
        assert not err_box, err_box
        assert doc is not None and doc["port"] != occupied and doc["port"] > 0
        assert doc["url"] == f"http://127.0.0.1:{doc['port']}/"
        with urllib.request.urlopen(doc["url"] + "api/ping", timeout=2) as resp:
            assert resp.status == 200 and json.loads(resp.read())["ok"] is True
        capsys.readouterr()
    finally:
        sock.close()
        th.join(5)


def _run_serve(repo, port, idle_timeout, err_box):
    try:
        viewer.serve(repo, port=port, open_browser=False, idle_timeout=idle_timeout)
    except Exception as e:  # noqa: BLE001
        err_box.append(e)


def test_view_explicit_occupied_port_and_retry_failure_report_error(repo, monkeypatch, capsys):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    occupied = sock.getsockname()[1]
    try:
        code = cli.main(["-C", str(repo), "view", "--port", str(occupied), "--no-open"])
        out = json.loads(capsys.readouterr().out)
        assert code == 1 and not out["ok"] and out["error"]["code"] == "viewer_bind"
        assert not (repo / ".linercad" / "viewer.json").exists()
    finally:
        sock.close()

    def always_in_use(*a, **k):
        raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr(viewer, "_Server", always_in_use)
    code = cli.main(["-C", str(repo), "view", "--no-open"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1 and not out["ok"] and out["error"]["code"] == "viewer_bind"
