"""Regressions from the independent review of the core chain (PR #21)."""

import os
import subprocess
import sys

from linercad import Drawing, checks
from linercad.annotate import default_look
from linercad.layout import Line, layout

PROG = """
import hashlib, sys, tempfile, pathlib
sys.path.insert(0, {tests!r})
from test_dxfout import make
from linercad.dxfout import to_doc, save_doc
doc, *_ = to_doc(make())
p = pathlib.Path(tempfile.mkdtemp()) / "a.dxf"
save_doc(doc, p)
print(hashlib.sha256(p.read_bytes()).hexdigest())
"""


def test_dxf_bytes_identical_across_processes():
    tests = os.path.dirname(__file__)
    out = set()
    for seed in ("1", "2", "3"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run(
            [sys.executable, "-c", PROG.format(tests=tests)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert r.returncode == 0, r.stderr
        out.add(r.stdout.strip())
    assert len(out) == 1


def test_feature_edges_are_not_edit_scoped():
    d = Drawing()
    d._scope = "e7"
    f = d.view("front").rect((0, 0), 1, 1)
    assert f.id == "F.front.rect_e7_1"
    assert [e.id for e in f.edges] == [f"E.front.rect_e7_1.{k}" for k in range(1, 5)]
    h = d.view("front").holes_on_circle("hh", (0, 0), 20, 2, 2)
    assert [e.id for e in h.edges] == ["E.front.hh.1", "E.front.hh.2"]


def test_forced_id_only_used_by_its_own_allocation():
    d = Drawing()
    v = d.view("front")
    d._forced_id = "F.front.plate"
    f = v.rect((0, 0), 2, 2, name="plate")
    assert f.edges[0].id == "E.front.plate.1"
    d._forced_id = "F.front.body"
    v.turned("body", [(0, 5), (10, 5)])
    assert "E.front.body.1" in d
    d._forced_id = None


def test_section_arrow_for_diagonal_views():
    std = Drawing().std
    assert default_look(std, "top", "left") == "down"
    assert default_look(std, "bottom", "left") == "up"
    assert default_look(std, "front", "left") == "left"
    assert default_look(std, "front", "top") == "up"


def test_view_align_uses_real_arc_extent():
    d = Drawing()
    f, t = d.view("front"), d.view("top")
    f.line((0, 0), (80, 0))
    f.arc((40, -20), 50, 36.87, 143.13)  # crowned top from x=0 to x=80
    t.rect((0, 0), 80, 30)
    layout(d)
    assert not [x for x in checks.run(d) if x["rule"] == "view_align"]


def test_circle_dim_follows_moved_circle():
    d = Drawing()
    v = d.view("left")
    c = v.circle((0, 0), 10, name="hole")
    v.dim.dia("h", circle=c)
    d["F.left.hole"].move(dx=30)
    layout(d)
    bx = d["D.h"].bbox
    assert bx[2] > d["E.left.hole.1"].bbox[0]  # drawn at the new place, not at x=0
    assert (
        min(p.p[0] for p in d["D.h"]._prims if isinstance(p, Line))
        > d.view("left").to_sheet(15, 0)[0]
    )


def test_note_default_leader_length():
    d = Drawing()
    v = d.view("front")
    v.line((0, 0), (10, 0), name="a")
    v.note("n", "C1", anchor="E.front.a.1:start")
    layout(d)
    assert d["N.n"].placement["resolved"]["length"] == d.std["note"]["leader_length"]


def test_radial_hole_centre_lines_split_at_hole_centre():
    d = Drawing()
    d.view("left").holes_on_circle("b", (0, 0), 120, 4, 40)
    layout(d)
    pieces = [p for p in d["C.left.b.1"]._prims if isinstance(p, Line)]
    assert len(pieces) == 2 and pieces[0].p == pieces[1].p
