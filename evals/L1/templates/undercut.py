"""L1: undercut groove at a shoulder (GB/T 4458.6 / 4457.5), width × bottom diameter designation."""

VIEWS = [{"name": "front", "mode": "plain"}]


def drawing(d1=24.0, d2=32.0, x=40.0, w=4.0, dg=21.0, length=70.0):
    return f"""from linercad import Drawing
d = Drawing(sheet="A4")
f = d.view("front")
r1, r2 = {d1} / 2, {d2} / 2
f.turned("b", [(0, r1), ({x}, r1), ({x}, r2), ({length}, r2)],
         grooves=[{{"name": "ug", "x": {x}, "w": {w}, "d": {dg}, "side": "left"}}])
f.dim.groove("g", "F.front.ug")
f.dim.dia("d1", ({x} / 2, r1), ({x} / 2, -r1), value={d1}, side="inside")
f.dim.dia("d2", ({x} + ({length} - {x}) / 2, r2), ({x} + ({length} - {x}) / 2, -r2), value={d2}, side="inside")
f.dim.linear("l0", (0, -r1), ({x} - {w}, -r1), dir="h", value={x} - {w}, side="bottom")
f.dim.linear("l2", ({x}, -r2), ({length}, -r2), dir="h", value={length} - {x}, side="bottom")
d.general_tol("m")
"""


def model(d1=24.0, d2=32.0, x=40.0, w=4.0, dg=21.0, length=70.0):
    from build123d import Axis, Polygon, revolve

    r1, r2, rg = d1 / 2, d2 / 2, dg / 2
    pts = [(0, 0), (0, r1), (x - w, r1), (x - w, rg), (x, rg), (x, r2), (length, r2), (length, 0)]
    return revolve(Polygon(*pts, align=None), Axis.X)
