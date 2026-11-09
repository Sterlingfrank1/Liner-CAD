"""叉形接头（叉架类）：杆部左端 M16 螺孔，右端叉口两叉开 Φ12 销孔。主视图沿对称面全剖（过螺孔和叉口槽，
叉口槽在剖切面里是空的，后一叉的内侧面可见，销孔在上面画成圆），俯视图表达叉口槽和销孔位置（虚线），
左视图从杆端看，螺孔用端视图规定画法。基准 A 是杆轴线：销孔轴线对 A 垂直，叉口槽对 A 对称。
模型轴：X 向右（轴线），Y 向后，Z 向上。主视 (X, Z)，俯视 (X, Y)，左视 (-Y, Z)；销孔轴线沿 Y。"""

from linercad import Drawing, Param

d = Drawing(sheet="A3", std="GB", scale="1:1")
P = d.params(
    D=Param(30, min=24, max=45, step=1, label="杆径", rule="D > 16 + 8"),
    ls=Param(40, min=30, max=60, step=1, label="杆长", rule="ls > 28 + 6"),
    B=Param(40, min=30, max=60, step=1, label="叉部高", rule="B > D + 4"),
    W=Param(40, min=30, max=60, step=1, label="叉部宽", rule="W > g + 12"),
    Lt=Param(90, min=70, max=130, step=1, label="总长", rule="Lt > ls + sd"),
    sd=Param(30, min=20, max=50, step=1, label="叉口槽深（自叉端）", rule="sd > 2 * dp"),
    g=Param(20, min=10, max=30, step=1, label="叉口槽宽", tol="H12"),
    dp=Param(12, min=8, max=20, step=1, label="销孔直径", tol="H9"),
    xp=Param(15, min=10, max=30, step=1, label="销孔距叉端", rule="xp > dp / 2 + 4"),
)
D, B, W, Lt, g, dp, xp = P.D, P.B, P.W, P.Lt, P.g, P.dp, P.xp
ls, sd = P.ls, P.sd
xs = Lt - sd  # 槽底
xc = Lt - xp  # 销孔中心
SPEC, TD, DD = "M16", 24, 28  # 螺孔：螺纹深 24，钻孔深 28

# ---- 主视图 (X, Z)：沿对称面（y = 0）全剖
front = d.view("front")
front.move(dx=12, dy=-14)
front.polygon(
    [
        (0, -D / 2),
        (ls, -D / 2),
        (ls, -B / 2),
        (xs, -B / 2),
        (xs, B / 2),
        (ls, B / 2),
        (ls, D / 2),
        (0, D / 2),
    ],
    name="cut",
)
front.tapped_hole("tap", (0, 0), "+x", SPEC, TD, drill_depth=DD)
front.hatch("a", loops=["F.front.cut", "F.front.tap"])
front.line((xs, -B / 2), (Lt, -B / 2), name="prong_b")
front.line((xs, B / 2), (Lt, B / 2), name="prong_t")
front.line((Lt, -B / 2), (Lt, B / 2), name="end")
front.circle((xc, 0), dp / 2, name="pin")
front.center_mark((xc, 0), dp / 2, name="pin")
front.centerline((-5, 0), (Lt + 5, 0), name="axis")

# ---- 俯视图 (X, Y)
top = d.view("top")
top.polygon(
    [
        (0, -D / 2),
        (ls, -D / 2),
        (ls, -W / 2),
        (Lt, -W / 2),
        (Lt, -g / 2),
        (xs, -g / 2),
        (xs, g / 2),
        (Lt, g / 2),
        (Lt, W / 2),
        (ls, W / 2),
        (ls, D / 2),
        (0, D / 2),
    ],
    name="outline",
)
top.line((ls, -D / 2), (ls, D / 2), name="junction")  # 杆与叉部的交界（圆在俯视图里投影成线）
top.tapped_hole("tap", (0, 0), "+x", SPEC, TD, drill_depth=DD, cut=False)
for sg in (1, -1):  # 销孔（虚线）：两叉各一段
    for x in (xc - dp / 2, xc + dp / 2):
        top.line(
            (x, sg * g / 2),
            (x, sg * W / 2),
            role="hidden",
            name=f"pin{'p' if sg > 0 else 'n'}{int(x)}",
        )
top.centerline((-5, 0), (xc + 3, 0), name="axis")  # 到销孔中心线为止，给槽宽尺寸留位置
top.centerline((xc, -W / 2 - 4), (xc, W / 2 + 4), name="pin")

# ---- 左视图 (-Y, Z)：从杆端看
left = d.view("left")
left.polygon([(-W / 2, -B / 2), (W / 2, -B / 2), (W / 2, B / 2), (-W / 2, B / 2)], name="block")
left.circle((0, 0), D / 2, name="shank")
left.thread_end("t1", (0, 0), SPEC, kind="int")
left.center_mark((0, 0), D / 2, name="axis")
for sg in (1, -1):
    left.line(
        (sg * g / 2, -B / 2),
        (sg * g / 2, B / 2),
        role="hidden",
        name=f"slot{'p' if sg > 0 else 'n'}",
    )
    for z in (dp / 2, -dp / 2):
        left.line(
            (sg * g / 2, z),
            (sg * W / 2, z),
            role="hidden",
            name=f"pin{'p' if sg > 0 else 'n'}{'t' if z > 0 else 'b'}",
        )
left.centerline((-W / 2 - 4, 0), (W / 2 + 4, 0), name="pin")

# ---- 尺寸：主视图
front.dim.dia("D", (0, D / 2), (0, -D / 2), value=D, side="left")
front.dim.linear("td", (0, D / 2), (TD, D / 2), dir="h", value=TD, side="top")
front.dim.linear("dd", (0, D / 2), (DD, D / 2), dir="h", value=DD, side="top", row=2)
front.dim.linear(
    "xp",
    (xc, B / 2),
    (Lt, B / 2),
    dir="h",
    value=xp,
    role="position",
    datum="E.front.end.1",
    side="top",
)
front.dim.linear("ls", (0, -D / 2), (ls, -B / 2), dir="h", value=ls, side="bottom")
front.dim.linear("sd", (xs, -B / 2), (Lt, -B / 2), dir="h", value=sd, side="bottom")
front.dim.linear(
    "Lt", (0, -D / 2), (Lt, -B / 2), dir="h", value=Lt, role="overall", side="bottom", row=2
)
front.dim.linear("B", (Lt, -B / 2), (Lt, B / 2), dir="v", value=B, side="right")
front.dim.dia("dp", circle="E.front.pin.1", value=dp, tol="H9", at=135)

# ---- 尺寸：俯视图、左视图
top.dim.linear("W", (Lt, -W / 2), (Lt, W / 2), dir="v", value=W, side="right")
xg = Lt - 3  # 槽内靠叉端
top.dim.linear("g", (xg, -g / 2), (xg, g / 2), dir="v", value=g, tol="H12", side="inside")
left.dim.hole("th", "F.left.t1")

# ---- 剖切符号（对称面）与 PMI：A = 杆轴线
d.section("B", view="front", cut_in="top", through=[(-8, 0), (Lt + 8, 0)])
front.datum("A", ref="D.D")
front.gtol("perp", "perpendicularity", 0.05, datums=["A"], zone="dia", ref="D.dp", at=0, length=35)
top.gtol("sym", "symmetry", 0.1, datums=["A"], ref="D.g")
front.rough("pin", 3.2, ref="D.dp")
top.rough("slot", 6.3, ref="E.top.outline.6", at=0.5, length=10)
d.rough_default(12.5)

d.notes.tech(["锻件不得有裂纹、折叠。", "未注圆角 R1~R2。", "调质处理 HB 220~260。"])
d.general_tol("m")
d.title(name="叉形接头", drawing_no="LC-CL-01", material="45", designer="Liner-CAD")
