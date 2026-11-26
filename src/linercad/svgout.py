"""SVG for the Viewer (M2 SPEC §1): written straight from the layout prims — the same prims the
DXF writer turns into entities — so every SVG node carries the element ID (``data-id``) and the
sub-prim index (``data-k``) that the DXF XDATA holds."""

from __future__ import annotations

import base64
import math
from html import escape
from pathlib import Path

from .layout import Arc, Circle, Hatch, Image, Line, Poly, Solid, Text
from .text import dxf_height, has_cjk


def _f(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _dash(std, role, ltscale=1.0):
    lt = std["lines"].get(role, {}).get("linetype", "CONTINUOUS")
    spec = std["linetypes"].get(lt)
    if not isinstance(spec, dict):
        return ""
    pat = [abs(x) * ltscale or 0.3 for x in spec["pattern"]]
    return f' stroke-dasharray="{",".join(_f(x) for x in pat)}"'


def _ctx(d):
    std = d.std
    W, H = d.template["size"]

    def P(p):
        return f"{_f(p[0])},{_f(H - p[1])}"

    widths = {r: s["width"] for r, s in std["lines"].items() if isinstance(s, dict)}
    return std, W, H, P, widths


def svg_groups(d) -> list[tuple[str, str, str]]:
    """``[(element id, kind, '<g data-id=..>..</g>')]`` of every drawn element, in paint order."""
    std, _W, H, P, widths = _ctx(d)
    out = []
    for e in d._els.values():
        cb = e._resolved.get("cell_box") if e.kind == "table.cell" else None
        has_cell = e.kind == "table.cell" and cb is not None
        if not e._prims and not has_cell:
            continue
        tbl = e._intent.get("table")
        tattr = f' data-table="{escape(tbl)}"' if tbl else ""
        parts = [f'<g data-id="{escape(e.id)}" data-kind="{escape(e.kind)}"{tattr}>']
        if has_cell:
            x0, y0, x1, y1 = cb
            parts.append(
                f'<rect data-k="hit" class="cell-hit" x="{_f(x0)}" y="{_f(H - y1)}" '
                f'width="{_f(x1 - x0)}" height="{_f(y1 - y0)}" fill="transparent" stroke="none"/>'
            )
        for k, pr in enumerate(e._prims):
            parts.append(_prim(pr, k, std, widths, P, H))
        parts.append("</g>")
        out.append((e.id, e.kind, "\n".join(x for x in parts if x)))
    return out


def hatch_pattern(d, pid="hatch", stroke="currentColor") -> str:
    """The section-lining ``<pattern>`` (GB/T 4457.5) the hatch prims fill with."""
    std, _W, _H, _P, widths = _ctx(d)
    hs = std["hatch"]
    return (
        f'<pattern id="{pid}" patternUnits="userSpaceOnUse" width="{_f(hs["spacing"])}" '
        f'height="{_f(hs["spacing"])}" patternTransform="rotate({_f(-hs["angle"])})">'
        f'<line x1="0" y1="0" x2="0" y2="{_f(hs["spacing"])}" stroke="{stroke}" '
        f'stroke-width="{_f(widths.get("hatch", 0.25))}"/></pattern>'
    )


def _hid(angle, spacing):
    return f"hatch-{_f(angle or 0).replace('.', '_')}-{_f(spacing or 0).replace('.', '_')}"


def hatch_defs(d) -> list[str]:
    """One extra pattern per distinct per-part hatch style (assemblies, GB/T 4458.6)."""
    std, _W, _H, _P, widths = _ctx(d)
    hs = std["hatch"]
    out, done = [], set()
    for e in d._els.values():
        for pr in e._prims:
            if not isinstance(pr, Hatch) or (pr.angle is None and pr.spacing is None):
                continue
            key = _hid(pr.angle, pr.spacing)
            if key in done:
                continue
            done.add(key)
            sp = pr.spacing or hs["spacing"]
            ang = hs["angle"] if pr.angle is None else pr.angle
            out.append(
                f'<pattern id="{key}" patternUnits="userSpaceOnUse" width="{_f(sp)}" '
                f'height="{_f(sp)}" patternTransform="rotate({_f(-ang)})">'
                f'<line x1="0" y1="0" x2="0" y2="{_f(sp)}" stroke="currentColor" '
                f'stroke-width="{_f(widths.get("hatch", 0.25))}"/></pattern>'
            )
    return out


def svg(d) -> str:
    """The whole sheet as an SVG string (millimetre units, y down)."""
    _std, W, H, _P, _widths = _ctx(d)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_f(W)} {_f(H)}" '
        f'width="{_f(W)}mm" height="{_f(H)}mm" data-sheet="{escape(d.sheet)}">',
        "<defs>",
        hatch_pattern(d),
        *hatch_defs(d),
        "</defs>",
        f'<rect x="0" y="0" width="{_f(W)}" height="{_f(H)}" fill="white" class="paper"/>',
    ]
    out.extend(html for _id, _kind, html in svg_groups(d))
    out.append("</svg>")
    return "\n".join(x for x in out if x)


def _stroke(std, widths, layer, ltscale=1.0, width=None):
    w = widths.get(layer, 0.25) if width is None else width
    return f' class="r-{layer}" stroke-width="{_f(w)}"{_dash(std, layer, ltscale)}'


def _prim(pr, k, std, widths, P, H):
    if isinstance(pr, Line):
        (x1, y1), (x2, y2) = pr.p, pr.q
        return (
            f'<line data-k="{k}" x1="{_f(x1)}" y1="{_f(H - y1)}" x2="{_f(x2)}" y2="{_f(H - y2)}"'
            f"{_stroke(std, widths, pr.layer, pr.ltscale, getattr(pr, 'width', None))}/>"
        )
    if isinstance(pr, Circle):
        return (
            f'<circle data-k="{k}" cx="{_f(pr.c[0])}" cy="{_f(H - pr.c[1])}" r="{_f(pr.r)}" fill="none"'
            f"{_stroke(std, widths, pr.layer, pr.ltscale)}/>"
        )
    if isinstance(pr, Arc):
        a0, a1 = pr.a0, pr.a1
        sweep = (a1 - a0) % 360 or 360
        p0 = (
            pr.c[0] + pr.r * math.cos(math.radians(a0)),
            pr.c[1] + pr.r * math.sin(math.radians(a0)),
        )
        p1 = (
            pr.c[0] + pr.r * math.cos(math.radians(a1)),
            pr.c[1] + pr.r * math.sin(math.radians(a1)),
        )
        large = 1 if sweep > 180 else 0  # counter-clockwise in y-up = sweep-flag 0 in y-down
        return (
            f'<path data-k="{k}" d="M{P(p0)} A{_f(pr.r)},{_f(pr.r)} 0 {large} 0 {P(p1)}" fill="none"'
            f"{_stroke(std, widths, pr.layer)}/>"
        )
    if isinstance(pr, Poly):
        pts = " ".join(P(p) for p in pr.pts)
        return (
            f'<polyline data-k="{k}" points="{pts}" fill="none"{_stroke(std, widths, pr.layer)}/>'
        )
    if isinstance(pr, Solid):
        pts = " ".join(P(p) for p in pr.pts)
        return f'<polygon data-k="{k}" points="{pts}" class="solid"/>'
    if isinstance(pr, Hatch):
        parts = []
        for lp in pr.loops:
            if lp and lp[0] == "circle":
                (cx, cy), r = lp[1], lp[2]
                parts.append(
                    f"M{P((cx + r, cy))} A{_f(r)},{_f(r)} 0 1 0 {P((cx - r, cy))} A{_f(r)},{_f(r)} 0 1 0 {P((cx + r, cy))}Z"
                )
            else:
                parts.append("M" + " L".join(P(p) for p in lp) + "Z")
        if getattr(pr, "solid", False):
            return (
                f'<path data-k="{k}" d="{" ".join(parts)}" fill="currentColor" '
                'fill-opacity="0.18" fill-rule="evenodd" class="hatch solid"/>'
            )
        fill = "hatch" if pr.angle is None and pr.spacing is None else _hid(pr.angle, pr.spacing)
        return f'<path data-k="{k}" d="{" ".join(parts)}" fill="url(#{fill})" fill-rule="evenodd" class="hatch"/>'
    if isinstance(pr, Text):
        # GB character height → SVG font size: CJK body = height; Latin cap height ≈ 0.72 em
        cjk = getattr(pr, "cjk", None)
        cjk = has_cjk(pr.text) if cjk is None else cjk
        size = pr.height if cjk else dxf_height(pr.text, pr.height, std) / 0.72
        wf = std["text"]["width_factor"]
        x, y = pr.at[0], H - pr.at[1]
        weight = ' font-weight="bold"' if getattr(pr, "bold", False) else ""
        return (
            f'<text data-k="{k}" transform="translate({_f(x)},{_f(y)}) rotate({_f(-pr.rot)}) scale({_f(wf)},1)" '
            f'font-size="{_f(size)}"{weight} text-anchor="middle" dominant-baseline="central">{escape(pr.text)}</text>'
        )
    if isinstance(pr, Image):
        bx0, by0, bx1, by1 = pr.box
        b64 = base64.b64encode(Path(pr.resolved_path).read_bytes()).decode("ascii")
        return (
            f'<image data-k="{k}" x="{_f(bx0)}" y="{_f(H - by1)}" '
            f'width="{_f(bx1 - bx0)}" height="{_f(by1 - by0)}" '
            f'href="data:image/png;base64,{b64}" preserveAspectRatio="none"/>'
        )
    return ""


def selector(e) -> str | None:
    """A ``d.q`` expression that finds this auto-numbered geometry (M2 SPEC §1 #5)."""
    if e.kind != "edge":
        return None
    i = e._intent
    v = i["view"]
    feat = (
        f', feature="{i["feature"]}"' if i.get("feature") else ""
    )  # coincident lines differ by feature
    if i["shape"] == "line":
        mx, my = e.mid
        dr = e.dir
        cond = f"length={_f(e.length)}" + (f', dir="{dr}"' if dr else "") + feat
        return f'd.q.lines(view="{v}").where({cond}).near({_f(mx)}, {_f(my)}, 0.5).one()'
    kind = "circles" if i["shape"] == "circle" else "arcs"
    # near() measures to the curve itself: use a point on it
    cx, cy = (i["c"][0] + i["r"], i["c"][1]) if i["shape"] == "circle" else e.mid
    return f'd.q.{kind}(view="{v}").where(r={_f(i["r"])}{feat}).near({_f(cx)}, {_f(cy)}, 0.5).one()'


def run_selector(d, text):
    """Evaluate a selector string WITHOUT eval: only ``d.q.<kind>(view=..).where(..).near(..).one()``
    with literal arguments is accepted."""
    import ast

    from .errors import InvalidArgument

    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError as e:
        raise InvalidArgument(f"选择器写法不对：{e}")
    calls = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        calls.append(node)
        node = node.func.value
    if not (
        isinstance(node, ast.Attribute)
        and node.attr == "q"
        and isinstance(node.value, ast.Name)
        and node.value.id == "d"
    ):
        raise InvalidArgument("选择器只能是 d.q.<种类>(...) 开头的链")

    def lit(a):
        try:
            v = ast.literal_eval(a)
        except ValueError:
            raise InvalidArgument("选择器参数只能是数字或字符串")
        if not isinstance(v, (int, float, str)) or isinstance(v, bool):
            raise InvalidArgument("选择器参数只能是数字或字符串")
        return v

    q = d.q
    allowed = ("lines", "circles", "arcs", "edges", "where", "near", "one", "exactly", "first")
    for c in reversed(calls):
        name = c.func.attr
        if name not in allowed:
            raise InvalidArgument(f"选择器里不允许 {name}()")
        q = getattr(q, name)(*[lit(a) for a in c.args], **{k.arg: lit(k.value) for k in c.keywords})
    return q
