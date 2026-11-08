"""L1: hub keyway (GB/T 1095) — full section with the keyway bottom at d + t2 in the upper half,
end view with the rectangular notch in the bore circle, width b (JS9) and depth d + t2."""

VIEWS = [{"name": "front", "mode": "full"}, {"name": "left", "mode": "plain"}]

SRC = """from linercad import Drawing

d = Drawing(sheet="A3")
bore, T = %(bore)r, 40
R, r0 = 1.8 * bore, bore / 2
front, left = d.view("front"), d.view("left")
front.turned("body", [(0, R), (T, R)], bore=[(0, r0), (T, r0)], cut="full", hub_keyway=True)
left.circle((0, 0), R, name="outer")
left.keyway_end("kw", (0, 0), bore, kind="hub")
left.center_mark((0, 0), R, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, -R), (0, R)])
front.dim.linear("T", (0, -R), (T, -R), value=T, side="bottom")
front.dim.dia("D", (0, R), (0, -R), value=2 * R, side="left")
front.dim.dia("d0", (T, r0), (T, -r0), value=bore, side="right")
left.dim.keyway("kb", "F.left.kw", what="b", side="inside")
left.dim.keyway("kd", "F.left.kw", what="depth")
d.general_tol("m")
"""


def drawing(bore=30):
    return SRC % {"bore": bore}


def model(bore=30):
    from build123d import Axis, Box, Face, Polyline, Pos, revolve

    from linercad import res

    k = res.key(bore)
    T, R, r0 = 40, 1.8 * bore, bore / 2
    pts = [(0, r0), (0, R), (T, R), (T, r0)]
    part = revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)
    part -= Pos(T / 2, 0, (r0 + k["t2"]) / 2) * Box(T + 2, k["b"], r0 + k["t2"])
    return part
