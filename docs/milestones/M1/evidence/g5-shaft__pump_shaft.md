# shaft__pump_shaft (final: errors 0, warnings 0; commits e1..e15)

## Initial drawing ("按需求出图", e1) — 5 builds, 4 failed (warnings fixed), 0 ok:false
- Started from `--from shaft`, rewrote drawing.py for pump shaft (M16 thread cls 6g, groove 3x Ø13, Ø20k6 x2, Ø26, Ø18k6 + keyway, A2.5 centre holes, removed section B, detail I).
- Findings fixed: param_cover tg/dg (added detail I with det.dim.linear gw/gh as the example does); overlap D.d4/G.rg; D.d5/R.j2; DT.B/R.j2; R.j1/R.j2 (ended by explicit `at=` on gtol/rough).
- Final: ok, errors 0, 0 warnings.

## R1 螺纹改成细牙 M16×1.5 — edit e2 + fix e3 (1 extra)
- drawing.py: `THREAD="M16x1.5"`; build -m ok but new overlap D.d1/R.j1 (longer text); fixed with edit `d["R.j1"].place(at=0.75)`. => 2 commits for the round.
## R2 跳动 0.015 + 垂直度 0.02 — edits e4..e11 (8 commits, 7 extra)
- script: `d["G.rg"].set(value=0.015)`; `face=d.q.lines(view="front").where(dir="v").near(61,11.5).one(); front.gtol("perp","perpendicularity",0.02,datums=["A-B"],ref=face)`.
- Layout of the new frame was very hard: default frame lands across the body (overlap). Tried at/length/move/D.d5 move for 7 more edits; each ok:true with new warnings (layout never fails the edit). Final: frame below right bearing + `d.accept("overlap","G.perp",...)` for l4 extension line crossing.
## R3 右轴承位加长 10 (146) — build e12, ok, 1 warning left (D.kd/D.gh overlap: section B moved into detail I); fixed in R4.
- drawing.py: `L 136->146`, `l4 35->45`.
## R4 断面图挪到键槽正下方 — e13..e15 (3 commits)
- Section was already centred under keyway (x=280.83 sheet) but overlapped detail; script `V.B.place(at=(280.83,112))`, `V.front.move(dy=40)` (needed: section fell into tech-notes area -> out_of_frame), `V.I.move(dx=30)`. Final 0 warnings.

## Skill/harness issues
- `lcad edit/build` returns ok:true and commits even with new warnings, so "one commit per round" conflicts with "fix warnings" (round 2 = 8 commits). No dry-run/preview of warnings before commit.
- No way to place a gtol frame sensibly: `place(at,length)` semantics (length sign = side, at= position along edge, frame y fixed at face end) undocumented; no auto avoidance of body/dim lines for frames on shoulder faces.
- Moving a dimension (D.d5) drags the datum symbol attached to it (DT.B) silently.
- `place(at=)` of a view takes sheet coordinates; moving auto-laid group changes where the front view sits (view origin of front shifts when the section is placed) — had to move front too.
- `res.thread` coarse default; thread dim text for M16×1.5-6g is rotated and overlaps rough symbols easily.
- SKILL: bore points cannot take names (ValueError "too many values to unpack") not stated.
