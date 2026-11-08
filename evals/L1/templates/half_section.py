"""L1: half section of a symmetric revolved part (GB/T 17452): upper half sectioned, lower half
outside; the dividing line is the centre line.  The HLR of a half section leaves a visible edge
along the axis (edge of the exposed cut plane), masked here for the geometry comparison."""

VIEWS = [{"name": "front", "mode": "half", "half": "top"}]

SRC = """from linercad import Drawing

d = Drawing(sheet="A3")
bore, L, B = %(bore)r, %(L)r, %(B)r
D, Dh = 4 * bore, 2 * bore
R, Rh, r0 = D / 2, Dh / 2, bore / 2
front = d.view("front")
body = front.turned(
    "body",
    [(0, R, "rim"), (B, R), (B, Rh, "hub"), (L, Rh)],
    bore=[(0, r0), (L, r0)],
    cut="half",
    half="top",
)
body._intent["mask"] = [[-1.0, -0.2], [L + 1, -0.2], [L + 1, 0.2], [-1.0, 0.2]]
front.dim.dia("D", (B, R), (B, -R), value=D, side="left")
front.dim.dia("Dh", (L, Rh), (L, -Rh), value=Dh, side="right", row=2)
front.dim.dia("d0", (L, r0), (L, -r0), value=bore, side="right")
front.dim.linear("B", (0, -R), (B, -R), value=B, side="bottom")
front.dim.linear("L", (0, -R), (L, -Rh), dir="h", value=L, side="bottom", row=2)
d.general_tol("m")
"""


def drawing(bore=24, L=40, B=18):
    return SRC % {"bore": bore, "L": L, "B": B}


def model(bore=24, L=40, B=18):
    from build123d import Axis, Face, Polyline, revolve

    D, Dh = 4 * bore, 2 * bore
    pts = [(0, bore / 2), (0, D / 2), (B, D / 2), (B, Dh / 2), (L, Dh / 2), (L, bore / 2)]
    return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)
