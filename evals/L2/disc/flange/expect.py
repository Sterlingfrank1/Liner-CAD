def expect(e):
    e.dim(value=15)
    e.dim(e.feature(cyl=30), fit='H7')
    e.datum('A', axis=True)
    e.gtol('perpendicularity', datums=['A'], max=0.03)
    e.rough(ra_max=1.6)
    e.note(contains='铸件时效处理。')
    e.view('front', must=False)
    e.view('left', must=False)
