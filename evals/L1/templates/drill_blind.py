"""L1: blind drilled holes on a pitch circle — cylindrical wall, flat-free 120° drill point, depth
measured to the end of the full-diameter part (GB/T 16675.2); end view with the equally spaced holes."""

VIEWS = [{"name": "front", "mode": "full"}, {"name": "left", "mode": "plain"}]

SRC = """from linercad import Drawing

d = Drawing(sheet="A3")
D, T, d0, pcd, n = 100, 30, 24, 70, %(n)d
dh, depth = %(dh)r, %(depth)r
R, r0, Rb = D / 2, d0 / 2, pcd / 2
front, left = d.view("front"), d.view("left")
front.turned(
    "body",
    [(0, R), (T, R)],
    bore=[(0, r0), (T, r0)],
    cut="full",
    holes=[{"name": "dr", "r": Rb, "d": dh, "x0": 0, "x1": depth, "tip": True}],
)
left.circle((0, 0), R, name="outer")
left.circle((0, 0), r0, name="bore")
left.holes_on_circle("hole", (0, 0), pcd=pcd, n=n, d=dh, start=90)
left.center_mark((0, 0), R, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, -R), (0, R)])
front.dim.linear("T", (0, -R), (T, -R), value=T, side="bottom")
front.dim.linear("depth", (0, R), (depth, R), value=depth, side="top")
front.dim.dia("D", (0, R), (0, -R), value=D, side="left")
front.dim.dia("d0", (T, r0), (T, -r0), value=d0, side="right")
left.dim.dia("dh", circle="E.left.hole.1", value=dh, prefix=f"{n}×", suffix=" EQS")
left.dim.dia("pcd", circle="C.left.hole", value=pcd)
d.general_tol("m")
"""


def drawing(n=4, dh=10, depth=18):
    return SRC % {"n": n, "dh": dh, "depth": depth}


def model(n=4, dh=10, depth=18):
    import math

    from build123d import Axis, Face, Polyline, Pos, revolve

    def lathe(pts):
        return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)

    D, T, d0, pcd = 100, 30, 24, 70
    part = lathe([(0, d0 / 2), (0, D / 2), (T, D / 2), (T, d0 / 2)])
    tip = dh / 2 / math.tan(math.radians(60))
    tool = lathe([(-1, 0), (-1, dh / 2), (depth, dh / 2), (depth + tip, 0)])
    for k in range(n):  # end view (u = −Y, v = Z)
        a = math.radians(90 + 360 * k / n)
        part -= Pos(0, -pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)) * tool
    return part
