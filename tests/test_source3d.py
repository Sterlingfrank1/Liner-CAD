"""M3 S1: 3D source — d.model + V.project (needs linercad[3d]; skipped otherwise)."""

import json
import math
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("build123d")

from linercad import runtime  # noqa: E402
from linercad.source3d import fit  # noqa: E402

MODEL = '''
from build123d import Box, Cylinder, Pos

def model(L=120, W=80, T=12, D=50, H=40, d=30):
    body = Pos(0, 0, T / 2) * Box(L, W, T) + Pos(0, 0, H / 2) * Cylinder(D / 2, H)
    body = body - Pos(0, 0, H / 2) * Cylinder(d / 2, H + 2)
    for x in (-L / 2 + 12, L / 2 - 12):
        for y in (-W / 2 + 12, W / 2 - 12):
            body = body - Pos(x, y, T / 2) * Cylinder(5, T + 2)
    return body
'''

DRAWING = '''
from linercad import Drawing, Param
d = Drawing(sheet="A3")
P = d.params(L=Param(120, min=80, max=200), d=Param(30, min=10, max=40, rule="d < 50"))
d.model("model.py")
{body}
'''


def make(tmp_path, body, model=MODEL):
    (tmp_path / "model.py").write_text(model, encoding="utf-8")
    (tmp_path / "drawing.py").write_text(
        DRAWING.format(body=textwrap.dedent(body)), encoding="utf-8"
    )
    return runtime.build(tmp_path)


def edges(d, view):
    return [e for e in d._els.values() if e.kind == "edge" and e.view == view]


def test_three_views_from_projection_keep_curve_types(tmp_path):
    r = make(
        tmp_path,
        """
        d.view("front").project()
        d.view("top").project()
        d.view("left").project()
        """,
    )
    d = r.d
    top = edges(d, "top")
    circles = sorted(e._intent["r"] for e in top if e.shape == "circle")
    assert circles.count(5) == 4 and 15 in circles and 25 in circles
    front = edges(d, "front")
    assert all(e.shape in ("line", "arc", "circle") for e in front)
    hidden = [e for e in front if e.role == "hidden"]
    assert hidden, "bore and bolt holes hidden in the front view"
    xs = [p for e in front if e.shape == "line" for p in (e._intent["p1"][0], e._intent["p2"][0])]
    assert min(xs) == pytest.approx(-60) and max(xs) == pytest.approx(60)
    errs = [f for f in r.findings if f["severity"] == "error"]
    assert not errs, errs


def test_src3d_provenance_and_outline(tmp_path):
    d = make(tmp_path, 'd.view("front").project()').d
    es = edges(d, "front")
    s3 = [e._intent["src3d"] for e in es]
    assert all(s["model"] == "M.main" for s in s3)
    real = [s for s in s3 if "edge" in s]
    assert real and all(s["faces"] and len(s["hash"]) == 10 for s in real)
    assert any(s.get("outline") for s in s3), "cylinder silhouettes have no model edge"


def test_full_section_hatches_the_cut_face(tmp_path):
    r = make(tmp_path, 'd.view("front").project(cut="full")')
    d = r.d
    h = d["H.front.model"]
    assert len(h.loops) == 2  # the two halves left and right of the bore
    assert not [e for e in edges(d, "front") if e.role == "hidden" and abs(e._intent.get("p1", [0])[0]) < 15]


def test_half_and_local_sections(tmp_path):
    d = make(
        tmp_path,
        """
        d.view("front").project(cut="half")
        d.view("top").project(region=[(30, -40), (70, -40), (70, -20), (30, -20)], depth=6)
        """,
    ).d
    assert "H.front.model" in d
    assert "H.top.model" in d
    assert any(e.kind == "wavy" and e.view == "top" for e in d._els.values())


def test_dimension_on_projected_edge_keeps_src3d(tmp_path):
    d = make(
        tmp_path,
        """
        v = d.view("top")
        v.project()
        v.dim.dia("bore", circle=d.q.circles(view="top", r=15).one())
        """,
    ).d
    dim = next(e for e in d._els.values() if e.kind == "dim")
    assert dim._intent["src3d_refs"][0]["model"] == "M.main"


def test_param_change_reprojects(tmp_path):
    r1 = make(tmp_path, 'd.view("top").project()')
    r = sorted(e._intent["r"] for e in edges(r1.d, "top") if e.shape == "circle")
    assert 15 in r
    text = (tmp_path / "drawing.py").read_text(encoding="utf-8").replace("Param(30,", "Param(20,")
    (tmp_path / "drawing.py").write_text(text, encoding="utf-8")
    r2 = runtime.build(tmp_path)
    r = sorted(e._intent["r"] for e in edges(r2.d, "top") if e.shape == "circle")
    assert 10 in r and 15 not in r
    assert list((tmp_path / ".linercad" / "cache").glob("proj-*.json"))


def test_fit_line_arc_circle():
    line = [(t, 2 * t) for t in (0, 0.5, 1)]
    assert fit(line)[0]["shape"] == "line"
    circ = [(3 * math.cos(a), 3 * math.sin(a)) for a in (2 * math.pi * k / 40 for k in range(41))]
    assert fit(circ)[0]["shape"] == "circle"
    cw = [(math.cos(a), math.sin(a)) for a in (math.pi / 2 - k * math.pi / 40 for k in range(21))]
    arc = fit(cw)[0]
    assert arc["shape"] == "arc" and arc["start"] == pytest.approx(0) and arc["end"] == pytest.approx(90)


def test_missing_extra_message(tmp_path):
    code = (
        "import sys, builtins\n"
        "real = builtins.__import__\n"
        "def imp(n, *a, **k):\n"
        "    if n.startswith('build123d'): raise ImportError(n)\n"
        "    return real(n, *a, **k)\n"
        "builtins.__import__ = imp\n"
        "from linercad.source3d import need_3d\n"
        "from linercad.errors import LinerError\n"
        "try:\n    need_3d()\nexcept LinerError as e:\n"
        "    import json; print(json.dumps(e.to_dict()))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    err = json.loads(out.stdout)
    assert err["code"] == "missing_extra" and "linercad[3d]" in err["hint"]
