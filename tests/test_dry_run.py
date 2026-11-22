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
    return r.returncode, json.loads(r.stdout)


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
    assert out["preview"].endswith(".dxf")
    preview = shaft / out["preview"]
    assert preview.is_file() and preview.stat().st_size > 0
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


def test_dry_run_stale_op_failure_matches_edit(shaft):
    script = write_script(
        shaft,
        '    d["D.L"].suppress()\n    d.raw("D.L").entities[0].dxf.color = 1\n',
    )
    before = repo_state(shaft)
    code, dry = cli("-C", str(shaft), "edit", str(script), "-m", "试改", "--dry-run")
    assert code == 1 and not dry["ok"] and dry["error"]["code"] == "stale"
    assert repo_state(shaft) == before
    code, real = cli("-C", str(shaft), "edit", str(script), "-m", "试改")
    assert code == 1 and real["error"]["code"] == dry["error"]["code"]


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
