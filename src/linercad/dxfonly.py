"""Only-primitive (DXF-only) scoring for arbitrary DXF drawings (E6, issue #80).

The C1 ruler (evals/dxf_import.py) judges the importer's output; this module judges any DXF from
its rendered entities only (LINE / ARC / CIRCLE / LWPOLYLINE / TEXT / DIMENSION / HATCH ...).
No semantic model, no element intent, no view ownership is used.

Judgeable part of the vector:

* G.layout: dxf_out_of_frame (all primitives inside the detected sheet frame) and
  dxf_text_overlap (text boxes do not substantially overlap each other; text-on-line needs dimension semantics).
* G.conv: dxf_hatch_defined (section fill has a usable pattern) and
  dxf_section_hatch_consistency (all hatches in one DXF share pattern / angle / scale).
* D.place: dxf_dim_text_present (DIMENSION carries a text) and dxf_dim_arrows
  (dimension geometry block carries two consistent arrowheads).

Everything that needs the semantic model (G.geo/align/express, D.complete/value/fit/chain, the
intent-level D.place rules, T.*, A.*, P.*) is reported as unavailable, not silently scored.

    from linercad.dxfonly import score_file
    score_file("any.dxf")["families"]
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf import path as ezpath

FAMILIES = ("G", "D", "T", "A", "P")

#: Only-primitive rules that enter the vector. basis names the benchmark-metrics entry.
RULE_TABLE = {
    "dxf_out_of_frame": {
        "family": "G",
        "basis": "G.layout（出框）",
        "judgeable": True,
        "description": "所有可见图元在图框内（图框从 DXF 图元本身探测；探测不到时该规则不适用）",
    },
    "dxf_text_overlap": {
        "family": "G",
        "basis": "G.layout（重叠）",
        "judgeable": True,
        "description": "文字外框不互相重叠（DXF-only 下只判文字-文字；文字压线需要尺寸/引线语义，不判）",
    },
    "dxf_hatch_defined": {
        "family": "G",
        "basis": "G.conv（剖面画法）",
        "judgeable": True,
        "description": "每个 HATCH 有实体填充或可用的图案定义（图案名 + 比例）",
    },
    "dxf_dim_text_present": {
        "family": "D",
        "basis": "D.place（尺寸文字可读）",
        "judgeable": True,
        "description": "每个 DIMENSION 带文字（覆盖值或测量显示 <>）",
    },
    "dxf_dim_arrows": {
        "family": "D",
        "basis": "D.place（箭头大小一致）",
        "judgeable": True,
        "description": "DIMENSION 几何块里有 >=2 个箭头且面积一致（无几何块的 DIMENSION 不适用）",
    },
}

#: Conceptual metric entries that depend on the semantic model; listed in every report.
INTENT_METRICS = {
    "G.geo": ("G", "需要 3D/HLR 投影作参考"),
    "G.linetype": ("G", "可见/隐藏线语义来自视图 intent"),
    "G.align": ("G", "需要视图归属（长对正/高平齐）"),
    "G.section": ("G", "需要剖视语义"),
    "G.express": ("G", "需要 3D 特征"),
    "G.layout.view_align": ("G", "需要视图归属"),
    "G.conv.hatch_consistency": ("G", "相邻零件允许不同方向/间距，需要零件/剖视归属"),
    "D.complete": ("D", "需要 3D 特征 / expect"),
    "D.redundant": ("D", "需要尺寸语义（封闭链/重复）"),
    "D.value": ("D", "需要被标几何的实测值（intent）"),
    "D.fit": ("D", "需要资源库公差与配合语义"),
    "D.chain": ("D", "需要尺寸链语义"),
    "D.group": ("D", "需要特征归属"),
    "D.place.dim_cross": ("D", "尺寸线/轮廓线需要尺寸 intent"),
    "D.place.row_spacing": ("D", "平行尺寸组需要尺寸 intent"),
    "D.place.nesting": ("D", "大小尺寸嵌套需要尺寸 intent"),
    "D.place.text_direction": ("D", "水平/垂直尺寸需要尺寸 intent"),
    "D.place.leader_cross": ("D", "引线目标需要尺寸 intent"),
    "D.place.dim_outline": ("D", "尺寸线与轮廓线需要尺寸 intent"),
    "D.place.ext_line": ("D", "尺寸界线需要尺寸 intent"),
    "D.place.text_overlap": ("D", "尺寸文字与图元重叠需要尺寸 intent"),
    "D.place.arrow": ("D", "箭头大小/朝向需要尺寸 intent"),
    "D.place.balloon_cross": ("D", "装配序号引线需要装配 intent"),
    "D.place.balloon_align": ("D", "装配序号对齐需要装配 intent"),
    "D.place.balloon_spacing": ("D", "装配序号间距需要装配 intent"),
    "T.syntax": ("T", "需要形位公差框格语义"),
    "T.datum": ("T", "需要基准语义"),
    "T.target": ("T", "需要被测要素语义"),
    "T.hier": ("T", "需要公差语义"),
    "T.rough": ("T", "需要粗糙度语义"),
    "T.func": ("T", "需要 expect"),
    "T.sem": ("T", "需要 PMI 语义元素"),
    "A.place": ("A", "需要装配序号 / 明细栏语义"),
    "A.bom": ("A", "需要装配明细语义"),
    "P.*": ("P", "过程指标（轮次/token）与图元无关"),
}


def unavailable_rules() -> list:
    """Every intent-dependent metric, with its family and the reason it cannot be judged."""
    return [
        {"rule": rule, "family": fam, "reason": why} for rule, (fam, why) in INTENT_METRICS.items()
    ]


# --------------------------------------------------------------------------- primitives


def _flat_text(e) -> str:
    try:
        if e.dxftype() == "MTEXT":
            return e.plain_text(fast=False)
        return str(e.dxf.get("text", ""))
    except Exception:  # noqa: BLE001 - unreadable text is just not judged
        return ""


def _text_box(e) -> dict | None:
    raw = _flat_text(e).strip()
    if not raw:
        return None
    lines = [ln for ln in raw.splitlines() if ln.strip()] or [raw]
    text = " ".join(lines)
    try:
        if e.dxftype() == "TEXT":
            h = float(e.dxf.get("height", 2.5) or 2.5)
            rot = math.radians(float(e.dxf.get("rotation", 0.0) or 0.0))
            halign = int(e.dxf.get("halign", 0) or 0)
            valign = int(e.dxf.get("valign", 0) or 0)
            at = e.dxf.insert
            if (halign or valign) and e.dxf.hasattr("align_point"):
                at = e.dxf.align_point  # aligned/fit/middle text is anchored at the alignment point
            natural = sum(1.0 if ord(ch) > 127 else 0.7 for ch in text) * h
            width = natural
            height = h
        else:
            h = float(e.dxf.get("char_height", 2.5) or 2.5)
            rot = math.radians(float(e.get_rotation() or 0.0))
            at = e.dxf.insert
            attach = int(e.dxf.get("attachment_point", 1) or 1)
            halign = 0 if attach in (1, 4, 7) else (1 if attach in (2, 5, 8) else 2)
            valign = 3 if attach in (1, 2, 3) else (2 if attach in (4, 5, 6) else 1)
            natural = max(sum(1.0 if ord(ch) > 127 else 0.7 for ch in ln) * h for ln in lines)
            defined = float(e.dxf.get("width", 0.0) or 0.0)
            width = defined if defined > 1e-6 else natural
            height = len(lines) * h * 1.5
    except Exception:  # noqa: BLE001
        return None
    c, s = math.cos(rot), math.sin(rot)

    def tr(u: float, v: float):
        return (float(at[0]) + u * c - v * s, float(at[1]) + u * s + v * c)

    if halign == 1:
        x0, x1 = -width / 2, width / 2
    elif halign == 2:
        x0, x1 = -width, 0.0
    else:
        x0, x1 = 0.0, width
    if valign == 3:
        y0, y1 = -height, 0.0
    elif valign == 2:
        y0, y1 = -height / 2, height / 2
    else:
        y0, y1 = 0.0, height
    pts = [tr(x0, y0), tr(x1, y0), tr(x1, y1), tr(x0, y1)]
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    return {
        "id": str(e.dxf.handle),
        "box": (min(xs), min(ys), max(xs), max(ys)),
        "text": text,
        "point": (float(at[0]), float(at[1])),
        "height": h,
        "lines": len(lines),
    }


def _segments_of(e) -> list:
    t = e.dxftype()
    out = []
    try:
        if t == "LINE":
            out.append(
                (
                    (float(e.dxf.start[0]), float(e.dxf.start[1])),
                    (float(e.dxf.end[0]), float(e.dxf.end[1])),
                )
            )
        elif t == "LWPOLYLINE":
            pts = [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
            n = len(pts)
            for i in range(n - 1 + (1 if e.closed and n > 2 else 0)):
                out.append((pts[i], pts[(i + 1) % n]))
        elif t == "POLYLINE":
            pts = [(float(v.dxf.location[0]), float(v.dxf.location[1])) for v in e.vertices]
            n = len(pts)
            for i in range(n - 1 + (1 if e.is_closed and n > 2 else 0)):
                out.append((pts[i], pts[(i + 1) % n]))
        elif t in ("CIRCLE", "ARC"):
            c = (float(e.dxf.center[0]), float(e.dxf.center[1]))
            r = float(e.dxf.radius)
            if t == "CIRCLE":
                a0, a1 = 0.0, 360.0
            else:
                a0 = float(e.dxf.start_angle)
                a1 = float(e.dxf.end_angle)
                if a1 <= a0:
                    a1 += 360.0
            span = a1 - a0
            n = max(8, int(math.ceil(span / 15.0)))
            pts = [
                (
                    c[0] + r * math.cos(math.radians(a0 + span * i / n)),
                    c[1] + r * math.sin(math.radians(a0 + span * i / n)),
                )
                for i in range(n + 1)
            ]
            out += list(zip(pts, pts[1:]))
        elif t in ("ELLIPSE", "SPLINE"):
            for sub in ezpath.make_path(e).flattening(0.2):
                pts = [(float(p.x), float(p.y)) for p in sub]
                out += list(zip(pts, pts[1:]))
    except Exception:  # noqa: BLE001 - unsupported geometry is simply not a segment
        out = []
    return out


def _entity_bbox(e):
    """Bounding box of an arbitrary entity (HATCH / INSERT / DIMENSION) via ezdxf.bbox."""
    try:
        from ezdxf import bbox as ezbbox

        b = ezbbox.extents([e])
        if b.has_data:
            return (float(b.extmin.x), float(b.extmin.y), float(b.extmax.x), float(b.extmax.y))
    except Exception:  # noqa: BLE001 - geometry we cannot measure is not judged
        return None
    return None


def _entities(msp) -> list:
    out = []
    for e in msp:
        t = e.dxftype()
        if t in ("LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE"):
            segs = _segments_of(e)
            xs = [p[0] for s in segs for p in s]
            ys = [p[1] for s in segs for p in s]
            box = (min(xs), min(ys), max(xs), max(ys)) if segs else None
            out.append({"type": t, "id": str(e.dxf.handle), "segments": segs, "box": box})
        elif t in ("HATCH", "INSERT", "DIMENSION"):
            box = _entity_bbox(e)
            if box is not None:
                out.append({"type": t, "id": str(e.dxf.handle), "segments": [], "box": box})
        elif t in ("TEXT", "MTEXT"):
            tb = _text_box(e)
            if tb is not None:
                out.append(
                    {
                        "type": t,
                        "id": tb["id"],
                        "segments": [],
                        "box": tb["box"],
                        "point": tb["point"],
                        "text": tb["text"],
                        "height": tb["height"],
                        "lines": tb["lines"],
                    }
                )
    return out


# --------------------------------------------------------------------------- primitive helpers


def _seg_in_box(p, q, box) -> float:
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return 0.0
    ux, uy = dx / L, dy / L
    hits = []
    for k in (0, 1):
        for bound in (box[k], box[k + 2]):
            comp = (ux, uy)[k]
            if abs(comp) < 1e-12:
                continue
            t = (bound - p[k]) / comp
            x, y = p[0] + ux * t, p[1] + uy * t
            if box[0] - 1e-9 <= x <= box[2] + 1e-9 and box[1] - 1e-9 <= y <= box[3] + 1e-9:
                hits.append(min(max(t, 0.0), L))
    inside = [
        t
        for t in (0.0, L)
        if box[0] - 1e-9 <= p[0] + ux * t <= box[2] + 1e-9
        and box[1] - 1e-9 <= p[1] + uy * t <= box[3] + 1e-9
    ]
    hits += inside
    return max(0.0, max(hits) - min(hits)) if len(hits) >= 2 else 0.0


def _box_overlap(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _rect_from_4pts(pts):
    xs = sorted({round(p[0], 6) for p in pts})
    ys = sorted({round(p[1], 6) for p in pts})
    if len(xs) != 2 or len(ys) != 2:
        return None
    return (xs[0], ys[0], xs[1], ys[1])


def _detect_frame(msp):
    """Largest axis-aligned closed rectangle drawn with primitives, as (rect, entity-ids)."""
    cands = []
    segs = []
    for e in msp:
        t = e.dxftype()
        if t == "LWPOLYLINE" and e.closed and len(list(e.get_points("xy"))) == 4:
            pts = [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
            r = _rect_from_4pts(pts)
            if r and (r[2] - r[0]) * (r[3] - r[1]) > 100:
                cands.append((r, {str(e.dxf.handle)}))
        elif t == "POLYLINE" and e.is_closed and len(list(e.vertices)) == 4:
            pts = [(float(v.dxf.location[0]), float(v.dxf.location[1])) for v in e.vertices]
            r = _rect_from_4pts(pts)
            if r and (r[2] - r[0]) * (r[3] - r[1]) > 100:
                cands.append((r, {str(e.dxf.handle)}))
        elif t == "LINE":
            segs.append((e.dxf.start, e.dxf.end, str(e.dxf.handle)))
    hs, vs = [], []
    for p, q, hid in segs:
        if abs(float(p[1]) - float(q[1])) <= 0.5:
            x0, x1 = sorted((float(p[0]), float(q[0])))
            hs.append((float((p[1] + q[1]) / 2), x0, x1, hid))
        elif abs(float(p[0]) - float(q[0])) <= 0.5:
            y0, y1 = sorted((float(p[1]), float(q[1])))
            vs.append((float((p[0] + q[0]) / 2), y0, y1, hid))
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            y0, xa, xb, h0 = hs[i]
            y1, xc, xd, h1 = hs[j]
            if abs(xa - xc) > 0.5 or abs(xb - xd) > 0.5 or abs(xb - xa) < 1:
                continue
            ylo, yhi = min(y0, y1), max(y0, y1)
            left = [
                v
                for v in vs
                if abs(v[0] - xa) <= 0.5
                and abs(min(v[1], v[2]) - ylo) <= 0.5
                and abs(max(v[1], v[2]) - yhi) <= 0.5
            ]
            right = [
                v
                for v in vs
                if abs(v[0] - xb) <= 0.5
                and abs(min(v[1], v[2]) - ylo) <= 0.5
                and abs(max(v[1], v[2]) - yhi) <= 0.5
            ]
            if left and right:
                r = (min(xa, xb), min(y0, y1), max(xa, xb), max(y0, y1))
                cands.append((r, {h0, h1, left[0][3], right[0][3]}))
    if not cands:
        return None
    xs, ys = [], []
    for e in msp:
        if e.dxftype() == "LINE":
            xs += [float(e.dxf.start[0]), float(e.dxf.end[0])]
            ys += [float(e.dxf.start[1]), float(e.dxf.end[1])]
        elif e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            pts = (
                [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
                if e.dxftype() == "LWPOLYLINE"
                else [(float(v.dxf.location[0]), float(v.dxf.location[1])) for v in e.vertices]
            )
            xs += [q[0] for q in pts]
            ys += [q[1] for q in pts]
        elif e.dxftype() in ("CIRCLE", "ARC"):
            c, r = e.dxf.center, float(e.dxf.radius)
            xs += [float(c[0]) - r, float(c[0]) + r]
            ys += [float(c[1]) - r, float(c[1]) + r]
    if not xs:
        return None
    drawing_area = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    best = max(cands, key=lambda c: (c[0][2] - c[0][0]) * (c[0][3] - c[0][1]))
    area = (best[0][2] - best[0][0]) * (best[0][3] - best[0][1])
    return best if area >= 0.5 * drawing_area else None


# --------------------------------------------------------------------------- rules


def _rule(name, opp, violations, note=""):
    info = RULE_TABLE[name]
    entry = {
        "id": name,
        "family": info["family"],
        "basis": info["basis"],
        "description": info["description"],
        "opportunities": opp,
        "violations": violations,
    }
    if note:
        entry["note"] = note
    return entry


def _rule_out_of_frame(msp, prims):
    found = _detect_frame(msp)
    if not found:
        return _rule("dxf_out_of_frame", 0, 0, "no sheet frame detected in the DXF primitives")
    (x0, y0, x1, y1), frame_ids = found
    checked = [p for p in prims if p["id"] not in frame_ids and p["box"] is not None]
    if not checked:
        return _rule("dxf_out_of_frame", 0, 0, "no primitives besides the frame")
    viol = 0
    for p in checked:
        if p.get("point") is not None:
            px, py = p["point"]
            outside = px < x0 - 0.01 or px > x1 + 0.01 or py < y0 - 0.01 or py > y1 + 0.01
        else:
            b = p["box"]
            outside = b[0] < x0 - 0.5 or b[1] < y0 - 0.5 or b[2] > x1 + 0.5 or b[3] > y1 + 0.5
        if outside:
            viol += 1
    r = _rule("dxf_out_of_frame", len(checked), viol)
    r["frame"] = [round(v, 3) for v in (x0, y0, x1, y1)]
    return r


def _rule_text_overlap(prims):
    texts = [p for p in prims if p["type"] in ("TEXT", "MTEXT")]
    viol = 0
    for t in texts:
        b = t["box"]
        hit = False
        for o in texts:
            if o is t:
                continue
            inter = _box_overlap(b, o["box"])
            if inter <= 0:
                continue
            area_a = max(1e-9, (b[2] - b[0]) * (b[3] - b[1]))
            area_b = max(1e-9, (o["box"][2] - o["box"][0]) * (o["box"][3] - o["box"][1]))
            if inter / max(1e-9, area_a + area_b - inter) > 0.1:
                hit = True
                break
        if hit:
            viol += 1
    return _rule("dxf_text_overlap", len(texts), viol)


def _rule_hatches(msp):
    hs = list(msp.query("HATCH"))
    defined_viol = 0
    for h in hs:
        solid = int(h.dxf.get("solid_fill", 0) or 0)
        name = str(h.dxf.get("pattern_name") or "")
        scale = float(h.dxf.get("pattern_scale", 0.0) or 0.0)
        if not solid and (not name or scale <= 0):
            defined_viol += 1
    return {"dxf_hatch_defined": _rule("dxf_hatch_defined", len(hs), defined_viol)}


def _dim_block(doc, e):
    name = e.dxf.get("geometry")
    if not name:
        return None
    try:
        return doc.blocks.get(name)
    except (KeyError, TypeError):
        return None


def _rule_dims(doc, msp):
    dims = list(msp.query("DIMENSION"))
    missing_text = 0
    arrow_viol = 0
    arrow_checked = 0
    for e in dims:
        text = str(e.dxf.get("text", "") or "")
        block = _dim_block(doc, e)
        block_texts = (
            [] if block is None else [b for b in block if b.dxftype() in ("TEXT", "MTEXT")]
        )
        if text.strip() == "" and not block_texts:
            missing_text += 1
        if block is None:
            continue
        arrow_checked += 1
        areas = []
        for b in block:
            if b.dxftype() == "SOLID":
                pts = [b.dxf.get(k) for k in ("vtx0", "vtx1", "vtx2", "vtx3")]
                pts = [(float(q[0]), float(q[1])) for q in pts if q is not None]
                if len(pts) >= 3:
                    a = abs(
                        sum(
                            pts[k][0] * pts[(k + 1) % len(pts)][1]
                            - pts[(k + 1) % len(pts)][0] * pts[k][1]
                            for k in range(len(pts))
                        )
                        / 2.0
                    )
                    if a > 1e-6:
                        areas.append(a)
            elif b.dxftype() == "INSERT":
                # standard dimension styles draw arrowheads as block references
                try:
                    ab = doc.blocks.get(b.dxf.name)
                except (KeyError, TypeError):
                    continue
                pts = []
                for abe in ab:
                    if abe.dxftype() == "SOLID":
                        for k in ("vtx0", "vtx1", "vtx2", "vtx3"):
                            q = abe.dxf.get(k)
                            if q is not None:
                                pts.append((float(q[0]), float(q[1])))
                    elif abe.dxftype() == "LWPOLYLINE":
                        for q in abe.get_points("xy"):
                            pts.append((float(q[0]), float(q[1])))
                area = 0.0
                if len(pts) >= 3:
                    xs = [q[0] for q in pts]
                    ys = [q[1] for q in pts]
                    scale = abs(float(b.dxf.get("xscale", 1.0) or 1.0)) * abs(
                        float(b.dxf.get("yscale", 1.0) or 1.0)
                    )
                    area = max(0.0, (max(xs) - min(xs)) * (max(ys) - min(ys))) * scale
                areas.append(area if area > 1e-6 else 1.0)  # tick-mark arrowheads have no fill area
        dimtype = int(e.dxf.get("dimtype", 0) or 0) & 0x0F
        expected = 1 if dimtype in (3, 4, 6) else 2  # radius/diameter/ordinate may use one arrow
        if len(areas) < expected:
            arrow_viol += 1
        elif len(areas) >= 2 and max(areas) / min(areas) > 1.25:
            arrow_viol += 1
    return {
        "dxf_dim_text_present": _rule("dxf_dim_text_present", len(dims), missing_text),
        "dxf_dim_arrows": _rule("dxf_dim_arrows", arrow_checked, arrow_viol),
    }


def score_doc(doc, name="<memory>") -> dict:
    msp = doc.modelspace()
    prims = _entities(msp)
    rules = {}
    for r in (
        _rule_out_of_frame(msp, prims),
        _rule_text_overlap(prims),
    ):
        rules[r["id"]] = r
    rules.update(_rule_hatches(msp))
    rules.update(_rule_dims(doc, msp))
    families = {
        fam: {"score": None, "opportunities": 0, "violations": 0, "rules": []} for fam in FAMILIES
    }
    for rid in RULE_TABLE:
        r = rules[rid]
        fam = r["family"]
        bucket = families[fam]
        bucket["rules"].append(rid)
        bucket["opportunities"] += r["opportunities"]
        bucket["violations"] += r["violations"]
    for bucket in families.values():
        if bucket["opportunities"]:
            bucket["score"] = round(
                max(0.0, 1.0 - bucket["violations"] / bucket["opportunities"]), 6
            )
        bucket["rules"] = sorted(bucket["rules"])
    return {
        "ok": True,
        "mode": "dxf-only",
        "file": str(name),
        "dxfversion": doc.dxfversion,
        "rules": rules,
        "families": families,
        "judgeable": {rid: RULE_TABLE[rid] for rid in RULE_TABLE},
        "unavailable": unavailable_rules(),
        "note": (
            "only-primitive ruler for arbitrary DXF (no semantic model); the C1 ruler in "
            "evals/dxf_import.py judges the importer's output with a different scope"
        ),
    }


def score_file(path) -> dict:
    try:
        doc = ezdxf.readfile(str(path))
        return score_doc(doc, Path(path).name)
    except Exception as e:  # noqa: BLE001 - one bad DXF is reported, not fatal
        return {
            "ok": False,
            "mode": "dxf-only",
            "file": str(path),
            "error": f"{type(e).__name__}: {e}",
            "rules": {},
            "families": {
                fam: {"score": None, "opportunities": 0, "violations": 0, "rules": []}
                for fam in FAMILIES
            },
            "unavailable": unavailable_rules(),
        }
