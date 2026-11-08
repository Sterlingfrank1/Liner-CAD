# shaft__spacer (final: errors 0, warnings 0; commits e1..e5)

## Initial ("按需求出图", e1) — 3 builds: 2 ok:false (bore tuple with name -> ValueError; unknown id E.front.cv.le), then ok, 0 warnings.
- From `--from sleeve`; cut="full"; end-face edges got via `d.q.lines(view="front").where(dir="v").near(...).one()` inside drawing.py (datum A = left face, parallelism 0.02 on right face, Ra1.6 both faces).
## R1 h8 + code&deviation — drawing.py: Param tol h8; dim.dia tol="h8", tol_show="both"; build e2 ok, 0 warn (1 attempt).
## R2 长度 32 — `L=Param(32)`; e3 ok, 0 warn.
## R3 加技术要求 — script `d.notes.tech("两端面磨平。")`; e4 ok, 0 warn.
## R4 左端面 Ra 0.8 — script `d["R.le"].set(value=0.8)`; e5 ok, 0 warn.

## Issues
- Full-section sleeve: no named edge for end faces / bore (bore points can't be named); must query by geometry.
- Bore-end inner chamfers: no dimension API except note "2×C1"; `dim.chamfer` for inner chamfer edges not tried (note is plain text, not indexed).
- `lcad build` for the initial draft when nothing is committed returns edit null, fine.
