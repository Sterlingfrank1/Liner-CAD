"""M3 S2: lcad log / diff / export (SPEC M3 §1.6), driven through the CLI as an agent would."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from linercad import versions
from linercad.errors import LinerError


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
    """init + two edits: e1 tolerance on D.H, e2 a technical requirement and D.L moved."""
    d = tmp_path / "part"
    assert lcad(tmp_path, "init", str(d))[0] == 0
    assert lcad(d, "edit", script(d, "a.py", 'd["D.H"].tol = "±0.1"'), "-m", "高度加公差")[0] == 0
    code, out = lcad(
        d,
        "edit",
        script(d, "b.py", 'd.notes.tech("去毛刺。")\nd["D.L"].place(side="top")'),
        "-m",
        "加技术要求，长度挪到上方",
    )
    assert code == 0, out
    return d


def worktrees(dir):
    return [ln for ln in git(dir, "worktree", "list").splitlines() if ln.strip()]


# ---- lcad log ------------------------------------------------------------------------------------


def test_log_lists_edits_newest_first(part):
    code, out = lcad(part, "log")
    assert code == 0 and out["ok"] is True
    rows = out["log"]
    assert [r["edit"] for r in rows] == ["e2", "e1", "e0"]
    assert [r["message"] for r in rows] == ["加技术要求，长度挪到上方", "高度加公差", "init"]
    assert set(rows[0]) == {"edit", "commit", "message", "time"}
    heads = git(part, "log", "--format=%h").split()
    assert [r["commit"] for r in rows] == heads
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*", rows[0]["time"])
    assert versions.log(part) == rows


def test_log_only_commits_touching_the_drawing(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)])
    p = tmp_path / "parts" / "p1"
    assert lcad(tmp_path, "init", str(p))[0] == 0
    (tmp_path / "other.txt").write_text("x", encoding="utf-8")
    git(tmp_path, "add", "other.txt")
    git(
        tmp_path,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "-m",
        "unrelated change",
    )
    # a hand commit touching the drawing, without an edit number
    (p / "drawing.py").write_text(
        (p / "drawing.py").read_text(encoding="utf-8") + "\n# note\n", encoding="utf-8"
    )
    git(tmp_path, "add", "parts/p1/drawing.py")
    git(
        tmp_path,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "-m",
        "tidy up by hand",
    )
    rows = lcad(p, "log")[1]["log"]
    assert [(r["edit"], r["message"]) for r in rows] == [(None, "tidy up by hand"), ("e0", "init")]


# ---- lcad diff -----------------------------------------------------------------------------------


def test_diff_between_edits_reports_ids_and_writes_overlay(part):
    code, out = lcad(part, "diff", "e1", "e2")
    assert code == 0, out
    assert out["ok"] is True
    assert any(i.startswith("N.tech") for i in out["added"]) and out["removed"] == []
    assert out["layout_changed"] and "D.L" in out["layout_changed"]
    assert set(out) >= {"added", "removed", "intent_changed", "layout_changed", "svg", "a", "b"}
    svg = Path(out["svg"])
    assert svg.name == "diff-e1-e2.svg" and svg.parent == part / ".linercad" / "tmp"
    text = svg.read_text(encoding="utf-8")
    assert text.startswith("<svg") and 'viewBox="0 0 420 297"' in text
    added_id = next(i for i in out["added"] if i.startswith("N.tech"))
    assert re.search(rf'<g class="df-add" data-id="{re.escape(added_id)}"', text)
    assert 'class="df-a"' in text and 'class="df-b"' in text  # A grey, B black
    assert "<style>" in text  # stand-alone file carries its own colours
    # e0 -> e1: the tolerance changes D.H's intent only
    out = lcad(part, "diff", "e0", "e1")[1]
    assert out["intent_changed"] == ["D.H"] and out["added"] == [] and out["removed"] == []
    assert out["details"]["D.H"]["intent"]["text"] == ["50", "50±0.1"]
    assert 'class="df-chg" data-id="D.H"' in Path(out["svg"]).read_text(encoding="utf-8")


def test_diff_removed_after_undo_and_same_revision_is_empty(part):
    assert lcad(part, "undo", "e2")[0] == 0  # e3 reverses e2
    out = lcad(part, "diff", "e2", "e3")[1]
    assert any(i.startswith("N.tech") for i in out["removed"]) and out["added"] == []
    assert 'class="df-del"' in Path(out["svg"]).read_text(encoding="utf-8")
    same = lcad(part, "diff", "e1", "e1")[1]
    assert same["added"] == same["removed"] == same["intent_changed"] == []
    assert same["layout_changed"] == []


def test_diff_accepts_commit_hash_head_and_working_tree(part):
    rows = lcad(part, "log")[1]["log"]
    by_edit = {r["edit"]: r["commit"] for r in rows}
    out = lcad(part, "diff", by_edit["e0"], "HEAD")[1]
    assert out["ok"] and "D.H" in out["intent_changed"]
    # B omitted: the working tree. An uncommitted parameter change shows up, the file is untouched.
    src = part / "drawing.py"
    text = src.read_text(encoding="utf-8").replace("L=Param(100", "L=Param(140")
    src.write_text(text, encoding="utf-8")
    out = lcad(part, "diff", "HEAD")[1]
    assert out["ok"] and "D.L" in out["intent_changed"] and out["b"]["ref"] == "working"
    assert out["svg"].endswith("diff-HEAD-working.svg")
    assert src.read_text(encoding="utf-8") == text
    assert len(worktrees(part)) == 1


def test_diff_leaves_no_worktrees_even_on_error(part, monkeypatch):
    assert len(worktrees(part)) == 1
    assert lcad(part, "diff", "e0", "e2")[0] == 0
    assert len(worktrees(part)) == 1
    code, out = lcad(part, "diff", "e0", "e9")
    assert code == 1 and out["error"]["code"] == "not_found" and "e1" in out["error"]["candidates"]
    assert len(worktrees(part)) == 1
    from linercad import runtime

    real = runtime.build
    calls = []

    def boom(dir, *a, **k):
        calls.append(dir)
        if len(calls) == 2:
            raise RuntimeError("second build fails")
        return real(dir, *a, **k)

    monkeypatch.setattr(runtime, "build", boom)
    with pytest.raises(RuntimeError):
        versions.diff(part, "e0", "e2")
    assert len(calls) == 2 and len(worktrees(part)) == 1
    assert not any(Path(c).exists() for c in calls)  # the temp checkouts are gone too


def test_diff_in_a_subdirectory_of_a_bigger_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)])
    p = tmp_path / "parts" / "p1"
    assert lcad(tmp_path, "init", str(p))[0] == 0
    assert lcad(p, "edit", script(p, "a.py", 'd["D.H"].tol = "h7"'), "-m", "加 h7")[0] == 0
    out = lcad(p, "diff", "e0", "e1")[1]
    assert out["ok"] and out["intent_changed"] == ["D.H"]
    assert len(worktrees(tmp_path)) == 1


# ---- B7: a whole-view translation is one view move, not one layout change per element -------------


def _el(view, bbox, kind="edge", origin=None):
    return {"kind": kind, "intent": {"view": view}, "bbox": bbox, "view": view, "origin": origin}


def test_compare_merges_a_whole_view_translation():
    # real snapshots contain the view element V.<name>: it is the explicit anchor of the view move
    a = {
        "V.left": _el("left", [0, 0, 60, 20], origin=[0, 0]),
        "E.left.1": _el("left", [0, 0, 10, 10]),
        "E.left.2": _el("left", [20, 0, 30, 10]),
        "E.front.1": _el("front", [100, 0, 110, 10]),
    }
    b = {
        "V.left": _el("left", [10, 5, 70, 25], origin=[10, 5]),
        "E.left.1": _el("left", [10, 5, 20, 15]),
        "E.left.2": _el("left", [30, 5, 40, 15]),
        "E.front.1": _el("front", [100, 0, 110, 10]),
    }
    out = versions.compare(a, b)
    assert out["view_moves"] == [{"view": "left", "dx": 10.0, "dy": 5.0, "elements": 3}]
    assert out["layout_changed"] == [] and out["details"] == {}
    # an element that moved differently from its view stays in layout_changed (the real extra move)
    b["E.left.2"] = _el("left", [35, 10, 45, 20])
    out = versions.compare(a, b)
    assert out["view_moves"] == [{"view": "left", "dx": 10.0, "dy": 5.0, "elements": 2}]
    assert out["layout_changed"] == ["E.left.2"]


def test_compare_view_anchor_wins_over_a_lone_child():
    a = {
        "V.left": _el("left", [0, 0, 40, 10], origin=[0, 0]),
        "E.left.1": _el("left", [0, 0, 5, 5]),
    }
    b = {
        "V.left": _el("left", [10, 0, 50, 10], origin=[10, 0]),
        "E.left.1": _el("left", [25, 0, 30, 5]),
    }
    out = versions.compare(a, b)
    assert out["view_moves"] == [{"view": "left", "dx": 10.0, "dy": 0.0, "elements": 1}]
    assert out["layout_changed"] == ["E.left.1"]


def test_compare_does_not_treat_a_shape_change_as_a_view_move():
    # the view origin is unchanged (only the content grew): V's bbox grows with the content
    a = {
        "V.left": _el("left", [0, 0, 40, 40], origin=[50, 60]),
        "E.left.1": _el("left", [0, 0, 20, 20]),
    }
    b = {
        "V.left": _el("left", [0, 0, 80, 80], origin=[50, 60]),
        "E.left.1": _el("left", [0, 0, 40, 40]),
    }
    out = versions.compare(a, b)
    assert out["view_moves"] == []
    assert out["layout_changed"] == ["E.left.1", "V.left"]


def test_compare_requires_a_strict_majority_without_an_anchor():
    a = {}
    b = {}
    for i, dx in enumerate((10, 10, 5, -5)):
        a[f"E.left.{i}"] = _el("left", [0, 0, 10, 10])
        b[f"E.left.{i}"] = _el("left", [dx, 0, 10 + dx, 10])
    out = versions.compare(a, b)
    assert out["view_moves"] == []  # the top group is exactly half: not a view translation
    assert out["layout_changed"] == sorted(a)


def test_compare_reports_no_view_move_for_conflicting_translations():
    a = {"E.left.1": _el("left", [0, 0, 10, 10]), "E.left.2": _el("left", [20, 0, 30, 10])}
    b = {"E.left.1": _el("left", [10, 0, 20, 10]), "E.left.2": _el("left", [10, 0, 20, 10])}
    out = versions.compare(a, b)  # +10 and -10 tie: no single common translation
    assert out["view_moves"] == []
    assert out["layout_changed"] == ["E.left.1", "E.left.2"]


def test_compare_keeps_a_lone_moved_element_as_layout_change():
    a = {"E.top.1": _el("top", [0, 0, 5, 5])}
    b = {"E.top.1": _el("top", [3, 0, 8, 5])}
    out = versions.compare(a, b)
    assert out["view_moves"] == []  # one element does not prove the whole view moved
    assert out["layout_changed"] == ["E.top.1"]


@pytest.fixture
def moved_view_repo(tmp_path):
    from linercad import txn

    p = tmp_path / "moved"
    txn.init(p, from_="flange")
    s = script(p, "mv.py", 'd.view("left").move(dx=2)')
    assert lcad(p, "edit", s, "-m", "左视图右移 2mm")[0] == 0
    return p


def test_diff_reports_view_moves_for_the_real_drawing(moved_view_repo):
    out = lcad(moved_view_repo, "diff", "e0", "e1")[1]
    moves = {m["view"]: m for m in out["view_moves"]}
    assert set(moves) == {"front", "left"}  # the layout re-centres the group around the sheet
    assert moves["left"]["dx"] == 1.0 and moves["front"]["dx"] == -1.0
    assert all(m["elements"] >= 2 for m in moves.values())
    assert out["counts"]["view_moves"] == len(out["view_moves"])
    assert "V.left" not in out["layout_changed"]  # the view itself is part of its translation
    # only elements moving differently from their view stay: the section label changes width
    assert out["layout_changed"] == ["S.A"]
    svg = Path(out["svg"]).read_text(encoding="utf-8")
    # the absorbed view elements stay blue in the overlay, so the moved view is still visible
    assert 'class="df-chg" data-id="E.left.outer.1"' in svg


# ---- lcad export ---------------------------------------------------------------------------------


def test_export_tags_rev_a_then_rev_b_one_commit_each(part, tmp_path):
    n0 = len(git(part, "log", "--format=%h").split())
    code, out = lcad(part, "export", "--to", str(tmp_path / "out"))
    assert code == 0, out
    assert out["tag"] == "rev-A" and out["edit"] == "e3" and out["errors"] == 0
    assert sorted(Path(f).name for f in out["files"]) == ["drawing.dxf", "drawing.pdf"]
    for f in out["files"]:
        assert Path(f).exists() and Path(f).stat().st_size > 1000
    pdf = Path(out["files"][1]).read_bytes()
    assert pdf[:5] == b"%PDF-"
    w, h = (float(x) for x in re.search(rb"/MediaBox \[ 0 0 ([\d.]+) ([\d.]+) \]", pdf).groups())
    assert (w, h) == pytest.approx((420 / 25.4 * 72, 297 / 25.4 * 72), abs=0.5)  # the A3 sheet
    assert git(part, "log", "-1", "--format=%s").strip() == "e3 · 发布 rev-A"
    assert git(part, "rev-parse", "--short", "rev-A").strip() == out["commit"]
    assert len(git(part, "log", "--format=%h").split()) == n0 + 1
    model = json.loads((part / ".linercad/build/model.json").read_text(encoding="utf-8"))
    cell = {e["id"]: e for e in model["elements"]}["T.title.revision"]
    assert cell["intent"]["text"] == "A"
    # second release
    code, out = lcad(part, "export", "--to", str(tmp_path / "out"), "--formats", "dxf")
    assert code == 0, out
    assert out["tag"] == "rev-B" and [Path(f).name for f in out["files"]] == ["drawing.dxf"]
    assert git(part, "tag", "-l", "rev-*").split() == ["rev-A", "rev-B"]
    assert git(part, "log", "-1", "--format=%s").strip() == "e4 · 发布 rev-B"
    assert len(git(part, "log", "--format=%h").split()) == n0 + 2
    assert not git(part, "status", "--porcelain", "--", ".").strip()
    # releases are diff-able by tag
    out = lcad(part, "diff", "rev-A", "rev-B")[1]
    assert out["ok"] and "T.title.revision" in out["intent_changed"]
    assert out["details"]["T.title.revision"]["intent"]["text"] == ["A", "B"]


def test_export_refuses_uncommitted_sources_and_bad_formats(part, tmp_path):
    src = part / "drawing.py"
    src.write_text(src.read_text(encoding="utf-8") + "\n# half-way\n", encoding="utf-8")
    code, out = lcad(part, "export", "--to", str(tmp_path / "o"))
    assert code == 1 and out["error"]["code"] == "dirty"
    assert git(part, "tag", "-l").strip() == ""
    src.write_text(src.read_text(encoding="utf-8").replace("\n# half-way\n", ""), encoding="utf-8")
    code, out = lcad(part, "export", "--to", str(tmp_path / "o"), "--formats", "dxf,step")
    assert code == 1 and out["error"]["code"] == "invalid_arg"
    assert "dxf" in out["error"]["candidates"] and git(part, "tag", "-l").strip() == ""


def test_export_without_revision_field_notes_it_and_tags_head(part, tmp_path, monkeypatch):
    monkeypatch.setattr(versions, "_has_revision_field", lambda d: False)
    n0 = len(git(part, "log", "--format=%h").split())
    out = versions.export(part, tmp_path / "o", ["dxf"])
    assert out["tag"] == "rev-A" and "修订" in out["note"]
    assert out["commit"] == git(part, "rev-parse", "--short", "HEAD").strip()
    assert len(git(part, "log", "--format=%h").split()) == n0
    assert git(part, "tag", "-l").split() == ["rev-A"]


def test_next_rev_letter_skips_used_tags(part):
    git(part, "tag", "rev-A")
    git(part, "tag", "rev-C")
    assert versions.next_rev(part) == "B"
    git(part, "tag", "rev-B")
    assert versions.next_rev(part) == "D"
    assert versions.rev_letter(26) == "AA" and versions.rev_letter(0) == "A"


def test_resolve_errors_name_candidates(part):
    with pytest.raises(LinerError) as e:
        versions.resolve(part, "e7")
    assert "e2" in e.value.candidates
    with pytest.raises(LinerError):
        versions.resolve(part, "not-a-ref")
    with pytest.raises(LinerError):
        versions.resolve(part, "--output=x")  # never reaches git as an option
