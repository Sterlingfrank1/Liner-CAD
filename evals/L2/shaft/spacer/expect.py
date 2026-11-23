def expect(e):
    e.dim(value=28)
    e.dim(e.feature(cyl=42, where="right"), fit="h9")
    e.dim(e.feature(cyl=30, where="right"), fit="H9")
    e.datum("A", axis=False)
    e.gtol("parallelism", datums=["A"], max=0.02)
    e.rough(ra_max=1.6)
    e.note(contains="去除毛刺锐边。")
    e.view("front", must=False)
