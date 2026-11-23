def expect(e):
    e.dim(value=45)
    e.dim(e.feature(cyl=32), fit="H7")
    e.dim(e.feature(cyl=40), fit="r6")
    e.datum("A", on=e.feature(cyl=32), axis=True)
    e.gtol("concentricity", on=e.feature(cyl=40), datums=["A"], max=0.03)
    e.rough(e.face("top"), ra_max=0.8)
    e.note(contains="压入座孔后精加工")
    e.view("front", must=False)
