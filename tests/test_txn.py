"""Transactions, git and CLI driven through `python -m linercad`, as an agent would."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SOURCES = {".gitattributes", ".gitignore", "drawing.actions.jsonl", "drawing.py"}


def lcad(dir, *args):
    r = subprocess.run(
        [sys.executable, "-m", "linercad", "-C", str(dir), *args], capture_output=True
    )
    assert b"\r" not in r.stdout
    return r.returncode, json.loads(r.stdout.decode("utf-8"))


def git(dir, *args):
    return subprocess.run(
        ["git", "-C", str(dir), *args], capture_output=True, text=True, encoding="utf-8"
    ).stdout


def subjects(dir):
    return git(dir, "log", "--format=%s").splitlines()


def script(dir, name, body):
    p = Path(dir) / ".linercad" / "tmp" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "def apply(d):\n" + "".join("    " + ln + "\n" for ln in body.splitlines()),
        encoding="utf-8",
    )
    return str(p)


@pytest.fixture
def part(tmp_path):
    d = tmp_path / "part"
    code, out = lcad(tmp_path, "init", str(d))
    assert code == 0, out
    return d


def test_init_tracks_only_sources_and_commits_e0(part):
    assert set(git(part, "ls-files").split()) == SOURCES
    assert subjects(part) == ["e0 · init"]
    assert (part / ".linercad/build/drawing.dxf").exists() and (
        part / ".linercad/build/model.json"
    ).exists()
    code, out = lcad(part.parent, "init", str(part))
    assert code == 1 and out["error"]["code"] == "invalid_arg"


def test_edit_appends_log_and_makes_one_commit(part):
    code, out = lcad(
        part,
        "edit",
        script(part, "a.py", 'd["D.L"].place(side="top")\nd["D.H"].tol = "±0.1"'),
        "-m",
        "长度挪到上面，高度加公差",
    )
    assert code == 0, out
    assert out["edit"] == "e1" and out["changed"] == ["D.L", "D.H"]
    assert subjects(part)[0] == "e1 · 长度挪到上面，高度加公差"
    log = [
        json.loads(x)
        for x in (part / "drawing.actions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert log[0] == {
        "edit": "e1",
        "op": "place",
        "id": "D.L",
        "args": {"side": "top", "row": 1, "offset": 0},
    }
    assert log[1]["args"] == {"tol": "±0.1"}
    assert set(git(part, "ls-files").split()) == SOURCES
    model = json.loads((part / ".linercad/build/model.json").read_text(encoding="utf-8"))
    dim = {e["id"]: e for e in model["elements"]}["D.H"]
    assert dim["intent"]["text"] == "50±0.1" and dim["history"] == ["e1"]


def test_failed_edit_rolls_back(part):
    before = (part / "drawing.actions.jsonl").read_bytes(), subjects(part)
    code, out = lcad(
        part, "edit", script(part, "bad.py", 'd["D.key"].tol = "h9"'), "-m", "改键槽公差"
    )
    assert code == 1 and out["rolled_back"] is True
    err = out["error"]
    assert err["code"] == "not_found" and "D.L" in err["candidates"] or "D.H" in err["candidates"]
    assert err["where"].endswith("bad.py:2")
    assert ((part / "drawing.actions.jsonl").read_bytes(), subjects(part)) == before
    code, out = lcad(part, "edit", script(part, "noop.py", "x = d['D.L'].text"), "-m", "看看")
    assert code == 1 and out["error"]["code"] == "no_ops"
    assert subjects(part) == before[1]


def test_param_change_in_drawing_py_replays_log(part):
    lcad(part, "edit", script(part, "m.py", 'd["D.L"].move(dy=-3)'), "-m", "长度尺寸往下挪 3")
    src = (part / "drawing.py").read_text(encoding="utf-8").replace("L=Param(100", "L=Param(140")
    (part / "drawing.py").write_text(src, encoding="utf-8")
    code, out = lcad(part, "build", "-m", "长度改成 140")
    assert (
        code == 0
        and out["edit"] == "e2"
        and not [w for w in out["warnings"] if w["pack"] == "layout"]
    )
    model = json.loads((part / ".linercad/build/model.json").read_text(encoding="utf-8"))
    dim = {e["id"]: e for e in model["elements"]}["D.L"]
    assert dim["intent"]["value"] == 140 and dim["placement"]["offset"] == 3
    assert subjects(part)[:2] == ["e2 · 长度改成 140", "e1 · 长度尺寸往下挪 3"]


def test_edit_commits_uncommitted_drawing_py_in_same_round(part):
    src = (part / "drawing.py").read_text(encoding="utf-8").replace("H=Param(50", "H=Param(60")
    (part / "drawing.py").write_text(src, encoding="utf-8")
    code, out = lcad(
        part, "edit", script(part, "a.py", 'd["D.H"].tol = "h7"'), "-m", "高度 60，加 h7"
    )
    assert code == 0
    assert git(part, "status", "--porcelain").strip() == ""
    assert "drawing.py" in git(part, "show", "--name-only", "--format=", "HEAD")


def test_undo_earlier_round(part):
    lcad(part, "edit", script(part, "a.py", 'd["D.H"].tol = "h7"'), "-m", "高度加公差")
    lcad(part, "edit", script(part, "b.py", 'd.notes.tech("去毛刺。")'), "-m", "加技术要求")
    code, out = lcad(part, "undo", "e1", "-m", "撤销公差")
    assert code == 0 and out["undone"] == "e1" and out["removed_ops"] == 1
    log = (part / "drawing.actions.jsonl").read_text(encoding="utf-8")
    assert '"e1"' not in log and '"e2"' in log
    assert "Undo-Of: e1" in git(part, "log", "-1", "--format=%b")
    assert subjects(part)[0] == "e3 · 撤销公差"
    code, out = lcad(part, "undo", "e3")
    assert code == 1 and out["error"]["code"] == "undo"
    code, out = lcad(part, "undo", "e9")
    assert code == 1 and "e2" in out["error"]["candidates"]


def test_undo_reverses_drawing_py_change(part):
    src = (part / "drawing.py").read_text(encoding="utf-8")
    (part / "drawing.py").write_text(src.replace("L=Param(100", "L=Param(150"), encoding="utf-8")
    lcad(part, "build", "-m", "长度 150")
    code, out = lcad(part, "undo", "e1")
    assert code == 0
    assert "L=Param(100" in (part / "drawing.py").read_text(encoding="utf-8")


def test_dirty_undo_refused(part):
    lcad(part, "edit", script(part, "a.py", 'd["D.H"].tol = "h7"'), "-m", "x")
    (part / "drawing.py").write_text(
        (part / "drawing.py").read_text(encoding="utf-8") + "\n# x\n", encoding="utf-8"
    )
    code, out = lcad(part, "undo", "e1")
    assert code == 1 and out["error"]["code"] == "dirty"


def test_subdir_of_bigger_repo_commits_only_its_sources(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)])
    (tmp_path / "other.txt").write_text("x", encoding="utf-8")
    git(tmp_path, "add", "other.txt")
    code, _ = lcad(tmp_path, "init", str(tmp_path / "parts" / "p1"))
    assert code == 0
    assert git(tmp_path, "show", "--name-only", "--format=", "HEAD").split() == [
        "parts/p1/.gitattributes",
        "parts/p1/.gitignore",
        "parts/p1/drawing.actions.jsonl",
        "parts/p1/drawing.py",
    ]
    assert "A  other.txt" in git(tmp_path, "status", "--porcelain")


def test_context_summary_and_detail(part):
    code, out = lcad(part, "context")
    assert code == 0 and {"D.L", "D.H"} <= {x["id"] for x in out["elements"]["dim"]}
    assert out["history"] == ["e0 · init"]
    code, out = lcad(part, "context", "D.L")
    item = out["items"][0]
    assert (
        item["element"]["id"] == "D.L" and item["source"] and item["snippet"][0] == "def apply(d):"
    )
    code, out = lcad(part, "context", "D.LL")
    assert code == 1 and "D.L" in out["error"]["candidates"]


def test_render_full_and_focus(part):
    code, out = lcad(part, "render")
    assert code == 0 and Path(out["png"]).exists()
    code, out = lcad(part, "render", "--focus", "D.L")
    assert code == 0 and Path(out["png"]).name == "render-D.L.png"


def test_edit_scoped_names_survive_replay(part):
    code, out = lcad(
        part,
        "edit",
        script(part, "a.py", 'd.view("front").line((0, 0), (10, 10), role="thin")'),
        "-m",
        "加一条细线",
    )
    assert code == 0 and out["changed"] == ["E.front.e1_1"]
    code, out = lcad(part, "context", "E.front.e1_1")
    assert code == 0 and out["items"][0]["element"]["src"] == {"edit": "e1", "line": 1}


# ---- regressions from the PR #22 review ---------------------------------------------------------


def test_undo_drawing_py_change_with_lf_file(part):
    p = part / "drawing.py"
    p.write_bytes(p.read_bytes().replace(b"H=Param(50", b"H=Param(60"))
    assert b"\r" not in p.read_bytes()
    lcad(part, "build", "-m", "高度 60")
    code, out = lcad(part, "undo", "e1")
    assert code == 0, out
    assert b"H=Param(50" in p.read_bytes() and b"\r" not in p.read_bytes()


def test_move_on_auto_placed_dim(part):
    code, out = lcad(part, "edit", script(part, "m.py", 'd["D.L"].move(dy=-4)'), "-m", "往下挪 4")
    assert code == 0, out
    assert out["ops"][0]["args"]["side"] == "bottom"


def test_undo_twice_refused_and_print_does_not_break_json(part):
    lcad(part, "edit", script(part, "a.py", 'print("hello")\nd["D.H"].tol = "h7"'), "-m", "x")
    lcad(part, "undo", "e1")
    code, out = lcad(part, "undo", "e1")
    assert code == 1 and out["error"]["code"] == "undo"
    code, out = lcad(part, "edit", script(part, "b.py", "import sys\nsys.exit(3)"), "-m", "y")
    assert code == 1 and out["error"]["code"] == "script"


def test_failed_init_cleans_up(tmp_path):
    code, out = lcad(tmp_path, "init", str(tmp_path / "w"), "--sheet", "A9")
    assert code == 1 and not (tmp_path / "w").exists()
    code, out = lcad(tmp_path, "init", str(tmp_path / "w"))
    assert code == 0


def test_bom_in_hand_edited_log(part):
    lcad(part, "edit", script(part, "a.py", 'd["D.H"].tol = "h7"'), "-m", "x")
    log = part / "drawing.actions.jsonl"
    log.write_bytes(b"\xef\xbb\xbf" + log.read_bytes())
    code, out = lcad(part, "build")
    assert code == 0, out
