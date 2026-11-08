"""Read a company DXF into an enterprise overlay (SPEC M1 §6).

Imported: line-role widths and colours (by layer name, else linetype name), text height (text
style / DIMSTYLE ``dimtxt``), arrow length (``dimasz``) and one title-block block (named
``TITLE*`` / ``标题栏``, else the first block with ATTDEFs): its lines and one field box per
ATTDEF. Nothing else in the DXF is read. The result has the overlay layout of
``std.load_overlay``: ``[std.*]`` overrides plus a replacement ``[title_block]``.
"""

from __future__ import annotations

import json
import re

import ezdxf

from ..errors import InvalidArgument
from . import load_std

# role -> name fragments, tried in this order against the layer name and then the linetype name
_ROLE_WORDS = (
    ("section", ("剖切", "CUTTING")),
    ("hatch", ("HATCH", "SECTION", "剖面", "填充")),
    ("dim", ("DIM", "标注", "尺寸")),
    ("text", ("TEXT", "文字", "注释", "NOTE")),
    ("phantom", ("PHANTOM", "双点", "假想")),
    ("center", ("CENTER", "CEN", "DASHDOT", "AXIS", "中心", "点画", "点划", "轴线")),
    ("hidden", ("HIDDEN", "DASH", "虚线", "不可见")),
    ("thin", ("THIN", "细实")),
    ("thick", ("THICK", "VISIBLE", "OUTLINE", "CONTOUR", "粗实", "轮廓", "可见")),
)
# normalised ATTDEF tag (upper case, no spaces / _ / -) -> field key shared by all templates
_FIELD_WORDS = {
    "name": "NAME TITLE DRAWINGNAME DWGNAME PARTNAME 图名 名称 图样名称 零件名称",
    "drawing_no": "DRAWINGNO DWGNO DRAWINGNUMBER PARTNO NUMBER NO 图号 图样代号 代号",
    "material": "MATERIAL MAT 材料 材料标记",
    "mass": "MASS WEIGHT 重量 质量",
    "scale": "SCALE 比例",
    "sheet": "SHEET SHEETS PAGE 页次 张数",
    "company": "COMPANY ORGANIZATION ORG OWNER 单位 公司 单位名称",
    "designer": "DESIGNER DESIGNEDBY DRAWNBY DRAWN DESIGN 设计",
    "checker": "CHECKER CHECKEDBY CHECKED CHECK 审核",
    "approver": "APPROVER APPROVEDBY APPROVED 批准",
    "process": "PROCESS 工艺",
    "standardizer": "STANDARDIZER 标准化",
    "date": "DATE 日期",
    "revision": "REVISION REV",
    "stage": "STAGE PHASE STATUS 阶段 阶段标记",
    "doc_type": "DOCTYPE DOCUMENTTYPE TYPE 文件类型",
}
_FIELD_KEY = {w: k for k, words in _FIELD_WORDS.items() for w in words.split()}
_EPS = 1e-6


def _role_of(layer) -> str | None:
    for names in (layer.dxf.name, layer.dxf.linetype):
        upper = str(names).upper()
        for role, words in _ROLE_WORDS:
            if any(w in upper for w in words):
                return role
    return None


def _lines_roles(doc, notes: list) -> dict:
    out: dict = {}
    for layer in doc.layers:
        role = _role_of(layer)
        if role is None or role in out or layer.dxf.name in ("0", "Defpoints"):
            continue
        spec = {}
        if layer.dxf.get("lineweight", 0) > 0:  # 1/100 mm; ≤ 0 is ByLayer / default
            spec["width"] = layer.dxf.lineweight / 100
        if layer.color:
            spec["color"] = abs(layer.color)
        if spec:
            out[role] = spec
            notes.append(f"图层 {layer.dxf.name} → 线型角色 {role}")
    return out


def _snap(value: float, series: list, what: str, notes: list) -> float:
    near = min(series, key=lambda s: abs(s - value))
    if abs(near - value) > 1e-6:
        notes.append(f"{what} {value:g} 不在字高系列，取 {near:g}")
    return near


def _text_and_arrow(doc, series: list, notes: list) -> dict:
    style_h = next((s.dxf.height for s in doc.styles if s.dxf.get("height", 0) > 0), None)
    current = doc.header.get("$DIMSTYLE", "Standard")  # the current style, else Standard
    ds = next((doc.dimstyles.get(n) for n in (current, "Standard") if n in doc.dimstyles), None)
    dimtxt = ds.dxf.get("dimtxt") if ds is not None else None
    dimtxt = dimtxt if dimtxt and dimtxt >= 1 else None  # < 1 is the inch default, not a choice
    out: dict = {}
    if dimtxt or style_h:
        out["dim"] = {"text_height": _snap(dimtxt or style_h, series, "标注字高", notes)}
        out["note"] = {"text_height": _snap(style_h or dimtxt, series, "文字字高", notes)}
    asz = ds.dxf.get("dimasz") if ds is not None else None
    if asz and asz >= 1:
        out.setdefault("dim", {})["arrow_length"] = float(asz)
    return out


def _segments(block) -> list:
    segs = []
    for e in block:
        if e.dxftype() == "LINE":
            a, b = e.dxf.start, e.dxf.end
            segs.append(((float(a.x), float(a.y)), (float(b.x), float(b.y))))
        elif e.dxftype() == "LWPOLYLINE":
            pts = [(float(x), float(y)) for x, y in e.get_points("xy")]
            if e.closed:
                pts.append(pts[0])
            segs += list(zip(pts, pts[1:]))
    return segs


def _cell(segs, x, y):
    """The rectangle bounded by the nearest axis-parallel segments around (x, y), or None."""
    near = {"l": [], "r": [], "b": [], "t": []}
    for (ax, ay), (bx, by) in segs:
        if abs(ax - bx) < _EPS and min(ay, by) - _EPS <= y <= max(ay, by) + _EPS:
            near["l" if ax <= x + _EPS else "r"].append(ax)
        if abs(ay - by) < _EPS and min(ax, bx) - _EPS <= x <= max(ax, bx) + _EPS:
            near["b" if ay <= y + _EPS else "t"].append(ay)
    if not all(near.values()):
        return None
    return max(near["l"]), max(near["b"]), min(near["r"]), min(near["t"])


def _title_block(doc, series: list, notes: list) -> dict | None:
    blocks = [b for b in doc.blocks if not b.name.startswith("*")]
    named = [b for b in blocks if b.name.upper().startswith("TITLE") or "标题栏" in b.name]
    pick = (named or [b for b in blocks if b.query("ATTDEF")] or [None])[0]
    if pick is None:
        notes.append("没有标题栏块（名为 TITLE* / 标题栏，或含 ATTDEF）：只导入了 [std]")
        return None
    segs = _segments(pick)
    xs = [p[0] for s in segs for p in s]
    ys = [p[1] for s in segs for p in s]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    lines = []
    for a, b in segs:
        edge = any(
            all(abs(p[i] - v) < _EPS for p in (a, b))
            for i, v in ((0, x0), (0, x1), (1, y0), (1, y1))
        )
        lines.append(
            {
                "p1": [round(a[0] - x0, 3), round(a[1] - y0, 3)],
                "p2": [round(b[0] - x0, 3), round(b[1] - y0, 3)],
                "role": "thick" if edge else "thin",
            }
        )
    fields: dict = {}
    for att in pick.query("ATTDEF"):
        tag = att.dxf.tag
        key = (
            _FIELD_KEY.get(re.sub(r"[\s_\-]+", "", tag).upper()) or re.sub(r"\W+", "_", tag).lower()
        )
        while key in fields:
            key += "_2"
        x, y, h = (float(v) for v in (att.dxf.insert.x, att.dxf.insert.y, att.dxf.height))
        cell = _cell(segs, x, y)
        box = (
            [cell[0] + 1, cell[1] + 1, cell[2] - 1, cell[3] - 1]
            if cell
            else [x, y - 0.3 * h, x + 10 * h, y + 1.3 * h]
        )
        if cell is None:
            notes.append(f"ATTDEF {tag} 不在任何格子里，槽位按字高估")
        fields[key] = {
            "label": att.dxf.get("prompt", "") or tag,
            "box": [round(v - o, 3) for v, o in zip(box, (x0, y0, x0, y0))],
            "height": _snap(h, series, f"{tag} 字高", notes),
            "default": att.dxf.get("text", ""),
        }
    return {
        "size": [round(x1 - x0, 3), round(y1 - y0, 3)],
        "lines": lines,
        "fields": fields,
    }


def import_dxf(path) -> tuple[dict, list]:
    """(overlay data, notes) from the company DXF at ``path``."""
    try:
        doc = ezdxf.readfile(path)
    except (OSError, ezdxf.DXFError) as e:
        raise InvalidArgument(f"读不了 DXF {path}：{e}", values={"path": str(path)})
    series, notes = load_std("GB")["text"]["heights"], []
    std = {}
    roles = _lines_roles(doc, notes)
    if roles:
        std["lines"] = roles
    std.update(_text_and_arrow(doc, series, notes))
    data = {"std": std} if std else {}
    tb = _title_block(doc, series, notes)
    if tb:
        data["title_block"] = tb
    return data, notes


# ---- the small TOML writer for that layout (no extra dependency) ---------------------------------


def _key(k: str) -> str:
    return k if re.fullmatch(r"[A-Za-z0-9_-]+", k) else json.dumps(k, ensure_ascii=False)


def _val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ", ".join(_val(x) for x in v) + "]"
    return "{ " + ", ".join(f"{_key(k)} = {_val(x)}" for k, x in v.items()) + " }"


def dump_toml(data: dict, path: tuple = ()) -> str:
    """TOML text for nested dicts of str / number / bool / list (lists of dicts: one per line)."""
    body, tables = [], []
    for k, v in data.items():
        if isinstance(v, dict):
            tables.append((k, v))
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            rows = "".join(f"    {_val(x)},\n" for x in v)
            body.append(f"{_key(k)} = [\n{rows}]")
        else:
            body.append(f"{_key(k)} = {_val(v)}")
    head = f"[{'.'.join(_key(p) for p in path)}]\n" if path and body else ""
    text = head + "".join(line + "\n" for line in body)
    return text + "".join("\n" + dump_toml(v, (*path, k)) for k, v in tables)
