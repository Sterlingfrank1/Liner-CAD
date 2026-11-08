"""L1: rectangular spline (GB/T 4459.3): axial view with the spline major / minor lines + end view."""

VIEWS = [{"name": "front", "mode": "plain"}, {"name": "left", "mode": "plain"}]


def drawing(spec="6x23x26x6", ls=40.0, length=90.0):
    return f'''from linercad import Drawing, res
d = Drawing(sheet="A3")
rD = res.spline("{spec}")["D"] / 2
rj = rD + 4
f = d.view("front")
e = d.view("left")
f.turned("b", [(0, rD, "spl"), ({ls}, rD), ({ls}, rj, "j"), ({length}, rj)])
f.spline("sp", "{spec}", 0, {ls})
e.spline_end("spe", (0, 0), "{spec}")
e.circle((0, 0), rj, name="j")
e.center_mark((0, 0), rj, name="axis")
f.dim.spline("sd", "F.front.sp")
e.dim.spline("sde", "F.left.spe")
xj = {ls} + ({length} - {ls}) / 2
f.dim.dia("dj", (xj, rj), (xj, -rj), value=2 * rj, side="inside")
f.dim.linear("l1", (0, -rD), ({ls}, -rj), dir="h", value={ls}, side="bottom")
f.dim.linear("L", (0, -rD), ({length}, -rj), dir="h", value={length}, role="overall", side="bottom", row=2)
d.general_tol("m")
'''


def model(spec="6x23x26x6", ls=40.0, length=90.0):
    from build123d import Axis, Box, Cylinder, Polygon, Pos, Rot, revolve

    from linercad import res

    s = res.spline(spec)
    N, d, D, B = s["N"], s["d"], s["D"], s["B"]
    rj = D / 2 + 4
    ax = Rot(0, 90, 0)
    core = Pos(ls / 2, 0, 0) * ax * Cylinder(d / 2, ls)
    for k in range(N):  # teeth centred on +Z, N-fold symmetric
        core = core + Rot(360 / N * k, 0, 0) * Pos(ls / 2, 0, (D / 2 + 1) / 2) * Box(
            ls, B, D / 2 + 1
        )
    spl = core & (Pos(ls / 2, 0, 0) * ax * Cylinder(D / 2, ls))
    body = revolve(Polygon((ls, 0), (ls, rj), (length, rj), (length, 0), align=None), Axis.X)
    return body + spl
