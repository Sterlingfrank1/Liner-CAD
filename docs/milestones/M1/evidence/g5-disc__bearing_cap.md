# disc__bearing_cap (final: errors 0, warnings 0; commits e1..e5)

## Initial ("按需求出图", e1) — 2 builds: first had 2 overlap warnings (D.Ls/D.T, G.coax/R.spig) fixed by row=3 and rough at=0.7; second clean. 0 ok:false.
- From `--from end_cover`: turned(cut="full", bore with internal seal groove as bore points, holes=[mh] through holes), left holes_on_circle(4), section A through top/bottom holes; PMI coax(zone dia)/perp/pos; datum A on spigot dim.
## R1 4×Φ11, PCD Φ82 — params `dm=11`, `pcd=82`; e2 ok 0 warn.
## R2 止口 f8 — `tol="f7"->"f8"` (param + dim); e3 ok 0 warn.
## R3 删去同轴度，改径向圆跳动 0.05 — script `d["G.coax"].suppress(); front.gtol("run","circular_runout",0.05,datums=["A"],ref="D.d0")`; e4 ok 0 warn.
## R4 背面粗糙度 Ra 1.6 — script `d["R.back"].set(value=1.6)`; e5 ok 0 warn.

## Issues
- No dedicated tool/dim for internal rectangular groove in a bore (dim.groove is for external `grooves`); done with linear/dia dims. Groove not a feature -> not indexed as a groove.
- Bore points can't carry names, so bore-side edges (hole surface for runout) are referenced through the dimension D.d0 only.
- Chamfer note for bore mouth is a plain note ("C1"), not a chamfer element.
