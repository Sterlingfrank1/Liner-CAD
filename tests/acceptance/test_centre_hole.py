"""A2 acceptance (issue #92): a shaft with an R type centre hole is written in a temporary
drawing repo, builds through the CLI and `lcad check` reports 0 errors - the hard condition of the
card, end to end (a real build, not the in-memory feature of tests/test_conv.py)."""

import json
import subprocess
import sys

DRAWING = '''"""A2 acceptance: shaft with an R type centre hole (GB/T 145-2001, GB/T 4459.5 marking)."""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    L=Param(120, min=80, max=200, step=1, label="总长"),
    d1=Param(20, min=12, max=30, step=1, label="轴颈直径", tol="k6"),
    d2=Param(30, min=22, max=45, step=1, label="轴身直径"),
)
front = d.view("front")
front.turned("body", [(0, P.d1 / 2), (30, P.d1 / 2), (30, P.d2 / 2), (P.L, P.d2 / 2)])
front.center_hole("chr", on="F.front.body", end="right", type="R", d=3.15)
front.center_hole("chl", on="F.front.body", end="left", type="A", d=2.5)
front.dim.dia("d1", (15, P.d1 / 2), (15, -P.d1 / 2), value=P.d1, tol="k6", side="inside")
front.dim.dia("d2", (75, P.d2 / 2), (75, -P.d2 / 2), value=P.d2, side="inside")
front.dim.linear(
    "L", (0, -P.d1 / 2), (P.L, -P.d2 / 2), dir="h", value=P.L, role="overall", side="bottom"
)
d.title(name="R 型中心孔轴", drawing_no="LC-A2-01", material="45", designer="Liner-CAD")
'''


def lcad(dir, *args):
    r = subprocess.run(
        [sys.executable, "-m", "linercad", "-C", str(dir), *args], capture_output=True
    )
    return r.returncode, json.loads(r.stdout.decode("utf-8"))


def test_r_centre_hole_shaft_checks_clean(tmp_path):
    d = tmp_path / "shaft_r"
    code, out = lcad(tmp_path, "init", str(d))
    assert code == 0, out
    (d / "drawing.py").write_text(DRAWING, encoding="utf-8")
    code, out = lcad(d, "build", "-m", "A2 acceptance: shaft with an R type centre hole")
    assert code == 0, out
    code, out = lcad(d, "check")
    assert code == 0 and out["ok"] and out["errors"] == 0, out
    # the R type centre hole reached the drawing as a semantic feature with the GB/T 4459.5 marking
    code, out = lcad(d, "context", "F.front.chr")
    assert code == 0, out
    intent = out["items"][0]["element"]["intent"]
    assert intent["designation"] == "R3.15/6.7" and intent["std"] == "GB/T 145-2001"
