"""M0 acceptance (SPEC §12): every example goes through 8 conversational edit rounds via the CLI.

The same user requests (ROUNDS[*][k][0]) are given to the independent G5 agent; here each one is
paired with a fixed script so the flow is a deterministic regression test.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SOURCES = {".gitattributes", ".gitignore", "drawing.actions.jsonl", "drawing.py"}

# (user request, kind, payload): kind "edit" → apply() body; "param" → (old, new) text in drawing.py;
# "fail" → apply() body that must be rolled back; "undo" → edit number to undo
ROUNDS = {
    "shaft": [
        ("把总长尺寸挪到轴的上方", "edit", 'd["D.L"].place(side="top")'),
        ("最粗那段的直径加公差 k6", "edit", 'd["D.d3"].tol = "k6"'),
        ("加一条技术要求：去除毛刺锐边", "edit", 'd.notes.tech("去除毛刺锐边。")'),
        ("删掉倒角的引线标注", "edit", 'd["D.c2"].suppress()'),
        ("总长改成 220", "param", ("L=Param(200", "L=Param(220")),
        ("把总长尺寸再往外挪 3 mm", "edit", 'd["D.L"].move(dy=3)'),
        ("把键槽宽度尺寸的公差改成 h9", "fail", 'd["D.key"].tol = "h9"'),
        ("撤销第 2 轮", "undo", "e2"),
    ],
    "flange": [
        ("把凸台外径尺寸挪到主视图另一侧", "edit", 'd["D.Dh"].place(side="left")'),
        ("外径加公差 h11", "edit", 'd["D.D"].tol = "h11"'),
        (
            "在主视图标注凸台长度",
            "edit",
            'd.view("front").dim.linear("hub", "E.front.body.hub:start", "E.front.body.ch:end", dir="h", side="top")',
        ),
        ("删掉第 3 条技术要求", "edit", 'd["N.tech.3"].suppress()'),
        ("外径加大 10", "param", ("D=Param(120", "D=Param(130")),
        ("把节圆直径的引出角度换到左上方", "edit", 'd["D.pcd"].place(at=135)'),
        ("把槽宽尺寸改成 8", "fail", 'd["D.slot"].value = 8'),
        ("撤销第 3 轮", "undo", "e3"),
    ],
    "bracket": [
        ("把总高尺寸挪到主视图右侧", "edit", 'd["D.H"].place(side="right")'),
        ("立板孔直径的公差改成 H7", "edit", 'd["D.D"].tol = "H7"'),
        (
            "在俯视图标注立板厚度",
            "edit",
            'd.view("top").dim.linear("wt", "E.top.wall_front.1:start", "E.top.outline.3:end", dir="v", side="left")',
        ),
        ("删掉左视图上的底板厚度尺寸", "edit", 'd["D.t"].suppress()'),
        ("底板加长 10", "param", ("A=Param(80", "A=Param(90")),
        ("把孔距尺寸放到第 2 排", "edit", 'd["D.pitch"].place(row=2)'),
        ("把加强筋厚度标注删掉", "fail", 'd["D.rib"].suppress()'),
        ("撤销第 2 轮", "undo", "e2"),
    ],
}


def lcad(dir, *args):
    r = subprocess.run(
        [sys.executable, "-m", "linercad", "-C", str(dir), *args], capture_output=True
    )
    return r.returncode, json.loads(r.stdout.decode("utf-8"))


def git(dir, *args):
    return subprocess.run(
        ["git", "-C", str(dir), *args], capture_output=True, text=True, encoding="utf-8"
    ).stdout


#: E5 placement debt of each example at init (frozen: D1/D2 shrink these lists deliberately);
#: the rounds themselves must not add placement warnings of a different kind beyond the init debt
PLACEMENT_DEBT = {
    "shaft": {
        ("place_dim_outline", "D.d1"),
        ("place_dim_outline", "D.d2"),
        ("place_dim_outline", "D.d3"),
        ("place_dim_outline", "D.d5"),
        ("place_ext_line", "D.gh"),
        ("place_ext_line", "D.gw"),
        ("place_nesting", "D.L"),
        ("place_text_overlap", "D.kd"),
    },
    "flange": set(),
    "bracket": set(),
}

#: placement debt after the eight edit rounds (frozen the same way; the rounds intentionally move
#: dimensions into crowded places, so this set is a separate yardstick from the init debt)
PLACEMENT_DEBT_FINAL = {
    "shaft": {
        ("place_dim_outline", "D.d1"),
        ("place_dim_outline", "D.d2"),
        ("place_dim_outline", "D.d3"),
        ("place_dim_outline", "D.d5"),
        ("place_ext_line", "D.gh"),
        ("place_ext_line", "D.gw"),
        ("place_nesting", "D.L"),
        ("place_text_overlap", "D.kd"),
        ("place_text_overlap", "D.ug"),
    },
    "flange": set(),
    "bracket": set(),
}


@pytest.mark.parametrize("part", list(ROUNDS))
def test_eight_rounds(tmp_path, part):
    d = tmp_path / part
    code, out = lcad(tmp_path, "init", str(d), "--from", part)
    # E5 records the current placement debt of the reference drawings (D1/D2 remove it); every
    # other pack must stay warning-free here.
    other = [f for f in out["warnings"] if f.get("pack") != "placement"]
    assert code == 0 and other == [], out
    # E5 placement debt of the shaft example, frozen here; D1/D2 shrink it in their own PRs
    debt = {(f["rule"], f["id"]) for f in out["warnings"] if f.get("pack") == "placement"}
    assert debt == PLACEMENT_DEBT[part], debt
    commits = 1
    for k, (msg, kind, payload) in enumerate(ROUNDS[part], 1):
        log_before = (d / "drawing.actions.jsonl").read_bytes()
        if kind in ("edit", "fail"):
            s = d / ".linercad" / "tmp" / f"r{k}.py"
            s.parent.mkdir(parents=True, exist_ok=True)
            s.write_text("def apply(d):\n    " + payload + "\n", encoding="utf-8")
            code, out = lcad(d, "edit", str(s), "-m", msg)
        elif kind == "param":
            src = (d / "drawing.py").read_text(encoding="utf-8")
            assert payload[0] in src
            (d / "drawing.py").write_text(src.replace(payload[0], payload[1]), encoding="utf-8")
            code, out = lcad(d, "build", "-m", msg)
        else:
            code, out = lcad(d, "undo", payload, "-m", msg)
        if kind == "fail":
            assert code == 1 and out["rolled_back"] and out["error"]["candidates"], out
            assert (d / "drawing.actions.jsonl").read_bytes() == log_before
        else:
            assert code == 0, (k, msg, out)
            commits += 1
            stale = [w for w in out["warnings"] if w["rule"] == "stale_op"]
            assert not stale, (k, stale)
        subj = git(d, "log", "--format=%s").splitlines()
        assert len(subj) == commits, (k, subj)
        if kind != "fail":
            assert re.fullmatch(rf"e\d+ · {re.escape(msg)}", subj[0])
        assert set(git(d, "ls-files").split()) == SOURCES
    # E5: after the eight rounds the placement debt must be exactly the frozen final set (the
    # rounds move annotations on purpose; a new rule/id pair is a placement regression)
    code, out = lcad(d, "check")
    assert code == 0
    placement = {(w["rule"], w["id"]) for w in out["packs"]["placement"]}
    if placement != PLACEMENT_DEBT_FINAL[part]:
        raise AssertionError(sorted(placement))
    assert git(d, "status", "--porcelain").strip() == ""
    code, out = lcad(d, "context")
    assert code == 0


@pytest.mark.parametrize("part", list(ROUNDS))
def test_rebuild_is_deterministic(tmp_path, part):
    d = tmp_path / part
    lcad(tmp_path, "init", str(d), "--from", part)
    s = d / ".linercad" / "tmp" / "a.py"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_text("def apply(d):\n    " + ROUNDS[part][0][2] + "\n", encoding="utf-8")
    lcad(d, "edit", str(s), "-m", ROUNDS[part][0][0])
    outs = []
    for _ in range(2):
        assert lcad(d, "build")[0] == 0
        b = Path(d) / ".linercad" / "build"
        outs.append(((b / "drawing.dxf").read_bytes(), (b / "model.json").read_bytes()))
    assert outs[0] == outs[1]
