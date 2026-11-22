"""H1: lcad edit --dry-run — execute the script, check and preview, but write nothing."""

import json
import os
import subprocess
import sys

import pytest

from linercad import txn


@pytest.fixture
def shaft(tmp_path):
    p = tmp_path / "s"
    txn.init(p, from_="shaft")
    return p


E1 = ("rule", "id", "message", "severity", "measured", "expected", "candidates", "clause")


def cli(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(
        [sys.executable, "-m", "linercad", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=cwd,
    )
    try:
        return r.returncode, json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"stdout={r.stdout!r} stderr={r.stderr!r}") from e


def repo_state(d):
    head = subprocess.run(
        ["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(d), "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    log = (d / "drawing.actions.jsonl").read_bytes()
    src = (d / "drawing.py").read_bytes()
    return head, status, log, src


def write_script(d, body, name="t.py"):
    p = d / ".linercad" / "tmp" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("def apply(d):\n" + body, encoding="utf-8")
    return p


def test_dry_run_writes_nothing_and_reports_change_findings_preview(shaft):
    before = repo_state(shaft)
    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    code, out = cli("-C", str(shaft), "edit", str(script), "-m", "试改", "--dry-run")
    assert code == 0 and out["ok"] and out["dry_run"] is True
    assert out["commit"] is None and out["edit"] == "e1"
    assert "D.L" in out["changed"]
    assert out["preview"].endswith(".png")
    png = shaft / out["preview"]
    assert png.is_file() and png.stat().st_size > 0  # rendered preview for the agent to look at
    dxf = shaft / out["preview_dxf"]
    assert dxf.is_file() and dxf.stat().st_size > 0
    assert out["warnings"], out
    for finding in out["warnings"]:
        assert all(k in finding for k in E1), finding
    assert repo_state(shaft) == before  # HEAD / status / log / drawing.py untouched


def test_dry_run_then_real_edit_report_is_consistent(shaft):
    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    code, dry = cli("-C", str(shaft), "edit", str(script), "-m", "试改", "--dry-run")
    assert code == 0 and dry["ok"]
    code, real = cli("-C", str(shaft), "edit", str(script), "-m", "试改")
    assert code == 0 and real["ok"] and real["commit"]
    assert dry["edit"] == real["edit"]
    for key in ("changed", "errors", "ops"):
        assert dry[key] == real[key], key
    assert [(w["rule"], w["id"], w["message"]) for w in dry["warnings"]] == [
        (w["rule"], w["id"], w["message"]) for w in real["warnings"]
    ]


def test_dry_run_failure_has_the_same_structure_as_edit(shaft):
    broken = write_script(shaft, '    raise RuntimeError("boom")\n')
    before = repo_state(shaft)
    code, dry = cli("-C", str(shaft), "edit", str(broken), "-m", "试改", "--dry-run")
    assert code == 1 and not dry["ok"] and dry["rolled_back"] is True
    assert dry["error"]["code"] == "script"
    assert repo_state(shaft) == before
    code, real = cli("-C", str(shaft), "edit", str(broken), "-m", "试改")
    assert code == 1 and not real["ok"]
    assert real["error"]["code"] == dry["error"]["code"]
    assert real["error"]["message"] == dry["error"]["message"]
    assert real["rolled_back"] is True


def test_dry_run_stale_op_failure_matches_edit(shaft, monkeypatch):
    from linercad.errors import StaleOp

    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    real_build = txn.build

    def stale_build(*args, **kwargs):
        if kwargs.get("current_edit"):
            raise StaleOp("本次修改的 raw 操作无法应用：模拟", id="D.L")
        return real_build(*args, **kwargs)

    monkeypatch.setattr(txn, "build", stale_build)
    before = repo_state(shaft)
    with pytest.raises(StaleOp) as dry_err:
        txn.edit(shaft, script, "试改", dry_run=True)
    assert dry_err.value.code == "stale"
    assert repo_state(shaft) == before  # a failed dry run writes nothing either
    with pytest.raises(StaleOp) as real_err:
        txn.edit(shaft, script, "试改")
    assert real_err.value.code == dry_err.value.code
    assert real_err.value.message == dry_err.value.message


def test_dry_run_no_ops_matches_edit(shaft):
    script = write_script(shaft, "    pass\n")
    before = repo_state(shaft)
    code, dry = cli("-C", str(shaft), "edit", str(script), "-m", "试改", "--dry-run")
    assert code == 1 and dry["error"]["code"] == "no_ops"
    assert repo_state(shaft) == before
    code, real = cli("-C", str(shaft), "edit", str(script), "-m", "试改")
    assert real["error"]["code"] == "no_ops"


def test_dry_run_python_api(shaft):
    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    before = repo_state(shaft)
    out = txn.edit(shaft, script, "试改", dry_run=True)
    assert out["ok"] and out["dry_run"] is True and out["commit"] is None
    assert repo_state(shaft) == before


def test_dry_run_does_not_start_the_viewer(shaft, monkeypatch):
    monkeypatch.delenv("LCAD_NO_VIEW", raising=False)
    monkeypatch.delenv("CI", raising=False)
    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    code, out = cli("-C", str(shaft), "edit", str(script), "-m", "试改", "--dry-run")
    assert code == 0 and out["ok"]
    assert not (shaft / ".linercad" / "viewer.json").exists()


def test_dry_run_without_a_message_is_allowed(shaft):
    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    code, out = cli("-C", str(shaft), "edit", str(script), "--dry-run")
    assert code == 0 and out["ok"] and out["dry_run"] is True
    assert "-m" in out["hint"]  # the hint must say how to commit for real


def test_dry_run_does_not_prune_the_script_it_was_asked_to_replay(shaft):
    import time

    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    old = time.time() - 3600
    os.utime(script, (old, old))  # older than the junk files below
    tmp = shaft / ".linercad" / "tmp"
    for k in range(25):
        f = tmp / f"junk-{k:02d}.py"
        f.write_text("pass\n", encoding="utf-8")
    code, dry = cli("-C", str(shaft), "edit", str(script), "-m", "试改", "--dry-run")
    assert code == 0 and dry["ok"]
    assert script.is_file()  # dry-run must not prune the script it just replayed
    code, real = cli("-C", str(shaft), "edit", str(script), "-m", "试改")
    assert code == 0 and real["ok"] and real["commit"]
