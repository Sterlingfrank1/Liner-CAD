"""H3: the first successful build / edit starts the background Viewer (and only once).

The JSON of lcad build / lcad edit carries viewer: {url, opened}; a running Viewer is reused
without opening a new tab; the background process exits when idle and removes its state file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
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
        code = f"from linercad.viewer import serve; serve({str(repo)!r})"
        run = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
        )
        assert run.returncode == 0, run.stderr
        payload = json.loads([ln for ln in run.stdout.splitlines() if ln.strip()][-1])
        assert payload.get("existing") is True and payload["url"] == first["url"]
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
        urls = {r["url"] for r in results if r and r.get("url")}
        assert len(urls) == 1  # the lock makes one viewer, the others reuse it
        assert json.loads(state.read_text(encoding="utf-8"))["pid"] > 0
    finally:
        _stop(state)
