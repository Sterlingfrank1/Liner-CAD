"""L1: tapped holes on a pitch circle — internal thread in a revolved full section (minor diameter
thick, major thin, thread-end line, 120° drill point) and the end view (thread_end), GB/T 4459.1."""

VIEWS = [{"name": "front", "mode": "full"}, {"name": "left", "mode": "plain"}]

SRC = """import math

from linercad import Drawing, res

d = Drawing(sheet="A3")
t = res.thread(%(spec)r)
D1, DN = t["d1"], t["d"]
T, TD, DD = 3 * DN, 1.5 * DN, 2 * DN  # thickness, thread depth, drill depth
pcd, r0, N = 8 * DN, 1.5 * DN, %(n)d
R = pcd / 2 + 2.5 * DN
front, left = d.view("front"), d.view("left")
front.turned(
    "body",
    [(0, R), (T, R)],
    bore=[(0, r0), (T, r0)],
    cut="full",
    holes=[{"name": "tap", "r": pcd / 2, "d": D1, "x0": 0, "x1": DD, "tip": True,
            "thread": %(spec)r, "depth": TD, "at": "%(at)s"}],
)
left.circle((0, 0), R, name="outer")
left.circle((0, 0), r0, name="bore")
left.circle((0, 0), pcd / 2, role="center", name="pcd")
for k in range(N):
    a = math.radians(90 + 360 * k / N)
    c = (pcd / 2 * math.cos(a), pcd / 2 * math.sin(a))
    left.thread_end(f"t{k + 1}", c, %(spec)r, kind="int")
    left.center_mark(c, DN * 0.8, name=f"c{k + 1}")
    if k:
        d.accept("conv_dim", f"F.left.t{k + 1}", "均布螺孔共用 t1 的代号")
left.center_mark((0, 0), R, name="axis")
d.section("A", view="front", cut_in="left", through=[(0, -R), (0, R)])
front.dim.linear("T", (0, -R), (T, -R), value=T, side="bottom")
front.dim.linear("td", (0, R), (TD, R), value=TD, side="top")
front.dim.linear("dd", (0, R), (DD, R), value=DD, side="top", row=2)
front.dim.dia("D", (0, R), (0, -R), value=2 * R, side="left")
front.dim.dia("d0", (T, r0), (T, -r0), value=2 * r0, side="right")
left.dim.hole("tap", "F.left.t1", n=N)
left.dim.dia("pcd", circle="E.left.pcd.1", value=pcd)
d.general_tol("m")
"""


def drawing(spec="M8", n=3):
    return SRC % {"spec": spec, "n": n, "at": "both" if n % 2 == 0 else "top"}


def model(spec="M8", n=3):
    import math

    from build123d import Axis, Face, Polyline, Pos, revolve

    from linercad import res

    def lathe(pts):
        return revolve(Face(Polyline(*[(x, r, 0) for x, r in pts], close=True)), Axis.X)

    t = res.thread(spec)
    D1, DN = t["d1"], t["d"]
    T, DD = 3 * DN, 2 * DN
    pcd, r0 = 8 * DN, 1.5 * DN
    R = pcd / 2 + 2.5 * DN
    part = lathe([(0, r0), (0, R), (T, R), (T, r0)])
    tip = D1 / 2 / math.tan(math.radians(60))
    tool = lathe([(-1, 0), (-1, D1 / 2), (DD, D1 / 2), (DD + tip, 0)])
    for k in range(n):  # end view (u = −Y, v = Z)
        a = math.radians(90 + 360 * k / n)
        part -= Pos(0, -pcd / 2 * math.cos(a), pcd / 2 * math.sin(a)) * tool
    return part
