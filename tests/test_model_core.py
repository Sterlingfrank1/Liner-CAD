import pytest

from linercad import Drawing, Param, errors
from linercad.model import BUILD


@pytest.fixture
def d():
    return Drawing(sheet="A3", std="GB", scale="1:1")


# ---- drawing, params, views ----------------------------------------------------------


def test_drawing_basics(d):
    assert d.sheet == "A3" and d.std_name == "GB"
    assert d.scale_text == "1:1" and d.scale == 1.0
    assert Drawing(scale="1:2").scale == 0.5
    with pytest.raises(errors.InvalidArgument):
        Drawing(scale="half")


def test_build_context_captures_drawing():
    box = []
    tok = BUILD.set(box)
    try:
        d = Drawing()
    finally:
        BUILD.reset(tok)
    assert box == [d]


def test_params_declared_once(d):
    P = d.params(D=Param(30, min=10, max=60))
    assert float(P.D) == 30
    with pytest.raises(errors.ParamError):
        d.params(L=Param(10))


def test_view_ids_and_unknown_view(d):
    front = d.view("front")
    assert front.id == "V.front" and d.view("front") is front
    with pytest.raises(errors.InvalidArgument) as e:
        d.view("isometric")
    assert "front" in e.value.candidates


# ---- IDs -----------------------------------------------------------------------------


def test_unnamed_edges_numbered_per_view(d):
    f, t = d.view("front"), d.view("top")
    a = f.line((0, 0), (10, 0))
    b = f.line((0, 5), (10, 5))
    c = t.line((0, 0), (1, 1))
    assert (a.id, b.id, c.id) == ("E.front.1", "E.front.2", "E.top.1")


def test_named_feature_edges(d):
    f = d.view("front")
    feat = f.rect((0, 0), 20, 10, name="plate")
    assert feat.id == "F.front.plate"
    assert [e.id for e in feat.edges] == [f"E.front.plate.{k}" for k in range(1, 5)]
    assert d["E.front.plate.1"].feature == "F.front.plate"
    assert "V.front" in d["E.front.plate.1"].refs and "F.front.plate" in d["E.front.plate.1"].refs


def test_named_line_returns_edge_and_feature(d):
    e = d.view("front").line((0, 0), (5, 0), name="ref")
    assert e.id == "E.front.ref.1" and "F.front.ref" in d


def test_duplicate_id_suggests_free_name(d):
    f = d.view("front")
    f.rect((0, 0), 1, 1, name="plate")
    with pytest.raises(errors.DuplicateId) as e:
        f.rect((5, 5), 1, 1, name="plate")
    assert e.value.id == "F.front.plate"
    assert e.value.candidates == ["F.front.plate_2"]


def test_bad_names_rejected(d):
    with pytest.raises(errors.InvalidArgument):
        d.view("front").rect((0, 0), 1, 1, name="1abc")
    with pytest.raises(errors.InvalidArgument):
        d.view("front").rect((0, 0), 1, 1, name="a b")
    d.view("front").rect((0, 0), 1, 1, name="底板")  # unicode letters are fine


def test_forced_id_and_counter_skip(d):
    f = d.view("front")
    d._forced_id = "E.front.3"
    assert f.line((0, 0), (1, 0)).id == "E.front.3"
    ids = [f.line((0, 0), (1, 0)).id for _ in range(3)]
    assert ids == ["E.front.1", "E.front.2", "E.front.4"]


def test_src_points_to_caller_line(d):
    import inspect

    line = inspect.currentframe().f_lineno + 1
    e = d.view("front").line((0, 0), (1, 0))
    assert e.src == {"file": "test_model_core.py", "line": line}


# ---- geometry ------------------------------------------------------------------------


def test_roles_validated(d):
    with pytest.raises(errors.InvalidArgument) as e:
        d.view("front").line((0, 0), (1, 0), role="dotted")
    assert "hidden" in e.value.candidates


def test_turned_mirror_and_verticals(d):
    f = d.view("front")
    # chamfer C1 at the left end, step at x=30, plain end at x=50, collinear point at x=10
    prof = [(0, 12), (1, 13), (10, 13), (30, 13), (30, 15), (50, 15)]
    feat = f.turned("body", prof, axis=0)
    edges = feat.edges
    lines = [(tuple(e.start), tuple(e.end)) for e in edges]
    verticals = sorted(e.start[0] for e in edges if e.dir == "v")
    # end faces, chamfer edge, shoulder, right end; nothing at the collinear point x=10
    assert verticals == [0, 1, 30, 50]
    shoulder = [e for e in edges if e.dir == "v" and e.start[0] == 30][0]
    assert sorted([shoulder.start[1], shoulder.end[1]]) == [-15, 15]
    # top and mirrored bottom contours, no vertical duplicates
    assert ((0, 12), (1, 13)) in lines and ((0, -12), (1, -13)) in lines
    assert len(lines) == len(set(lines))
    assert len([e for e in edges if e.dir == "v"]) == 4
    # axis centre line
    axis = d["C.front.body"]
    assert axis.intent["p1"] == [0, 0] and axis.intent["p2"] == [50, 0]
    assert axis.refs[-1] == "F.front.body"


def test_turned_axis_offset_and_validation(d):
    f = d.view("front")
    feat = f.turned("s", [(0, 5), (10, 5)], axis=20)
    ys = sorted({e.start[1] for e in feat.edges if e.dir == "h"})
    assert ys == [15, 25]
    with pytest.raises(errors.InvalidArgument):
        f.turned("bad", [(10, 5), (0, 5)])
    with pytest.raises(errors.InvalidArgument):
        f.turned("bad2", [(0, 0), (10, 5)])


def test_holes_on_circle(d):
    left = d.view("left")
    feat = left.holes_on_circle("bolt", (0, 0), pcd=90, n=4, d=12, start=90)
    holes = feat.edges
    assert len(holes) == 4 and all(h.shape == "circle" and h.r == 6 for h in holes)
    assert holes[0].center == pytest.approx((0, 45))
    assert holes[1].center == pytest.approx((-45, 0))
    pitch = d["C.left.bolt"]
    assert pitch.intent["type"] == "circle" and pitch.intent["r"] == 45
    radial = d["C.left.bolt.1"]
    (x1, y1), (x2, y2) = radial.intent["p1"], radial.intent["p2"]
    assert x1 == pytest.approx(0) and x2 == pytest.approx(0)
    assert sorted([y1, y2]) == pytest.approx([39, 51])


def test_center_mark_and_centerline(d):
    f = d.view("front")
    m = f.center_mark((10, 10), 5)
    c = f.centerline((0, 0), (20, 0), name="axis")
    assert m.id == "C.front.1" and m.intent["type"] == "mark"
    assert c.id == "C.front.axis"


def test_param_expressions_accepted(d):
    P = d.params(L=Param(40), D=Param(20))
    e = d.view("front").line((0, P.D / 2), (P.L, P.D / 2))
    assert e.end == (40.0, 10.0)


def test_anchors(d):
    f = d.view("front")
    e = f.line((0, 0), (10, 0), name="base")
    c = f.circle((5, 5), 2, name="hole")
    a = f.line("E.front.base.1:end", "E.front.hole.1:center")
    assert a.start == (10.0, 0.0) and a.end == (5.0, 5.0)
    with pytest.raises(errors.InvalidArgument) as ex:
        f.line("E.front.base.1:top", (0, 0))
    assert "start" in ex.value.candidates
    with pytest.raises(errors.NotFound):
        f.line("E.front.nope.1:start", (0, 0))
    t = d.view("top")
    with pytest.raises(errors.InvalidArgument):
        t.line("E.front.base.1:start", (0, 0))
    assert e and c


def test_edge_properties(d):
    f = d.view("front")
    e = f.line((0, 0), (0, 7))
    assert e.dir == "v" and e.length == 7 and e.mid == (0.0, 3.5)
    a = f.arc((0, 0), 10, 0, 90)
    assert a.start == pytest.approx((10, 0)) and a.end == pytest.approx((0, 10))


# ---- element API ------------------------------------------------------------------------


def test_element_set_and_attribute_assignment(d):
    e = d.view("front").line((0, 0), (1, 0))
    e.role = "hidden"
    assert e.role == "hidden"
    e.set(role="center")
    assert e.intent["role"] == "center"
    with pytest.raises(errors.InvalidArgument) as ex:
        e.set(colour="red")
    assert ex.value.candidates == ["role"]
    with pytest.raises(errors.InvalidArgument):
        e.length = 5


def test_unknown_method_hints_synonym(d):
    e = d.view("front").line((0, 0), (1, 0))
    with pytest.raises(errors.InvalidArgument) as ex:
        e.delete()
    assert "suppress" in ex.value.hint
    assert not hasattr(e, "nonexistent")


def test_suppress_removes_children(d):
    f = d.view("front")
    f.turned("body", [(0, 5), (10, 5)])
    d["F.front.body"].suppress()
    assert "F.front.body" not in d and "E.front.body.1" not in d and "C.front.body" not in d


def test_move_edge_and_feature(d):
    f = d.view("front")
    e = f.line((0, 0), (1, 0))
    e.move(dx=2, dy=3)
    assert e.start == (2, 3)
    feat = f.turned("body", [(0, 5), (10, 5)])
    feat.move(dx=1)
    assert d["C.front.body"].intent["p1"] == [1, 0]
    assert min(x.start[0] for x in feat.edges) == 1


def test_view_move_accumulates_offset(d):
    v = d.view("top")
    v.move(dy=-5)
    v.move(dy=-2)
    assert v.placement["offset"] == [0, -7]


def test_getitem_candidates(d):
    d.view("front").rect((0, 0), 1, 1, name="plate")
    with pytest.raises(errors.NotFound) as e:
        d["F.front.plat"]
    assert "F.front.plate" in e.value.candidates


def test_to_dict_fields(d):
    e = d.view("front").line((0, 0), (1, 0))
    rec = e.to_dict()
    assert list(rec) == ["id", "kind", "intent", "placement", "refs", "covers", "tags", "src", "history", "status"]
    assert rec["status"] == "ok" and rec["kind"] == "edge"


# ---- queries --------------------------------------------------------------------------------


@pytest.fixture
def plate(d):
    f = d.view("front")
    f.rect((0, 0), 30, 10, name="plate")
    f.circle((15, 5), 3, name="hole")
    d.view("top").rect((0, 0), 30, 20, name="plate")
    return d


def test_q_kinds_and_filters(plate):
    d = plate
    assert len(d.q.lines(view="front")) == 4
    assert len(d.q.lines()) == 8
    assert d.q.circles().one().id == "E.front.hole.1"
    assert d.q.views().ids() == ["V.front", "V.top"]
    with pytest.raises(errors.InvalidArgument) as e:
        d.q.dimz()
    assert "dims" in e.value.candidates


def test_where_with_tolerance_and_near(plate):
    d = plate
    e = d.q.lines(view="front").where(length=30, dir="h").near(15, 10).exactly(1)[0]
    assert e.id == "E.front.plate.3"
    assert d.q.lines(view="front").where(length=30.004, dir="h").exactly(2)
    assert len(d.q.lines(view="front").where(length=30.5, tol=0.6)) == 4
    assert len(d.q.lines(view="front").where(lambda el: el.start[1] == 0)) == 3


def test_near_requires_single_view(plate):
    with pytest.raises(errors.InvalidArgument):
        plate.q.lines().near(0, 0)


def test_exactly_reports_candidates(plate):
    d = plate
    with pytest.raises(errors.CountMismatch) as e:
        d.q.lines(view="front").where(dir="h").exactly(1)
    assert e.value.values == {"expected": 1, "found": 2}
    assert any("E.front.plate.1" in c for c in e.value.candidates)
    with pytest.raises(errors.CountMismatch) as e:
        d.q.lines(view="front").near(15, 30).one()
    assert any("dist=" in c for c in e.value.candidates)


def test_where_unknown_condition(plate):
    with pytest.raises(errors.InvalidArgument) as e:
        plate.q.lines().where(colour="red")
    assert "length" in e.value.candidates


def test_near_sheet_uses_resolved_bbox(plate):
    d = plate
    d["E.front.plate.1"]._resolved["bbox"] = [100, 100, 130, 100]
    d["E.front.hole.1"]._resolved["bbox"] = [112, 102, 118, 108]
    assert [e.id for e in d.near(115, 101, r=3)] == ["E.front.plate.1", "E.front.hole.1"]
