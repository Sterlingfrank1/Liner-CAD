# disc__gear_blank (final: errors 0, warnings 0; commits e1..e5)

## Initial ("按需求出图", e1) — 3 builds: 1 ok:false (E.left.lh_pcd not found; PCD circle is `C.left.lh`), 1 with 3 findings (missing axial step x=28.5 -> added chamfer dim ch2; param_cover pl/dl -> `value=P.dl` on hole dim), then clean.
- From `--from pulley`: turned(cut="half", hub_keyway=True, holes=[lh]) + left view holes_on_circle(6) + keyway_end + section A. Ambiguity: hub placed on the right (left view = disc face).
## R1 孔改成 Φ35 H7 — `d0=Param(35)`; build e2 ok, 0 warn. Keyway followed automatically (10JS9, 38.3 +0.2/0), 1 attempt.
## R2 跳动 0.025 + 右端面端面跳动 0.03 — script: `d["G.run"].set(value=0.025)`; `face=d.q.lines(view="front").where(dir="v").near(45,24).one(); front.gtol("end","circular_runout",0.03,datums=["A"],ref=face)`; e3 ok, 0 warn, 1 attempt. ("右端面" read as the hub end face x=45; "端面圆跳动" = circular_runout on a face — no separate axial-runout char.)
## R3 减轻孔 6×Φ18 — `dl=Param(18)`; e4 ok 0 warn.
## R4 加技术要求 — script `d.notes.tech("去除毛刺锐边。")`; e5 ok 0 warn.

## Issues
- Hole dimension in end view needs `circle=E.left.<name>.1` and PCD circle id `C.left.<name>` (centre circle) — not documented in SKILL; ID found via not_found candidates / context.
- hub_keyway=True keyway depth/width are right but `lcad context` only works after a successful build (can't list IDs while build fails).
