import json

import pytest

from linercad import Drawing, Param, errors
from linercad.dxfout import APPID, to_doc
from linercad.layout import layout
from linercad.record import Recorder, dumps, fill_layout, replay


def make(L=120, extra_unnamed=0):
    d = Drawing(sheet="A3")
    P = d.params(L=Param(L, min=10, max=400), D=Param(30))
    f = d.view("front")
    for k in range(extra_unnamed):
        f.line((0, 50 + k), (5, 50 + k))
    f.turned("body", [(0, P.D / 2), (P.L, P.D / 2)])
    f.dim.linear("L", (0, -P.D / 2), (P.L, -P.D / 2), value=P.L, side="bottom")
    f.dim.dia("D", (P.L / 2, P.D / 2), (P.L / 2, -P.D / 2), value=P.D, side="inside")
    d.notes.tech(["调质处理。"])
    return d


def record(d, fn, edit="e1"):
    layout(d)
    rec = Recorder(d, edit)
    d._recorder, d._scope = rec, edit
    try:
        fn(d)
    finally:
        d._recorder, d._scope = None, None
    return [dict(op, _line=k + 1) for k, op in enumerate(rec.ops)]


def rebuild(ops, current=None, **kw):
    d = make(**kw)
    stale = replay(d, ops, current)
    layout(d)
    return d, stale


# ---- recording ------------------------------------------------------------------------------------


def test_record_modify_ops_and_line_format():
    d = make()
    ops = record(d, lambda d: (d["D.L"].place(side="top"), setattr(d["D.D"], "tol", "h7")))
    assert [(o["op"], o["id"], o["args"]) for o in ops] == [
        ("place", "D.L", {"side": "top"}),
        ("set", "D.D", {"tol": "h7"}),
    ]
    line = dumps(ops[0])
    assert line == '{"edit":"e1","op":"place","id":"D.L","args":{"side":"top"}}'
    assert list(json.loads(line)) == ["edit", "op", "id", "args"]


def test_only_outermost_call_recorded_and_view_carried():
    d = make()
    ops = record(d, lambda d: d.view("front").turned("boss", [(0, 5), (10, 5)], axis=40))
    assert len(ops) == 1
    assert ops[0]["op"] == "turned" and ops[0]["id"] == "F.front.boss"
    assert ops[0]["args"]["view"] == "front" and ops[0]["args"]["name"] == "boss"
    ops = record(d, lambda d: d.view("front").dim.linear("x", (0, 0), (10, 0)))
    assert ops[0]["op"] == "dim.linear" and ops[0]["args"]["view"] == "front"


def test_existing_view_not_recorded_new_view_is():
    d = make()
    ops = record(d, lambda d: (d.view("front"), d.view("top")))
    assert [(o["op"], o["id"]) for o in ops] == [("view", "V.top")]


def test_title_records_one_set_per_field():
    d = make()
    ops = record(d, lambda d: d.title(name="轴", material="45"))
    assert [(o["op"], o["id"], o["args"]) for o in ops] == [
        ("set", "T.title.name", {"text": "轴"}),
        ("set", "T.title.material", {"text": "45"}),
    ]


def test_tech_notes_one_op_per_line_scoped_ids():
    d = make()
    ops = record(d, lambda d: d.notes.tech(["去毛刺。", "未注圆角 R1。"]))
    assert [(o["op"], o["id"]) for o in ops] == [
        ("notes.tech", "N.tech.e1_1"),
        ("notes.tech", "N.tech.e1_2"),
    ]


def test_query_arguments_are_rejected():
    d = make()
    with pytest.raises(errors.InvalidArgument) as e:
        record(
            d, lambda d: d.view("front").dim.linear("x", ref=d.q.lines(view="front").where(dir="h"))
        )
    assert ".one()" in e.value.hint


def test_params_read_only_in_scripts():
    d = make()
    with pytest.raises(errors.ParamError):
        record(d, lambda d: d.params(X=Param(1)))
    with pytest.raises(errors.ParamError):
        record(d, lambda d: setattr(d.P, "L", 5))


# ---- replay -------------------------------------------------------------------------------------------


def test_expression_recorded_as_source_and_follows_params():
    d = make()
    ops = record(
        d, lambda d: d.view("front").dim.linear("half", (0, 20), (d.P.L / 2, 20), value=d.P.L / 2)
    )
    assert ops[0]["args"]["p2"] == [{"expr": "L / 2"}, 20]
    assert ops[0]["args"]["value"] == {"expr": "L / 2"}
    d2, stale = rebuild(ops, L=200)
    assert not stale and d2["D.half"].value == 100 and d2["D.half"].intent["p2"] == [100, 20]


def test_anchor_recorded_and_follows_geometry():
    d = make()
    ops = record(
        d,
        lambda d: d.view("front").dim.linear(
            "seg", "E.front.body.1:start", "E.front.body.1:end", side="top"
        ),
    )
    assert ops[0]["args"]["p1"] == "E.front.body.1:start"
    d2, _ = rebuild(ops, L=200)
    assert d2["D.seg"].value == 200


def test_scoped_ids_survive_drawing_changes():
    d = make()
    ops = record(d, lambda d: d.view("front").line((0, 0), (1, 1)))
    assert ops[0]["id"] == "E.front.e1_1"
    d2, stale = rebuild(ops, extra_unnamed=3)  # drawing.py now has more unnamed lines
    assert not stale and "E.front.e1_1" in d2 and d2["E.front.e1_1"].end == (1, 1)


def test_log_created_elements_have_log_src_and_history():
    d = make()
    ops = record(d, lambda d: d.view("front").dim.linear("x", (0, 0), (10, 0)))
    d2, _ = rebuild(ops)
    assert d2["D.x"].src == {"edit": "e1", "line": 1}
    assert d2["D.x"].history == ["e1"]
    ops2 = [
        dict(o, edit="e2", _line=2)
        for o in record(make(), lambda d: d["D.L"].set(tol="js7"), edit="e2")
    ]
    d3, _ = rebuild(ops + ops2)
    assert d3["D.L"].history == ["e2"] and d3["D.L"].src["file"]


def test_move_is_relative_and_freezes_side_row():
    d = make()
    ops = record(d, lambda d: d["D.L"].move(dy=-3))
    filled = fill_layout(ops, rebuild(ops)[0])
    assert filled[0]["args"] == {"dy": -3, "side": "bottom", "row": 1}
    ops2 = record(make(), lambda d: d["D.L"].move(dy=-2), edit="e2")
    filled2 = fill_layout([dict(o, edit="e2") for o in ops2], rebuild(filled + ops2)[0])
    d2, stale = rebuild(filled + filled2, L=200)
    assert not stale and d2["D.L"].offset == 5 and d2["D.L"].side == "bottom" and d2["D.L"].row == 1


def test_place_is_completed_with_engine_choices():
    d = make()
    ops = record(d, lambda d: d["D.L"].place(side="top"))
    d1, _ = rebuild(ops)
    filled = fill_layout(ops, d1)
    assert filled[0]["args"] == {"side": "top", "row": d1["D.L"].row, "offset": 0}


def test_stale_ops_are_skipped_and_reported():
    d = make()
    ops = record(d, lambda d: (d["D.L"].set(tol="js7"), d["D.D"].place(side="inside", offset=2)))
    bad = [dict(ops[0], id="D.LL", _line=1), dict(ops[1], _line=2)]
    d2, stale = rebuild(bad)
    assert len(stale) == 1
    s = stale[0]
    assert s["edit"] == "e1" and s["line"] == 1 and s["op"] == "set" and s["id"] == "D.LL"
    assert "D.L" in s["candidates"]
    assert d2["D.D"].offset == 2  # the rest still applied


def test_create_with_existing_id_is_stale():
    d = make()
    ops = record(d, lambda d: d.view("front").dim.linear("x", (0, 0), (10, 0)))
    d2, stale = rebuild(ops + [dict(ops[0], _line=2)])
    assert len(stale) == 1 and "已存在" in stale[0]["reason"]


def test_current_edit_failure_raises():
    d = make()
    ops = record(d, lambda d: d["D.L"].set(tol="js7"))
    with pytest.raises(errors.StaleOp):
        rebuild([dict(ops[0], id="D.nope")], current="e1")


def test_suppress_then_dependants_stale():
    d = make()
    ops = record(d, lambda d: d["D.D"].suppress())
    later = [
        dict(o, edit="e2", _line=2)
        for o in record(make(), lambda d: d["D.D"].set(tol="h6"), edit="e2")
    ]
    d2, stale = rebuild(ops + later)
    assert "D.D" not in d2 and stale[0]["id"] == "D.D" and stale[0]["edit"] == "e2"


def test_accept_recorded_and_replayed():
    d = make()
    ops = record(d, lambda d: d.accept("overlap", "D.L", "有意"))
    assert ops[0] == {
        "edit": "e1",
        "op": "accept",
        "id": "D.L",
        "args": {"rule": "overlap", "reason": "有意"},
        "_line": 1,
    }
    d2, _ = rebuild(ops)
    assert d2._accepted[("overlap", "D.L")] == "有意"


def test_raw_override_and_raw_add():
    d = make()
    layout(d)
    _, index, _ = to_doc(d)
    d._dxf_index = index
    ents = d.raw("D.L").entities
    assert ents[0].dxftype == "LINE"
    ops = record(
        d,
        lambda d: (
            setattr(d.raw("D.L").entities[0].dxf, "color", 1),
            d.raw_add("LINE", start=(10, 10), end=(20, 10), layer="THIN"),
        ),
    )
    assert ops[0] == {
        "edit": "e1",
        "op": "raw",
        "id": "D.L",
        "args": {"sub": 0, "attr": "color", "value": 1},
        "_line": 1,
    }
    assert ops[1]["op"] == "raw_add" and ops[1]["id"] == "X.e1_1"
    assert ops[1]["args"]["start"] == [10, 10]
    d2, stale = rebuild(ops)
    doc, index2, fails = to_doc(d2)
    assert not fails and index2["D.L"][0].dxf.color == 1
    x = index2["X.e1_1"][0]
    assert x.dxftype() == "LINE" and x.get_xdata(APPID)[0].value == "X.e1_1"
    with pytest.raises(errors.UnknownAttribute):
        d.raw("D.L").entities[0].translate(1, 0, 0)


def test_raw_bad_sub_index_is_stale():
    d = make()
    layout(d)
    ops = [
        {
            "edit": "e1",
            "op": "raw",
            "id": "D.L",
            "args": {"sub": 99, "attr": "color", "value": 1},
            "_line": 1,
        }
    ]
    d2, _ = rebuild(ops)
    _, _, fails = to_doc(d2)
    assert fails and fails[0]["edit"] == "e1" and fails[0]["line"] == 1


def test_thread_mesh_records_its_feature_id_and_replays():
    d = Drawing()
    d.view("front")
    ops = record(
        d,
        lambda x: x.view("front").thread_mesh(
            "joint", "M10", screw=(0, 50), hole=(20, 70), outer=12
        ),
    )
    assert ops[0]["op"] == "thread_mesh"
    assert ops[0]["id"] == "F.front.joint"
    d2 = Drawing()
    d2.view("front")
    stale = replay(d2, ops, None)
    assert not stale, stale
    layout(d2)
    assert "F.front.joint" in d2
