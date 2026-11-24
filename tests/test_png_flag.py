"""C2: lcad build --png / lcad edit --png — render PNG in the same successful transaction."""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from linercad import txn

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def shaft(tmp_path):
    p = tmp_path / "s"
    txn.init(p, from_="shaft")
    return p


def cli(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["LCAD_NO_VIEW"] = "1"
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
    log = (d / "drawing.actions.jsonl").read_bytes()
    src = (d / "drawing.py").read_bytes()
    return head, log, src


def write_script(d, body, name="t.py"):
    p = d / ".linercad" / "tmp" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("def apply(d):\n" + body, encoding="utf-8")
    return p


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == PNG_MAGIC
    return struct.unpack(">II", data[16:24])


def test_build_and_edit_with_png_render_in_same_transaction(shaft):
    src = shaft / "drawing.py"
    src.write_text(src.read_text(encoding="utf-8") + "\n# C2 build test\n", encoding="utf-8")
    code, bout = cli("-C", str(shaft), "build", "--png", "-m", "更新并出图")
    assert code == 0 and bout["ok"] and bout["commit"] and bout["edit"] == "e1", bout
    bpng = Path(bout["png"])
    assert bpng.is_file() and bpng.stat().st_size > 0
    w, h = png_size(bpng)
    assert abs(w - round(420 / 25.4 * 150)) <= 2 and abs(h - round(297 / 25.4 * 150)) <= 2

    bpng.unlink()
    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    code, eout = cli("-C", str(shaft), "edit", str(script), "--png", "-m", "改尺寸并出图")
    assert code == 0 and eout["ok"] and eout["commit"] and eout["edit"] == "e2", eout
    assert "D.L" in eout["changed"] and eout["ops"]
    epng = Path(eout["png"])
    assert epng.is_file() and epng.stat().st_size > 0
    ew, eh = png_size(epng)
    assert abs(ew - round(420 / 25.4 * 150)) <= 2 and abs(eh - round(297 / 25.4 * 150)) <= 2

    # dry-run with --png also yields png pointing at the preview without committing
    before = repo_state(shaft)
    script2 = write_script(shaft, '    d["D.L"].place(side="bottom")\n', name="t2.py")
    code, dout = cli("-C", str(shaft), "edit", str(script2), "--dry-run", "--png", "-m", "试改")
    assert code == 0 and dout["ok"] and dout["dry_run"] is True and dout["commit"] is None
    assert "png" in dout and Path(dout["png"]).is_file()
    assert repo_state(shaft) == before


def test_build_and_edit_without_png_flag_keep_existing_behavior(shaft):
    render_path = shaft / ".linercad" / "tmp" / "render.png"
    render_path.unlink(missing_ok=True)
    src = shaft / "drawing.py"
    src.write_text(src.read_text(encoding="utf-8") + "\n# no png build\n", encoding="utf-8")
    code, bout = cli("-C", str(shaft), "build", "-m", "无图构建")
    assert code == 0 and bout["ok"] and "png" not in bout
    assert not render_path.exists()

    script = write_script(shaft, '    d["D.L"].place(side="top")\n')
    code, eout = cli("-C", str(shaft), "edit", str(script), "-m", "无图编辑")
    assert code == 0 and eout["ok"] and "png" not in eout
    assert not render_path.exists()


def test_build_and_edit_png_do_not_render_on_failure_and_roll_back(shaft):
    render_path = shaft / ".linercad" / "tmp" / "render.png"
    render_path.unlink(missing_ok=True)

    # 1. Failing build --png
    good_src = (shaft / "drawing.py").read_text(encoding="utf-8")
    before = repo_state(shaft)
    (shaft / "drawing.py").write_text("raise RuntimeError('build fail')\n", encoding="utf-8")
    code, bout = cli("-C", str(shaft), "build", "--png", "-m", "坏构建")
    assert code == 1 and not bout["ok"] and bout["rolled_back"] is True
    assert "png" not in bout and not render_path.exists()
    # restore working-tree drawing.py for subsequent edit failure checks
    (shaft / "drawing.py").write_text(good_src, encoding="utf-8")
    assert repo_state(shaft) == before

    # 2. Failing edit --png (script error, NoOps, missing -m)
    broken = write_script(shaft, '    raise RuntimeError("edit fail")\n', name="bad.py")
    noop = write_script(shaft, "    pass\n", name="noop.py")
    for args in (
        ("edit", str(broken), "--png", "-m", "失败脚本"),
        ("edit", str(noop), "--png", "-m", "空操作"),
        ("edit", str(broken), "--png"),
    ):
        code, eout = cli("-C", str(shaft), *args)
        assert code == 1 and not eout["ok"] and eout["rolled_back"] is True
        assert "png" not in eout and not render_path.exists()
        assert repo_state(shaft) == before


def test_cli_help_documents_png_and_has_no_review_command():
    code, out = cli("--help")
    assert code == 0 and out["ok"]
    assert "--png" in out["commands"]["build"]
    assert "--png" in out["commands"]["edit"]
    assert "review" not in out["commands"]
