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
LEADER_TYPES = ("chamfer", "groove", "hole", "spline")  # dimensions written on a leader
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


_FIT_RE = re.compile(r"^(?P<letters>[A-Za-z]{1,2})(?P<grade>\d{1,2})$")
_NUM = r"[+\-]?\d+(?:\.\d+)?"


def fmt_dev(vals):
    """Upper / lower deviations with the same number of decimals; 0 written as 0 (GB/T 4458.5)."""
    dec = max(len(fmt_num(abs(v), 4).partition(".")[2]) for v in vals)
    out = []
    for v in vals:
        if abs(v) < 1e-12:
            out.append("0")
        else:
            out.append(("+" if v > 0 else "-") + f"{abs(v):.{max(dec, 1)}f}")
    return out


def parse_tol(tol, size, envelope=False):
    """Tolerance text → structured tolerance (SPEC M1 §3.1), or None."""
    if tol is None:
        return None
    if isinstance(tol, (list, tuple)) and len(tol) == 2:
        up, lo = float(tol[0]), float(tol[1])
        kind = "dev"
        code = None
    else:
        s = str(tol).strip().replace("＋", "+").replace("－", "-").replace("−", "-")
        m = _FIT_RE.match(s)
        if m:
            from . import res

            f = res.fit(s, size)
            return {
                "kind": "fit",
                "code": f["code"],
                "upper": f["upper"],
                "lower": f["lower"],
                "envelope": bool(envelope),
                "std": f.get("std"),
            }
        pair = re.fullmatch(r"([A-Z]{1,2}\d{1,2})\s*/\s*([a-z]{1,2}\d{1,2})", s)
        if pair:  # assembly fit hole/shaft, e.g. H7/k6 (GB/T 1800.1; GB/T 4458.5 注法)
            from . import res

            h, sh = res.fit(pair.group(1), size), res.fit(pair.group(2), size)
            return {
                "kind": "fit",
                "code": f"{h['code']}/{sh['code']}",
                "upper": h["upper"],
                "lower": h["lower"],
                "shaft": {"code": sh["code"], "upper": sh["upper"], "lower": sh["lower"]},
                "envelope": bool(envelope),
                "std": h.get("std"),
            }
        if re.fullmatch(r"±\s*\d+(?:\.\d+)?", s):
            v = float(s[1:])
            up, lo, kind, code = v, -v, "sym", None
        elif re.fullmatch(rf"({_NUM})\s*/\s*({_NUM})", s):
            a, b = re.fullmatch(rf"({_NUM})\s*/\s*({_NUM})", s).groups()
            up, lo, kind, code = float(a), float(b), "dev", None
        else:
            raise InvalidArgument(
                f"公差 {tol!r} 看不懂",
                values={"tol": tol},
                candidates=["k6", "H7", "H7/k6", "±0.1", "+0.021/0", "-0.02/-0.05"],
                hint="配合代号、对称公差 ±x，或 上偏差/下偏差",
            )
    if up < lo - 1e-12:
        raise InvalidArgument(f"上偏差 {up:g} 小于下偏差 {lo:g}", values={"upper": up, "lower": lo})
    return {
        "kind": kind,
        "upper": up,
        "lower": lo,
        "envelope": bool(envelope),
        "std": None,
        "code": code,
    }


class Dim(Element):
    """A dimension: linear (h/v), aligned, diameter, radius, angle or chamfer."""

    kind = "dim"
    SETTABLE = (
        "value",
        "tol",
        "fit",
        "tol_show",
        "envelope",
        "reference",
        "prefix",
        "suffix",
        "text",
        "role",
        "datum",
    )
    READ = ("value", "text", "side", "row", "offset", "at", "type", "tolerance")

    type = property(lambda s: s._intent["type"])
    value = property(lambda s: s._intent["value"])
    text = property(lambda s: s._intent["text"])
    tolerance = property(lambda s: dict(s._intent["tolerance"] or {}) or None)

    @property
    def LAYOUT(self):  # noqa: N802 - per-instance layout fields
        t = self._intent["type"]
        if t in LEADER_TYPES:
            return ("dir", "length")
        if t == "angle":
            return ("r",)
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
        i["dev"], i["tail"] = None, ""
        if i.get("override") is not None:
            i["text"] = str(i["override"])
            return
        if i.get("designation"):
            i["text"] = f"{i['prefix']}{i['designation']}{i['suffix']}"
            return
        dec = int(self._d.std["dim"].get("decimals", 3))
        if i["type"] == "angle":
            base = f"{i['prefix']}{fmt_num(i['value'], dec)}°"
        elif i["type"] == "chamfer":
            c = fmt_num(i["value"], dec)
            ang = i.get("angle", 45.0)
            base = f"C{c}" if abs(ang - 45) < 0.01 else f"{c}×{fmt_num(ang, 2)}°"
            base = f"{i['prefix']}{base}"
        else:
            sym = {"dia": "Φ", "rad": "R"}.get(i["type"], "")
            base = f"{i['prefix']}{sym}{fmt_num(i['value'], dec)}"
        t, show = i.get("tolerance"), i.get("tol_show") or "code"
        if t is None:
            if i.get("tol") and i["type"] == "angle":
                base += str(i["tol"])
            text, tail = base, ""
        elif t["kind"] == "sym":
            text, tail = f"{base}±{fmt_num(t['upper'], 4)}", ""
        elif t["kind"] == "fit" and show == "code":
            text, tail = f"{base}{t['code']}", ""
        else:
            i["dev"] = fmt_dev([t["upper"], t["lower"]])
            if t["kind"] == "fit" and show == "both":
                text, tail = f"{base}{t['code']}(", ")"
            else:
                text, tail = base, ""
        if i.get("reference") and i["dev"] is None:
            text = f"({text}{i['suffix']})"
        else:
            if i["dev"] is not None:
                tail = f"{tail}{i['suffix']}"
            else:
                text = f"{text}{i['suffix']}"
        i["text"], i["tail"] = text, tail

    def _retol(self):
        i = self._intent
        if i["type"] in ("angle",) + LEADER_TYPES:
            i["tolerance"] = None
            return
        env = bool(i.get("envelope"))
        try:
            i["tolerance"] = parse_tol(i.get("tol"), i["value"], env)
        except InvalidArgument as e:
            e.id = e.id or self._id
            raise
        if i["tolerance"] is not None and i.get("tol_show") is None:
            pass
        if i["tolerance"] is not None and i["tolerance"]["kind"] != "fit":
            i["tol_show"] = "dev"
        elif i.get("tol_show") == "dev" and i["tolerance"] is None:
            i["tol_show"] = None

    def _apply_set(self, fields):
        i = self._intent
        if "fit" in fields:
            fields = dict(fields)
            fields["tol"] = fields.pop("fit")
        order = (
            "value",
            "tol",
            "tol_show",
            "envelope",
            "reference",
            "prefix",
            "suffix",
            "text",
            "datum",
            "role",
        )
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
                i["tol"] = (
                    None if v is None else (list(v) if isinstance(v, (list, tuple)) else str(v))
                )
                i["tol_show"] = None
            elif k == "tol_show":
                if v not in (None, "code", "dev", "both"):
                    raise InvalidArgument(
                        "tol_show 只能是 code / dev / both",
                        id=self._id,
                        candidates=["code", "dev", "both"],
                    )
                i["tol_show"] = v
            elif k in ("envelope", "reference"):
                i[k] = bool(v)
        if i["role"] == "position" and not i.get("datum"):
            raise InvalidArgument(f"{self._id} 是定位尺寸，datum 不能为空", id=self._id)
        self._retol()
        if i.get("tol_show") is None and i.get("tolerance"):
            i["tol_show"] = "code" if i["tolerance"]["kind"] == "fit" else "dev"
        if i.get("tol_show") in ("dev", "both") and not i.get("tolerance"):
            i["tol_show"] = None
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
        if intent.get("type") == "aligned":
            allowed = ("top", "bottom", "left", "right")
        else:
            allowed = (
                ("top", "bottom", "inside")
                if intent.get("dir") == "h"
                else ("left", "right", "inside")
            )
        if s not in allowed:
            raise InvalidArgument(
                f"{eid} 是{ {'h': '水平', 'v': '竖直'}.get(intent.get('dir'), '对齐') }尺寸，side 不能是 {s!r}",
                id=eid,
                candidates=list(allowed),
            )
    if "row" in fields and fields["row"] is not None:
        r = fields["row"]
        if not isinstance(r, int) or isinstance(r, bool) or r < 1:
            raise InvalidArgument(f"{eid} 的 row 必须是 ≥1 的整数", id=eid, values={"row": r})
    for k in ("offset", "at", "r", "dir", "length"):
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
        pmi=None,
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
            "tol": None
            if tol is None
            else (list(tol) if isinstance(tol, (list, tuple)) else str(tol)),
            "tolerance": None,
            "tol_show": (pmi or {}).get("tol_show"),
            "envelope": bool((pmi or {}).get("envelope")),
            "reference": bool((pmi or {}).get("reference")),
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
        el._apply_set({})  # tolerance lookup, display mode, text
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
        tol_show=None,
        envelope=False,
        reference=False,
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
            pmi={"tol_show": tol_show, "envelope": envelope, "reference": reference},
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
        tol_show=None,
        envelope=False,
        reference=False,
    ):
        if circle is not None:
            cid, c, r = self._circle(circle, ("circle", "arc"))
            p = {"circle": cid, "c": c, "r": r, "measured": 2 * r}
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
                {"at": at},
                [cid],
                pmi={"tol_show": tol_show, "envelope": envelope, "reference": reference},
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
            pmi={"tol_show": tol_show, "envelope": envelope, "reference": reference},
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
        tol_show=None,
        envelope=False,
        reference=False,
    ):
        if circle is None:
            raise InvalidArgument("半径尺寸需要 circle=圆弧边")
        cid, c, r = self._circle(circle, ("arc",))
        p = {"circle": cid, "c": c, "r": r, "measured": r}
        return self._new(
            name,
            "rad",
            p,
            value,
            tol,
            role,
            datum,
            prefix,
            suffix,
            text,
            {"at": at},
            [cid],
            pmi={"tol_show": tol_show, "envelope": envelope, "reference": reference},
        )

    def _line_edge(self, ref, what):
        e = _el(self._d, ref, what)
        if not isinstance(e, Edge) or e.shape != "line":
            raise InvalidArgument(f"{what} 应为直线边，{e.id} 是 {e.kind}", id=e.id)
        if e.view != self._view.name:
            raise InvalidArgument(f"{e.id} 在视图 {e.view}，不在 {self._view.name}", id=e.id)
        return e

    @mutator("dim.aligned")
    def aligned(
        self,
        name=None,
        p1=None,
        p2=None,
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
        tol_show=None,
        envelope=False,
        reference=False,
    ):
        """Aligned dimension: measures the true distance p1–p2 (GB/T 4458.4)."""
        refs = []
        if ref is not None:
            e = self._line_edge(ref, "ref")
            p1, p2 = e.start, e.end
            refs.append(e.id)
        if p1 is None or p2 is None:
            raise InvalidArgument("对齐尺寸需要 p1、p2（或 ref=直线边）")
        for q in (p1, p2):
            if isinstance(q, str) and ":" in q:
                refs.append(q.split(":")[0])
        a = resolve_point(self._d, p1, view=self._view.name, what="p1")
        b = resolve_point(self._d, p2, view=self._view.name, what="p2")
        m = math.dist(a, b)
        if m < 1e-9:
            raise InvalidArgument("两点重合，尺寸为 0", values={"p1": list(a)})
        p = {"p1": list(a), "p2": list(b), "dir": "a", "measured": m}
        return self._new(
            name,
            "aligned",
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
            pmi={"tol_show": tol_show, "envelope": envelope, "reference": reference},
        )

    @mutator("dim.angle")
    def angle(
        self, name=None, line1=None, line2=None, value=None, tol=None, prefix="", text=None, r=None
    ):
        """Angle between two line edges; the number is written horizontally (GB/T 4458.4)."""
        e1, e2 = self._line_edge(line1, "line1"), self._line_edge(line2, "line2")
        (a, b), (c, d_) = (e1.start, e1.end), (e2.start, e2.end)
        den = (b[0] - a[0]) * (d_[1] - c[1]) - (b[1] - a[1]) * (d_[0] - c[0])
        if abs(den) < 1e-12:
            raise InvalidArgument(f"{e1.id} 与 {e2.id} 平行，没有角度", id=e1.id)
        t = ((c[0] - a[0]) * (d_[1] - c[1]) - (c[1] - a[1]) * (d_[0] - c[0])) / den
        V = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

        def ray(p, q):
            far = p if math.dist(p, V) > math.dist(q, V) else q
            return math.degrees(math.atan2(far[1] - V[1], far[0] - V[0]))

        a1, a2 = ray(a, b), ray(c, d_)
        sweep = (a2 - a1) % 360
        if sweep > 180:
            a1, a2, sweep = a2, a1, 360 - sweep
        p = {"vertex": list(V), "a1": a1, "a2": a2, "dir": "angle", "measured": sweep}
        el = self._new(
            name, "angle", p, value, tol, "size", None, prefix, "", text, {"r": r}, [e1.id, e2.id]
        )
        return el

    @mutator("dim.chamfer")
    def chamfer(self, name=None, edge=None, prefix="", text=None, dir=None, length=None):
        """Chamfer on a turned part (axis along x): 45° → ``C<n>``, else ``<n>×<angle>°``."""
        e = self._line_edge(edge, "edge")
        (x0, y0), (x1, y1) = e.start, e.end
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        if dx < 1e-9 or dy < 1e-9:
            raise InvalidArgument(f"{e.id} 不是倒角斜边（水平或竖直）", id=e.id)
        ang = math.degrees(math.atan2(dy, dx))
        size = dx if abs(ang - 45) >= 0.01 else dx
        p = {
            "p1": [x0, y0],
            "p2": [x1, y1],
            "anchor": [(x0 + x1) / 2, (y0 + y1) / 2],
            "angle": round(ang, 4),
            "size": size,
            "dir": "chamfer",
            "measured": size,
        }
        return self._new(
            name,
            "chamfer",
            p,
            None,
            None,
            "size",
            None,
            prefix,
            "",
            text,
            {"dir": dir, "length": length},
            [e.id],
        )

    # ---- designation dimensions of conventional features (SPEC M1 §4) --------------------------
    def _conv(self, feature, types):
        f = _el(self._d, feature, "feature")
        if not isinstance(f, Feature) or f.type not in types:
            raise InvalidArgument(
                f"{f.id} 不是 {'/'.join(types)} 特征", id=f.id, candidates=list(types)
            )
        if f.view != self._view.name:
            raise InvalidArgument(f"{f.id} 在视图 {f.view}，不在 {self._view.name}", id=f.id)
        return f

    def _leader(self, name, type_, anchor, measured, designation, refs, dir, length, extra=None):
        p = {
            "anchor": list(anchor),
            "p1": list(anchor),
            "p2": list(anchor),
            "dir": type_,
            "measured": measured,
            **(extra or {}),
        }
        el = self._new(
            name,
            type_,
            p,
            None,
            None,
            "size",
            None,
            "",
            "",
            None,
            {"dir": dir, "length": length},
            refs,
        )
        el._intent["designation"] = designation
        el._render_text()
        return el

    @mutator("dim.thread")
    def thread(self, name=None, feature=None, side=None, row=None, offset=None, at=None):
        """Thread designation on the major diameter: M20×1.5-6g (coarse pitch not written)."""
        f = self._conv(feature, ("thread", "thread_mesh"))
        i = f._intent
        des = (
            f"M{fmt_num(i['d'])}"
            + ("" if i.get("coarse") else f"×{fmt_num(i['P'])}")
            + f"-{i['cls']}"
        )
        if i.get("end_view"):
            circ = [e for e in f.edges if e.shape == "circle"][0]
            el = self.dia(name, circle=circ, at=at)
        else:
            xm, ax, r = (i["x0"] + i["x1"]) / 2, i["axis"], i["d"] / 2
            el = self.dia(name, (xm, ax + r), (xm, ax - r), side=side, row=row, offset=offset)
        el._intent["designation"] = des
        el._intent["feature"] = f.id
        el._refs.append(f.id)
        el._render_text()
        return el

    @mutator("dim.groove")
    def groove(self, name=None, groove=None, fmt="wd", dir=None, length=None):
        """Undercut / overrun groove: width × diameter (wd) or width × depth (wh)."""
        f = self._conv(groove, ("groove",))
        i = f._intent
        if fmt not in ("wd", "wh"):
            raise InvalidArgument(
                "fmt 只能是 'wd'（槽宽×直径）或 'wh'（槽宽×槽深）", candidates=["wd", "wh"]
            )
        des = (
            f"{fmt_num(i['w'])}×Φ{fmt_num(i['d'])}"
            if fmt == "wd"
            else f"{fmt_num(i['w'])}×{fmt_num(i['r'] - i['rg'])}"
        )
        anchor = ((i["x0"] + i["x1"]) / 2, i["axis"] + i["rg"])
        return self._leader(
            name, "groove", anchor, i["w"], des, [f.id], dir, length, {"x0": i["x0"], "x1": i["x1"]}
        )

    @mutator("dim.hole")
    def hole(self, name=None, feature=None, n=1, dir=None, length=None):
        """Hole callout on a leader, e.g. 4×M8-6H↧16 (GB/T 16675.2 depth symbol)."""
        f = self._conv(feature, ("tapped_hole", "thread"))
        i = f._intent
        des = (
            ("" if int(n) == 1 else f"{int(n)}×")
            + f"M{fmt_num(i['d'])}"
            + ("" if i.get("coarse") else f"×{fmt_num(i['P'])}")
            + f"-{i['cls']}"
        )
        if i.get("depth"):
            des += f"↧{fmt_num(i['depth'])}"
        if i.get("end_view"):
            c, r = i["c"], i["d"] / 2
            anchor = (c[0] + r * 0.7071, c[1] + r * 0.7071)
        else:
            anchor = tuple(i["points"][0])
        return self._leader(name, "hole", anchor, i["d"], des, [f.id], dir, length)

    @mutator("dim.spline")
    def spline(self, name=None, feature=None, dir=None, length=None):
        """Rectangular spline designation (GB/T 1144): ⨅ N×d f×D f×B f + standard."""
        f = self._conv(feature, ("spline",))
        i = f._intent
        fd, fD, fB = i.get("fits") or ["f7", "a11", "d10"]
        des = f"⨅{i['N']}×{fmt_num(i['d'])}{fd}×{fmt_num(i['D'])}{fD}×{fmt_num(i['B'])}{fB} {i.get('std') or ''}".strip()
        if i.get("end_view"):
            anchor = (i["c"][0], i["c"][1] + i["D"] / 2)
        else:
            anchor = ((i["x0"] + i["x1"]) / 2, i["axis"] + i["D"] / 2)
        return self._leader(name, "spline", anchor, i["D"], des, [f.id], dir, length)

    @mutator("dim.keyway")
    def keyway(self, name=None, feature=None, what="b", side=None, row=None, offset=None):
        """Keyway width b (N9 shaft / JS9 hub) or depth d−t1 / d+t2 with the GB/T 1095 deviations."""
        f = self._conv(feature, ("shaft_cut", "keyway"))
        i = f._intent
        if what not in ("b", "depth"):
            raise InvalidArgument("what 只能是 'b' 或 'depth'", candidates=["b", "depth"])
        if f.type == "shaft_cut":
            if not i.get("keyway"):
                raise InvalidArgument(f"{f.id} 没有键槽", id=f.id)
            kw = self._d[i["keyway"]]._intent
            c, r, ang, hub = tuple(i.get("c") or (0.0, 0.0)), i["d"] / 2, i["notch_angle"], False
        else:
            kw = i
            c, r, ang, hub = tuple(i["c"]), i["d"] / 2, 90.0, True
            ang = (
                math.degrees(math.atan2(*reversed([p - q for p, q in zip(i["points"][-2], c)])))
                if False
                else ang
            )
        u = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
        t = (-u[1], u[0])
        b = kw["b"]
        if what == "b":
            depth = -kw["t2"] if hub else kw["t1"]
            inner = r - depth
            p1 = (c[0] + u[0] * inner - t[0] * b / 2, c[1] + u[1] * inner - t[1] * b / 2)
            p2 = (c[0] + u[0] * inner + t[0] * b / 2, c[1] + u[1] * inner + t[1] * b / 2)
            tol = kw.get("tol_b") or ("JS9" if hub else "N9")
            el = self.linear(name, p1, p2, value=b, tol=tol, side=side, row=row, offset=offset)
            el._refs.append(f.id)  # conv_dim counts dimensions that reference the keyway
            return el
        far = (c[0] - u[0] * r, c[1] - u[1] * r)
        if hub:
            near = (c[0] + u[0] * (r + kw["t2"]), c[1] + u[1] * (r + kw["t2"]))
            val, dev = 2 * r + kw["t2"], kw.get("t2_dev")
            tol = None if not dev else (dev[0], 0.0)
        else:
            near = (c[0] + u[0] * (r - kw["t1"]), c[1] + u[1] * (r - kw["t1"]))
            val, dev = 2 * r - kw["t1"], kw.get("t1_dev")
            tol = None if not dev else (0.0, -dev[0])
        el = self.linear(name, far, near, value=val, tol=tol, side=side, row=row, offset=offset)
        el._refs.append(f.id)
        return el


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


def _cell_parts(value):
    """Cell input → (rendered text, expr src or None, covered param names)."""
    if value is None:
        return "", None, []
    if hasattr(value, "src") and hasattr(value, "params"):
        val, expr, covers = _expr_parts(value)
        return fmt_num(val), expr, covers
    return str(value), None, []


class Cell(Element):
    """A title-block field or semantic table cell."""

    kind = "table.cell"
    SETTABLE = ("text",)
    READ = ("text", "field", "table", "row", "col", "header")

    text = property(lambda s: s._intent["text"])
    field = property(lambda s: s._intent.get("field"))
    table = property(lambda s: s._intent.get("table"))
    row = property(lambda s: s._intent.get("row"))
    col = property(lambda s: s._intent.get("col"))
    header = property(lambda s: s._intent.get("header"))

    def _apply_set(self, fields):
        text, expr, covers = _cell_parts(fields["text"])
        self._intent["text"] = text
        if expr is not None:
            self._intent["expr"] = expr
        else:
            self._intent.pop("expr", None)
        self._covers[:] = covers

    def suppress(self):
        if "table" in self._intent and "field" not in self._intent:
            tbl = self._intent["table"]
            raise InvalidArgument(
                f'不能单独删除单元格 {self._id}；删除整张表用 d["T.{tbl}"].suppress()，清空内容用 .text = ""',
                id=self._id,
                candidates=[f"T.{tbl}"],
            )
        return super().suppress()


def _check_positive(v, what):
    if isinstance(v, bool):
        raise InvalidArgument(f"{what} 不能是布尔值", values={what: repr(v)})
    val = num(v, what)
    if val <= 0:
        raise InvalidArgument(f"{what} 必须大于 0（当前 {val:g}）", values={what: val})
    return val


def _check_table_cols(cols, ncols):
    if not isinstance(cols, (list, tuple)) or len(cols) != ncols:
        raise InvalidArgument(
            f"cols 必须给出 {ncols} 个正数列宽",
            values={"expected_len": ncols},
        )
    return [_check_positive(w, f"cols[{k}]") for k, w in enumerate(cols)]


def _check_table_at(at):
    if at is None:
        return None
    if not isinstance(at, (list, tuple)) or len(at) != 2:
        raise InvalidArgument("at 必须是 (x, y) 二元坐标")
    if isinstance(at[0], bool) or isinstance(at[1], bool):
        raise InvalidArgument("at 坐标不能包含布尔值")
    return [num(at[0], "at[0]"), num(at[1], "at[1]")]


class Table(Element):
    """Semantic sheet table (``d.table``): ``T.<name>`` owns 1-based ``T.<name>.<r>.<c>`` cells."""

    kind = "table"
    SETTABLE = ("title", "cols", "row_height", "text_height", "wrap")
    LAYOUT = ("at",)
    READ = (
        "name",
        "title",
        "cols",
        "row_height",
        "text_height",
        "wrap",
        "nrows",
        "ncols",
        "at",
        "headers",
    )

    name = property(lambda s: s._intent["name"])
    title = property(lambda s: s._intent.get("title"))
    cols = property(
        lambda s: (
            list(s._intent["cols"])
            if s._intent.get("cols") is not None
            else (list(s._resolved["cols"]) if "cols" in s._resolved else None)
        )
    )
    row_height = property(lambda s: s._intent.get("row_height"))
    text_height = property(lambda s: s._intent.get("text_height"))
    wrap = property(lambda s: s._intent.get("wrap", True))
    nrows = property(lambda s: s._intent["nrows"])
    ncols = property(lambda s: s._intent["ncols"])
    headers = property(lambda s: s._intent.get("headers"))

    @property
    def at(self):
        v = self._layout.get("at")
        if v is not None:
            ox, oy = self._layout.get("offset", [0.0, 0.0])
            return [v[0] + ox, v[1] + oy]
        r = self._resolved.get("at")
        return list(r) if r is not None else None

    def _children(self):
        name = self._intent["name"]
        return [
            f"T.{name}.{r}.{c}"
            for r in range(1, self._intent["nrows"] + 1)
            for c in range(1, self._intent["ncols"] + 1)
        ]

    def _apply_set(self, fields):
        if "title" in fields:
            t = fields["title"]
            self._intent["title"] = None if t is None else str(t)
        if "cols" in fields:
            c = fields["cols"]
            self._intent["cols"] = (
                None if c is None else _check_table_cols(c, self._intent["ncols"])
            )
        if "row_height" in fields:
            rh = fields["row_height"]
            self._intent["row_height"] = None if rh is None else _check_positive(rh, "row_height")
        if "text_height" in fields:
            th = fields["text_height"]
            self._intent["text_height"] = None if th is None else _check_positive(th, "text_height")
        if "wrap" in fields:
            if not isinstance(fields["wrap"], bool):
                raise InvalidArgument("wrap 必须是 bool")
            self._intent["wrap"] = fields["wrap"]

    def _apply_place(self, fields):
        if "at" in fields:
            self._layout["at"] = _check_table_at(fields["at"])
            self._layout.pop("offset", None)
            if self._layout["at"] is None:
                self._resolved.pop("at", None)

    def _apply_move(self, dx, dy):
        ox, oy = self._layout.get("offset", [0.0, 0.0])
        self._layout["offset"] = [ox + dx, oy + dy]
        if self._layout.get("at") is None and "at" in self._resolved:
            r = self._resolved["at"]
            self._resolved["at"] = [r[0] + dx, r[1] + dy]


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


def _check_path_look(look, pts):
    _check_look(look, pts[0], pts[1])
    _check_look(look, pts[-2], pts[-1])


def section_kind(pts) -> str:
    """full (2 points) / stepped (axis-parallel legs, right-angle turns) / aligned."""
    if len(pts) == 2:
        return "full"
    segs = list(zip(pts, pts[1:]))
    axis = [abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9 for a, b in segs]
    if all(axis):
        return "stepped"
    return "aligned"


class Section(Element):
    """Section cutting-plane symbol in ``cut_in`` (any polyline path) + ``X-X`` label above
    ``view``: full, stepped, aligned (rotated) or removed sections (SPEC M1 §5)."""

    kind = "section"
    SETTABLE = ("look",)

    def _apply_set(self, fields):
        if fields["look"] not in SECTION_LOOK:
            raise InvalidArgument(
                f"look 只能是 {SECTION_LOOK}", id=self._id, candidates=list(SECTION_LOOK)
            )
        _check_path_look(fields["look"], self._intent["through"])
        self._intent["look"] = fields["look"]


VIEW_DIR = {
    "front": (0, 1, 0),
    "top": (0, 0, -1),
    "bottom": (0, 0, 1),
    "left": (1, 0, 0),
    "right": (-1, 0, 0),
    "rear": (0, -1, 0),
}


def default_look(std, view, cut_in) -> str:
    """Arrow direction in ``cut_in``: the section view's viewing direction (model axes) in
    ``cut_in``'s local axes (SPEC 3.1). Holds for first- and third-angle projection alike."""
    from .checks import VIEW_AXES

    if view not in VIEW_DIR or cut_in not in VIEW_DIR:
        raise InvalidArgument("剖视的两个视图都要是基本视图", candidates=list(VIEW_DIR))
    if view == cut_in:
        raise InvalidArgument("view 和 cut_in 不能是同一个视图", values={"view": view})
    look = dict(zip("XYZ", VIEW_DIR[view]))
    (su, au), (sv, av) = VIEW_AXES[cut_in]
    du, dv = su * look[au], sv * look[av]
    if du == 0 and dv == 0:
        raise InvalidArgument(
            f"在 {cut_in} 视图里看不到 {view} 的投射方向，请给 look=", candidates=list(SECTION_LOOK)
        )
    if abs(du) >= abs(dv):
        return "right" if du > 0 else "left"
    return "up" if dv > 0 else "down"


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


def view_hatch(self, name, loops, outline=None):
    d = self._d
    if outline not in (None, "thin", "thick"):
        raise InvalidArgument(
            "outline 只能是 None、'thin'（重合断面）或 'thick'", values={"outline": outline}
        )
    if not loops:
        raise InvalidArgument("hatch 至少要一个边界环")
    ls = [_loop_of(d, x, self.name) for x in loops]
    hid = f"H.{self.name}.{_required_name(name, '剖面线')}"
    refs = [self.id] + [x["ref"] for x in ls if "ref" in x]
    intent = {"view": self.name, "loops": ls}
    if outline:
        intent["outline"] = outline
    return d._add(Hatch(d, hid, intent, refs=refs))


def drawing_section(self, letter, view, cut_in, through, look=None):
    d = self
    if not (isinstance(letter, str) and re.fullmatch(r"[A-Z]", letter)):
        raise InvalidArgument("剖视字母应为一个大写拉丁字母", values={"letter": letter})
    for v in (view, cut_in):
        if f"V.{v}" not in d._els:
            raise NotFound(f"视图 {v} 不存在", id=f"V.{v}", candidates=[e.id for e in d.views()])
    try:
        pts = [
            resolve_point(d, p, view=cut_in, what=f"through[{k}]") for k, p in enumerate(through)
        ]
    except TypeError:
        raise InvalidArgument("through 应为点列 [p1, p2, ...]")
    if len(pts) < 2:
        raise InvalidArgument("through 至少两个点", values={"n": len(pts)})
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) < 1e-9:
            raise InvalidArgument("through 有重合的相邻点", values={"p": list(a)})
    if look is None:
        look = default_look(d.std, view, cut_in)
    elif look not in SECTION_LOOK:
        raise InvalidArgument(f"look 只能是 {SECTION_LOOK}", candidates=list(SECTION_LOOK))
    _check_path_look(look, pts)
    intent = {
        "letter": letter,
        "view": view,
        "cut_in": cut_in,
        "through": [list(p) for p in pts],
        "look": look,
        "kind": section_kind(pts),
    }
    return d._add(Section(d, f"S.{letter}", intent, refs=[f"V.{view}", f"V.{cut_in}"]))


def drawing_title(self, **fields):
    cells = {
        e.field: e for e in self._els.values() if e.kind == "table.cell" and "field" in e._intent
    }
    bad = [k for k in fields if k not in cells]
    if bad:
        raise InvalidArgument(f"标题栏没有字段 {', '.join(bad)}", candidates=sorted(cells))
    for k, v in fields.items():
        cells[k].set(text=v)


RESERVED_TABLE_NAMES = ("title", "bom", "frame")


def drawing_table(
    self,
    name,
    rows,
    *,
    headers=None,
    title=None,
    cols=None,
    row_height=None,
    text_height=None,
    at=None,
    wrap=True,
):
    """Create a semantic parameter/spec table ``T.<name>`` and 1-based cells ``T.<name>.<r>.<c>``."""
    check_name(name, "表名")
    if name in RESERVED_TABLE_NAMES:
        raise InvalidArgument(
            f'表名不能用 "{name}"（已保留给系统元素 T.{name}）', values={"name": name}
        )
    if not isinstance(rows, (list, tuple)) or not rows:
        raise InvalidArgument("rows 必须是非空二维行序列")
    if not all(isinstance(r, (list, tuple)) and r for r in rows):
        raise InvalidArgument("rows 的每一行必须是非空序列")
    if headers is not None:
        if not isinstance(headers, (list, tuple)) or not headers:
            raise InvalidArgument("headers 必须是非空序列")
        ncols = len(headers)
    else:
        ncols = len(rows[0])
    for idx, row in enumerate(rows, 1):
        if len(row) != ncols:
            raise InvalidArgument(
                f"第 {idx} 行有 {len(row)} 列，与表头/首行 {ncols} 列不一致",
                values={"row": idx, "got": len(row), "expected": ncols},
            )
    if not isinstance(wrap, bool):
        raise InvalidArgument("wrap 必须是 bool")
    cols_v = None if cols is None else _check_table_cols(cols, ncols)
    rh_v = None if row_height is None else _check_positive(row_height, "row_height")
    th_v = None if text_height is None else _check_positive(text_height, "text_height")
    at_v = _check_table_at(at)

    all_rows = ([list(headers)] if headers is not None else []) + [list(r) for r in rows]
    nrows = len(all_rows)
    intent = {
        "name": name,
        "title": None if title is None else str(title),
        "cols": cols_v,
        "row_height": rh_v,
        "text_height": th_v,
        "wrap": wrap,
        "nrows": nrows,
        "ncols": ncols,
        "headers": bool(headers is not None),
    }
    tbl = self._add(Table(self, f"T.{name}", intent))
    if at_v is not None:
        tbl._layout["at"] = at_v
    for r, row in enumerate(all_rows, 1):
        is_hdr = bool(headers is not None and r == 1)
        for c, raw_val in enumerate(row, 1):
            text, expr, covers = _cell_parts(raw_val)
            cintent = {
                "table": name,
                "row": r,
                "col": c,
                "header": is_hdr,
                "text": text,
            }
            if expr is not None:
                cintent["expr"] = expr
            self._add(Cell(self, f"T.{name}.{r}.{c}", cintent, covers=covers))
    return tbl


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
                {
                    "table": "title",
                    "field": field,
                    "label": spec.get("label", field),
                    "text": text,
                },
            )
        )
