import pytest

from linercad import Drawing, Param, errors
from linercad.annotate import default_look, fmt_num


@pytest.fixture
def d():
    d = Drawing(sheet="A3")
    d.params(D=Param(30, min=10, max=60), L=Param(120), l1=Param(40))
    f = d.view("front")
    f.turned("body", [(0, 15), (40, 15), (40, 20), (120, 20)])
    return d


def test_fmt_num():
    assert [fmt_num(v) for v in (30, 30.0, 12.5, 0.1 + 0.2, -0.0, 1e-9)] == [
        "30",
        "30",
        "12.5",
        "0.3",
        "0",
        "0",
    ]


def test_linear_measured_and_text(d):
    dim = d.view("front").dim.linear("len", (0, -15), (40, -15))
    assert dim.id == "D.len" and dim.kind == "dim"
    assert dim.intent["dir"] == "h" and dim.value == 40 and dim.text == "40"
    assert dim.covers == [] and dim.intent["expr"] is None
    assert dim.refs == ["V.front"]


def test_value_expression_covers_and_default_name(d):
    P = d.P
    a = d.view("front").dim.linear(None, (0, -20), (120, -20), value=P.L, role="overall")
    assert a.id == "D.L" and a.covers == ["L"] and a.intent["expr"] == "L"
    b = d.view("front").dim.linear(None, (0, -20), (120, -20), value=P.L)
    assert b.id == "D.front.1"  # D.L already taken
    c = d.view("front").dim.linear(None, (40, 0), (120, 0), value=P.L - P.l1)
    assert c.id == "D.front.2" and c.covers == ["L", "l1"] and c.value == 80


def test_dia_on_non_circular_view_and_tol(d):
    P = d.P
    dim = d.view("front").dim.dia(None, (20, 15), (20, -15), value=P.D, tol="h7", side="inside")
    assert dim.id == "D.D" and dim.intent["dir"] == "v"
    assert dim.text == "Φ30h7"
    assert dim.placement["side"] == "inside" and dim.LAYOUT == ("side", "row", "offset")


def test_prefix_suffix_and_text_override(d):
    dim = d.view("front").dim.linear("x", (0, 0), (40, 0), prefix="2×", suffix=" EQS")
    assert dim.text == "2×40 EQS"
    dim.text = "自定义"
    assert dim.text == "自定义"
    dim.set(text=None)
    assert dim.text == "2×40 EQS"
    dim.tol = "±0.1"
    assert dim.text == "2×40±0.1 EQS"
    dim.value = 41
    assert dim.text == "2×41±0.1 EQS" and dim.covers == []
    dim.value = None
    assert dim.value == 40


def test_set_value_expression_updates_covers(d):
    dim = d.view("front").dim.linear("x", (0, 0), (40, 0))
    dim.set(value=d.P.l1)
    assert dim.covers == ["l1"] and dim.intent["expr"] == "l1"


def test_position_requires_datum(d):
    f = d.view("front")
    with pytest.raises(errors.InvalidArgument) as e:
        f.dim.linear("pos", (0, 0), (40, 0), role="position")
    assert "datum" in e.value.message
    dim = f.dim.linear("pos", (0, 0), (40, 0), role="position", datum="E.front.body.1")
    assert dim.intent["datum"] == "E.front.body.1" and "E.front.body.1" in dim.refs
    with pytest.raises(errors.NotFound):
        f.dim.linear("pos2", (0, 0), (40, 0), role="position", datum="E.front.nope")
    other = f.dim.linear("plain", (0, 0), (40, 0))
    with pytest.raises(errors.InvalidArgument):
        other.set(role="position")
    other.set(role="position", datum="E.front.body.1:start")
    assert other.intent["role"] == "position"


def test_dir_inference_and_errors(d):
    f = d.view("front")
    assert f.dim.linear("v", (0, 0), (0, 10)).intent["dir"] == "v"
    with pytest.raises(errors.InvalidArgument) as e:
        f.dim.linear("diag", (0, 0), (10, 10))
    assert "dir" in e.value.message
    assert f.dim.linear("diag", (0, 0), (10, 7), dir="v").value == 7
    with pytest.raises(errors.InvalidArgument):
        f.dim.linear("zero", (0, 0), (0, 10), dir="h")


def test_ref_takes_edge_endpoints(d):
    top = d.q.lines(view="front").where(dir="h").near(80, 20).one()
    dim = d.view("front").dim.linear("seg", ref=top)
    assert dim.value == 80 and top.id in dim.refs
    with pytest.raises(errors.InvalidArgument):
        d.view("front").dim.linear("bad", ref="C.front.body")


def test_anchor_points_recorded_in_refs(d):
    dim = d.view("front").dim.linear("a", "E.front.body.1:start", "E.front.body.1:end")
    assert "E.front.body.1" in dim.refs and dim.value == 40


def test_layout_field_validation(d):
    f = d.view("front")
    with pytest.raises(errors.InvalidArgument) as e:
        f.dim.linear("h", (0, 0), (40, 0), side="left")
    assert e.value.candidates == ["top", "bottom", "inside"]
    with pytest.raises(errors.InvalidArgument):
        f.dim.linear("h2", (0, 0), (40, 0), row=0)
    dim = f.dim.linear("h3", (0, 0), (40, 0), side="top", row=2, offset=1.5)
    assert (dim.side, dim.row, dim.offset) == ("top", 2, 1.5)
    with pytest.raises(errors.InvalidArgument):
        dim.place(at=45)


def test_circle_view_dia_and_rad():
    d = Drawing()
    left = d.view("left")
    c = left.circle((0, 0), 30, name="outer")
    a = left.arc((0, 0), 10, 0, 90, name="corner")
    dia = left.dim.dia("Do", circle=c, at=45)
    assert dia.text == "Φ60" and dia.LAYOUT == ("at",) and dia.at == 45
    assert dia.intent["circle"] == "E.left.outer.1"
    rad = left.dim.rad("Rc", circle="F.left.corner")
    assert rad.text == "R10"
    with pytest.raises(errors.InvalidArgument):
        left.dim.rad("bad")
    line = left.line((0, 0), (1, 0))
    with pytest.raises(errors.InvalidArgument):
        left.dim.dia("bad", circle=line)
    with pytest.raises(errors.InvalidArgument):
        d.view("front").dim.dia("other", circle=c)
    with pytest.raises(errors.InvalidArgument):
        dia.place(side="top")


def test_move_dim_outward_only(d):
    dim = d.view("front").dim.linear("m", (0, -15), (40, -15), side="bottom", row=1)
    dim.move(dy=-3)
    assert dim.offset == 3
    dim.move(dy=1)
    assert dim.offset == 2
    with pytest.raises(errors.InvalidArgument) as e:
        dim.move(dx=2)
    assert "外法向" in e.value.message


def test_leader_note(d):
    n = d.view("front").note("chamfer", "C1", anchor="E.front.body.1:start", dir=45)
    assert n.id == "N.chamfer" and n.text == "C1" and n.placement["dir"] == 45
    assert "E.front.body.1" in n.refs
    n.move(dx=2)
    n.move(dx=1, dy=-1)
    assert n.placement["shift"] == [3, -1]
    n.place(length=12)
    assert n.placement["length"] == 12
    auto = d.view("front").note(None, "x", (0, 0))
    assert auto.id == "N.front.1"


def test_tech_notes_numbering_not_reused(d):
    a = d.notes.tech(["调质处理 220~250HBW。", "未注倒角 C1。"])
    assert [n.id for n in a] == ["N.tech.1", "N.tech.2"]
    d["N.tech.2"].suppress()
    (b,) = d.notes.tech("去毛刺。")
    assert b.id == "N.tech.3"
    with pytest.raises(errors.InvalidArgument):
        b.move(dx=1)


def test_title_fields(d):
    assert d["T.title.scale"].text == "1:1"
    d.title(name="阶梯轴", material="45")
    assert d["T.title.name"].text == "阶梯轴" and d["T.title.material"].text == "45"
    with pytest.raises(errors.InvalidArgument) as e:
        d.title(colour="red")
    assert "material" in e.value.candidates
    assert d["T.frame"].kind == "frame"


def test_section_and_default_look():
    d = Drawing()
    d.view("front")
    d.view("left")
    s = d.section("A", view="front", cut_in="left", through=[(0, -70), (0, 70)])
    assert s.id == "S.A" and s.intent["look"] == "left"
    assert s.refs == ["V.front", "V.left"]
    with pytest.raises(errors.DuplicateId):
        d.section("A", view="front", cut_in="left", through=[(0, -70), (0, 70)])
    with pytest.raises(errors.InvalidArgument):
        d.section("ab", view="front", cut_in="left", through=[(0, 0), (0, 1)])
    with pytest.raises(errors.NotFound):
        d.section("B", view="front", cut_in="top", through=[(0, 0), (1, 0)])
    s.look = "right"
    assert s.intent["look"] == "right"


def test_default_look_first_and_third_angle():
    std = {"views": {"projection": "first", "positions": {"first": {"top": [0, -1], "left": [1, 0], "right": [-1, 0]}}}}
    assert default_look(std, "front", "left") == "left"
    assert default_look(std, "front", "top") == "up"
    assert default_look(std, "left", "front") == "right"
    std3 = {"views": {"projection": "third", "positions": {"third": {"top": [0, 1], "right": [1, 0]}}}}
    assert default_look(std3, "front", "top") == "up"
    assert default_look(std3, "front", "right") == "right"


def test_hatch_loops(d):
    f = d.view("front")
    up = f.polygon([(0, 5), (40, 5), (40, 15), (0, 15)], name="upper")
    hole = f.circle((20, 10), 2, name="h")
    h = f.hatch("sec", loops=[up, "E.front.h.1", [(50, 0), (60, 0), (60, 5)]])
    assert h.id == "H.front.sec"
    assert h.loops[0] == {"ref": "F.front.upper"} and h.loops[1] == {"ref": "E.front.h.1"}
    assert h.loops[2]["points"][2] == [60, 5]
    assert hole
    with pytest.raises(errors.InvalidArgument):
        f.hatch("bad", loops=["F.front.body"])  # turned outline is not a closed feature
    with pytest.raises(errors.InvalidArgument):
        f.hatch("bad2", loops=[])
    auto = f.hatch(None, loops=[up])
    assert auto.id == "H.front.1"
