"""L1: stepped section (GB/T 4458.6) of a disc with two plain holes in different parallel planes.
The cutting line runs along the axis plane, jogs sideways between the bore and the second hole and
continues in a parallel plane through that hole; the section view shows both holes as in one plane.
The model puts both holes in the axis plane (the equivalent of the stepped cut); the end view is
not compared because it shows the real hole positions."""

VIEWS = [{"name": "front", "mode": "full"}]

SRC = """from linercad import Drawing

d = Drawing(sheet="A3")
D, T, d0 = 100, 24, 24
c, v2, v1, dh1, dh2 = %(c)r, 34, 32, 12, 8  # sideways offset of hole 2, hole v positions, diameters
R, r0 = D / 2, d0 / 2
front, left = d.view("front"), d.view("left")
front.turned(
    "body",
    [(0, R), (T, R)],
    bore=[(0, r0), (T, r0)],
    cut="full",
    holes=[
        {"name": "h1", "r": v1, "d": dh1, "x0": 0, "x1": T, "at": "top"},
        {"name": "h2", "r": v2, "d": dh2, "x0": 0, "x1": T, "at": "bottom"},
    ],
)
left.circle((0, 0), R, name="outer")
left.circle((0, 0), r0, name="bore")
left.circle((0, v1), dh1 / 2, name="h1")
left.circle((c, -v2), dh2 / 2, name="h2")
left.center_mark((0, v1), 9, name="c1")
left.center_mark((c, -v2), 7, name="c2")
left.center_mark((0, 0), R, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, R), (0, -20), (c, -20), (c, -R)])
front.dim.linear("T", (0, -R), (T, -R), value=T, side="bottom")
front.dim.dia("D", (0, R), (0, -R), value=D, side="left")
front.dim.dia("d0", (T, r0), (T, -r0), value=d0, side="right")
left.dim.dia("h1", circle="E.left.h1.1", value=dh1)
left.dim.dia("h2", circle="E.left.h2.1", value=dh2)
d.general_tol("m")
"""


def drawing(c=18):
    return SRC % {"c": c}


def model(c=18):
    from build123d import Axis, Cylinder, Face, Polyline, Pos, Rot, revolve

    D, T, d0, v2, v1, dh1, dh2 = 100, 24, 24, 34, 32, 12, 8
    pts = [(0, d0 / 2), (0, D / 2), (T, D / 2), (T, d0 / 2)]
    part = revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)
    x = Pos(T / 2, 0, 0) * Rot(0, 90, 0)
    part -= Pos(0, 0, v1) * x * Cylinder(dh1 / 2, T + 2)
    part -= Pos(0, 0, -v2) * x * Cylinder(dh2 / 2, T + 2)
    return part
