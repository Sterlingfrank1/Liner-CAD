"""DXF import (M3 S4): ``d.import_dxf``, ``lcad init --from-dxf``, ``lcad inspect``."""

import json
import subprocess
import sys
from pathlib import Path

import ezdxf
import pytest
from ezdxf import units

from linercad import Drawing, checks, importdxf
from linercad.runtime import build

DATA = Path(__file__).parent / "data" / "dxf"
SAMPLE = DATA / "sample_part.dxf"


def lcad(dir, *args):
    r = subprocess.run(
        [sys.executable, "-m", "linercad", "-C", str(dir), *args], capture_output=True
    )
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


@pytest.fixture(scope="module")
def sample_doc():
    return ezdxf.readfile(SAMPLE)


@pytest.fixture
def imported(tmp_path):
    """The sample imported with ``lcad init --from-dxf``: (drawing dir, init output)."""
    d = tmp_path / "part"
    code, out = lcad(tmp_path, "init", str(d), "--from-dxf", str(SAMPLE))
    assert code == 0, out
    return d, out


def model(dir):
    m = json.loads((Path(dir) / ".linercad/build/model.json").read_text(encoding="utf-8"))
    return {e["id"]: e for e in m["elements"]}


def make_dxf(path, fill, units_=units.MM):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units_
    fill(doc, doc.modelspace())
    doc.saveas(path)
    return path


# ---- the sample file --------------------------------------------------------------------------------


def importlib_util_load(path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_sample", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sample_is_small_and_regenerates(tmp_path):
    assert SAMPLE.stat().st_size < 200_000
    spec = importlib_util_load(DATA / "make_sample.py")
    out = spec.main(tmp_path / "again.dxf")
    again = ezdxf.readfile(out)
    types = lambda doc: sorted(e.dxftype() for e in doc.modelspace())  # noqa: E731
    assert types(again) == types(ezdxf.readfile(SAMPLE))


# ---- lcad inspect -----------------------------------------------------------------------------------


def test_inspect_reports_layers_types_extents_and_a_png(tmp_path):
    code, out = lcad(tmp_path, "inspect", str(SAMPLE))
    assert code == 0 and out["ok"] is True
    assert {"layers", "entities", "extents", "maps_to", "png", "sheet", "units", "size"} <= set(out)
    by_layer = {x["name"]: x for x in out["layers"]}
    assert by_layer["HIDDEN"]["linetype"] == "HIDDEN" and by_layer["HIDDEN"]["count"] == 3
    assert by_layer["CENTER"]["count"] == 5 and by_layer["OUTLINE"]["color"] == 7
    assert out["entities"]["DIMENSION"] == 8 and out["entities"]["LINE"] == 14
    assert out["extents"][0] == 0 and out["extents"][2] == 100 and out["extents"][3] == 60
    maps = out["maps_to"]
    assert maps["edges"] == {"CIRCLE": 3, "LINE": 14, "LWPOLYLINE": 1}
    assert sum(maps["dims"].values()) == 8 and maps["dims"]["radius"] == 1
    assert maps["texts"] == {"MTEXT": 1, "TEXT": 1} and maps["notes"] == {}
    assert maps["raw"] == {"ELLIPSE": 1, "SPLINE": 1}
    assert maps["hatches"] == {"HATCH": 1}
    assert maps["skipped"] == {"INSERT": 1, "POINT": 1}
    assert out["sheet"] == {"sheet": "A4", "scale": "1:1"}
    png = Path(out["png"])
    assert png.is_file() and png.suffix == ".png" and png.stat().st_size > 2000
    assert not (tmp_path / ".linercad").exists()  # not a drawing directory: system temp dir


def test_inspect_in_a_drawing_dir_writes_into_its_tmp(imported):
    d, _ = imported
    code, out = lcad(d, "inspect", str(SAMPLE))
    assert code == 0
    assert Path(out["png"]).parent.resolve() == (d / ".linercad" / "tmp").resolve()


def test_inspect_unreadable_file(tmp_path):
    bad = tmp_path / "bad.dxf"
    bad.write_text("this is not a dxf file\n", encoding="utf-8")
    code, out = lcad(tmp_path, "inspect", str(bad))
    assert code == 1 and out["ok"] is False and out["error"]["code"] in ("invalid_arg", "not_found")
    code, out = lcad(tmp_path, "inspect", str(tmp_path / "missing.dxf"))
    assert code == 1 and out["error"]["code"] == "not_found"


# ---- lcad init --from-dxf ---------------------------------------------------------------------------


def test_init_from_dxf_copies_ref_writes_drawing_and_commits_e0(imported):
    d, out = imported
    assert out["edit"] == "e0" and out["errors"] == 0
    assert out["import"]["sheet"] == "A4" and out["import"]["scale"] == "1:1"
    assert (d / "ref.dxf").read_bytes() == SAMPLE.read_bytes()
    src = (d / "drawing.py").read_text(encoding="utf-8")
    assert 'Drawing(sheet="A4"' in src and 'd.import_dxf("ref.dxf")' in src
    assert set(git(d, "ls-files").split()) == {
        ".gitattributes",
        ".gitignore",
        "drawing.actions.jsonl",
        "drawing.py",
        "ref.dxf",
    }
    assert git(d, "log", "--format=%s").splitlines() == ["e0 · init"]
    assert (d / ".linercad/build/drawing.dxf").exists()


def test_init_from_dxf_failures_leave_nothing_behind(tmp_path):
    bad = tmp_path / "bad.dxf"
    bad.write_text("nope", encoding="utf-8")
    target = tmp_path / "x"
    code, out = lcad(tmp_path, "init", str(target), "--from-dxf", str(bad))
    assert code == 1 and not target.exists()
    code, out = lcad(tmp_path, "init", str(target), "--from-dxf", str(SAMPLE), "--from", "shaft")
    assert code == 1 and out["error"]["code"] == "invalid_arg" and not target.exists()


def test_explicit_sheet_wins_over_the_guess(tmp_path):
    code, out = lcad(
        tmp_path, "init", str(tmp_path / "p"), "--from-dxf", str(SAMPLE), "--sheet", "A3"
    )
    assert code == 0 and out["import"]["sheet"] == "A3"
    assert 'sheet="A3"' in (tmp_path / "p" / "drawing.py").read_text(encoding="utf-8")


def test_sheet_guess_from_extents():
    assert importdxf.guess_sheet(100, 60) == ("A4", "1:1")
    assert importdxf.guess_sheet(300, 150) == ("A3", "1:1")
    assert importdxf.guess_sheet(1000, 600)[0] == "A0"
    assert importdxf.guess_sheet(2000, 1000) == ("A0", "1:2")
    sheet, scale = importdxf.guess_sheet(30000, 20000)
    assert sheet == "A0" and scale.startswith("1:") and int(scale[2:]) >= 50


# ---- what the sample becomes ----------------------------------------------------------------------------


def test_edges_by_role_and_polyline_bulges(imported):
    d, _ = imported
    m = model(d)
    edges = [e for e in m.values() if e["kind"] == "edge"]
    roles = {}
    for e in edges:
        roles[e["intent"]["role"]] = roles.get(e["intent"]["role"], 0) + 1
    assert roles == {"thick": 11, "hidden": 4, "center": 5, "thin": 1}
    assert all(e["id"].startswith("E.front.") and e["intent"]["view"] == "front" for e in edges)
    shapes = [e["intent"]["shape"] for e in edges]
    assert (shapes.count("line"), shapes.count("circle"), shapes.count("arc")) == (16, 3, 2)
    # the slot's bulges: two semicircles of R10 about (60, 30) and (80, 30)
    arcs = sorted(
        (e["intent"]["c"][0], e["intent"]["r"]) for e in edges if e["intent"]["shape"] == "arc"
    )
    assert arcs == [(60.0, 10.0), (80.0, 10.0)]
    # entity linetype beats the layer's: DASHED on OUTLINE → hidden; layer THIN → thin
    by_handle = {e["intent"]["dxf"]["layer"] + str(e["intent"].get("p1")): e for e in edges}
    assert by_handle["OUTLINE[20.0, 5.0]"]["intent"]["role"] == "hidden"
    assert by_handle["THIN[62.0, 12.0]"]["intent"]["role"] == "thin"
    i = m["I.ref"]["intent"]
    assert i["counts"]["edges"] == roles and i["counts"]["raw"] == 2
    assert (
        i["counts"]["notes"] == 0 and i["counts"]["texts"] == 2
    )  # TEXT/MTEXT became text elements
    assert i["counts"]["skipped"] == {"INSERT": 1, "POINT": 1} and i["counts"]["hatches"] == 1
    assert i["units"] == "mm" and i["extents"] == [0.0, -55.0, 100.0, 60.0]
    assert i["path"] == "ref.dxf" and len(i["sha256"]) == 64


def test_dimensions_carry_the_dxf_values(imported, sample_doc):
    d, _ = imported
    m = model(d)
    dims = [
        m[k]
        for k in sorted((k for k in m if k.startswith("D.")), key=lambda k: int(k.split("_")[1]))
    ]
    src = list(sample_doc.modelspace().query("DIMENSION"))
    assert len(dims) == len(src) == 8
    kinds = ["linear", "linear", "aligned", "dia", "dia", "rad", "angle", "angle"]
    for el, dx, kind in zip(dims, src, kinds):
        assert el["intent"]["type"] == kind, el["id"]
        assert el["intent"]["value"] == pytest.approx(dx.get_measurement(), abs=1e-4)
    assert [x["intent"].get("dir") for x in dims[:2]] == ["h", "v"]
    assert dims[0]["intent"]["text"] == "100" and dims[1]["intent"]["text"] == "60"
    # override text is kept; "<>" stands for the measurement
    assert dims[4]["intent"]["override"] == "Φ8 THRU"
    assert dims[5]["intent"]["override"] == "2xR10"
    assert dims[3]["intent"]["text"] == "Φ20" and dims[3]["intent"]["override"] is None
    # measured points that coincide with imported edge ends reference those edges
    assert any(r.startswith("E.front.") for r in dims[0]["refs"])
    assert dims[3]["intent"]["circle"] in m and m[dims[3]["intent"]["circle"]]["intent"]["r"] == 10
    assert (
        dims[5]["intent"]["circle"] in m
        and m[dims[5]["intent"]["circle"]]["intent"]["shape"] == "arc"
    )
    assert all("I.ref" in x["refs"] for x in dims)
    # the anonymous *D blocks are not exploded: only the sample's own geometry is in the model
    assert not [k for k in m if k.startswith("E.front.") and int(k.rsplit(".", 1)[1]) > 21]


def test_notes_and_raw_curves(imported):
    d, _ = imported
    m = model(d)
    texts = [e for e in m.values() if e["kind"] == "text"]
    assert sorted(n["intent"]["text"] for n in texts) == [
        "SAMPLE PART",
        "Technical requirements\n1. Deburr all edges",
    ]
    assert [e for e in m.values() if e["kind"] == "note"] == []
    raws = [e for e in m.values() if e["kind"] == "raw"]
    assert sorted(r["intent"]["dxftype"] for r in raws) == ["ELLIPSE", "SPLINE"]
    assert all(
        r["intent"]["view"] == "front" and r["placement"]["resolved"].get("bbox") for r in raws
    )
    # in the output DXF they sit where the view is placed on the sheet, at sheet scale
    doc = ezdxf.readfile(d / ".linercad/build/drawing.dxf")
    ell = [e for e in doc.modelspace() if e.dxftype() == "ELLIPSE"][0]
    (ox, oy) = m["V.front"]["placement"]["resolved"]["origin"]
    assert ell.dxf.center.x == pytest.approx(ox + 50, abs=1e-3)
    assert ell.dxf.center.y == pytest.approx(oy + 12, abs=1e-3)
    assert [e for e in doc.modelspace() if e.dxftype() == "SPLINE"]
    types = {e.dxftype() for e in doc.modelspace()}
    assert "HATCH" in types and not types & {"INSERT", "POINT"}


def test_import_builds_without_errors(imported):
    d, out = imported
    res = build(d)
    assert not [f for f in res.findings if f["severity"] == "error"]
    rules = {f["rule"] for f in res.findings}
    # warnings a foreign drawing may carry: the layout overlap / general tolerance gaps, plus the
    # E5 placement metrics (they observe any drawing made of primitives, imported ones included)
    allowed = {"overlap", "general_tol"} | {r for r in checks.RULES if r.startswith("place_")}
    assert rules <= allowed, rules
    assert not res.stale
    el = res.d["I.ref"]
    assert el.kind == "import" and el.path == "ref.dxf" and el.counts["dims"] == 8
    code, ctx = lcad(d, "context")
    assert code == 0 and ctx["elements"]["import"][0]["id"] == "I.ref"


def test_viewer_svg_draws_imported_curves_and_suppress_removes_the_import(imported):
    from linercad import svgout

    d, _ = imported
    res = build(d)
    svg = svgout.svg(res.d)
    raws = [e.id for e in res.d.elements if e.kind == "raw"]
    assert len(raws) == 2 and all(f'data-id="{r}"' in svg for r in raws)
    n = len(res.d.elements)
    res.d["I.ref"].suppress()  # the import owns everything it created
    assert [e for e in res.d.elements if e.kind in ("edge", "dim", "note", "raw", "import")] == []
    assert len(res.d.elements) < n


# ---- editing an imported drawing --------------------------------------------------------------------


def test_edit_moves_sets_and_changes_a_dimension_tolerance(imported):
    d, _ = imported
    body = (
        'd["D.dim_1"].tol = "±0.1"\n'
        'd["E.front.2"].role = "thin"\n'
        'd["E.front.6"].move(dy=1)\n'
        'd["D.dim_2"].place(side="right")\n'
        'd["D.dim_4"].tol = "H7"\n'
        'd.notes.tech(["Deburr all edges."])\n'
        'd.q.circles(view="front").where(r=10).near(40, 30, 0.5).one().move(dx=2)'
    )
    code, out = lcad(
        d, "edit", script(d, "e1.py", body), "-m", "tolerances, a thin line, a moved hole"
    )
    assert code == 0, out
    assert out["errors"] == 0 and out["edit"] == "e1"
    assert git(d, "log", "--format=%s").splitlines()[0].startswith("e1 · ")
    m = model(d)
    assert m["D.dim_1"]["intent"]["text"] == "100±0.1"
    assert m["D.dim_4"]["intent"]["text"].startswith("Φ20H7")
    assert m["E.front.2"]["intent"]["role"] == "thin"
    assert m["E.front.6"]["intent"]["p1"][1] == 46.0
    assert m["V.front"] and m["I.ref"]["intent"]["counts"]["dims"] == 8
    # a rebuild replays the log over the import and gives the same result
    code, again = lcad(d, "build")
    assert code == 0 and again["errors"] == 0
    assert model(d)["D.dim_1"]["intent"]["text"] == "100±0.1"
    code, out = lcad(d, "undo", "e1")
    assert code == 0 and model(d)["D.dim_1"]["intent"]["text"] == "100"


def test_import_can_be_an_edit(imported):
    """d.import_dxf is a recorded drawing-level op: a second file lands in another view and replays."""
    d, _ = imported
    extra = make_dxf(
        d / "extra.dxf",
        lambda doc, msp: (
            msp.add_line((0, 0), (40, 0)),
            msp.add_line((40, 0), (40, 20)),
            msp.add_circle((10, 10), 5),
        ),
    )
    assert extra.exists()
    code, out = lcad(
        d, "edit", script(d, "imp.py", 'd.import_dxf("extra.dxf", view="top")'), "-m", "top view"
    )
    assert code == 0, out
    assert out["ops"][0]["op"] == "import_dxf" and out["ops"][0]["id"] == "I.extra"
    assert out["errors"] == 0
    m = model(d)
    assert m["I.extra"]["intent"]["counts"]["edges"] == {"thick": 3}
    assert [k for k in m if k.startswith("E.top.")]
    assert (
        "extra.dxf" in git(d, "ls-files").split()
    )  # a DXF in the drawing dir is a committed source
    code, again = lcad(d, "build")
    assert code == 0 and again["errors"] == 0 and "I.extra" in model(d)


# ---- roles, units, odd input ----------------------------------------------------------------------------


def _role_doc():
    doc = ezdxf.new("R2018", setup=True)
    for name, lt, lw in (
        ("PLAIN", "Continuous", -3),
        ("HIDDEN", "HIDDEN", -3),
        ("AXES", "CENTER2", -3),
        ("PH", "PHANTOM", -3),
        ("LW25", "Continuous", 25),
        ("LW50", "Continuous", 50),
        ("DIMS", "Continuous", -3),
        ("中心线", "Continuous", -3),
        ("ISO", "ACAD_ISO02W100", -3),
    ):
        if lt not in doc.linetypes:
            doc.linetypes.add(lt, pattern=[0.0])
        doc.layers.add(name, linetype=lt, lineweight=lw)
    return doc


@pytest.mark.parametrize(
    ("layer", "attribs", "role"),
    [
        ("PLAIN", {}, "thick"),
        ("HIDDEN", {}, "hidden"),
        ("AXES", {}, "center"),
        ("PH", {}, "phantom"),
        ("LW25", {}, "thin"),
        ("LW50", {}, "thick"),
        ("DIMS", {}, "thin"),
        ("中心线", {}, "center"),
        ("ISO", {}, "hidden"),
        ("PLAIN", {"linetype": "DASHED"}, "hidden"),
        ("PLAIN", {"linetype": "DASHDOT"}, "center"),
        ("HIDDEN", {"linetype": "Continuous"}, "hidden"),  # the layer name still says hidden
        ("PLAIN", {"lineweight": 18}, "thin"),
        ("LW50", {"lineweight": 25}, "thin"),
        ("LW25", {"lineweight": 70}, "thick"),
    ],
)
def test_role_from_linetype_layer_and_lineweight(layer, attribs, role):
    doc = _role_doc()
    e = doc.modelspace().add_line((0, 0), (1, 0), dxfattribs={"layer": layer, **attribs})
    if layer == "LW25" and attribs.get("lineweight") == 70:
        assert importdxf.role_of(doc, e) == "thick"
        return
    assert importdxf.role_of(doc, e) == role


def test_inch_drawings_are_converted_to_mm(tmp_path):
    p = make_dxf(
        tmp_path / "in.dxf",
        lambda doc, msp: (msp.add_line((0, 0), (4, 0)), msp.add_circle((2, 1), 0.5)),
        units_=units.IN,
    )
    d = Drawing(sheet="A3")
    imp = d.import_dxf(str(p))
    line = d.q.lines(view="front").one()
    assert line.length == pytest.approx(101.6) and imp.counts["edges"] == {"thick": 2}
    assert d.q.circles(view="front").one().r == pytest.approx(12.7)
    assert imp._intent["units"] == "in" and imp._intent["unit_factor"] == pytest.approx(25.4)


def test_ocs_mirrored_arcs_and_polyline_arcs_keep_their_geometry(tmp_path):
    def fill(doc, msp):
        a = msp.add_arc((10, 5), 4, 30, 100)
        a.dxf.extrusion = (0, 0, -1)  # mirrored in x: centre (-10, 5), 80..150 degrees
        msp.add_lwpolyline([(0, 0, -1), (10, 0, 0)], format="xyb")  # a negative bulge: clockwise

    p = make_dxf(tmp_path / "ocs.dxf", fill)
    d = Drawing()
    d.import_dxf(str(p))
    arcs = list(d.q.arcs(view="front"))
    a = [x for x in arcs if round(x.center[0], 3) == -10.0][0]
    assert (a.center[1], a.r) == (5.0, 4.0)
    assert (a._intent["start"], a._intent["end"]) == (80.0, 150.0)
    bulge = [x for x in arcs if round(x.center[0], 3) == 5.0][0]  # clockwise: over the chord
    assert bulge.r == pytest.approx(5.0) and bulge.mid[1] == pytest.approx(5.0)


def test_unmapped_dimensions_become_notes_and_degenerate_things_are_counted(tmp_path):
    def fill(doc, msp):
        msp.add_line((0, 0), (50, 0))
        msp.add_line((5, 5), (5, 5))  # zero length
        msp.add_diameter_dim(center=(20, 20), radius=5, angle=45, override={"dimtxt": 2.5}).render()
        msp.add_angular_dim_2l(
            base=(10, 10),
            line1=((0, 0), (30, 0)),
            line2=((0, 0), (20, 30)),
            override={"dimtxt": 2.5},
        ).render()
        h = doc.layers.add("OFF")
        h.off()
        msp.add_line((0, 9), (9, 9), dxfattribs={"layer": "OFF"})
        msp.add_text("kept").set_placement((0, -5))

    p = make_dxf(tmp_path / "odd.dxf", fill)
    d = Drawing()
    imp = d.import_dxf(str(p))
    c = imp.counts
    assert c["edges"] == {"thick": 1} and c["dims"] == 0 and c["dims_as_notes"] == 2
    assert c["notes"] == 2  # only the two dimensions whose geometry was not drawn
    assert c["texts"] == 1
    assert c["skipped"] == {"LINE(degenerate)": 1, "LINE(layer off)": 1}
    note_texts = sorted(n.text for n in d.q.notes())
    plain_texts = sorted(e.text for e in d._els.values() if e.kind == "text")
    assert "Φ10" in note_texts and any(t.endswith("°") for t in note_texts)
    assert plain_texts == ["kept"]


def test_reflex_angles_keep_the_dxf_number_as_text(tmp_path):
    def fill(doc, msp):
        msp.add_line((0, 0), (50, 0))
        msp.add_line((0, 0), (40, 30))
        msp.add_angular_dim_3p(
            base=(30, 10), center=(0, 0), p1=(40, 30), p2=(50, 0), override={"dimtxt": 2.5}
        ).render()

    p = make_dxf(tmp_path / "reflex.dxf", fill)
    dxf_meas = [e for e in ezdxf.readfile(p).modelspace() if e.dxftype() == "DIMENSION"][
        0
    ].get_measurement()
    assert dxf_meas > 180
    d = Drawing()
    d.import_dxf(str(p))
    dim = d.q.dims().one()
    assert dim.type == "angle" and dim.value == pytest.approx(360 - dxf_meas, abs=1e-3)
    assert dim.text == "323.13°"


def test_radius_of_a_whole_circle_is_written_as_a_diameter_with_the_dxf_text(tmp_path):
    def fill(doc, msp):
        msp.add_circle((20, 20), 6)
        msp.add_radius_dim(center=(20, 20), radius=6, angle=30, override={"dimtxt": 2.5}).render()

    p = make_dxf(tmp_path / "rad.dxf", fill)
    d = Drawing()
    d.import_dxf(str(p))
    dim = d.q.dims().one()
    assert dim.type == "dia" and dim.text == "R6"


def test_import_errors_name_the_problem(tmp_path):
    from linercad.errors import NotFound

    d = Drawing()
    with pytest.raises(NotFound) as e:
        d.import_dxf(str(tmp_path / "nope.dxf"))
    assert "nope.dxf" in e.value.message
    p = make_dxf(tmp_path / "ok.dxf", lambda doc, msp: msp.add_line((0, 0), (1, 1)))
    d.import_dxf(str(p))
    d.import_dxf(str(p))  # the same file twice: distinct import IDs
    assert [x.id for x in d.elements if x.kind == "import"] == ["I.ok", "I.ok_2"]
