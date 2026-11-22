"""DXF import (M3 SPEC §1.5): a foreign DXF becomes edges, dimensions, notes and raw ``X`` elements.

``classify`` is the single mapping table (``lcad inspect`` prints it, ``Drawing.import_dxf`` follows it):

=============================================  ==============================================================
LINE / ARC / CIRCLE / LWPOLYLINE / 2D POLYLINE  unnamed edges ``E.<view>.<n>``; polyline bulges become arcs;
                                                role from the linetype (entity, else layer), see ``role_of``
DIMENSION (linear, aligned, diameter, radius,   dimension elements ``D.dim_<n>``: measured points are the
angular)                                        defpoints, the value is ``get_measurement()``, override text
                                                is kept; the anonymous ``*D`` block is NOT exploded
TEXT / MTEXT                                    leader notes ``N.txt_<n>``
SPLINE / ELLIPSE                                raw ``X.<n>`` (view-local coordinates, drawn through)
anything else (HATCH, INSERT, POINT, ...)       skipped, counted by type
=============================================  ==============================================================

Coordinates are kept as in the DXF (no origin shift), converted to millimetres from ``$INSUNITS``.
"""

from __future__ import annotations

import hashlib
import math
import re
import tempfile
from pathlib import Path

import ezdxf
from ezdxf import units as dxf_units
from ezdxf.lldxf.encoding import decode_dxf_unicode

from .errors import InvalidArgument, NotFound
from .model import DRAW_DIR, Element, RawEl, check_name
from .text import text_size

EDGE_TYPES = ("LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE")
RAW_TYPES = ("SPLINE", "ELLIPSE")
NOTE_TYPES = ("TEXT", "MTEXT")
DIM_KINDS = {0: "linear", 1: "aligned", 2: "angular", 3: "diameter", 4: "radius", 5: "angular3p"}
DIM_UNSUPPORTED = {6: "ordinate"}
BUCKETS = ("edges", "dims", "texts", "notes", "raw", "skipped")
SHEETS = ("A4", "A3", "A2", "A1", "A0")
SCALE_STEPS = (2, 5, 10, 20, 50, 100, 200, 500, 1000)
DIM_MARGIN = 25.0  # sheet mm kept free around the geometry for dimensions when guessing the sheet
THIN_LINEWEIGHT = 35  # <= 0.35 mm (DXF lineweights are 1/100 mm) on a continuous line is thin
SIDE_VEC = {"top": (0, 1), "bottom": (0, -1), "left": (-1, 0), "right": (1, 0)}
EPS = 1e-9

# role words, tried in this order against a linetype name, then (continuous lines) a layer name
_ROLE_WORDS = (
    ("phantom", ("PHANTOM", "DIVIDE", "ISO05W", "ISO12W", "ISO14W", "ISO15W", "双点", "假想")),
    (
        "center",
        ("CENTER", "CENTRE", "DASHDOT", "AXIS", "CHAIN", "ISO04W", "ISO08W", "ISO10W", "ISO11W")
        + ("中心", "点画", "点划", "轴线"),
    ),
    ("hidden", ("HIDDEN", "DASH", "ISO02W", "ISO03W", "虚线", "不可见")),
)
_THIN_WORDS = ("THIN", "DIM", "HATCH", "SECTION", "LEADER", "细", "标注", "尺寸", "剖面")
_CODES = (("%%c", "Φ"), ("%%d", "°"), ("%%p", "±"))


# ---- reading ------------------------------------------------------------------------------------------


def resolve_path(d, path) -> Path:
    """``path`` relative to the drawing directory (absolute paths are used as given)."""
    p = Path(path)
    if not p.is_absolute():
        p = (d._dir or DRAW_DIR.get() or Path.cwd()) / p
    return p


def read_dxf(path) -> ezdxf.document.Drawing:
    p = Path(path)
    if not p.is_file():
        raise NotFound(f"找不到 DXF 文件 {p}", values={"path": str(p)}, hint="路径相对图纸目录")
    try:
        return ezdxf.readfile(p)
    except Exception:  # noqa: BLE001 - foreign files are often slightly broken: try to recover
        try:
            from ezdxf import recover

            doc, _auditor = recover.readfile(p)
            return doc
        except Exception as e:  # noqa: BLE001
            raise InvalidArgument(
                f"读不了 DXF {p.name}：{type(e).__name__}: {e}", values={"path": str(p)}
            ) from e


def content_hash(path) -> str:
    """SHA-256 of the file with CRLF folded to LF (git may normalise line endings)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def unit_factor(doc) -> tuple[float, str]:
    """(factor to millimetres, unit name) from ``$INSUNITS``; unitless is taken as mm."""
    u = doc.units
    if u in (0, dxf_units.MM):
        return 1.0, "mm"
    try:
        return float(dxf_units.conversion_factor(u, dxf_units.MM)), str(dxf_units.decode(u))
    except Exception:  # noqa: BLE001
        return 1.0, "mm"


# ---- classification -------------------------------------------------------------------------------------


def dim_kind(e) -> str:
    t = e.dimtype
    return DIM_KINDS.get(t) or DIM_UNSUPPORTED.get(t) or f"type{t}"


def classify(e) -> tuple[str, str]:
    """(bucket, label) of a modelspace entity: where it goes and what to count it as."""
    t = e.dxftype()
    if t in ("LINE", "ARC", "CIRCLE", "LWPOLYLINE"):
        return "edges", t
    if t == "POLYLINE":
        return ("edges", t) if e.is_2d_polyline else ("skipped", "POLYLINE(3D/mesh)")
    if t == "DIMENSION":
        k = dim_kind(e)
        return ("dims", k) if k in DIM_KINDS.values() else ("skipped", f"DIMENSION({k})")
    if t in NOTE_TYPES:
        return "texts", t
    if t in RAW_TYPES:
        return "raw", t
    return "skipped", t


def _visible(doc, e) -> bool:
    try:
        lay = doc.layers.get(e.dxf.layer)
    except Exception:  # noqa: BLE001
        return True
    return not (lay.is_off() or lay.is_frozen())


def scan(doc) -> dict:
    """Bucket counts of the modelspace, entities on layers that are off or frozen counted as skipped."""
    out = {b: {} for b in BUCKETS}
    for e in doc.modelspace():
        bucket, label = classify(e)
        if bucket != "skipped" and not _visible(doc, e):
            bucket, label = "skipped", f"{label}(layer off)"
        out[bucket][label] = out[bucket].get(label, 0) + 1
    return out


# ---- line roles -----------------------------------------------------------------------------------------


def _by_words(name: str):
    up = name.upper()
    for role, words in _ROLE_WORDS:
        if any(w in up for w in words):
            return role
    return None


def role_of(doc, e) -> str:
    """Line role of an entity: its linetype (else the layer's) decides hidden / centre / phantom;
    a continuous line is thick unless the layer name or a lineweight <= 0.35 mm says thin."""
    layer = None
    try:
        layer = doc.layers.get(e.dxf.layer)
    except Exception:  # noqa: BLE001
        pass
    lt = str(e.dxf.get("linetype", "BYLAYER")).upper()
    if lt in ("BYLAYER", "BYBLOCK"):
        lt = str(layer.dxf.linetype).upper() if layer is not None else "CONTINUOUS"
    role = _by_words(lt)
    lname = str(e.dxf.get("layer", "0"))
    if role is None and lt in ("CONTINUOUS", ""):
        role = _by_words(lname)  # a layer called HIDDEN / 中心线 with a continuous linetype
    if role is not None:
        return role
    lw = e.dxf.get("lineweight", -1)
    if lw == -1 and layer is not None:
        lw = layer.dxf.get("lineweight", -3)
    if 0 <= lw <= THIN_LINEWEIGHT or any(w in lname.upper() for w in _THIN_WORDS):
        return "thin"
    return "thick"


# ---- geometry helpers -----------------------------------------------------------------------------------


def _flipped(e) -> bool:
    ex = e.dxf.get("extrusion", (0, 0, 1))
    return ex[2] < 0


def _planar(e) -> bool:
    ex = e.dxf.get("extrusion", (0, 0, 1))
    return abs(ex[0]) < 1e-9 and abs(ex[1]) < 1e-9


def _segments(e):
    """WCS segments of an edge entity: ('line', p, q) / ('arc', c, r, a0, a1) / ('circle', c, r)."""
    t = e.dxftype()
    if t == "LINE":
        s, f = e.dxf.start, e.dxf.end
        yield ("line", (s.x, s.y), (f.x, f.y))
    elif t in ("CIRCLE", "ARC"):
        if not _planar(e):
            return
        c, r = e.dxf.center, e.dxf.radius
        cx = -c.x if _flipped(e) else c.x
        if t == "CIRCLE":
            yield ("circle", (cx, c.y), r)
        else:
            a0, a1 = e.dxf.start_angle, e.dxf.end_angle
            if _flipped(e):
                a0, a1 = 180.0 - a1, 180.0 - a0
            yield ("arc", (cx, c.y), r, a0 % 360.0, a1 % 360.0)
    else:  # LWPOLYLINE, 2D POLYLINE: ezdxf cuts them into LINE and ARC pieces (bulges → arcs)
        if not _planar(e):
            return
        for v in e.virtual_entities():
            yield from _segments(v)


def _extents(doc, k) -> list | None:
    """Bounding box (mm) of what the import brings in: edges, raw curves, measured points and notes."""
    xs, ys = [], []

    def add(x, y, r=0.0):
        xs.extend((x - r, x + r))
        ys.extend((y - r, y + r))

    for e in doc.modelspace():
        bucket, _ = classify(e)
        if bucket == "skipped" or not _visible(doc, e):
            continue
        t = e.dxftype()
        try:
            if bucket == "edges":
                for s in _segments(e):
                    if s[0] == "line":
                        add(*s[1])
                        add(*s[2])
                    else:
                        add(*s[1], r=s[2])
            elif bucket == "dims":
                names = ("defpoint2", "defpoint3", "defpoint4")
                if e.dimtype in (2, 3, 4):  # elsewhere defpoint is only the dimension line position
                    names += ("defpoint",)
                for a in names:
                    if e.dxf.hasattr(a):
                        v = e.dxf.get(a)
                        add(v[0], v[1])
            elif bucket in ("notes", "texts"):
                v = e.dxf.insert
                add(v[0], v[1])
            elif t == "SPLINE":
                for v in list(e.control_points) + list(e.fit_points):
                    add(v[0], v[1])
            elif t == "ELLIPSE":
                c, m = e.dxf.center, e.dxf.major_axis
                add(c.x, c.y, r=math.hypot(m.x, m.y))
        except Exception:  # noqa: BLE001 - a damaged entity must not stop the survey
            continue
    if not xs:
        return None
    return [
        round(min(xs) * k, 6),
        round(min(ys) * k, 6),
        round(max(xs) * k, 6),
        round(max(ys) * k, 6),
    ]


def guess_sheet(width, height, std="GB") -> tuple[str, str]:
    """Smallest basic sheet (A4 … A0) that holds the extents at 1:1 with room for dimensions and the
    title block; beyond A0 the next preferred reduction scale. Returns (sheet, scale text)."""
    from .std import load_template

    def fits(sheet, s):
        tpl = load_template(std, sheet)
        f, tb = tpl["frame"], tpl["title_block"]["size"]
        return (
            width * s + 2 * DIM_MARGIN <= f[2] - f[0]
            and height * s + 2 * DIM_MARGIN + tb[1] <= f[3] - f[1]
        )

    for sheet in SHEETS:
        if fits(sheet, 1.0):
            return sheet, "1:1"
    for n in SCALE_STEPS:
        if fits("A0", 1.0 / n):
            return "A0", f"1:{n}"
    return "A0", f"1:{SCALE_STEPS[-1]}"


# ---- text -----------------------------------------------------------------------------------------------


def clean_text(text) -> str:
    """DXF text codes and MTEXT formatting → plain text (``%%c`` → Φ, ``%%d`` → °, ``%%p`` → ±)."""
    s = str(text or "")
    if "\\" in s or "{" in s:
        from ezdxf.tools.text import plain_mtext

        s = plain_mtext(s)
    for code, ch in _CODES:
        s = s.replace(code, ch).replace(code.upper(), ch)
    return " ".join(s.split())


# ---- raw curves (SPLINE / ELLIPSE) -----------------------------------------------------------------------

_SCRATCH = None


def _scratch_msp():
    global _SCRATCH
    if _SCRATCH is None:
        _SCRATCH = ezdxf.new("R2018")
    return _SCRATCH.modelspace()


def _raw_pack(e, k):
    """(attribs, data) of a SPLINE / ELLIPSE in view-local mm, JSON-ready; None if not reproducible."""
    if not _planar(e) or _flipped(e):
        return None
    if e.dxftype() == "SPLINE":
        attribs = {"degree": int(e.dxf.degree), "flags": int(e.dxf.flags)}

        def pts(seq):
            return [[round(v[0] * k, 6), round(v[1] * k, 6), 0.0] for v in seq]

        data = {
            "control_points": pts(e.control_points),
            "fit_points": pts(e.fit_points),
            "knots": [float(x) for x in e.knots],
            "weights": [float(x) for x in e.weights],
        }
        if not data["control_points"] and not data["fit_points"]:
            return None
        return attribs, data
    c, m = e.dxf.center, e.dxf.major_axis
    attribs = {
        "center": [round(c.x * k, 6), round(c.y * k, 6), 0.0],
        "major_axis": [round(m.x * k, 6), round(m.y * k, 6), 0.0],
        "ratio": float(e.dxf.ratio),
        "start_param": float(e.dxf.start_param),
        "end_param": float(e.dxf.end_param),
    }
    return attribs, {}


def make_raw(msp, intent, layer=None):
    """Create the DXF entity of a raw element (view-local coordinates, not transformed)."""
    attribs = dict(intent["attribs"])
    if layer:
        attribs["layer"] = layer
    ent = msp.new_entity(intent["dxftype"], attribs)
    data = intent.get("data") or {}
    if intent["dxftype"] == "SPLINE":
        if data.get("control_points"):
            ent.control_points = [tuple(p) for p in data["control_points"]]
        if data.get("fit_points"):
            ent.fit_points = [tuple(p) for p in data["fit_points"]]
        if data.get("knots"):
            ent.knots = list(data["knots"])
        if data.get("weights"):
            ent.weights = list(data["weights"])
    return ent


def raw_polylines(intent, distance=0.05) -> list:
    """The raw curve flattened to polylines in view-local mm (for the Viewer and for collisions)."""
    from ezdxf import path as ezpath

    msp = _scratch_msp()
    try:
        ent = make_raw(msp, intent)
        try:
            p = ezpath.make_path(ent)
            return [
                [(v.x, v.y) for v in sub.flattening(distance)]
                for sub in p.sub_paths()
                if len(sub) > 0
            ]
        finally:
            msp.delete_entity(ent)
    except Exception:  # noqa: BLE001 - drawn in the DXF anyway; just not shown in the SVG
        return []


# ---- the import element ---------------------------------------------------------------------------------


class PlainText(Element):
    """A plain text element imported from a DXF TEXT / MTEXT entity (no leader)."""

    kind = "text"
    SETTABLE = ("text", "height", "rotation")
    READ = ("text", "at", "height", "rotation", "style", "halign", "valign", "layer")

    text = property(lambda s: s._intent["text"])
    at = property(lambda s: list(s._intent["at"]))
    height = property(lambda s: s._intent["height"])
    rotation = property(lambda s: s._intent["rotation"])
    style = property(lambda s: s._intent.get("style", "Standard"))
    halign = property(lambda s: s._intent.get("halign", 0))
    valign = property(lambda s: s._intent.get("valign", 0))
    layer = property(lambda s: s._intent.get("layer", "0"))

    def _apply_set(self, fields):
        from .errors import InvalidArgument

        if "text" in fields:
            self._intent["text"] = str(fields["text"])
        for key in ("height", "rotation"):
            if key in fields:
                v = float(fields[key])
                if key == "height" and not (v > 0):
                    raise InvalidArgument(f"{self._id} 的字高必须为正", id=self._id)
                self._intent[key] = v

    def _apply_move(self, dx, dy):
        at = self._intent["at"]
        self._intent["at"] = [at[0] + dx, at[1] + dy]


class Import(Element):
    """One imported DXF file: what it brought in, and the owner of everything it created."""

    kind = "import"
    READ = ("path", "counts")

    path = property(lambda s: s._intent["path"])
    counts = property(lambda s: dict(s._intent["counts"]))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._created = []

    def _children(self):
        return list(self._created)


class _Ctx:
    """State of one import run."""

    def __init__(self, d, doc, view, imp, k):
        self.d, self.doc, self.view, self.imp, self.k = d, doc, view, imp, k
        self.created = imp._created
        self.grid = {}  # rounded point → [(edge id, anchor, x, y)]
        self.rounds = []  # circle / arc edges: (id, shape, cx, cy, r)
        self.lines = []  # line edges: (id, p1, p2)
        self.roles = {}  # role counts of the created edges
        self.fallback = 0
        self.texts = 0

    def own(self, el):
        el._refs.append(self.imp.id)
        self.created.append(el.id)
        return el


GRID = 0.01


def _cell(x, y):
    return (round(x / GRID), round(y / GRID))


def _index_point(ctx, eid, anchor, p):
    ctx.grid.setdefault(_cell(*p), []).append((eid, anchor, p[0], p[1]))


def _anchor_at(ctx, p, tol=1e-3):
    """``"E.front.3:start"`` when an imported edge ends at ``p``, else the plain point."""
    cx, cy = _cell(*p)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for eid, anchor, x, y in ctx.grid.get((cx + dx, cy + dy), ()):
                if math.hypot(x - p[0], y - p[1]) <= tol:
                    return f"{eid}:{anchor}"
    return (p[0], p[1])


# ---- edges ----------------------------------------------------------------------------------------------


def _r6(v):
    return round(v, 6)


def _edge(ctx, seg, role, e):
    k = ctx.k
    meta = {"dxf": {"layer": str(e.dxf.layer), "handle": str(e.dxf.handle)}}
    if seg[0] == "line":
        p, q = (_r6(seg[1][0] * k), _r6(seg[1][1] * k)), (_r6(seg[2][0] * k), _r6(seg[2][1] * k))
        if math.dist(p, q) < 1e-6:
            return None
        intent = {"shape": "line", "p1": list(p), "p2": list(q), "role": role, **meta}
    else:
        c, r = (_r6(seg[1][0] * k), _r6(seg[1][1] * k)), _r6(seg[2] * k)
        if not r > 1e-6 or not math.isfinite(r):
            return None
        intent = {"shape": seg[0], "c": list(c), "r": r, "role": role, **meta}
        if seg[0] == "arc":
            intent.update(start=_r6(seg[3]), end=_r6(seg[4]))
    el = ctx.own(ctx.view._edge(None, intent))
    ctx.roles[role] = ctx.roles.get(role, 0) + 1
    if seg[0] == "line":
        ctx.lines.append((el.id, p, q))
        _index_point(ctx, el.id, "start", p)
        _index_point(ctx, el.id, "end", q)
    else:
        ctx.rounds.append((el.id, seg[0], c[0], c[1], r))
        if seg[0] == "arc":
            _index_point(ctx, el.id, "start", el.start)
            _index_point(ctx, el.id, "end", el.end)
    return el


def _edges(ctx, e) -> bool:
    role = role_of(ctx.doc, e)
    segs = list(_segments(e))
    n = 0
    for seg in segs:
        n += _edge(ctx, seg, role, e) is not None
    return n > 0


# ---- raw, notes -----------------------------------------------------------------------------------------


def _raw(ctx, e) -> bool:
    packed = _raw_pack(e, ctx.k)
    if packed is None:
        return False
    attribs, data = packed
    intent = {
        "dxftype": e.dxftype(),
        "attribs": attribs,
        "data": data,
        "view": ctx.view.name,
        "role": role_of(ctx.doc, e),
        "dxf": {"layer": str(e.dxf.layer), "handle": str(e.dxf.handle)},
    }
    msp = _scratch_msp()
    try:  # make_raw must accept it, or the DXF writer would fail on every later build
        msp.delete_entity(make_raw(msp, intent))
    except Exception:  # noqa: BLE001
        return False
    d = ctx.d
    el = RawEl(d, d._alloc("X"), intent, refs=[ctx.view.id])
    ctx.own(d._add(el))
    return True


def _note(ctx, text, p) -> bool:
    text = clean_text(text)
    if not text:
        return False
    name = ctx.d._auto_name("N", (), "txt")
    ctx.own(ctx.view.note(name, text, (_r6(p[0] * ctx.k), _r6(p[1] * ctx.k))))
    return True


def _text(ctx, e) -> bool:
    """TEXT / MTEXT -> a plain text element (no leader), keeping position, height, rotation,
    alignment and style. MTEXT keeps its line breaks (decoded and cleaned line by line)."""
    k = ctx.k
    is_mtext = e.dxftype() == "MTEXT"
    if is_mtext:
        raw = e.plain_text(fast=False)  # fast mode drops lines of long MTEXT
    else:
        raw = e.dxf.text
    raw = _decode_text(raw)
    if is_mtext:
        text = "\n".join(clean_text(part) for part in raw.split("\n"))
    else:
        text = clean_text(raw)
    if not text.strip():
        return False
    intent = {"view": ctx.view.name, "text": text}
    if is_mtext:
        h = float(e.dxf.get("char_height", 2.5) or 2.5)
        rot = float(e.get_rotation())
        p = e.dxf.insert
        attachment = int(e.dxf.get("attachment_point", 1))
        halign, valign = _mtext_align(attachment)
        intent.update(
            attachment=attachment,
            line_spacing=float(e.dxf.get("line_spacing_factor", 1.0) or 1.0),
            align="attachment",
        )
    else:
        h = float(e.dxf.get("height", 2.5) or 2.5)
        rot = float(e.dxf.get("rotation", 0.0))
        p = e.dxf.insert
        halign = int(e.dxf.get("halign", 0))
        valign = int(e.dxf.get("valign", 0))
        align = {0: "left", 1: "center", 2: "right", 3: "aligned", 4: "middle", 5: "fit"}.get(
            halign, "left"
        )
        if (halign or valign) and e.dxf.hasattr("align_point"):
            a2 = e.dxf.align_point
            if halign in (3, 4, 5):
                dx, dy = (a2[0] - p[0]) * k, (a2[1] - p[1]) * k
                dist = math.hypot(dx, dy)
                if halign in (3, 5) and dist > 1e-9:
                    rot = math.degrees(math.atan2(dy, dx))
                if halign == 3 and dist > 1e-9 and h > 0:
                    w1 = text_size(text, h, ctx.d.std)[0]
                    if w1 > 1e-9:
                        h = h * dist / w1  # ALIGNED scales the text to fit between the points
                if halign == 5:
                    intent["fit_width"] = _r6(dist)
                p = a2
            else:
                p = a2
        intent.update(align=align, line_spacing=1.0)
    intent.update(
        at=[_r6(p[0] * k), _r6(p[1] * k)],
        height=_r6(h * k),
        rotation=_r6(rot),
        halign=halign,
        valign=valign,
        style=str(e.dxf.get("style", "Standard")),
        layer=str(e.dxf.get("layer", "0")),
        dxf={"layer": str(e.dxf.layer), "handle": str(e.dxf.handle)},
        insert=[_r6(e.dxf.insert[0] * k), _r6(e.dxf.insert[1] * k)],
    )
    if e.dxf.hasattr("align_point"):
        intent["align_point"] = [_r6(e.dxf.align_point[0] * k), _r6(e.dxf.align_point[1] * k)]
    if not (intent["height"] > 0):
        return False
    name = ctx.d._auto_name("T", (), "txt")
    ctx.own(ctx.d._add(PlainText(ctx.d, f"T.{name}", intent, refs=[ctx.view.id])))
    ctx.texts += 1
    return True


def _decode_text(raw: str) -> str:
    """DXF \\U+xxxx escapes -> real Unicode where possible."""
    try:
        return decode_dxf_unicode(raw)
    except Exception:  # noqa: BLE001 - a damaged string must not kill the import
        return raw


def _mtext_align(attachment: int) -> tuple:
    """MTEXT attachment point 1..9 -> (halign 0/1/2, TEXT-style valign 3/2/1)."""
    col = (attachment - 1) % 3
    row = (attachment - 1) // 3
    halign = (0, 1, 2)[col]
    valign = (3, 2, 1)[row]  # top -> valign 3, middle -> 2, bottom -> 1
    return halign, valign


# ---- dimensions -----------------------------------------------------------------------------------------


def _pt(ctx, e, name):
    if not e.dxf.hasattr(name):
        return None
    v = e.dxf.get(name)
    return (_r6(v[0] * ctx.k), _r6(v[1] * ctx.k))


def _measured(e, fallback):
    try:
        return float(e.get_measurement())
    except Exception:  # noqa: BLE001
        return fallback


def _override(e, default_text):
    """The DXF dimension text as an override, ``<>`` standing for the measurement; None = automatic."""
    t = str(e.dxf.get("text", "") or "")
    if t.strip() in ("", "<>"):
        return None
    return clean_text(t.replace("<>", default_text))


def _num(v, nd=3):
    from .annotate import fmt_num

    return fmt_num(v, nd)


def _value(meas, geometric):
    """Pass the DXF value only when it differs from what the geometry gives."""
    return None if abs(meas - geometric) <= 1e-6 * max(1.0, abs(geometric)) else meas


def _side_linear(dp, p1, p2, horizontal):
    k = 1 if horizontal else 0
    if dp is None:
        return None
    lo, hi = min(p1[k], p2[k]), max(p1[k], p2[k])
    if dp[k] > hi + 1e-6:
        return "top" if horizontal else "right"
    if dp[k] < lo - 1e-6:
        return "bottom" if horizontal else "left"
    return None


def _side_aligned(dp, p1, p2):
    if dp is None:
        return None
    ux, uy = p2[0] - p1[0], p2[1] - p1[1]
    n = math.hypot(ux, uy)
    if n < EPS:
        return None
    nx, ny = -uy / n, ux / n
    off = (dp[0] - p1[0]) * nx + (dp[1] - p1[1]) * ny
    if abs(off) < 1e-6:
        return None
    sg = 1 if off > 0 else -1
    return max(SIDE_VEC, key=lambda s: SIDE_VEC[s][0] * nx * sg + SIDE_VEC[s][1] * ny * sg)


def _find_round(ctx, c, r, kinds):
    tol = 1e-3 * max(1.0, r)
    for eid, shape, cx, cy, rr in ctx.rounds:
        if shape in kinds and math.hypot(cx - c[0], cy - c[1]) <= tol and abs(rr - r) <= tol:
            return eid
    return None


def _find_line(ctx, a, b):
    """An imported line edge lying on the infinite line a–b and overlapping the segment a–b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n < EPS:
        return None
    ux, uy = dx / n, dy / n
    tol = 1e-3 * max(1.0, n * 1e-2)
    for eid, p, q in ctx.lines:
        if all(abs((x - a[0]) * uy - (y - a[1]) * ux) <= tol for x, y in (p, q)):
            t0 = (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
            t1 = (q[0] - a[0]) * ux + (q[1] - a[1]) * uy
            if max(min(t0, t1), 0.0) < min(max(t0, t1), n) - tol:
                return eid
    return None


def _dim_note(ctx, e, text, p) -> bool:
    ctx.fallback += 1
    return _note(ctx, text, p or (0.0, 0.0))


def _dimension(ctx, e) -> bool:
    """One DIMENSION → a dimension element (True), a note when the geometry it measures was not
    imported, or nothing (False)."""
    kind = dim_kind(e)
    ns = ctx.view.dim
    name = ctx.d._auto_name("D", (), "dim")
    dp = _pt(ctx, e, "defpoint")
    mid = _pt(ctx, e, "text_midpoint") or dp
    k = ctx.k
    if kind in ("linear", "aligned"):
        p1, p2 = _pt(ctx, e, "defpoint2"), _pt(ctx, e, "defpoint3")
        if p1 is None or p2 is None:
            return False
        meas = _measured(e, math.dist(p1, p2) / k) * k
        a1, a2 = _anchor_at(ctx, p1), _anchor_at(ctx, p2)
        ang = e.dxf.get("angle", 0.0) if kind == "linear" else None
        ang = None if ang is None else ang % 180.0
        horizontal = ang is not None and (ang < 0.05 or ang > 179.95)
        vertical = ang is not None and abs(ang - 90.0) < 0.05
        if horizontal or vertical:
            geo = abs(p2[0] - p1[0]) if horizontal else abs(p2[1] - p1[1])
            if geo < 1e-9:
                return False
            text = _override(e, _num(meas))
            ctx.own(
                ns.linear(
                    name,
                    a1,
                    a2,
                    dir="h" if horizontal else "v",
                    value=_value(meas, geo),
                    text=text,
                    side=_side_linear(dp, p1, p2, horizontal),
                )
            )
            return True
        geo = math.dist(p1, p2)
        if geo < 1e-9:
            return False
        ctx.own(
            ns.aligned(
                name,
                a1,
                a2,
                value=_value(meas, geo),
                text=_override(e, _num(meas)),
                side=_side_aligned(dp, p1, p2),
            )
        )
        return True
    if kind in ("diameter", "radius"):
        q = _pt(ctx, e, "defpoint4")
        if dp is None or q is None:
            return False
        meas = _measured(e, 0.0) * k
        if kind == "diameter":
            c, r = ((dp[0] + q[0]) / 2, (dp[1] + q[1]) / 2), math.dist(dp, q) / 2
            meas = meas or 2 * r
        else:
            c, r = dp, math.dist(dp, q)
            meas = meas or r
        sym = "Φ" if kind == "diameter" else "R"
        text = _override(e, sym + _num(meas))
        cid = _find_round(ctx, c, r, ("circle", "arc"))
        if cid is None:
            return _dim_note(ctx, e, text or sym + _num(meas), mid)
        if kind == "diameter":
            ctx.own(ns.dia(name, circle=cid, value=_value(meas, 2 * r), text=text))
        elif ctx.d[cid].shape == "arc":
            ctx.own(ns.rad(name, circle=cid, value=_value(meas, r), text=text))
        else:  # GB/T 4458.4 dimensions a whole circle by diameter; the DXF said radius: keep its text
            ctx.own(ns.dia(name, circle=cid, text=text or sym + _num(meas)))
        return True
    # angular: two lines (2L) or centre + two points (3P)
    if kind == "angular":
        a, b = _pt(ctx, e, "defpoint2"), _pt(ctx, e, "defpoint3")
        c, d_ = _pt(ctx, e, "defpoint4"), dp
        l1, l2 = (a, b), (c, d_)
    else:
        v = _pt(ctx, e, "defpoint4")
        l1, l2 = (v, _pt(ctx, e, "defpoint2")), (v, _pt(ctx, e, "defpoint3"))
    if any(p is None for pair in (l1, l2) for p in pair):
        return False
    meas = _measured(e, 0.0)
    shown = _num(meas, 2) + "°"
    text = _override(e, shown)
    e1, e2 = _find_line(ctx, *l1), _find_line(ctx, *l2)
    if e1 is None or e2 is None or e1 == e2:
        return _dim_note(ctx, e, text or shown, mid)
    if (
        meas > 180.0
    ):  # a reflex angle: the engine draws the angle below 180, so keep the DXF's number as text
        text = text or shown
    try:
        ctx.own(
            ns.angle(name, line1=e1, line2=e2, value=meas if meas <= 180.0 else None, text=text)
        )
    except InvalidArgument:  # parallel lines: no angle to dimension
        return _dim_note(ctx, e, text or _num(meas, 2) + "°", mid)
    return True


# ---- the import -----------------------------------------------------------------------------------------


def _import_id(d, stem) -> str:
    fid = d._take_forced(["I"])
    if fid is not None:
        return fid
    s = re.sub(r"[^\w\-]", "_", stem) or "dxf"
    if not re.match(r"[^\W\d_]", s):
        s = "f" + s
    base, n, cand = f"I.{s}", 2, f"I.{s}"
    while cand in d._els:
        cand = f"{base}_{n}"
        n += 1
    return cand


def import_dxf(d, path, view="front"):
    """Bring the modelspace of a DXF file into view ``view`` (see the module docstring)."""
    src = resolve_path(d, path)
    doc = read_dxf(src)
    k, unit = unit_factor(doc)
    v = d.view(check_name(view, "视图名"))
    iid = _import_id(d, src.stem)
    imp = Import(d, iid, {"path": str(path).replace("\\", "/"), "view": v.name}, refs=[v.id])
    d._add(imp)
    ctx = _Ctx(d, doc, v, imp, k)
    made = {b: 0 for b in BUCKETS}
    skipped, from_ = {}, {b: {} for b in BUCKETS}
    ents = list(doc.modelspace())

    def done(bucket, label, ok):
        if ok:
            made[bucket] += 1
            from_[bucket][label] = from_[bucket].get(label, 0) + 1
        else:
            skipped[f"{label}(degenerate)"] = skipped.get(f"{label}(degenerate)", 0) + 1

    for stage in (("edges", "raw"), ("dims", "texts")):  # geometry first: dimensions look edges up
        for e in ents:
            bucket, label = classify(e)
            if bucket == "skipped":
                if stage[0] == "edges":
                    skipped[label] = skipped.get(label, 0) + 1
            elif bucket in stage:
                if not _visible(doc, e):
                    skipped[f"{label}(layer off)"] = skipped.get(f"{label}(layer off)", 0) + 1
                    continue
                fn = {"edges": _edges, "raw": _raw, "dims": _dimension, "texts": _text}[bucket]
                done(bucket, label, fn(ctx, e))
    imp._intent.update(
        sha256=content_hash(src),
        units=unit,
        unit_factor=k,
        extents=_extents(doc, k),
        counts={
            "edges": dict(sorted(ctx.roles.items())),
            "dims": made["dims"] - ctx.fallback,
            "notes": ctx.fallback,
            "texts": made["texts"],
            "raw": made["raw"],
            "skipped": dict(sorted(skipped.items())),
            "dims_as_notes": ctx.fallback,
            "from": {b: dict(sorted(from_[b].items())) for b in BUCKETS if b != "skipped"},
        },
    )
    return imp


# ---- lcad init --from-dxf / lcad inspect -----------------------------------------------------------------


def prepare_init(path, std="GB") -> dict:
    """Read a DXF for ``lcad init --from-dxf``: sheet / scale guess and the import summary."""
    p = Path(path)
    doc = read_dxf(p)
    k, _ = unit_factor(doc)
    ext = _extents(doc, k)
    w, h = (ext[2] - ext[0], ext[3] - ext[1]) if ext else (0.0, 0.0)
    sheet, scale = guess_sheet(w, h, std)
    return {"sheet": sheet, "scale": scale, "extents": ext}


def layers_of(doc) -> list:
    counts = {}
    for e in doc.modelspace():
        counts[e.dxf.layer] = counts.get(e.dxf.layer, 0) + 1
    out = []
    for lay in doc.layers:
        out.append(
            {
                "name": lay.dxf.name,
                "linetype": lay.dxf.linetype,
                "color": lay.dxf.color,
                "count": counts.pop(lay.dxf.name, 0),
            }
        )
    for name, n in sorted(counts.items()):  # used but not in the layer table
        out.append({"name": name, "linetype": None, "color": None, "count": n})
    return out


def render_png(doc, out) -> Path:
    """The whole modelspace through ezdxf's matplotlib drawing add-on."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    fig = plt.figure(figsize=(10, 7))
    try:
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        cfg = Configuration(background_policy=BackgroundPolicy.WHITE)
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(
            doc.modelspace(), finalize=True
        )
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=110, facecolor="white")
    finally:
        plt.close(fig)
    return out


def inspect(path, tmp_dir=None) -> dict:
    """Survey of a DXF for ``lcad inspect``: layers, entity statistics, extents, where each entity
    type goes on import, and a temporary PNG (``tmp_dir``, else the system temp directory)."""
    p = Path(path)
    doc = read_dxf(p)
    k, unit = unit_factor(doc)
    types = {}
    for e in doc.modelspace():
        types[e.dxftype()] = types.get(e.dxftype(), 0) + 1
    ext = _extents(doc, k)
    maps = scan(doc)
    out = {
        "ok": True,
        "file": str(p),
        "dxfversion": doc.dxfversion,
        "units": unit,
        "layers": layers_of(doc),
        "entities": dict(sorted(types.items())),
        "extents": ext,
        "size": [round(ext[2] - ext[0], 6), round(ext[3] - ext[1], 6)] if ext else None,
        "maps_to": {b: dict(sorted(maps[b].items())) for b in BUCKETS},
        "sheet": None,
        "png": None,
    }
    if ext:
        sheet, scale = guess_sheet(ext[2] - ext[0], ext[3] - ext[1])
        out["sheet"] = {"sheet": sheet, "scale": scale}
    folder = Path(tmp_dir) if tmp_dir else Path(tempfile.gettempdir()) / "linercad-inspect"
    try:
        png = render_png(doc, folder / f"inspect-{p.stem}-{content_hash(p)[:8]}.png")
        out["png"] = str(png)
    except Exception as e:  # noqa: BLE001 - a picture is a convenience, never a failure
        out["png_error"] = f"{type(e).__name__}: {e}"
    return out
