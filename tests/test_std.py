"""Standard profile (GB) and sheet templates: SPEC §6, card C2."""

import copy
import re

import pytest

from linercad.errors import InvalidArgument
from linercad.std import deep_merge, load_std, load_template

SHEETS = ["A4", "A3", "A2", "A1", "A0"]
CASES = [(std, sheet) for std in ("GB", "ISO") for sheet in SHEETS]
FIELDS = [
    "name",
    "drawing_no",
    "material",
    "scale",
    "mass",
    "sheet",
    "company",
    "designer",
    "checker",
    "date",
]
GROUPS = {
    "lines",
    "wavy",
    "checks",
    "tolerancing",
    "datum",
    "rough",
    "linetypes",
    "text",
    "dim",
    "center",
    "note",
    "hatch",
    "section",
    "views",
    "scales",
    "sheets",
    "title_block",
    "tech_notes",
    "placement",  # E5: D.place / A.place numeric conventions
    "assembly",  # D3: balloon diameter / gap (δ) / alignment tolerance
}


@pytest.fixture(scope="module")
def gb():
    return load_std("GB")


# --------------------------------------------------------------------------- gb.toml values


def test_assembly_values_are_shared_between_gb_and_iso():
    gb = load_std("GB")["assembly"]
    iso = load_std("ISO")["assembly"]
    for key in ("balloon_height", "balloon_radius", "balloon_offset"):
        assert gb[key] == iso[key], key
    # δ / alignment tolerance have a single source: the E5 placement table
    for table in (gb, iso):
        assert "balloon_gap" not in table and "balloon_align_tol" not in table
    for name in ("GB", "ISO"):
        placement = load_std(name)["placement"]
        assert placement["balloon_clearance"] > 0 and placement["balloon_align_tol"] > 0


def test_name(gb):
    assert gb["name"] == "GB"


def test_group_set_is_exactly_the_documented_one(gb):
    assert set(gb) - {"name"} == GROUPS


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_every_group_has_a_basis(gb, group):
    basis = gb[group].get("basis")
    assert isinstance(basis, str) and basis.strip(), f"[{group}] needs a non-empty basis"


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_basis_names_a_standard_or_says_convention(gb, group):
    # "no number without a source": a GB/T number, or the word convention
    assert re.search(r"GB/T \d+|convention", gb[group]["basis"]), gb[group]["basis"]


def test_line_widths_and_ratio(gb):
    lines = gb["lines"]
    assert lines["thick"]["width"] == 0.5
    assert lines["thin"]["width"] == 0.25
    assert lines["section"]["width"] == 0.7
    assert lines["thick"]["width"] / lines["thin"]["width"] == 2
    for role in ("hidden", "center", "phantom", "dim", "text", "hatch"):
        assert lines[role]["width"] == 0.25, role


def test_line_colors_layers_linetypes(gb):
    lines = gb["lines"]
    colors = {r: lines[r]["color"] for r in lines if r != "basis"}
    assert colors == {
        "thick": 7,
        "thin": 3,
        "hidden": 2,
        "center": 1,
        "phantom": 6,
        "dim": 3,
        "text": 3,
        "hatch": 3,
        "section": 7,
    }
    for role, spec in lines.items():
        if role != "basis":
            assert spec["layer"] == role.upper()
    assert lines["hidden"]["linetype"] == "LC_HIDDEN"
    assert lines["center"]["linetype"] == "LC_CENTER"
    assert lines["phantom"]["linetype"] == "LC_PHANTOM"


def test_every_line_role_uses_a_defined_linetype(gb):
    known = {"CONTINUOUS"} | {k for k in gb["linetypes"] if k != "basis"}
    layers = []
    for role, spec in gb["lines"].items():
        if role == "basis":
            continue
        assert spec["linetype"] in known, role
        layers.append(spec["layer"])
    assert len(layers) == len(set(layers)) == 9


def test_linetype_patterns(gb):
    lt = gb["linetypes"]
    assert lt["LC_HIDDEN"]["pattern"] == [4.0, -1.0]
    assert lt["LC_CENTER"]["pattern"] == [20.0, -3.0, 0.5, -3.0]
    assert lt["LC_PHANTOM"]["pattern"] == [20.0, -3.0, 0.5, -3.0, 0.5, -3.0]
    for name in ("LC_HIDDEN", "LC_CENTER", "LC_PHANTOM"):
        assert lt[name]["description"]
        # centre line and phantom line start with a long dash and end with a gap
        assert lt[name]["pattern"][0] > 0 and lt[name]["pattern"][-1] < 0


def test_text_style(gb):
    t = gb["text"]
    assert t["font"] == "simfang.ttf"
    assert t["width_factor"] == 0.7
    assert t["heights"] == [1.8, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0, 20.0]
    assert t["cjk_em"] == 1.463
    assert t["char_width"]["cjk"] == 1.463
    assert 0.73 <= t["char_width"]["other"] <= 0.74


def test_dim_numbers(gb):
    d = gb["dim"]
    assert d["text_height"] == 3.5
    assert d["arrow_length"] == 3.0
    assert d["arrow_width"] == 1.0
    assert d["ext_beyond"] == 2.0
    assert d["ext_gap"] == 0.0
    assert d["text_gap"] == 1.0
    assert d["first_row"] == 10.0
    assert d["row_pitch"] == 7.0
    assert d["max_rows"] == 6
    assert d["clearance"] == 0.5
    assert d["decimals"] == 3


def test_center_note_hatch_section(gb):
    assert gb["center"]["extend"] == 3.0
    assert gb["note"]["leader_length"] == 8.0
    assert gb["note"]["shoulder_gap"] == 1.0
    assert gb["note"]["text_height"] == 3.5
    h = gb["hatch"]
    assert (h["pattern"], h["angle"], h["spacing"]) == ("ANSI31", 45.0, 3.0)
    s = gb["section"]
    assert s["stroke_length"] == 6.0
    assert s["stroke_gap"] == 2.0
    assert s["arrow_length"] == 6.0
    assert s["letter_height"] == 5.0
    assert s["label_height"] == 5.0
    assert s["label_gap"] == 4.0


def test_views_first_angle_positions(gb):
    v = gb["views"]
    assert v["projection"] == "first"
    assert v["gap"] == 8.0
    assert v["positions"]["first"] == {
        "top": [0, -1],
        "bottom": [0, 1],
        "left": [1, 0],
        "right": [-1, 0],
        "rear": [2, 0],
    }


def test_views_third_angle_is_the_mirror_of_first(gb):
    first, third = gb["views"]["positions"]["first"], gb["views"]["positions"]["third"]
    for name in ("top", "bottom", "left", "right"):
        assert third[name] == [-c for c in first[name]], name
    assert third["rear"] == first["rear"] == [2, 0]


def test_sheets_and_margins(gb):
    s = gb["sheets"]
    assert s["A0"] == [841.0, 1189.0]
    assert s["A1"] == [594.0, 841.0]
    assert s["A2"] == [420.0, 594.0]
    assert s["A3"] == [297.0, 420.0]
    assert s["A4"] == [210.0, 297.0]
    assert s["binding"] == 25.0
    assert s["margin"] == {"A0": 10.0, "A1": 10.0, "A2": 10.0, "A3": 5.0, "A4": 5.0}


def test_scales(gb):
    s = gb["scales"]
    assert s["preferred"] == ["1:1", "1:2", "1:5", "1:10", "2:1", "5:1", "10:1"]
    assert s["allowed"] == ["1:1.5", "1:2.5", "1:3", "1:4", "1:6", "2.5:1", "4:1"]


def test_title_block_and_tech_notes(gb):
    assert gb["title_block"]["size"] == [180.0, 56.0]
    t = gb["tech_notes"]
    assert t["title"] == "技术要求"
    assert t["title_height"] == 5.0
    assert t["height"] == 3.5
    assert t["line_spacing"] == 1.6
    assert t["gap"] == 5.0


def test_all_text_heights_come_from_the_height_series(gb):
    series = gb["text"]["heights"]
    for value in (
        gb["dim"]["text_height"],
        gb["note"]["text_height"],
        gb["section"]["letter_height"],
        gb["section"]["label_height"],
        gb["tech_notes"]["title_height"],
        gb["tech_notes"]["height"],
    ):
        assert value in series


# --------------------------------------------------------------------------- deep_merge


def test_deep_merge_recurses_into_dicts():
    base = {"a": {"x": 1, "y": {"p": 1, "q": 2}}, "b": 1}
    over = {"a": {"y": {"q": 9}}}
    assert deep_merge(base, over) == {"a": {"x": 1, "y": {"p": 1, "q": 9}}, "b": 1}


def test_deep_merge_replaces_scalars_and_lists_whole():
    base = {"n": 1, "xs": [1, 2, 3], "d": {"ys": [[0, 1], [2, 3]]}}
    over = {"n": 2.5, "xs": [9], "d": {"ys": [[7, 7]]}}
    assert deep_merge(base, over) == {"n": 2.5, "xs": [9], "d": {"ys": [[7, 7]]}}


def test_deep_merge_over_adds_new_keys_and_keeps_untouched_ones():
    assert deep_merge({"a": 1}, {"b": {"c": 2}}) == {"a": 1, "b": {"c": 2}}


def test_deep_merge_type_changes_take_the_overlay():
    assert deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}
    assert deep_merge({"a": 5}, {"a": {"b": 1}}) == {"a": {"b": 1}}
    assert deep_merge({"a": [1]}, {"a": {"b": 1}}) == {"a": {"b": 1}}


def test_deep_merge_does_not_mutate_or_alias_its_inputs():
    base = {"a": {"x": [1, 2]}, "k": 1}
    over = {"a": {"z": [3]}, "m": {"n": [4]}}
    base_before, over_before = copy.deepcopy(base), copy.deepcopy(over)
    result = deep_merge(base, over)
    assert base == base_before and over == over_before
    # editing the result must not leak back into either input
    result["a"]["x"].append(99)
    result["a"]["z"].append(99)
    result["m"]["n"].append(99)
    assert base == base_before and over == over_before


def test_deep_merge_empty_overlay_is_a_copy():
    base = {"a": {"x": [1]}}
    result = deep_merge(base, {})
    assert result == base and result is not base and result["a"] is not base["a"]


# --------------------------------------------------------------------------- load_std


def test_load_std_returns_a_fresh_copy_each_time():
    a, b = load_std("GB"), load_std("GB")
    assert a == b and a is not b
    a["dim"]["first_row"] = 99.0
    a["text"]["heights"].append(99.0)
    assert load_std("GB")["dim"]["first_row"] == 10.0
    assert load_std("GB")["text"]["heights"][-1] == 20.0


def test_overlay_dict_recursive_keeps_siblings_and_basis(gb):
    out = load_std("GB", overlays=[{"dim": {"text_height": 2.5}}])
    assert out["dim"]["text_height"] == 2.5
    assert out["dim"]["first_row"] == 10.0
    assert out["dim"]["basis"] == gb["dim"]["basis"]
    assert out["lines"] == gb["lines"]


def test_overlay_scalar_replaced(gb):
    out = load_std("GB", [{"views": {"gap": 12.0, "projection": "third"}}])
    assert out["views"]["gap"] == 12.0 and out["views"]["projection"] == "third"
    assert out["views"]["positions"] == gb["views"]["positions"]


def test_overlay_list_replaced_whole():
    out = load_std("GB", [{"text": {"heights": [3.5, 5.0]}, "scales": {"preferred": ["1:1"]}}])
    assert out["text"]["heights"] == [3.5, 5.0]
    assert out["scales"]["preferred"] == ["1:1"]
    assert out["scales"]["allowed"][0] == "1:1.5"


def test_overlay_nested_inline_table_and_list_inside_it():
    out = load_std(
        "GB",
        [{"lines": {"thick": {"width": 0.7}}, "views": {"positions": {"first": {"top": [0, -2]}}}}],
    )
    assert out["lines"]["thick"] == {
        "layer": "THICK",
        "width": 0.7,
        "color": 7,
        "linetype": "CONTINUOUS",
    }
    assert out["views"]["positions"]["first"]["top"] == [0, -2]
    assert out["views"]["positions"]["first"]["bottom"] == [0, 1]


def test_overlays_apply_in_order_later_wins():
    out = load_std(
        "GB", [{"dim": {"first_row": 12.0}}, {"dim": {"first_row": 14.0, "row_pitch": 8.0}}]
    )
    assert out["dim"]["first_row"] == 14.0 and out["dim"]["row_pitch"] == 8.0


def test_overlays_accept_tuple_and_do_not_change_the_overlay_or_the_builtin():
    overlay = {"dim": {"decimals": 2}}
    before = copy.deepcopy(overlay)
    assert load_std("GB", (overlay,))["dim"]["decimals"] == 2
    assert overlay == before
    assert load_std("GB")["dim"]["decimals"] == 3


def test_overlay_may_add_new_groups():
    out = load_std("GB", [{"company": {"basis": "convention", "logo": "x.svg"}}])
    assert out["company"]["logo"] == "x.svg"


def test_single_dict_instead_of_a_list_is_rejected_with_a_hint():
    with pytest.raises(InvalidArgument) as ei:
        load_std("GB", {"dim": {"text_height": 2.5}})
    assert ei.value.hint and "[" in ei.value.hint


def test_non_dict_overlay_entry_is_rejected():
    with pytest.raises(InvalidArgument) as ei:
        load_std("GB", [{"dim": {}}, "dim"])
    assert ei.value.values.get("index") == 1


# --------------------------------------------------------------------------- errors


@pytest.mark.parametrize("bad", ["XYZ", "", "GB-A3"])
def test_unknown_std_raises_with_candidates(bad):
    with pytest.raises(InvalidArgument) as ei:
        load_std(bad)
    assert ei.value.code == "invalid_arg"
    assert ei.value.candidates == ["GB", "ISO"]
    assert repr(bad) in ei.value.message


def test_non_string_std_raises():
    with pytest.raises(InvalidArgument):
        load_std(None)  # type: ignore[arg-type]


def test_unknown_sheet_raises_with_candidates():
    with pytest.raises(InvalidArgument) as ei:
        load_template("GB", "A5")
    assert ei.value.code == "invalid_arg"
    assert ei.value.candidates == ["A0", "A1", "A2", "A3", "A4"]
    assert "A5" in ei.value.message


@pytest.mark.parametrize("bad", ["", "a3", "GB-A3", None])
def test_bad_sheet_names_raise(bad):
    with pytest.raises(InvalidArgument):
        load_template("GB", bad)  # type: ignore[arg-type]


def test_template_for_unknown_std_raises():
    with pytest.raises(InvalidArgument) as ei:
        load_template("XYZ", "A3")
    assert ei.value.candidates == ["GB", "ISO"]


# --------------------------------------------------------------------------- templates


def tb_of(sheet, std="GB"):
    return load_template(std, sheet)["title_block"]


def test_template_sizes_and_margins():
    a4, a3, a2 = (load_template("GB", s) for s in ("A4", "A3", "A2"))
    assert a4["size"] == [210.0, 297.0] and a4["margins"] == [25.0, 5.0, 5.0, 5.0]
    assert a3["size"] == [420.0, 297.0] and a3["margins"] == [25.0, 5.0, 5.0, 5.0]
    assert a2["size"] == [594.0, 420.0] and a2["margins"] == [25.0, 10.0, 10.0, 10.0]
    for sheet, t in (("A4", a4), ("A3", a3), ("A2", a2)):
        assert t["name"] == f"GB-{sheet}" and t["sheet"] == sheet


@pytest.mark.parametrize("sheet", SHEETS)
def test_template_agrees_with_the_gb_profile(gb, sheet):
    t = load_template("GB", sheet)
    w, h = gb["sheets"][sheet]
    # A4 is portrait, A3 / A2 landscape; the long side of the paper is the same one as in gb.toml
    assert sorted(t["size"]) == sorted([w, h])
    assert t["size"] == ([w, h] if sheet == "A4" else [h, w])
    c = gb["sheets"]["margin"][sheet]
    assert t["margins"] == [gb["sheets"]["binding"], c, c, c]
    assert t["title_block"]["size"] == gb["title_block"]["size"]


@pytest.mark.parametrize(
    "sheet,origin,frame",
    [
        ("A4", [25.0, 5.0], [25.0, 5.0, 205.0, 292.0]),
        ("A3", [235.0, 5.0], [25.0, 5.0, 415.0, 292.0]),
        ("A2", [404.0, 10.0], [25.0, 10.0, 584.0, 410.0]),
    ],
)
def test_computed_origin_and_frame(sheet, origin, frame):
    t = load_template("GB", sheet)
    assert t["title_block"]["origin"] == origin
    assert t["frame"] == frame


@pytest.mark.parametrize("sheet", SHEETS)
def test_title_block_sits_in_the_lower_right_corner_of_the_inner_frame(sheet):
    t = load_template("GB", sheet)
    (ox, oy), (tw, th) = t["title_block"]["origin"], t["title_block"]["size"]
    x0, y0, x1, y1 = t["frame"]
    assert (tw, th) == (180.0, 56.0)
    assert ox >= x0 and oy >= y0 and ox + tw <= x1 and oy + th <= y1  # not outside
    assert ox + tw == x1 and oy == y0  # at the lower right corner
    # frame stays inside the paper and leaves the binding margin on the left
    left, bottom, right, top = t["margins"]
    assert x0 == left and y0 == bottom
    assert x1 == t["size"][0] - right and y1 == t["size"][1] - top


@pytest.mark.parametrize("sheet", SHEETS)
def test_required_fields_present_with_expected_shape(sheet):
    fields = tb_of(sheet)["fields"]
    assert set(FIELDS) <= set(fields)
    for key in FIELDS:
        f = fields[key]
        assert isinstance(f["label"], str) and f["label"]
        assert isinstance(f["default"], str)
        x0, y0, x1, y1 = f["box"]
        assert x0 < x1 and y0 < y1
        assert isinstance(f["height"], float)


@pytest.mark.parametrize("sheet", SHEETS)
def test_field_heights_and_defaults(sheet, gb):
    fields = tb_of(sheet)["fields"]
    assert fields["name"]["height"] == 7.0
    assert fields["drawing_no"]["height"] == 5.0
    for key in FIELDS:
        if key not in ("name", "drawing_no", "company"):
            assert fields[key]["height"] == 3.5, key
        assert fields[key]["height"] in gb["text"]["heights"]
        assert fields[key]["default"] == ("共 1 张 第 1 张" if key == "sheet" else ""), key


@pytest.mark.parametrize("sheet", SHEETS)
def test_name_slot_is_the_largest(sheet):
    fields = tb_of(sheet)["fields"]
    areas = {
        k: (f["box"][2] - f["box"][0]) * (f["box"][3] - f["box"][1]) for k, f in fields.items()
    }
    assert max(areas, key=areas.get) == "name"


def test_all_gb_title_blocks_have_the_same_layout():
    base = tb_of("A3")
    for sheet in ("A4", "A2", "A1", "A0"):
        other = tb_of(sheet)
        for key in ("size", "lines", "labels", "fields"):
            assert other[key] == base[key], (sheet, key)


# -- geometry of the title block ---------------------------------------------------------


def _text_width(text, height, std):
    """SPEC §2 estimate: coefficient x cap height x width factor; CJK text has cap = h / cjk_em."""
    t = std["text"]
    has_cjk = any(ord(c) > 0x2E80 for c in text)
    cap = height / t["cjk_em"] if has_cjk else height
    units = sum(t["char_width"]["cjk" if ord(c) > 0x2E80 else "other"] for c in text)
    return units * cap * t["width_factor"]


def _cell(lines, point):
    """The rectangle bounded by the nearest lines around `point` (all lines are axis-parallel)."""
    x, y = point
    lefts, rights, bottoms, tops = [], [], [], []
    for ln in lines:
        (ax, ay), (bx, by) = ln["p1"], ln["p2"]
        if ax == bx and min(ay, by) <= y <= max(ay, by):  # vertical line
            (lefts if ax < x else rights if ax > x else []).append(ax)
        if ay == by and min(ax, bx) <= x <= max(ax, bx):  # horizontal line
            (bottoms if ay < y else tops if ay > y else []).append(ay)
    assert lefts and rights and bottoms and tops, f"{point} is not enclosed by lines"
    return max(lefts), max(bottoms), min(rights), min(tops)


def _inside(inner, outer, eps=1e-9):
    return (
        inner[0] >= outer[0] - eps
        and inner[1] >= outer[1] - eps
        and inner[2] <= outer[2] + eps
        and inner[3] <= outer[3] + eps
    )


def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 1e-9 and min(a[3], b[3]) - max(a[1], b[1]) > 1e-9


def _label_extent(label, std):
    w = _text_width(label["text"], label["height"], std)
    cx, cy = label["at"]
    return cx - w / 2, cy - label["height"] / 2, cx + w / 2, cy + label["height"] / 2


@pytest.mark.parametrize("std,sheet", CASES)
def test_lines_are_axis_parallel_thick_border_and_thin_inside(gb, std, sheet):
    tb = tb_of(sheet, std)
    w, h = tb["size"]
    roles = set(gb["lines"]) - {"basis"}
    border = set()
    for ln in tb["lines"]:
        assert ln["role"] in roles and ln["role"] in ("thick", "thin")
        (ax, ay), (bx, by) = ln["p1"], ln["p2"]
        assert ax == bx or ay == by, f"slanted line {ln}"
        assert 0 <= min(ax, bx) and max(ax, bx) <= w and 0 <= min(ay, by) and max(ay, by) <= h
        on_edge = (ax == bx and ax in (0, w)) or (ay == by and ay in (0, h))
        assert (ln["role"] == "thick") == on_edge, f"{ln}: outer border thick, inner thin"
        if on_edge:
            border.add((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))
    assert border == {(0, 0, w, 0), (0, h, w, h), (0, 0, 0, h), (w, 0, w, h)}


@pytest.mark.parametrize("sheet", SHEETS)
def test_fixed_labels_shape(gb, sheet):
    tb = tb_of(sheet)
    w, h = tb["size"]
    assert tb["labels"]
    seen = set()
    for lb in tb["labels"]:
        assert isinstance(lb["text"], str) and lb["text"].strip()
        assert lb["height"] == 3.5
        assert 0 < lb["at"][0] < w and 0 < lb["at"][1] < h
        assert lb["text"] not in seen
        seen.add(lb["text"])
    # the signature and "other" zones print the field labels (names and codes are self-evident)
    fields = tb["fields"]
    for key in ("designer", "checker", "process", "approver", "standardizer"):
        assert fields[key]["label"] in seen, key
    for key in ("material", "stage", "mass", "scale"):
        assert fields[key]["label"] in seen, key
    for word in ("标记", "处数", "分区", "更改文件号", "签名", "年月日"):  # the change zone header
        assert word in seen


@pytest.mark.parametrize("std,sheet", CASES)
def test_every_slot_and_label_lies_in_a_cell_bounded_by_lines(gb, std, sheet):
    tb = tb_of(sheet, std)
    w, h = tb["size"]
    block = (0, 0, w, h)
    for key, f in tb["fields"].items():
        box = tuple(f["box"])
        assert _inside(box, block), key
        cell = _cell(tb["lines"], ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))
        assert _inside(box, cell), f"slot {key} {box} crosses a line of cell {cell}"
        assert f["height"] <= box[3] - box[1], f"slot {key}: text taller than the slot"
    for lb in tb["labels"]:
        cell = _cell(tb["lines"], tuple(lb["at"]))
        ext = _label_extent(lb, gb)
        assert _inside(ext, cell), f"label {lb['text']} {ext} does not fit cell {cell}"


@pytest.mark.parametrize("std,sheet", CASES)
def test_slots_and_labels_do_not_overlap(gb, std, sheet):
    tb = tb_of(sheet, std)
    boxes = {k: tuple(f["box"]) for k, f in tb["fields"].items()}
    names = sorted(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            assert not _overlap(boxes[a], boxes[b]), f"slots {a} and {b} overlap"
    extents = {lb["text"]: _label_extent(lb, gb) for lb in tb["labels"]}
    for text, ext in extents.items():
        for key, box in boxes.items():
            assert not _overlap(ext, box), f"label {text} overlaps slot {key}"
    texts = sorted(extents)
    for i, a in enumerate(texts):
        for b in texts[i + 1 :]:
            assert not _overlap(extents[a], extents[b]), f"labels {a} and {b} overlap"


@pytest.mark.parametrize("std,sheet", CASES)
def test_default_values_fit_their_slots(gb, std, sheet):
    for key, f in tb_of(sheet, std)["fields"].items():
        box = f["box"]
        assert _text_width(f["default"], f["height"], gb) <= box[2] - box[0], key


@pytest.mark.parametrize("sheet", SHEETS)
def test_each_label_sits_next_to_its_own_slot(sheet):
    # a printed label is in the cell left of its field's slot on the same row, or just above it
    tb = tb_of(sheet)
    by_text = {lb["text"]: lb for lb in tb["labels"]}
    for key, f in tb["fields"].items():
        if f["label"] not in by_text:
            continue
        cx, cy = by_text[f["label"]]["at"]
        x0, y0, x1, y1 = f["box"]
        left = cx < x0 and y0 <= cy <= y1
        above = x0 <= cx <= x1 and cy > y1
        assert left or above, f"label of {key} is neither left of nor above its slot"
