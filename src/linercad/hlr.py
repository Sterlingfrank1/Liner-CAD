"""Hidden-line projection of build123d shapes into Liner-CAD view coordinates (SPEC M1 §8).

Private, development-time module: used by the geometry comparison in ``evals/`` and, from M3, as
the 3D geometry source. Needs the optional dependency ``linercad[3d]`` (build123d).
"""

from __future__ import annotations

import math

# camera looking direction (model axes) and up vector per basic view; the viewport's (x, y)
# then equal the view's local (u, v) of M0 SPEC §3.1 (camera right = look × up)
CAMERA = {
    "front": ((0, 1, 0), (0, 0, 1)),
    "rear": ((0, -1, 0), (0, 0, 1)),
    "top": ((0, 0, -1), (0, 1, 0)),
    "bottom": ((0, 0, 1), (0, -1, 0)),
    "left": ((1, 0, 0), (0, 0, 1)),
    "right": ((-1, 0, 0), (0, 0, 1)),
}
FAR = 10000.0
STEP = 0.25  # sampling step along projected edges, mm


def _sample(edge, step=STEP):
    L = edge.length
    n = max(1, int(math.ceil(L / step)))
    return [(p.X, p.Y) for p in (edge @ (k / n) for k in range(n + 1))]


def project(shape, view, hidden=False):
    """Visible (and hidden) edges of ``shape`` seen in ``view`` → {"visible": [polyline], ...}."""
    look, up = CAMERA[view]
    origin = tuple(-FAR * c for c in look)
    vis, hid = shape.project_to_viewport(origin, up, (0, 0, 0))
    out = {"visible": [_sample(e) for e in vis]}
    if hidden:
        out["hidden"] = [_sample(e) for e in hid]
    return out


def _box(lo, hi):
    from build123d import Box, Pos

    c = tuple((a + b) / 2 for a, b in zip(lo, hi))
    return Pos(*c) * Box(*(b - a for a, b in zip(lo, hi)))


def section(shape, view, mode="full", half="top"):
    """``shape`` with the material toward the viewer removed: the whole near half for a full
    section, the near quarter on the ``half`` side for a half section (axis through the origin)."""
    look, up = CAMERA[view]
    lo, hi = [-FAR] * 3, [FAR] * 3
    k = next(i for i in range(3) if look[i])
    if look[k] > 0:  # viewer on the negative side of axis k
        hi[k] = 0.0
    else:
        lo[k] = 0.0
    if mode == "half":
        j = next(i for i in range(3) if up[i])
        top = (up[j] > 0) == (half == "top")
        if top:
            lo[j] = 0.0
        else:
            hi[j] = 0.0
    elif mode != "full":
        raise ValueError(f"mode {mode!r}")
    return shape - _box(lo, hi)


def section_project(shape, view, mode="full", half="top", hidden=False):
    return project(section(shape, view, mode, half), view, hidden)


def slice_view(shape, parent, trace, axes):
    """Removed section: cut ``shape`` by the plane through the parent-view ``trace`` (two points
    in parent coordinates) and express the section outline in the section view's local axes
    (SPEC M1 §5: v along the trace, u = depth toward the parent's viewer × axes['depth'])."""
    from build123d import Plane, Vector

    look, up = CAMERA[parent]
    right = _cross(look, up)
    toward = tuple(-c for c in look)
    (a0, a1), (b0, b1) = trace
    p0 = Vector(*(a0 * r + a1 * u for r, u in zip(right, up)))
    p1 = Vector(*(b0 * r + b1 * u for r, u in zip(right, up)))
    t = (p1 - p0).normalized()
    normal = t.cross(Vector(*toward))
    plane = Plane(origin=p0, x_dir=t, z_dir=normal)
    faces = shape.intersect(plane)
    tv, depth = axes["v"], axes["depth"]
    tdir = Vector(*(tv[0] * r + tv[1] * u for r, u in zip(right, up)))
    out = []
    for f in faces:
        for e in f.edges():
            pts = []
            n = max(1, int(math.ceil(e.length / STEP)))
            for k in range(n + 1):
                P = e @ (k / n)
                pts.append((P.dot(Vector(*toward)) * depth, P.dot(tdir)))
            out.append(pts)
    return {"visible": out}


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
