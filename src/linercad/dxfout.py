"""DXF and model.json output (SPEC §9.1, §3.3).

Prims (sheet coordinates) → ezdxf entities. Every entity carries XDATA
``[(1000, element id), (1071, sub index)]`` under the appid ``LINERCAD``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import ezdxf
from ezdxf.document import CREATED_BY_EZDXF
from ezdxf.enums import TextEntityAlignment

from .errors import InvalidArgument
from .layout import Arc, Circle, Hatch, Line, Poly, Solid, Text
from .text import dxf_height

APPID = "LINERCAD"
SCHEMA = "linercad.model/0"
RAW_TYPES = ("LINE", "CIRCLE", "ARC", "TEXT", "LWPOLYLINE", "POINT")


def _layer(std, role):
    return std["lines"][role]["layer"]


def _setup(doc, std):
    md = doc.ezdxf_metadata()  # ezdxf stamps creation time here; keep output byte-stable
    md[CREATED_BY_EZDXF] = f"{ezdxf.__version__} @ linercad"
    doc.units = ezdxf.units.MM
    doc.header["$MEASUREMENT"] = 1
    for name, lt in std["linetypes"].items():
        if not isinstance(lt, dict):
            continue
        pat = list(lt["pattern"])
        doc.linetypes.add(
            name, pattern=[sum(abs(x) for x in pat), *pat], description=lt.get("description", "")
        )
    for _role, spec in std["lines"].items():
        if not isinstance(spec, dict):
            continue
        doc.layers.add(
            spec["layer"],
            color=spec["color"],
            lineweight=int(round(spec["width"] * 100)),
            linetype=spec["linetype"],
        )
    style = doc.styles.add("LC", font=std["text"]["font"])
    style.dxf.width = std["text"]["width_factor"]
    doc.appids.add(APPID)


def _point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for k in range(n):
        (x1, y1), (x2, y2) = poly[k], poly[(k + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _in_region(pt, loops):
    """Even-odd rule over the hatch loops."""
    k = 0
    for lp in loops:
        if lp and lp[0] == "circle":
            c, r = lp[1], lp[2]
            k += (pt[0] - c[0]) ** 2 + (pt[1] - c[1]) ** 2 < r * r
        else:
            k += _point_in_poly(pt, lp)
    return k % 2 == 1


def _islands(hatch, text_boxes):
    out = []
    for b in text_boxes:
        corners = [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]
        if all(_in_region(c, hatch.loops) for c in corners):
            m = 0.5
            out.append(
                [
                    (b[0] - m, b[1] - m),
                    (b[2] + m, b[1] - m),
                    (b[2] + m, b[3] + m),
                    (b[0] - m, b[3] + m),
                ]
            )
    return out


def _alignment(align) -> TextEntityAlignment:
    """(halign, valign) of the source entity -> ezdxf TEXT alignment."""
    halign, valign = align
    if halign == 3:
        return TextEntityAlignment.ALIGNED
    if halign == 5:
        return TextEntityAlignment.FIT
    if halign == 4:
        return TextEntityAlignment.MIDDLE
    col = {0: "LEFT", 1: "CENTER", 2: "RIGHT"}.get(halign, "LEFT")
    row = {0: "", 1: "BOTTOM_", 2: "MIDDLE_", 3: "TOP_"}.get(valign, "")
    name = (row + col) if row else ("CENTER" if col == "CENTER" else col)
    return getattr(TextEntityAlignment, name, TextEntityAlignment.MIDDLE_CENTER)


def _write(msp, pr, std, text_boxes):
    lay = {"layer": _layer(std, pr.layer)}
    if isinstance(pr, Line):
        if pr.ltscale != 1.0:
            lay["ltscale"] = pr.ltscale
        return msp.add_line(pr.p, pr.q, dxfattribs=lay)
    if isinstance(pr, Circle):
        if pr.ltscale != 1.0:
            lay["ltscale"] = pr.ltscale
        return msp.add_circle(pr.c, pr.r, dxfattribs=lay)
    if isinstance(pr, Arc):
        return msp.add_arc(pr.c, pr.r, pr.a0, pr.a1, dxfattribs=lay)
    if isinstance(pr, Solid):
        return msp.add_solid(list(pr.pts), dxfattribs=lay)
    if isinstance(pr, Poly):
        return msp.add_lwpolyline(list(pr.pts), dxfattribs=lay)
    if isinstance(pr, Text):
        if pr.exact_height and pr.anchor is not None and pr.align is not None:
            # imported TEXT / MTEXT: keep the DXF height, style, source layer and alignment verbatim
            doc = msp.doc
            style = pr.style or "LC"
            if not doc.styles.has_entry(style):
                doc.styles.add(style, font=std["text"]["font"])
            layer = pr.layer_name or _layer(std, pr.layer)
            if not doc.layers.has_entry(layer):
                doc.layers.add(layer, color=7)
            t = msp.add_text(
                pr.text,
                height=pr.height,
                rotation=pr.rot,
                dxfattribs={"layer": layer, "style": style, "width": std["text"]["width_factor"]},
            )
            align = _alignment(pr.align)
            if align in (TextEntityAlignment.ALIGNED, TextEntityAlignment.FIT) and pr.anchor2:
                t.set_placement(pr.anchor, pr.anchor2, align=align)
            else:
                t.set_placement(pr.anchor, align=align)
            return t
        t = msp.add_text(
            pr.text,
            height=dxf_height(pr.text, pr.height, std, pr.cjk),
            rotation=pr.rot,
            dxfattribs={**lay, "style": "LC", "width": std["text"]["width_factor"]},
        )
        t.set_placement(pr.at, align=TextEntityAlignment.MIDDLE_CENTER)
        return t
    if isinstance(pr, Hatch):
        hs = std["hatch"]
        h = msp.add_hatch(dxfattribs=lay)
        flags = tuple(getattr(pr, "loop_flags", ()) or ())
        if getattr(pr, "solid", False):
            h.set_solid_fill(color=7)
            for idx, lp in enumerate(pr.loops):
                if lp and lp[0] == "circle":
                    h.paths.add_edge_path().add_arc(lp[1], lp[2], 0, 360)
                else:
                    h.paths.add_polyline_path(
                        list(lp), is_closed=True, flags=flags[idx] if idx < len(flags) else 1
                    )
            h.dxf.hatch_style = int(getattr(pr, "hatch_style", 0) or 0)
            return h
        if getattr(pr, "pattern", None):
            h.set_pattern_fill(
                pr.pattern,
                scale=float(getattr(pr, "scale", None) or 1.0),
                angle=float(pr.angle or 0.0),
            )
        else:
            sp = pr.spacing or hs["spacing"]
            ang = hs["angle"] if pr.angle is None else pr.angle
            h.set_pattern_fill(hs["pattern"], scale=sp / 3.175, angle=ang - 45)
        for idx, lp in enumerate(pr.loops):
            if lp and lp[0] == "circle":
                h.paths.add_edge_path().add_arc(lp[1], lp[2], 0, 360)
            else:
                h.paths.add_polyline_path(
                    list(lp), is_closed=True, flags=flags[idx] if idx < len(flags) else 1
                )
        h.dxf.hatch_style = int(getattr(pr, "hatch_style", 0) or 0)
        for isl in _islands(pr, text_boxes):
            h.paths.add_polyline_path(isl, is_closed=True)
        return h
    raise TypeError(pr)


def _raw_entity(d, msp, e):
    """A raw element's entity. One from ``d.raw_add`` is written as given (sheet coordinates); one
    imported from a DXF has view-local coordinates, moved to the sheet by its view's placement."""
    from ezdxf.math import Matrix44

    from .importdxf import make_raw

    i = e._intent
    if "data" not in i:
        return msp.new_entity(i["dxftype"], dict(i["attribs"]))
    ent = make_raw(msp, i, layer=_layer(d.std, i.get("role", "thick")))
    v = d._els.get(f"V.{i.get('view')}")
    origin = v._resolved.get("origin") if v is not None else None
    if origin:
        s = v.scale
        ent.transform(Matrix44.chain(Matrix44.scale(s, s, 1), Matrix44.translate(*origin, 0)))
    return ent


def to_doc(d):
    """Build the ezdxf document. Returns (doc, index, raw_failures).

    ``index`` maps element id → list of its entities (in sub-index order);
    ``raw_failures`` lists ``d.raw`` overrides that could not be applied (stale ops).
    """
    std = d.std
    doc = ezdxf.new("R2018", setup=False)
    _setup(doc, std)
    msp = doc.modelspace()
    text_boxes = [p.box for e in d._els.values() for p in e._prims if isinstance(p, Text)]
    index, failures = {}, []
    for e in d._els.values():
        ents = []
        if e.kind == "raw":
            ents.append(_raw_entity(d, msp, e))
        else:
            for pr in e._prims:
                ents.append(_write(msp, pr, std, text_boxes))
        for k, ent in enumerate(ents):
            ent.set_xdata(APPID, [(1000, e.id), (1071, k)])
        for ov in getattr(e, "_raw", []):
            k, attr = ov["sub"], ov["attr"]
            try:
                if not 0 <= k < len(ents):
                    raise InvalidArgument(f"{e.id} 没有第 {k} 个子图元（共 {len(ents)} 个）")
                ent = ents[k]
                if not ent.dxf.is_supported(attr):
                    raise InvalidArgument(f"{ent.dxftype()} 没有 DXF 属性 {attr}")
                ent.dxf.set(attr, ov["value"])
            except Exception as ex:  # an override that cannot apply is a stale op, never a crash
                failures.append(
                    {
                        "edit": ov.get("edit"),
                        "line": ov.get("line"),
                        "op": "raw",
                        "id": e.id,
                        "reason": str(ex),
                        "candidates": [],
                    }
                )
        index[e.id] = ents
    return doc, index, failures


def save_doc(doc, path):
    """Save with fixed metadata (byte-identical output for identical input); atomic replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    old = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        doc.classes.add_required_classes(doc.dxfversion)
        # ezdxf fills CLASSES while iterating a set, so the order depends on the hash seed: sort it
        doc.classes.classes = dict(sorted(doc.classes.classes.items()))
        doc.saveas(tmp)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = old
    os.replace(tmp, path)
    return path


def model_dict(d, findings=(), edit=None) -> dict:
    tpl = d.template
    views = {v.name: {"origin": v._resolved.get("origin"), "scale": d.scale} for v in d.views()}
    P = d.P
    from .model import _round

    return _round(
        {
            "schema": SCHEMA,
            "drawing": {
                "sheet": d.sheet,
                "std": d.std_name,
                "projection": d.std["views"]["projection"],
                "overlay": d.overlay,
                "scale": d.scale_text,
                "edit": edit,
                "frame": list(tpl["frame"]),
                "views": views,
            },
            "params": [P[n].to_dict(n) for n in P.names()],
            "elements": [e.to_dict() for e in d._els.values()],
            "findings": list(findings),
        }
    )


def write_text_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)
    return path


def write_model(d, path, findings=(), edit=None):
    return write_text_atomic(
        path, json.dumps(model_dict(d, findings, edit), ensure_ascii=False, indent=1) + "\n"
    )
