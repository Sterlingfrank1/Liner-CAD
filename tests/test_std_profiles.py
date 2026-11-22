"""ISO profile, projection method, full title blocks, enterprise overlay (M1/C6, SPEC §6)."""

import json
import tomllib
from importlib import resources

import ezdxf
import pytest

from linercad import cli, commands, rules
from linercad.dxfout import model_dict
from linercad.errors import InvalidArgument
from linercad.layout import Circle, Line, Text
from linercad.model import Drawing
from linercad.runtime import build
from linercad.std import load_std, load_template

KEYS = (
    "name drawing_no material mass scale sheet company designer checker approver process "
    "standardizer date revision stage doc_type"
).split()
SHEETS = ["A4", "A3", "A2", "A1", "A0"]
SERIES = load_std("GB")["text"]["heights"]


def example_text(name, std):
    text = (resources.files("linercad") / "examples" / name / "drawing.py").read_text("utf-8")
    return text.replace('std="GB"', f'std="{std}"')


def build_text(tmp_path, text):
    (tmp_path / "drawing.py").write_text(text, encoding="utf-8")
    return build(tmp_path)


def prims(d, id):
    return d[id]._prims


# ---- ISO profile -------------------------------------------------------------------------------


@pytest.mark.parametrize("std", ["GB", "ISO"])
@pytest.mark.parametrize("name", ["shaft", "flange"])
def test_same_drawing_builds_without_errors_in_both_profiles(tmp_path, name, std):
    res = build_text(tmp_path, example_text(name, std))
    assert res.d.std_name == std
    assert [f for f in res.findings if f["severity"] == "error"] == []


def test_iso_profile_extends_gb_and_cites_iso_numbers():
    gb, iso = load_std("GB"), load_std("ISO")
    assert iso["name"] == "ISO" and "extends" not in iso
    assert set(iso) == set(gb)
    assert iso["text"]["font"] == gb["text"]["font"] and iso["dim"]["decimals"] == 3
    for group, spec in iso.items():
        if group != "name":
            assert "ISO" in spec["basis"] or "convention" in spec["basis"], group
    assert set(iso["checks"]) == set(gb["checks"])
    assert all("GB" not in v for v in iso["checks"].values())
    assert "ISO 21920-1:2021" in iso["rough"]["basis"] and iso["rough"]["std"] == "ISO 1302:2002"
    assert iso["tolerancing"]["gtol_std"] == "ISO 1101:2017"
    assert iso["tolerancing"]["general_note"] == "General tolerances ISO 2768-{cls}"
    assert iso["tech_notes"]["title"] == "NOTES"


def test_iso_findings_cite_iso_standards(tmp_path):
    d = build_text(tmp_path, example_text("shaft", "ISO") + "\nd['D.d1'].tol = 'h7'\n").d
    assert "General tolerances ISO 2768-m" in [
        e._intent["text"] for e in d._els.values() if e.kind == "note"
    ]


# ---- projection method --------------------------------------------------------------------------

TWO_VIEWS = """from linercad import Drawing
d = Drawing(sheet="A3", std="ISO", scale="1:1", projection={proj})
d.view("front").rect((0, 0), 60, 40)
d.view("left").rect((0, 0), 30, 40)
"""


@pytest.mark.parametrize(
    "proj,left_of_front", [("None", False), ('"first"', False), ('"third"', True)]
)
def test_third_angle_puts_left_view_left_of_front(tmp_path, proj, left_of_front):
    d = build_text(tmp_path, TWO_VIEWS.format(proj=proj)).d
    left, front = d.view("left")._resolved["origin"][0], d.view("front")._resolved["origin"][0]
    assert (left < front) is left_of_front


def test_unknown_projection_lists_candidates():
    with pytest.raises(InvalidArgument) as ei:
        Drawing(projection="second")
    assert ei.value.candidates == ["first", "third"]


def _symbol(d):
    tb = d.template["title_block"]
    ox, oy = tb["origin"]
    box = (ox, oy, ox + tb["size"][0], oy + tb["size"][1])
    ps = prims(d, "T.frame")
    circles = [p for p in ps if isinstance(p, Circle) and p.layer == "thick"]
    cone = [
        p
        for p in ps
        if isinstance(p, Line) and p.p[0] != p.q[0] and p.p[1] != p.q[1] and p.layer == "thick"
    ]
    return box, circles, cone


@pytest.mark.parametrize("std", ["GB", "ISO"])
@pytest.mark.parametrize("proj,circles_right", [("first", True), ("third", False)])
def test_projection_symbol_is_a_cone_and_circles_mirrored_by_method(std, proj, circles_right):
    d = Drawing(sheet="A3", std=std, projection=proj)
    from linercad.layout import layout

    layout(d)
    box, circles, cone = _symbol(d)
    assert len(circles) == 2 and len(cone) == 2  # concentric circles; the cone's two slanted sides
    assert circles[0].c == circles[1].c
    for c in circles:
        assert box[0] <= c.c[0] - c.r and c.c[0] + c.r <= box[2]
        assert box[1] <= c.c[1] - c.r and c.c[1] + c.r <= box[3]
    cone_x = sum(p.p[0] + p.q[0] for p in cone) / (2 * len(cone))
    assert (circles[0].c[0] > cone_x) is circles_right


# ---- title blocks ---------------------------------------------------------------------------------


@pytest.mark.parametrize("std", ["GB", "ISO"])
@pytest.mark.parametrize("sheet", SHEETS)
def test_both_profiles_have_the_same_title_field_keys(std, sheet):
    d = Drawing(sheet=sheet, std=std)
    assert [k for k in KEYS if d.get(f"T.title.{k}") is None] == []
    assert load_template(std, sheet)["title_block"]["size"][0] <= 180.0


def _vlines_at(tb, y):
    return sorted(
        {
            ln["p1"][0]
            for ln in tb["lines"]
            if ln["p1"][0] == ln["p2"][0] and ln["p1"][1] <= y <= ln["p2"][1]
        }
    )


def test_gb_block_is_the_full_gb_t_10609_1_layout():
    tb = load_template("GB", "A3")["title_block"]
    assert tb["size"] == [180.0, 56.0]
    xs = _vlines_at(tb, 31.5)  # the header row of the change zone
    assert [b - a for a, b in zip(xs[:7], xs[1:7])] == [10, 10, 16, 16, 12, 16]
    ys = {ln["p1"][1] for ln in tb["lines"] if ln["p1"][1] == ln["p2"][1] and ln["p1"][0] == 0}
    assert {7.0, 14.0, 21.0, 28.0, 35.0, 42.0, 49.0} <= ys  # rows of 7 mm in the left zone
    words = {lb["text"] for lb in tb["labels"]}
    zone_words = (
        "标记 处数 分区 更改文件号 签名 年月日 设计 审核 工艺 批准 标准化 材料标记 阶段标记 重量 比例"
    ).split()
    assert set(zone_words) <= words


def test_iso_block_has_the_iso_7200_fields_in_english():
    tb = load_template("ISO", "A3")["title_block"]
    labels = {f["label"] for f in tb["fields"].values()}
    mandatory = {
        "Legal owner",
        "Identification number",
        "Revision index",
        "Date of issue",
        "Sheet",
        "Title",
        "Document type",
        "Created by",
        "Approved by",
    }
    assert mandatory <= labels and {"Scale", "Material", "Mass"} <= labels
    assert all(lb["text"].isascii() for lb in tb["labels"])


LONG = dict(
    name="一个特别长的图样名称" * 4,
    drawing_no="LC-VERY-LONG-DRAWING-NUMBER-2026-0001-REV-B",
    company="某某某某机械制造股份有限公司第三分厂工艺装备研究所",
    material="45 钢调质处理后表面发黑",
    date="2026-05-06",
    designer="张三丰",
)


@pytest.mark.parametrize("std", ["GB", "ISO"])
def test_title_values_shrink_to_the_height_series(tmp_path, std):
    text = f"""from linercad import Drawing
d = Drawing(sheet="A3", std="{std}", scale="1:1")
d.view("front").rect((0, 0), 60, 40)
d.title(**{LONG!r})
"""
    res = build_text(tmp_path, text)
    d = res.d
    spec = d.template["title_block"]["fields"]["name"]
    for key in LONG:
        hs = {p.height for p in prims(d, f"T.title.{key}") if isinstance(p, Text)}
        assert hs and hs <= set(SERIES), (key, hs)
    name_h = prims(d, "T.title.name")[0].height
    assert name_h < spec["height"]
    assert not [f for f in res.findings if f["rule"] == "text_height"]


# ---- enterprise overlay ---------------------------------------------------------------------


def company_dxf(path):
    doc = ezdxf.new("R2018", setup=["linetypes"])
    for name, color, lw, lt in [
        ("THICK", 7, 70, "Continuous"),
        ("THIN", 3, 35, "Continuous"),
        ("CENTER", 1, 35, "CENTER"),
        ("HIDDEN", 2, 35, "HIDDEN"),
        ("DIM", 3, 35, "Continuous"),
    ]:
        doc.layers.add(name, color=color, lineweight=lw, linetype=lt)
    style = doc.dimstyles.get("Standard")
    style.dxf.dimtxt = 2.5
    style.dxf.dimasz = 2.5
    blk = doc.blocks.new("TITLE_BLOCK")
    blk.add_lwpolyline([(0, 0), (150, 0), (150, 35), (0, 35)], close=True)
    blk.add_line((0, 17.5), (150, 17.5))
    blk.add_line((40, 0), (40, 35))
    blk.add_line((100, 0), (100, 17.5))
    for tag, at, h in [
        ("PART_NAME", (42, 20), 7.0),
        ("DWG_NO", (42, 3), 5.0),
        ("MATERIAL", (102, 3), 3.5),
        ("DRAWN_BY", (2, 3), 3.5),
        ("ZONE", (2, 20), 3.5),
    ]:
        blk.add_attdef(tag, insert=at, height=h)
    doc.saveas(path)


SHAFT_ACME = example_text("shaft", "GB").replace('std="GB",', 'std="GB", overlay="acme",')


@pytest.fixture
def acme(tmp_path):
    company_dxf(tmp_path / "acme.dxf")
    out = commands.template_import(tmp_path, tmp_path / "acme.dxf", "acme")
    return tmp_path, out


def test_template_import_writes_the_overlay(acme):
    tmp, out = acme
    ov = tomllib.loads((tmp / "templates" / "acme.toml").read_text(encoding="utf-8"))
    assert out["ok"] and out["path"] == "templates/acme.toml"
    lines = ov["std"]["lines"]
    assert (lines["thick"]["width"], lines["thin"]["width"]) == (0.7, 0.35)
    assert ov["std"]["dim"]["text_height"] == 2.5 and ov["std"]["dim"]["arrow_length"] == 2.5
    tb = ov["title_block"]
    assert tb["size"] == [150.0, 35.0]
    # ATTDEF tags map to the common field keys; the unknown one keeps its own key
    assert set(tb["fields"]) == {"name", "drawing_no", "material", "designer", "zone"}
    name = tb["fields"]["name"]
    assert name["box"][0] >= 40 and name["box"][1] >= 17.5 and name["box"][2] <= 150


def test_template_import_cli(tmp_path, capsys):
    company_dxf(tmp_path / "acme.dxf")
    argv = ["-C", str(tmp_path), "template", "import", str(tmp_path / "acme.dxf"), "--name", "acme"]
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert (tmp_path / "templates" / "acme.toml").exists() and "template" in cli.COMMANDS


def test_overlay_makes_the_company_practice_legal(acme):
    tmp, _ = acme
    res = build_text(tmp, SHAFT_ACME)
    d = res.d
    assert d.overlay == "acme" and d.template["title_block"]["size"] == [150.0, 35.0]
    assert [f for f in res.findings if f["pack"] == "drafting"] == []
    dim_heights = {
        t.height
        for e in d._els.values()
        if e.kind == "dim"
        for t in e._prims
        if isinstance(t, Text)
    }
    assert 2.5 in dim_heights
    model = model_dict(d)
    assert model["drawing"]["overlay"] == "acme" and model["drawing"]["projection"] == "first"
    # the same drawing judged by the plain GB profile is not legal: the overlay is what allows it
    d.std = load_std("GB")
    found, _ = rules.text_height(d)
    assert found and all(f["rule"] == "text_height" for f in found)


def test_missing_overlay_lists_the_available_ones(acme):
    tmp, _ = acme
    with pytest.raises(InvalidArgument) as ei:
        build_text(tmp, SHAFT_ACME.replace('"acme"', '"nope"'))
    assert ei.value.candidates == ["acme"]
