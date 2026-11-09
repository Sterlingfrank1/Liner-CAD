"""Completeness comparison for 3D-sourced drawings (SPEC M3 §2 row 2). Development / evaluation only.

A 3D-sourced drawing has no independent 2D reference to compare edges against (the edges *are* the
model), so what can be checked is whether the drawing says everything the model implies. Required
dimensions are inferred from the model:

* every distinct cylindrical-face diameter (holes, bores, bosses, slot ends), rounded to 0.01 mm. A
  cylinder family counts when its faces together span at least 180 degrees; fillet and round faces
  (quarter-round corners, casting fillets) are covered by the general note, not by a dimension;
* the three overall bounding-box sizes (L along X, W along Y, H along Z).

A requirement is covered when a dimension element matches it within 0.01 mm (``value`` or the
measured geometry): diameters by a diameter dimension (a radius dimension counts twice its value, a
dimension carrying a Phi prefix counts, and a thread designation Mxx covers every cylinder between
its minor and major diameter); sizes by any linear / aligned dimension.
"""

from __future__ import annotations

import math
import re

TOL = 0.01
MIN_SPAN = math.pi - 1e-3  # radians: a half cylinder or more is a hole / boss, less is a round
THREAD = re.compile(r"M(\d+(?:\.\d+)?)(?:[x×](\d+(?:\.\d+)?))?")


def _radius(face) -> float:
    """Radius of a cylindrical face (``Face.radius`` is None for a trimmed surface)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    return BRepAdaptor_Surface(face.wrapped).Cylinder().Radius()


def _span(face) -> float:
    """Angular extent of a cylindrical face, radians."""
    from OCP.BRepTools import BRepTools

    u0, u1, _, _ = BRepTools.UVBounds_s(face.wrapped)
    return abs(u1 - u0)


def required(shape) -> list[dict]:
    """The dimensions the model implies: [{"kind": "dia" | "size", "name", "value", "faces"?}]."""
    fam: dict[float, list[float]] = {}
    for f in shape.faces():
        if f.geom_type.name == "CYLINDER":
            fam.setdefault(round(2 * _radius(f), 2), []).append(_span(f))
    out = [
        {"kind": "dia", "name": f"Φ{dia:g}", "value": dia, "faces": len(spans)}
        for dia, spans in sorted(fam.items())
        if sum(spans) >= MIN_SPAN
    ]
    size = shape.bounding_box().size
    for name, v in zip("LWH", (size.X, size.Y, size.Z)):
        out.append({"kind": "size", "name": name, "value": round(v, 2)})
    return out


def _thread_range(designation):
    """(minor, major) diameter of a thread designation such as 4×M8-6H↧16, or None."""
    m = THREAD.search(designation or "")
    if not m:
        return None
    from linercad import res

    try:
        t = res.thread(f"M{m.group(1)}" + (f"x{m.group(2)}" if m.group(2) else ""))
    except Exception:  # noqa: BLE001 - an unknown designation simply covers nothing
        return None
    return t["d1"], t["d"]


def _dims(d):
    """(diameter values, thread ranges, linear values) offered by the drawing's dimensions."""
    dias, threads, sizes = [], [], []
    for e in d._els.values():
        if e.kind != "dim":
            continue
        i = e._intent
        vals = [v for v in (i.get("value"), i.get("measured")) if v is not None]
        typ = i["type"]
        if typ == "dia":
            dias += vals
        elif typ == "rad":
            dias += [2 * v for v in vals]
        elif typ in ("linear", "aligned"):
            sizes += vals
            if "Φ" in (i.get("prefix") or "") + (i.get("text") or ""):
                dias += vals
        if i.get("designation"):
            rng = _thread_range(i["designation"])
            if rng:
                threads.append(rng)
    return dias, threads, sizes


def compare(d, shape) -> dict:
    """{"required": [...], "missing": [...], "pass": bool} for drawing ``d`` against ``shape``."""
    req = required(shape)
    dias, threads, sizes = _dims(d)
    missing = []
    for r in req:
        v = r["value"]
        if r["kind"] == "dia":
            ok = any(abs(x - v) <= TOL for x in dias) or any(
                lo - TOL <= v <= hi + TOL for lo, hi in threads
            )
        else:
            ok = any(abs(x - v) <= TOL for x in sizes)
        if not ok:
            missing.append(r)
    return {"required": req, "missing": missing, "pass": not missing}
