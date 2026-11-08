"""L1: shaft keyway (GB/T 1095) in the front view, width and depth in a removed section."""

VIEWS = [{"name": "front", "mode": "plain"}]  # the removed section is compared automatically


def drawing(d=28.0, x0=20.0, kl=40.0, length=100.0):
    return f"""from linercad import Drawing
d = Drawing(sheet="A3")
f = d.view("front")
r = {d} / 2
f.turned("b", [(0, r, "s"), ({length}, r)])
f.keyway("kw", {x0}, {kl}, {d})
f.dim.dia("db", ({length} * 0.85, r), ({length} * 0.85, -r), value={d}, side="inside")
f.dim.linear("ks", (0, r), ({x0}, r), dir="h", value={x0}, role="position", datum="E.front.b.s:start", side="top")
f.dim.linear("kl", ({x0}, r), ({x0} + {kl}, r), dir="h", value={kl}, side="top")
f.dim.linear("L", (0, -r), ({length}, -r), dir="h", value={length}, role="overall", side="bottom")
xm = {x0} + {kl} / 2
sec = d.removed_section("A", parent="front", through=[(xm, -r - 6), (xm, r + 6)], look="left")
sec.shaft_cut("s", {d}, keyway="F.front.kw")
sec.dim.keyway("kb", "F.A.s", what="b")
sec.dim.keyway("kd", "F.A.s", what="depth")
d.general_tol("m")
"""


def model(d=28.0, x0=20.0, kl=40.0, length=100.0):
    from build123d import (
        Axis,
        BuildSketch,
        Locations,
        Plane,
        Polygon,
        SlotCenterToCenter,
        extrude,
        revolve,
    )

    from linercad import res

    k = res.key(d)
    b, t1, R = k["b"], k["t1"], d / 2
    shaft = revolve(Polygon((0, 0), (0, R), (length, R), (length, 0), align=None), Axis.X)
    with BuildSketch(Plane.XZ.offset(R - t1)) as sk:  # keyway bottom at y = -(R - t1)
        with Locations((x0 + kl / 2, 0)):
            SlotCenterToCenter(kl - b, b)
    return shaft - extrude(sk.sketch, amount=t1 + 1)
