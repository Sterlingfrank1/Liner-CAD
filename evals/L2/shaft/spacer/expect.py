def expect(e):
    e.dim(value=28)
    e.dim(e.feature(cyl=42), fit="h9")
    e.dim(e.feature(cyl=30), fit="H9")
    e.datum("A", on=e.face("left"), axis=False)
    e.gtol("parallelism", on=e.face("right"), datums=["A"], max=0.02)
    e.rough(e.face("left"), ra_max=1.6)
    e.note(contains="去除毛刺锐边。")
    e.view("front", must=False)
