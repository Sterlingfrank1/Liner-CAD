"""C3 (R15 RED -> GREEN): PNG logo inside title-block cell, 4-way bbox consistency <= 0.2 mm,
`logo_external_ref` check, `lcad export` external image copy and Viewer zip download."""

from __future__ import annotations

import base64
import io
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

import pytest
from PIL import Image as PILImage

from linercad import Drawing, checks, errors, svgout, txn, versions
from linercad.layout import layout
from linercad.render import render_pdf, render_png
from linercad.runtime import build
from linercad.viewer import Viewer


def _write_png(path: Path, size=(40, 20), color=(0, 51, 170, 255)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    im = PILImage.new("RGBA", size, color)
    im.save(path, format="PNG")
    return path


def _png_blue_bbox_mm(png_path: Path, sheet_w: float, sheet_h: float):
    im = PILImage.open(png_path).convert("RGB")
    iw, ih = im.size
    px = im.load()
    xs, ys = [], []
    for y in range(ih):
        for x in range(iw):
            r, g, b = px[x, y]
            if b - max(r, g) > 40:
                xs.append(x)
                ys.append(y)
    assert xs and ys, "no blue logo pixels found in rendered PNG"
    x0 = min(xs) / iw * sheet_w
    x1 = (max(xs) + 1) / iw * sheet_w
    y1 = sheet_h - min(ys) / ih * sheet_h
    y0 = sheet_h - (max(ys) + 1) / ih * sheet_h
    return [x0, y0, x1, y1]


def _pdf_image_bbox_mm(pdf_path: Path):
    raw = pdf_path.read_bytes()
    pt_to_mm = 25.4 / 72.0
    best = None
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        try:
            text = zlib.decompress(m.group(1)).decode("latin1")
        except zlib.error:
            continue
        # Matplotlib embeds raster images with `w 0 0 h x y cm\n.../X... Do` or `a b c d e f cm ... Do`
        for hit in re.finditer(
            r"([\d.eE+-]+)\s+0\s+0\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+cm\s+/(?:Im\w*|I\w+|X\w*)\s+Do",
            text,
        ):
            w, h, x, y = (float(hit.group(k)) * pt_to_mm for k in (1, 2, 3, 4))
            best = [x, y, x + w, y + h]
    assert best is not None, "no raster image placement found in PDF stream"
    return best


def test_logo_api_sizing_alignment_and_validation(tmp_path):
    logo_file = _write_png(tmp_path / "assets" / "logo.png", size=(40, 20))
    p = tmp_path / "d"
    p.mkdir()
    src = """from linercad import Drawing
d = Drawing(sheet="A3", std="GB")
d.view("front").rect((0, 0), 30, 20, name="r")
d.title(name="法兰盘", material="45")
d.logo(cell="T.title.company", path="assets/logo.png", width=20)
"""
    (p / "assets").mkdir(parents=True)
    (p / "assets" / "logo.png").write_bytes(logo_file.read_bytes())
    (p / "drawing.py").write_text(src, encoding="utf-8")

    res = build(p)
    el = res.d["T.title.logo.company"]
    assert el.kind == "logo"
    bx0, by0, bx1, by1 = el.bbox
    assert (bx1 - bx0) == pytest.approx(20.0, abs=1e-4)
    assert (by1 - by0) == pytest.approx(10.0, abs=1e-4)  # 40x20 aspect ratio preserved
    assert "T.title.company" in el.refs

    # Missing file and invalid arguments fail cleanly
    d_bad = Drawing(sheet="A3")
    with pytest.raises(errors.InvalidArgument):
        d_bad.logo(cell="missing_cell", path="assets/logo.png")
    with pytest.raises(errors.InvalidArgument):
        d_bad.logo(cell="company", path="assets/logo.jpg")
    with pytest.raises(errors.InvalidArgument):
        d_bad.logo(cell="company", path="assets/logo.png", width=0)
    with pytest.raises(errors.InvalidArgument):
        d_bad.logo(cell="company", path="assets/logo.png", align="top")

    d_miss = Drawing(sheet="A3")
    d_miss.logo(cell="company", path="missing_logo.png", width=12, height=6)
    with pytest.raises(errors.BuildError) as err:
        layout(d_miss)
    assert "missing_logo.png" in err.value.message


def test_logo_four_outputs_within_0_2mm_and_external_ref_check(tmp_path):
    p = tmp_path / "draw"
    txn.init(p)
    raw_logo = _write_png(p / "assets" / "logo.png", size=(40, 20), color=(0, 51, 170, 255))
    logo_bytes = raw_logo.read_bytes()
    (p / "drawing.py").write_text(
        """from linercad import Drawing
d = Drawing(sheet="A3", std="GB")
d.view("front").rect((0, 0), 30, 20, name="r")
d.title(name="法兰盘", drawing_no="LC-LOGO-01", material="45")
d.logo(cell="company", path="assets/logo.png", width=24, height=10, align="left")
""",
        encoding="utf-8",
    )
    txn.build_commit(p, msg="add company logo")
    res = build(p)
    d = res.d
    expected = d["T.title.logo.company"].bbox
    W, H = d.template["size"]

    # 1) DXF IMAGE entity
    imgs = list(res.doc.modelspace().query("IMAGE"))
    idefs = list(res.doc.objects.query("IMAGEDEF"))
    assert len(imgs) == 1 and len(idefs) == 1
    assert idefs[0].dxf.filename == "assets/logo.png"
    pts = list(imgs[0].boundary_path_wcs())
    dxf_box = [
        min(pt.x for pt in pts),
        min(pt.y for pt in pts),
        max(pt.x for pt in pts),
        max(pt.y for pt in pts),
    ]
    assert dxf_box == pytest.approx(expected, abs=0.2)

    # 2) SVG <image>
    svg_str = svgout.svg(d)
    root = ET.fromstring(svg_str)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    im_node = root.find('.//svg:g[@data-id="T.title.logo.company"]/svg:image', ns)
    assert im_node is not None
    sx, sy = float(im_node.attrib["x"]), float(im_node.attrib["y"])
    sw, sh = float(im_node.attrib["width"]), float(im_node.attrib["height"])
    svg_box = [sx, H - sy - sh, sx + sw, H - sy]
    assert svg_box == pytest.approx(expected, abs=0.2)
    href = im_node.attrib["href"]
    assert href.startswith("data:image/png;base64,")
    assert base64.b64decode(href.split(",", 1)[1]) == logo_bytes

    # 3) PNG rendered from DXF (dpi=300 for ~0.085 mm/px resolution)
    out_png = tmp_path / "check.png"
    render_png(res.doc, (W, H), out_png, dpi=300)
    png_box = _png_blue_bbox_mm(out_png, W, H)
    assert png_box == pytest.approx(expected, abs=0.2)

    # 4) PDF rendered from DXF
    out_pdf = tmp_path / "check.pdf"
    render_pdf(res.doc, (W, H), out_pdf)
    pdf_box = _pdf_image_bbox_mm(out_pdf)
    assert pdf_box == pytest.approx(expected, abs=0.2)

    # logo_external_ref check + accept
    found = [f for f in res.findings if f["rule"] == "logo_external_ref"]
    assert found and found[0]["severity"] == "warn"
    assert found[0]["id"] == "T.title.logo.company"
    assert found[0]["pack"] == "drafting"

    # lcad export copies external image into output dir and lists it in files
    export_dir = tmp_path / "exported"
    exp = versions.export(p, export_dir, formats="dxf,pdf")
    assert exp["ok"]
    copied = export_dir / "assets" / "logo.png"
    assert copied.is_file() and copied.read_bytes() == logo_bytes
    assert any(Path(f).resolve() == copied.resolve() for f in exp["files"])

    # Viewer download packages external image into zip
    v = Viewer(p)
    body, ctype, fname, archive = v.download("dxf")
    assert archive == "zip" and ctype == "application/zip" and fname.endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        assert set(zf.namelist()) == {"drawing.dxf", "assets/logo.png"}
        assert zf.read("assets/logo.png") == logo_bytes


def test_logo_edit_replay(tmp_path):
    p = tmp_path / "e"
    txn.init(p)
    _write_png(p / "assets" / "logo.png", size=(30, 15))
    (p / "drawing.py").write_text(
        """from linercad import Drawing
d = Drawing(sheet="A3")
d.view("front").rect((0, 0), 30, 20, name="r")
d.title(name="零件")
""",
        encoding="utf-8",
    )
    txn.build_commit(p, msg="base")
    s1 = tmp_path / "add_logo.py"
    s1.write_text(
        'def apply(d):\n    d.logo(cell="company", path="assets/logo.png", height=8)\n',
        encoding="utf-8",
    )
    out, res = txn.edit_full(p, s1, "add logo")
    assert out["ok"] and "T.title.logo.company" in res.d
    rebuilt = build(p)
    assert "T.title.logo.company" in rebuilt.d
    assert rebuilt.d["T.title.logo.company"].bbox == pytest.approx(
        res.d["T.title.logo.company"].bbox, abs=0.05
    )
    d_ok = rebuilt.d
    d_ok.accept("logo_external_ref", "T.title.logo.company", "export 时一起复制")
    layout(d_ok)
    assert not [f for f in checks.run(d_ok) if f["rule"] == "logo_external_ref"]
