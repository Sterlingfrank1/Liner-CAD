"""M1 C5: leftovers from M0 — build reports `changed`, PNG line weights, diameter text placement."""

from linercad import Drawing, Param, render, txn
from linercad.layout import Text, layout


def test_build_reports_changed(tmp_path):
    p = tmp_path / "b"
    txn.init(p)
    src = p / "drawing.py"
    src.write_text(
        src.read_text(encoding="utf-8") + '\nd.view("front").rect((0, 0), 40, 20, name="plate")\n',
        encoding="utf-8",
    )
    out = txn.build_commit(p, "加一块板")
    assert out["ok"] and "F.front.plate" in out["changed"]
    again = txn.build_commit(p)
    assert again["changed"] == []


def test_png_widens_lines_keeping_ratio():
    assert render.LINEWEIGHT_SCALING > 1


def test_inside_diameter_text_clear_of_axis():
    d = Drawing()
    P = d.params(D=Param(40))
    f = d.view("front")
    f.turned("b", [(0, P.D / 2), (60, P.D / 2)])
    el = f.dim.dia("D", (30, P.D / 2), (30, -P.D / 2), value=P.D, side="inside")
    layout(d)
    t = [p for p in el._prims if isinstance(p, Text)][0]
    axis_y = f.to_sheet(0, 0)[1]
    assert t.box[1] > axis_y  # the centre line does not run through the number
