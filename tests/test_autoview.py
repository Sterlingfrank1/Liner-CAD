"""H3: the first successful build / edit starts the background Viewer (and only once).

The JSON of lcad build / lcad edit carries viewer: {url, opened}; a running Viewer is reused
without opening a new tab; the background process exits when idle and removes its state file.
"""

from __future__ import annotations

import json
import os
import subprocess
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

    # --no-view turns it off and leaves the key out of the JSON
    monkeypatch.setattr(viewer, "autostart", lambda *a, **k: None)
    code = cli.main(["-C", str(repo), "build", "--no-view"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["ok"] and "viewer" not in out


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
    try:
        first = viewer.autostart(repo)
        assert first["url"].startswith("http://127.0.0.1:") and first["opened"] is True
        doc = json.loads(state.read_text(encoding="utf-8"))
        pid = doc["pid"]
        assert doc["port"] > 0 and viewer._pid_alive(pid) and viewer._port_open(doc["port"])

        second = viewer.autostart(repo)  # already running: refresh only, no new tab
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
