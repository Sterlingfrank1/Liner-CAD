"""L1: type A centre hole at a shaft end (GB/T 4459.5 simplified representation, GB/T 145 sizes)."""

VIEWS = [{"name": "front", "mode": "plain"}]


def drawing(D=30.0, d=3.15, length=60.0):
    return f"""from linercad import Drawing
d = Drawing(sheet="A4")
f = d.view("front")
f.turned("b", [(0, {D} / 2 - 1, "ch"), (1, {D} / 2), ({length}, {D} / 2)])
f.center_hole("c", on="F.front.b", end="left", type="A", d={d})
f.dim.dia("db", ({length} / 2, {D} / 2), ({length} / 2, -{D} / 2), value={D}, side="inside")
f.dim.chamfer("c1", "E.front.b.ch")
f.dim.linear("L", (0, -{D} / 2), ({length}, -{D} / 2), dir="h", value={length}, role="overall", side="bottom")
d.general_tol("m")
"""


def model(D=30.0, d=3.15, length=60.0):
    from build123d import Axis, Cylinder, Pos, Rot, chamfer

    p = Pos(length / 2, 0, 0) * Rot(0, 90, 0) * Cylinder(D / 2, length)
    end = p.edges().filter_by(Axis.X, reverse=True).sort_by(Axis.X)[0]
    return chamfer(end, 1)
