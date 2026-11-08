"""Annotation intent layer (SPEC §4.3): dimensions, notes, technical requirements, title block,
sections and hatching. Layout (where things go on the sheet) is computed in ``layout.py``."""

from __future__ import annotations

import math
import re

from .errors import InvalidArgument, NotFound
from .geometry import CenterLine, Edge, Feature, resolve_point
from .model import Element, check_name, num
from .record import mutator

ROLES_DIM = ("size", "position", "overall")
SIDES = ("top", "bottom", "left", "right", "inside")
SECTION_LOOK = ("left", "right", "up", "down")


def fmt_num(v: float, decimals: int = 3) -> str:
    s = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _expr_parts(value):
    """value → (float, expr src or None, covered param names)."""
    if value is None:
        return None, None, []
    if hasattr(value, "src") and hasattr(value, "params"):
        return float(value), value.src, sorted(value.params)
    return num(value, "value"), None, []


def _required_name(name, what):
    if name is None:
        raise InvalidArgument(
            f"{what}必须起名（第一个参数），日志和 @ID 引用靠它", hint="例如 'L'、'd1'、'bore'"
        )
    return check_name(name)


def _el(d, ref, what):
    if isinstance(ref, Element):
        return ref
    if isinstance(ref, str):
        return d[ref]
    raise InvalidArgument(f"{what} 应为元素或元素 ID，收到 {ref!r}")


class Dim(Element):
    """A dimension: linear (h/v), diameter or radius."""

    kind = "dim"
    SETTABLE = ("value", "tol", "prefix", "suffix", "text", "role", "datum")
    READ = ("value", "text", "side", "row", "offset", "at", "type")

    type = property(lambda s: s._intent["type"])
    value = property(lambda s: s._intent["value"])
    text = property(lambda s: s._intent["text"])

    @property
    def LAYOUT(self):  # noqa: N802 - per-instance layout fields
        return ("at",) if self._intent.get("circle") else ("side", "row", "offset")

    def _lay(self, k):
        v = self._layout.get(k)
        return self._resolved.get(k) if v is None else v

    side = property(lambda s: s._lay("side"))
    row = property(lambda s: s._lay("row"))
    offset = property(lambda s: s._lay("offset") or 0)
    at = property(lambda s: s._lay("at"))

    def _render_text(self):
        i = self._intent
        if i.get("override") is not None:
            i["text"] = str(i["override"])
            return
        sym = {"dia": "Φ", "rad": "R"}.get(i["type"], "")
        dec = int(self._d.std["dim"].get("decimals", 3))
        i["text"] = f"{i['prefix']}{sym}{fmt_num(i['value'], dec)}{i['tol'] or ''}{i['suffix']}"

    def _apply_set(self, fields):
        i = self._intent
        order = ("value", "tol", "prefix", "suffix", "text", "datum", "role")
        for k, v in sorted(fields.items(), key=lambda kv: order.index(kv[0])):
            if k == "value":
                if v is None:
                    i["value"], i["expr"] = i["measured"], None
                    self._covers[:] = []
                else:
                    val, expr, covers = _expr_parts(v)
                    i["value"], i["expr"] = val, expr
                    self._covers[:] = covers
            elif k == "text":
                i["override"] = None if v is None else str(v)
            elif k == "role":
                if v not in ROLES_DIM:
                    raise InvalidArgument(
                        f"尺寸角色 {v!r} 不存在", id=self._id, candidates=list(ROLES_DIM)
                    )
                if v == "position" and not i.get("datum"):
                    raise InvalidArgument(
                        f"{self._id} 改成定位尺寸需要先给 datum",
                        id=self._id,
                        hint="set(role='position', datum=...)",
                    )
                i["role"] = v
            elif k == "datum":
                i["datum"] = _datum(self._d, v, i["view"])
            elif k in ("prefix", "suffix"):
                i[k] = "" if v is None else str(v)
            elif k == "tol":
                i["tol"] = None if v is None else str(v)
        if i["role"] == "position" and not i.get("datum"):
            raise InvalidArgument(f"{self._id} 是定位尺寸，datum 不能为空", id=self._id)
        self._render_text()

    def _apply_place(self, fields):
        _check_layout(self._id, fields, self._intent)
        super()._apply_place(fields)

    def _apply_move(self, dx, dy):
        if self._intent.get("circle"):
            raise InvalidArgument(f"{self._id} 在圆视图上，用 place(at=角度) 调整", id=self._id)
        side = self.side
        if side is None:
            raise InvalidArgument(f"{self._id} 还没有布局结果，先 lcad build", id=self._id)
        normal = {"top": (0, 1), "bottom": (0, -1), "left": (-1, 0), "right": (1, 0)}.get(side)
        if (
            normal is None
        ):  # inside: the dimension line moves across, along x for v-dims, y for h-dims
            normal = (1, 0) if self._intent["dir"] == "v" else (0, 1)
        along = dx * normal[1] - dy * normal[0]
        if abs(along) > 1e-9:
            raise InvalidArgument(
                f"{self._id} 只能沿外法向微调（{side} 侧），文字沿尺寸线的位置由引擎决定",
                id=self._id,
                values={"dx": dx, "dy": dy, "side": side},
                hint="换侧用 place(side=...)，换排用 place(row=...)",
            )
        off = dx * normal[0] + dy * normal[1]
        self._layout["offset"] = (
            self._layout.get("offset") or self._resolved.get("offset") or 0
        ) + off


def _check_layout(eid, fields, intent):
    if "side" in fields and fields["side"] is not None:
        s = fields["side"]
        allowed = (
            ("top", "bottom", "inside") if intent.get("dir") == "h" else ("left", "right", "inside")
        )
        if s not in allowed:
            raise InvalidArgument(
                f"{eid} 是{'水平' if intent.get('dir') == 'h' else '竖直'}尺寸，side 不能是 {s!r}",
                id=eid,
                candidates=list(allowed),
            )
    if "row" in fields and fields["row"] is not None:
        r = fields["row"]
        if not isinstance(r, int) or isinstance(r, bool) or r < 1:
            raise InvalidArgument(f"{eid} 的 row 必须是 ≥1 的整数", id=eid, values={"row": r})
    for k in ("offset", "at"):
        if k in fields and fields[k] is not None:
            fields[k] = num(fields[k], k)


def _datum(d, datum, view):
    if datum is None:
        return None
    if isinstance(datum, Element):
        return datum.id
    if isinstance(datum, str):
        if ":" in datum:
            resolve_point(d, datum, view=view, what="datum")
        else:
            d[datum]
        return datum
    raise InvalidArgument(f"datum 应为元素 ID 或锚点串，收到 {datum!r}")


class DimNS:
    """``view.dim``: dimension constructors bound to one view."""

    def __init__(self, view):
        self._d = view._d
        self._view = view

    def _new(
        self,
        name,
        type_,
        p,
        value,
        tol,
        role,
        datum,
        prefix,
        suffix,
        text,
        layout,
        refs,
        covers_extra=(),
    ):
        d, v = self._d, self._view.name
        if role not in ROLES_DIM:
            raise InvalidArgument(f"尺寸角色 {role!r} 不存在", candidates=list(ROLES_DIM))
        measured = p.pop("measured")
        val, expr, covers = _expr_parts(value)
        if val is None:
            val = measured
        datum_id = _datum(d, datum, v)
        if role == "position" and not datum_id:
            raise InvalidArgument(
                "定位尺寸（role='position'）必须给 datum（基准元素 ID 或锚点）",
                values={"name": name},
                hint="例如 datum='E.front.body.1' 或 datum='E.front.base.1:start'",
            )
        did = f"D.{_required_name(name, '尺寸')}"
        intent = {
            "type": type_,
            "view": v,
            **p,
            "measured": measured,
            "value": val,
            "expr": expr,
            "tol": None if tol is None else str(tol),
            "prefix": prefix or "",
            "suffix": suffix or "",
            "override": None if text is None else str(text),
            "text": "",
            "role": role,
            "datum": datum_id,
        }
        allrefs = [self._view.id, *refs]
        if datum_id:
            allrefs.append(datum_id.split(":")[0])
        el = Dim(d, did, intent, refs=allrefs, covers=sorted(set(covers) | set(covers_extra)))
        el._render_text()
        lay = {k: x for k, x in layout.items() if x is not None}
        _check_layout(did, lay, intent)
        el._layout.update(lay)
        return d._add(el)

    def _two_points(self, p1, p2, dir, ref):
        refs = []
        if ref is not None:
            e = _el(self._d, ref, "ref")
            if not isinstance(e, Edge) or e.shape != "line":
                raise InvalidArgument(f"ref 应为直线边，{e.id} 是 {e.kind}", id=e.id)
            p1, p2 = e.start, e.end
            refs.append(e.id)
        if p1 is None or p2 is None:
            raise InvalidArgument("线性尺寸需要 p1、p2（或 ref=直线边）")
        for p in (p1, p2):
            if isinstance(p, str) and ":" in p:
                refs.append(p.split(":")[0])
        a = resolve_point(self._d, p1, view=self._view.name, what="p1")
        b = resolve_point(self._d, p2, view=self._view.name, what="p2")
        if dir is None:
            if abs(a[1] - b[1]) < 1e-9:
                dir = "h"
            elif abs(a[0] - b[0]) < 1e-9:
                dir = "v"
            else:
                raise InvalidArgument(
                    "两点既不水平也不竖直，请给 dir='h'（量 Δx）或 dir='v'（量 Δy）",
                    values={"p1": list(a), "p2": list(b)},
                )
        if dir not in ("h", "v"):
            raise InvalidArgument(f"dir 只能是 'h' 或 'v'，收到 {dir!r}", candidates=["h", "v"])
        measured = abs(b[0] - a[0]) if dir == "h" else abs(b[1] - a[1])
        if measured < 1e-9:
            raise InvalidArgument(
                "两点在测量方向上重合，尺寸为 0", values={"p1": list(a), "p2": list(b)}
            )
        return {"p1": list(a), "p2": list(b), "dir": dir, "measured": measured}, refs

    def _circle(self, circle, kinds):
        """→ (element id, centre, radius) of a circle/arc edge or a circular centre line."""
        e = _el(self._d, circle, "circle")
        if isinstance(e, Feature) and len(e.edges) == 1:
            e = e.edges[0]
        if e.view != self._view.name:
            raise InvalidArgument(f"{e.id} 在视图 {e.view}，不在 {self._view.name}", id=e.id)
        if isinstance(e, Edge) and e.shape in kinds:
            return e.id, list(e.center), e.r
        if isinstance(e, CenterLine) and e.type == "circle" and "circle" in kinds:
            return e.id, list(e._intent["c"]), e._intent["r"]
        if isinstance(e, Edge) and e.shape == "circle" and kinds == ("arc",):
            raise InvalidArgument(
                f"{e.id} 是整圆：整圆标直径（GB/T 4458.4），用 dim.dia(circle=...)", id=e.id
            )
        raise InvalidArgument(f"circle 应为{'或'.join(kinds)}，{e.id} 不是", id=e.id)

    @mutator("dim.linear")
    def linear(
        self,
        name=None,
        p1=None,
        p2=None,
        dir=None,
        value=None,
        tol=None,
        role="size",
        datum=None,
        prefix="",
        suffix="",
        text=None,
        side=None,
        row=None,
        offset=None,
        ref=None,
    ):
        p, refs = self._two_points(p1, p2, dir, ref)
        return self._new(
            name,
            "linear",
            p,
            value,
            tol,
            role,
            datum,
            prefix,
            suffix,
            text,
            {"side": side, "row": row, "offset": offset},
            refs,
        )

    @mutator("dim.dia")
    def dia(
        self,
        name=None,
        p1=None,
        p2=None,
        circle=None,
        at=None,
        value=None,
        tol=None,
        role="size",
        datum=None,
        prefix="",
        suffix="",
        text=None,
        side=None,
        row=None,
        offset=None,
        ref=None,
    ):
        if circle is not None:
            cid, c, r = self._circle(circle, ("circle", "arc"))
            p = {"circle": cid, "c": c, "r": r, "measured": 2 * r}
            return self._new(
                name, "dia", p, value, tol, role, datum, prefix, suffix, text, {"at": at}, [cid]
            )
        p, refs = self._two_points(p1, p2, None, ref)
        return self._new(
            name,
            "dia",
            p,
            value,
            tol,
            role,
            datum,
            prefix,
            suffix,
            text,
            {"side": side, "row": row, "offset": offset},
            refs,
        )

    @mutator("dim.rad")
    def rad(
        self,
        name=None,
        circle=None,
        at=None,
        value=None,
        tol=None,
        role="size",
        datum=None,
        prefix="",
        suffix="",
        text=None,
    ):
        if circle is None:
            raise InvalidArgument("半径尺寸需要 circle=圆弧边")
        cid, c, r = self._circle(circle, ("arc",))
        p = {"circle": cid, "c": c, "r": r, "measured": r}
        return self._new(
            name, "rad", p, value, tol, role, datum, prefix, suffix, text, {"at": at}, [cid]
        )


class Note(Element):
    """Leader note (anchor + direction) or a technical-requirement line."""

    kind = "note"
    SETTABLE = ("text",)
    READ = ("text",)

    text = property(lambda s: s._intent["text"])

    @property
    def LAYOUT(self):  # noqa: N802
        return () if self._intent.get("tech") else ("dir", "length")

    def _apply_set(self, fields):
        self._intent["text"] = str(fields["text"])

    def _apply_place(self, fields):
        for k in ("dir", "length"):
            if fields.get(k) is not None:
                fields[k] = num(fields[k], k)
        if fields.get("length") is not None and fields["length"] <= 0:
            raise InvalidArgument(f"{self._id} 的 length 必须为正", id=self._id)
        super()._apply_place(fields)

    def _apply_move(self, dx, dy):
        if self._intent.get("tech"):
            raise InvalidArgument("技术要求的位置由模板决定，不能 move", id=self._id)
        sx, sy = self._layout.get("shift", [0.0, 0.0])
        self._layout["shift"] = [sx + dx, sy + dy]


class NotesNS:
    """``d.notes``: technical requirements."""

    def __init__(self, d):
        self._d = d

    def tech(self, lines):
        """Append technical-requirement lines → N.tech.<k> (numbers are never reused)."""
        if isinstance(lines, str):
            lines = [lines]
        return [self._tech_one(t) for t in lines]

    @mutator("notes.tech")
    def _tech_one(self, text):
        d = self._d
        nid = d._alloc("N", ("tech",))
        return d._add(Note(d, nid, {"tech": True, "text": str(text)}))


class Cell(Element):
    """A title-block field."""

    kind = "table.cell"
    SETTABLE = ("text",)
    READ = ("text", "field")

    text = property(lambda s: s._intent["text"])
    field = property(lambda s: s._intent["field"])

    def _apply_set(self, fields):
        self._intent["text"] = "" if fields["text"] is None else str(fields["text"])


class Frame(Element):
    """Sheet border, inner frame and title-block lines (from the template)."""

    kind = "frame"


class Hatch(Element):
    """Section lining over closed loops; nested loops are islands."""

    kind = "hatch"
    READ = ("loops",)

    loops = property(lambda s: list(s._intent["loops"]))


LOOK_VEC = {"left": (-1, 0), "right": (1, 0), "up": (0, 1), "down": (0, -1)}


def _check_look(look, a, b):
    ux, uy = b[0] - a[0], b[1] - a[1]
    lx, ly = LOOK_VEC[look]
    n = math.hypot(ux, uy)
    if abs(ux * ly - uy * lx) / n < 1e-6:
        raise InvalidArgument(
            f"投射方向 {look} 与剖切迹线平行",
            values={"through": [list(a), list(b)]},
            candidates=[k for k, (x, y) in LOOK_VEC.items() if abs(ux * y - uy * x) / n > 1e-6],
        )


class Section(Element):
    """Full section: cutting-plane symbol in ``cut_in`` + ``X-X`` label above ``view``."""

    kind = "section"
    SETTABLE = ("look",)

    def _apply_set(self, fields):
        if fields["look"] not in SECTION_LOOK:
            raise InvalidArgument(
                f"look 只能是 {SECTION_LOOK}", id=self._id, candidates=list(SECTION_LOOK)
            )
        a, b = self._intent["through"]
        _check_look(fields["look"], a, b)
        self._intent["look"] = fields["look"]


def default_look(std, view, cut_in) -> str:
    """Arrow direction in the cut view: first angle → towards the section view, third → away."""
    proj = std["views"]["projection"]
    pos = {"front": [0, 0], **std["views"]["positions"][proj]}
    if view not in pos or cut_in not in pos:
        raise InvalidArgument("剖视的两个视图都要是基本视图", candidates=list(pos))
    dx = pos[view][0] - pos[cut_in][0]
    dy = pos[view][1] - pos[cut_in][1]
    if proj != "first":
        dx, dy = -dx, -dy
    if dx == 0 and dy == 0:
        raise InvalidArgument("view 和 cut_in 不能是同一个视图", values={"view": view})
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "up" if dy > 0 else "down"


# ---- implementations behind View.note/hatch and Drawing.section/title ---------------------


def view_note(self, name, text, anchor, dir=None, length=None):
    d = self._d
    a = resolve_point(d, anchor, view=self.name, what="anchor")
    nid = f"N.{_required_name(name, '引线注释')}"
    refs = [self.id]
    if isinstance(anchor, str):
        refs.append(anchor.split(":")[0])
    el = Note(d, nid, {"view": self.name, "anchor": list(a), "text": str(text)}, refs=refs)
    lay = {}
    if dir is not None:
        lay["dir"] = dir
    if length is not None:
        lay["length"] = length
    el._apply_place(lay)
    return d._add(el)


def _loop_of(d, item, view):
    if isinstance(item, (Element, str)):
        e = _el(d, item, "loop")
        if isinstance(e, Edge) and e.shape == "circle":
            return {"ref": e.id}
        if not isinstance(e, Feature) or not e.closed:
            raise InvalidArgument(
                f"{e.id} 不是闭合特征，不能作剖面线边界",
                id=e.id,
                hint="用 polygon/rect/circle 建闭合特征",
            )
        if e.view != view:
            raise InvalidArgument(f"{e.id} 在视图 {e.view}，不在 {view}", id=e.id)
        return {"ref": e.id}
    pts = [resolve_point(d, p, view=view) for p in item]
    if len(pts) < 3:
        raise InvalidArgument("点列边界至少 3 个点", values={"n": len(pts)})
    return {"points": [list(p) for p in pts]}


def view_hatch(self, name, loops):
    d = self._d
    if not loops:
        raise InvalidArgument("hatch 至少要一个边界环")
    ls = [_loop_of(d, x, self.name) for x in loops]
    hid = f"H.{self.name}.{_required_name(name, '剖面线')}"
    refs = [self.id] + [x["ref"] for x in ls if "ref" in x]
    return d._add(Hatch(d, hid, {"view": self.name, "loops": ls}, refs=refs))


def drawing_section(self, letter, view, cut_in, through, look=None):
    d = self
    if not (isinstance(letter, str) and re.fullmatch(r"[A-Z]", letter)):
        raise InvalidArgument("剖视字母应为一个大写拉丁字母", values={"letter": letter})
    for v in (view, cut_in):
        if f"V.{v}" not in d._els:
            raise NotFound(f"视图 {v} 不存在", id=f"V.{v}", candidates=[e.id for e in d.views()])
    try:
        p1, p2 = through
    except (TypeError, ValueError):
        raise InvalidArgument("through 应为两点 [p1, p2]")
    a = resolve_point(d, p1, view=cut_in, what="through[0]")
    b = resolve_point(d, p2, view=cut_in, what="through[1]")
    if math.dist(a, b) < 1e-9:
        raise InvalidArgument("through 的两点重合", values={"p": list(a)})
    if look is None:
        look = default_look(d.std, view, cut_in)
    elif look not in SECTION_LOOK:
        raise InvalidArgument(f"look 只能是 {SECTION_LOOK}", candidates=list(SECTION_LOOK))
    _check_look(look, a, b)
    intent = {
        "letter": letter,
        "view": view,
        "cut_in": cut_in,
        "through": [list(a), list(b)],
        "look": look,
    }
    return d._add(Section(d, f"S.{letter}", intent, refs=[f"V.{view}", f"V.{cut_in}"]))


def drawing_title(self, **fields):
    cells = {e.field: e for e in self._els.values() if e.kind == "table.cell"}
    bad = [k for k in fields if k not in cells]
    if bad:
        raise InvalidArgument(f"标题栏没有字段 {', '.join(bad)}", candidates=sorted(cells))
    for k, v in fields.items():
        cells[k].set(text=v)


def init_sheet(d):
    """Create T.frame and the title-block cells from the template."""
    tb = d.template["title_block"]
    d._add(Frame(d, "T.frame", {"sheet": d.sheet, "size": list(d.template["size"])}))
    for field, spec in tb["fields"].items():
        text = d.scale_text if field == "scale" else spec.get("default", "")
        d._add(
            Cell(
                d,
                f"T.title.{field}",
                {"field": field, "label": spec.get("label", field), "text": text},
            )
        )
