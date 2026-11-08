"""L1: external thread on a shaft end (GB/T 4459.1), with its designation."""

VIEWS = [{"name": "front", "mode": "plain"}]


def drawing(spec="M20", length=30.0, d_body=None):
    return f'''from linercad import Drawing, res
d = Drawing(sheet="A4")
t = res.thread("{spec}")
D = t["d"]
body = {d_body!r} or D + 8
f = d.view("front")
f.turned("b", [(0, D / 2 - 1, "ch"), (1, D / 2, "thr"), ({length} + 10, D / 2), ({length} + 10, body / 2, "bd"), ({length} + 40, body / 2)])
f.thread("t", "{spec}", 0, {length})
f.dim.thread("td", "F.front.t")
f.dim.chamfer("c", "E.front.b.ch")
f.dim.dia("db", ({length} + 25, body / 2), ({length} + 25, -body / 2), value=body, side="inside")
f.dim.linear("l1", (0, -D / 2), ({length} + 10, -D / 2), dir="h", value={length} + 10, side="bottom")
f.dim.linear("L", (0, -D / 2), ({length} + 40, -body / 2), dir="h", value={length} + 40, side="bottom", row=2, role="overall")
d.general_tol("m")
'''


def model(spec="M20", length=30.0, d_body=None):
    from build123d import Axis, Cylinder, Pos, Rot, chamfer

    from linercad import res

    D = res.thread(spec)["d"]
    body = d_body or D + 8
    x = Rot(0, 90, 0)
    p = Pos((length + 10) / 2, 0, 0) * x * Cylinder(D / 2, length + 10)
    p = p + Pos(length + 10 + 15, 0, 0) * x * Cylinder(body / 2, 30)
    end = p.edges().filter_by(Axis.X, reverse=True).sort_by(Axis.X)[0]
    return chamfer(end, 1)
