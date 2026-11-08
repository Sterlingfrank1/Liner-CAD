"""L1: aligned (rotated) section (GB/T 4458.6, 4459.1) of a disc with three equally spaced holes.
The cutting line runs along the axis to the top hole, then bends at the axis to the second hole;
the second plane is rotated into the first one, so the section view shows holes at the top and the
bottom.  The model puts the holes in the axis plane (the equivalent of the rotated cut); the end
view is not compared because it shows the real hole positions."""

VIEWS = [{"name": "front", "mode": "full"}]

SRC = """import math

from linercad import Drawing

d = Drawing(sheet="A3")
D, T, d0, pcd, dh = %(D)r, 24, 24, %(pcd)r, %(dh)r
R, r0, Rb = D / 2, d0 / 2, pcd / 2
front, left = d.view("front"), d.view("left")
front.turned(
    "body",
    [(0, R), (T, R)],
    bore=[(0, r0), (T, r0)],
    cut="full",
    holes=[{"name": "h", "r": Rb, "d": dh, "x0": 0, "x1": T}],
)
left.circle((0, 0), R, name="outer")
left.circle((0, 0), r0, name="bore")
left.holes_on_circle("hole", (0, 0), pcd=pcd, n=3, d=dh, start=90)
left.center_mark((0, 0), R, name="axis")
a = math.radians(210)
d.section("A", view="front", cut_in="left", through=[(0, R), (0, 0), (R * math.cos(a), R * math.sin(a))])
front.dim.linear("T", (0, -R), (T, -R), value=T, side="bottom")
front.dim.dia("D", (0, R), (0, -R), value=D, side="left")
front.dim.dia("d0", (T, r0), (T, -r0), value=d0, side="right")
left.dim.dia("dh", circle="E.left.hole.1", value=dh, prefix="3×", suffix=" EQS")
left.dim.dia("pcd", circle="C.left.hole", value=pcd)
d.accept("overlap", "S.A", "转折点在轴线中心，转折处的字母与中心线相邻（GB/T 4458.6 允许省略，此处保留）")
d.general_tol("m")
"""


def drawing(D=100, pcd=70, dh=12):
    return SRC % {"D": D, "pcd": pcd, "dh": dh}


def model(D=100, pcd=70, dh=12):
    from build123d import Axis, Cylinder, Face, Polyline, Pos, Rot, revolve

    T, d0 = 24, 24
    pts = [(0, d0 / 2), (0, D / 2), (T, D / 2), (T, d0 / 2)]
    part = revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)
    for z in (pcd / 2, -pcd / 2):  # the rotated hole sits in the axis plane, opposite the first
        part -= Pos(T / 2, 0, z) * Rot(0, 90, 0) * Cylinder(dh / 2, T + 2)
    return part
