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


def section(shape, view, mode="full", half="top", at=0.0, region=None):
    """``shape`` with the material toward the viewer removed: the whole near half for a full
    section, the near quarter on the ``half`` side for a half section (``top`` / ``bottom`` split
    at the view's horizontal axis, ``left`` / ``right`` at its vertical axis, through the origin).
    ``at``: the cutting plane's model coordinate along the viewing axis; ``region``: view-local
    polygon, a local (broken-out) section removes material only inside it."""
    look, up = CAMERA[view]
    lo, hi = [-FAR] * 3, [FAR] * 3
    k = next(i for i in range(3) if look[i])
    if look[k] > 0:  # viewer on the negative side of axis k
        hi[k] = at
    else:
        lo[k] = at
    if mode == "half":
        if half in ("top", "bottom"):
            ax, keep_pos = up, half == "top"
        elif half in ("left", "right"):
            ax, keep_pos = _cross(look, up), half == "right"
        else:
            raise ValueError(f"half {half!r}")
        j = next(i for i in range(3) if ax[i])
        if (ax[j] > 0) == keep_pos:
            lo[j] = 0.0
        else:
            hi[j] = 0.0
    elif mode != "full":
        raise ValueError(f"mode {mode!r}")
    cutter = _box(lo, hi)
    if region:
        from build123d import Face, Vector, Wire, extrude

        r = _cross(look, up)
        pts = [Vector(*(u * a + v * b for a, b in zip(r, up))) for u, v in region]
        prism = extrude(Face(Wire.make_polygon(pts, close=True)), FAR, dir=look, both=True)
        cutter = cutter & prism
    return shape - cutter


def cut_faces(cut, view, at=0.0, original=None):
    """Planar faces of a sectioned shape lying on the cutting plane and facing the viewer (the
    section area); faces that already existed in ``original`` (a flush face, nothing cut) are
    not section area."""
    look, _ = CAMERA[view]
    k = next(i for i in range(3) if look[i])

    def on_plane(f):
        if f.geom_type.name != "PLANE":
            return False
        n = _t(f.normal_at())
        return n[k] * look[k] < -1 + 1e-6 and abs(_t(f.center())[k] - at) < 1e-4

    old = []
    if original is not None:
        old = [(_t(f.center()), round(f.area, 4)) for f in original.faces() if on_plane(f)]
    out = []
    for f in cut.faces():
        if not on_plane(f):
            continue
        c, a = _t(f.center()), round(f.area, 4)
        if any(
            abs(a - oa) < 1e-3 and max(abs(x - y) for x, y in zip(c, oc)) < 1e-4 for oc, oa in old
        ):
            continue
        out.append(f)
    return out


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


def _t(v):
    return (v.X, v.Y, v.Z)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def right_of(view):
    look, up = CAMERA[view]
    return _cross(look, up)


def to_view(view, p):
    """3D model point → view-local (u, v)."""
    look, up = CAMERA[view]
    r = _cross(look, up)
    return (p[0] * r[0] + p[1] * r[1] + p[2] * r[2], p[0] * up[0] + p[1] * up[1] + p[2] * up[2])


def project_classes(shape, view, hidden=True):
    """HLR edges by class → [(cls, visible, edge)]; cls in sharp / smooth / outline (SPEC M3 §1.1).
    Edges lie in the viewport plane: their (X, Y) are the view's (u, v)."""
    from build123d import Edge, Vector
    from OCP.BRepLib import BRepLib
    from OCP.gp import gp_Ax1, gp_Ax2
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    look, up = CAMERA[view]
    algo = HLRBRep_Algo()
    algo.Add(shape.wrapped)
    origin = Vector(*(-FAR * c for c in look))
    ax = gp_Ax2()
    ax.SetAxis(gp_Ax1(origin.to_pnt(), Vector(*(-c for c in look)).to_dir()))
    ax.SetYDirection(Vector(*up).to_dir())
    algo.Projector(HLRAlgo_Projector(ax))
    algo.Update()
    algo.Hide()
    h = HLRBRep_HLRToShape(algo)
    groups = [
        ("sharp", True, h.VCompound()),
        ("smooth", True, h.Rg1LineVCompound()),
        ("outline", True, h.OutLineVCompound()),
    ]
    if hidden:
        groups += [
            ("sharp", False, h.HCompound()),
            ("smooth", False, h.Rg1LineHCompound()),
            ("outline", False, h.OutLineHCompound()),
        ]
    out = []
    for cls, vis, comp in groups:
        if comp.IsNull():
            continue
        ex = TopExp_Explorer(comp, TopAbs_EDGE)
        while ex.More():
            e = ex.Current()
            BRepLib.BuildCurves3d_s(e, 1e-5)
            out.append((cls, vis, Edge(e)))
            ex.Next()
    return out
