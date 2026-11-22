"""M2 V2: PMI leaders do not cut through other annotations (M1 render review items 1, 6, 11, 12);
a technical-notes block mixing Chinese and English uses one text metric (ISO flange, item 4)."""

import pytest

from linercad import txn
from linercad.layout import Line, Text, _crosses
from linercad.runtime import build
from linercad.text import dxf_height

ANN = ("dim", "note", "gtol", "rough", "datum")
# known leftovers: an axis datum on a bore nested inside an outer diameter (the leader must stay on
# the dimension line), positions the example fixes on purpose, a roughness symbol standing on a face
ALLOWED = {  # baseline: leaders fixed by the example or attached to a nested inner diameter
    "sleeve": {("DT.A", "D.D"), ("G.perp", "D.Df")},
    "flange": {("DT.A", "D.Dh"), ("G.perp", "D.D"), ("R.bore", "D.Dh")},
    "end_cover": {
        ("DT.A", "D.dc"),
        ("DT.A", "D.ds"),
        ("R.bore", "D.dc"),
        ("R.bore", "D.ds"),
        ("R.bore", "R.spig"),
        ("R.spig", "R.bore"),
        # G.pos has a written at=0.5: the probe over D.tap's 4 sides x 6 rows still crosses
        # its diagonal dimension line; E5 place_leader_cross (dimension-line scope) counts 0
        # here, the stricter local test keeps it as a documented residual
        ("G.pos", "D.tap"),
    },
    "pulley": {("DT.A", "D.Dh"), ("R.bore", "D.Dh"), ("R.flank", "D.e")},
}


def leader_crossings(d):
    """PMI leaders cutting another dimension's *dimension line* (E5 place_dim_cross scope).

    A leader crossing an extension line is normal drafting (the same rule the E5 metric uses),
    so only dimension lines are judged here.
    """
    from linercad import place

    dims = {}
    for e in d._els.values():
        info = place._dim_info(e)
        if info is None:
            continue
        dims[e.id] = [(s.p, s.q) for s in place._dim_segments(info[1])]
    lines = {
        e.id: [p for p in e._prims if isinstance(p, Line)] for e in d._els.values() if e.kind in ANN
    }
    out = set()
    for e in d._els.values():
        if e.kind not in ("gtol", "rough", "datum") or not lines[e.id]:
            continue
        lead = lines[e.id][0]
        for oid, osegs in dims.items():
            if oid != e.id and oid != e._intent.get("ref"):
                if any(_crosses(lead.p, lead.q, a, b) for a, b in osegs):
                    out.add((e.id, oid))
    return out


@pytest.mark.parametrize(
    "name", ["shaft", "sleeve", "spline_shaft", "flange", "end_cover", "pulley"]
)
def test_pmi_leaders_do_not_cross_annotations(tmp_path, name):
    p = tmp_path / name
    txn.init(p, from_=name)
    assert leader_crossings(build(p).d) <= ALLOWED.get(name, set())


def test_mixed_language_notes_share_one_size(tmp_path):
    p = tmp_path / "f"
    txn.init(p, from_="flange")
    src = p / "drawing.py"
    src.write_text(
        src.read_text(encoding="utf-8").replace('std="GB"', 'std="ISO"'), encoding="utf-8"
    )
    d = build(p).d
    notes = [e for e in d._els.values() if e.kind == "note" and e._intent.get("tech")]
    assert any(e._intent.get("gentol") for e in notes)
    hs = set()
    for e in notes:
        t = [x for x in e._prims if isinstance(x, Text) and x.text[0].isdigit()][0]
        hs.add(round(dxf_height(t.text, t.height, d.std, t.cjk), 6))
    assert len(hs) == 1


def test_leader_avoids_a_dimension_when_it_can():
    from linercad import Drawing
    from linercad.layout import layout

    d = Drawing()
    f = d.view("front")
    f.turned("b", [(0, 20, "top"), (100, 20)])
    f.dim.linear("half", (0, 20), (60, 20), side="top")  # spans most of the top above the part
    f.datum("A", ref="E.front.b.top_lo")
    f.gtol("st", "straightness", 0.02, ref="E.front.b.top")
    layout(d)
    assert ("G.st", "D.half") not in leader_crossings(d)
