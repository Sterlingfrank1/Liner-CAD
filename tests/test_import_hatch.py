"""C3: DXF HATCH import as section-lining (hatch) elements (issue #78)."""

from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
from ezdxf import units

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "evals"))

import dxf_import as metrics  # noqa: E402

from linercad import Drawing, importdxf  # noqa: E402
from linercad.layout import layout  # noqa: E402


def _doc():
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    return doc


def make_pattern_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    h.set_pattern_fill("ANSI31", scale=2.0, angle=45.0)
    h.paths.add_polyline_path([(0, 0), (40, 0), (40, 20), (0, 0)])
    doc.saveas(path)
    return path


def make_edge_path_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    h.set_pattern_fill("ANSI31", scale=0.5, angle=0.0)
    p = h.paths.add_edge_path()
    p.add_arc((0, 0), 20, 0, 90)  # quarter arc boundary, (20,0) -> (0,20)
    p.add_line((0, 20), (40, 20))
    p.add_line((40, 20), (40, 0))
    p.add_line((40, 0), (20, 0))
    doc.saveas(path)
    return path


def make_islands_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    h.set_pattern_fill("ANSI31", scale=1.0, angle=45.0)
    h.paths.add_polyline_path([(0, 0), (60, 0), (60, 40), (0, 40), (0, 0)])
    h.paths.add_polyline_path([(20, 15), (40, 15), (40, 30), (20, 30), (20, 15)])
    doc.saveas(path)
    return path


def make_solid_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    h.set_solid_fill(color=7)
    h.paths.add_polyline_path([(0, 0), (30, 0), (30, 15), (0, 15), (0, 0)])
    doc.saveas(path)
    return path


def make_gradient_dxf(path):
    doc = _doc()
    msp = doc.modelspace()
    h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    h.set_gradient(color1=(255, 0, 0), color2=(0, 0, 255))
    h.paths.add_polyline_path([(0, 0), (10, 0), (10, 10), (0, 0)])
    doc.saveas(path)
    return path


def imported(path):
    d = Drawing(sheet="A3")
    imp = importdxf.import_dxf(d, str(path))
    layout(d)
    hatches = [e for e in d._els.values() if e.kind == "hatch"]
    return d, imp, hatches


def _bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _points(loop):
    return loop["points"] if isinstance(loop, dict) else loop


def test_partial_boundaries_are_reported_but_keep_the_hatch(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    h.set_pattern_fill("ANSI31", scale=1.0, angle=45.0)
    h.paths.add_edge_path()  # empty boundary path: reported, not fatal
    h.paths.add_polyline_path([(0, 0), (20, 0), (20, 10), (0, 0)])
    path = tmp_path / "partial.dxf"
    doc.saveas(path)
    _d, imp, hatches = imported(path)
    assert len(hatches) == 1 and imp.counts["hatches"] == 1
    warnings = imp.counts["hatch_warnings"]
    assert warnings and any("path 1" in w["reason"] for w in warnings)
    assert hatches[0]._intent["dropped_paths"]
    assert any("path 1" in d for d in hatches[0]._intent["dropped_paths"])


def test_pattern_hatch_becomes_a_hatch_element(tmp_path):
    _d, imp, hatches = imported(make_pattern_dxf(tmp_path / "p.dxf"))
    assert len(hatches) == 1
    e = hatches[0]
    assert e.kind == "hatch"
    assert e._intent.get("pattern") == "ANSI31"
    assert abs(e._intent.get("angle", -999) - 45.0) <= 0.01
    assert abs(e._intent.get("scale", -999) - 2.0) <= 0.01
    assert e._intent.get("solid") is False
    loops = e._intent["loops"]
    assert len(loops) == 1
    b = _bbox(_points(loops[0]))
    assert abs(b[0] - 0.0) <= 0.01 and abs(b[1] - 0.0) <= 0.01
    assert abs(b[2] - 40.0) <= 0.01 and abs(b[3] - 20.0) <= 0.01
    assert imp.counts["hatches"] == 1
    assert imp.counts["from"]["hatches"] == {"HATCH": 1}
    assert e._prims and any(hasattr(p, "loops") for p in e._prims)


def test_edge_path_boundary_keeps_arc_geometry(tmp_path):
    _d, imp, hatches = imported(make_edge_path_dxf(tmp_path / "e.dxf"))
    assert len(hatches) == 1 and imp.counts["hatches"] == 1
    points = _points(hatches[0]._intent["loops"][0])
    assert len(points) > 4  # the quarter arc is flattened, not dropped
    b = _bbox(points)
    assert abs(b[0] + 0.0) <= 0.01 and abs(b[1] - 0.0) <= 0.01
    assert abs(b[2] - 40.0) <= 0.01 and abs(b[3] - 20.0) <= 0.01
    # every flattened point lies on the boundary within the 0.01 mm tolerance
    for x, y in points:
        on_rect = min(abs(x), abs(x - 40), abs(y), abs(y - 20)) <= 0.011
        on_arc = abs((x * x + y * y) ** 0.5 - 20.0) <= 0.05
        assert on_rect or on_arc, (x, y)


def test_islands_are_kept_as_separate_loops(tmp_path):
    _d, _imp, hatches = imported(make_islands_dxf(tmp_path / "i.dxf"))
    assert len(hatches) == 1
    loops = hatches[0]._intent["loops"]
    assert len(loops) == 2
    outer = _bbox(_points(loops[0]))
    inner = _bbox(_points(loops[1]))
    assert abs(outer[2] - 60.0) <= 0.01 and abs(inner[2] - 40.0) <= 0.01


def test_solid_fill_is_kept_as_a_solid_hatch(tmp_path):
    _d, imp, hatches = imported(make_solid_dxf(tmp_path / "s.dxf"))
    assert len(hatches) == 1 and imp.counts["hatches"] == 1
    e = hatches[0]
    assert e._intent.get("solid") is True
    b = _bbox(_points(e._intent["loops"][0]))
    assert abs(b[2] - 30.0) <= 0.01 and abs(b[3] - 15.0) <= 0.01


def test_unrepresentable_hatches_are_reported(tmp_path):
    _d, imp, hatches = imported(make_gradient_dxf(tmp_path / "g.dxf"))
    assert hatches == []
    assert imp.counts["hatches"] == 0
    assert imp.counts["skipped"], imp.counts
    assert any("gradient" in str(k).lower() for k in imp.counts["skipped"]), imp.counts["skipped"]
    reasons = imp.counts.get("hatch_skipped", [])
    assert reasons and any("gradient" in r["reason"].lower() for r in reasons)


def _lcad(dir, *args):
    import json
    import subprocess

    r = subprocess.run(
        [sys.executable, "-m", "linercad", "-C", str(dir), *args], capture_output=True
    )
    return r.returncode, json.loads(r.stdout.decode("utf-8"))


def test_pattern_angle_and_scale_survive_the_build(tmp_path):
    src = make_pattern_dxf(tmp_path / "p.dxf")
    d = tmp_path / "part"
    code, out = _lcad(tmp_path, "init", str(d), "--from-dxf", str(src))
    assert code == 0, out
    doc = ezdxf.readfile(d / ".linercad/build/drawing.dxf")
    hatch = next(e for e in doc.modelspace().query("HATCH"))
    assert hatch.dxf.pattern_name == "ANSI31"
    assert abs(hatch.dxf.pattern_angle - 45.0) <= 1e-6
    assert abs(hatch.dxf.pattern_scale - 2.0) <= 1e-6
    assert len(list(hatch.paths)) == 1


def test_solid_fill_survives_the_build(tmp_path):
    src = make_solid_dxf(tmp_path / "s.dxf")
    d = tmp_path / "part"
    code, out = _lcad(tmp_path, "init", str(d), "--from-dxf", str(src))
    assert code == 0, out
    doc = ezdxf.readfile(d / ".linercad/build/drawing.dxf")
    hatch = next(e for e in doc.modelspace().query("HATCH"))
    assert hatch.dxf.solid_fill == 1  # ezdxf may still carry the placeholder name SOLID


def test_arc_sampling_meets_the_001_mm_tolerance():
    for r in (20.0, 1000.0):
        pts = importdxf._arc_points((0.0, 0.0), r, 0.0, 90.0)
        for a, b in zip(pts, pts[1:]):
            mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
            sagitta = r - (mx * mx + my * my) ** 0.5
            assert sagitta <= 0.01 + 1e-9, (r, sagitta)


def test_predefined_pattern_without_equivalent_is_reported(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    h.set_pattern_fill("ANSI37", scale=1.0, angle=0.0)
    h.paths.add_polyline_path([(0, 0), (10, 0), (10, 10), (0, 0)])
    src = tmp_path / "ansi37.dxf"
    doc.saveas(src)
    _d, imp, hatches = imported(src)
    assert hatches == []
    skipped = imp.counts["hatch_skipped"]
    assert skipped and skipped[0]["handle"] and skipped[0]["layer"]
    assert "ANSI37" in skipped[0]["reason"]
    assert any("ANSI37" in key for key in imp.counts["skipped"])


def test_open_and_zero_area_boundaries_are_reported(tmp_path):
    doc = _doc()
    msp = doc.modelspace()
    h = msp.add_hatch(dxfattribs={"layer": "HATCH"})
    h.set_pattern_fill("ANSI31", scale=1.0, angle=45.0)
    p = h.paths.add_edge_path()
    p.add_line((0, 0), (10, 0))
    p.add_line((10.1, 0), (10.1, 10))  # 0.1 mm gap: open boundary
    p.add_line((10.1, 10), (0, 10))
    p.add_line((0, 10), (0, 0))
    h.paths.add_polyline_path([(0, 0), (5, 0), (10, 0), (0, 0)])  # zero area
    src = tmp_path / "open.dxf"
    doc.saveas(src)
    _d, imp, hatches = imported(src)
    assert hatches == []
    reasons = " ".join(r["reason"] for r in imp.counts["hatch_skipped"])
    assert "open boundary" in reasons and "zero-area" in reasons


def test_c1_metric_records_the_hatch(tmp_path):
    entry = metrics.evaluate_file(make_pattern_dxf(tmp_path / "p.dxf"))
    h = entry["metrics"]["hatch_retention"]
    assert h["source"] == 1 and h["retained"] == 1 and h["rate"] == 1.0
    by_type = entry["metrics"]["entity_retention"]["by_type"]["HATCH"]
    assert by_type["rate"] == 1.0
    assert entry["inspect"]["maps_to"]["hatches"] == {"HATCH": 1}


def test_c1_metric_reports_unrepresentable_hatch_as_skipped(tmp_path):
    entry = metrics.evaluate_file(make_gradient_dxf(tmp_path / "g.dxf"))
    h = entry["metrics"]["hatch_retention"]
    assert h["source"] == 1 and h["retained"] == 0
    assert entry["import"]["counts"]["hatch_skipped"]
