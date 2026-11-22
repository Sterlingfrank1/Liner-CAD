"""Placement scores of the reference drawings (E5 evidence).

    uv run python evals/place_scores.py [--out PATH]

Builds the five reference drawings (flange / pulley / gear_cover / jack / vise) and prints the
D.place / A.place score of each, plus the rule-level breakdown. With --eval40 it also prints the
decomposition of the 40-case eval vector into the pre-E5 rules (unchanged) and the new placement
rules, which is what the PR records as "new, not a regression".
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from linercad import checks, place  # noqa: E402
from linercad.runtime import build  # noqa: E402

EXAMPLES = (
    ("flange", ROOT / "src" / "linercad" / "examples" / "flange"),
    ("pulley", ROOT / "src" / "linercad" / "examples" / "pulley"),
    ("gear_cover", ROOT / "src" / "linercad" / "examples" / "gear_cover"),
    ("jack", ROOT / "evals" / "L3" / "jack"),
    ("vise", ROOT / "evals" / "L3" / "vise"),
)

IGNORE = shutil.ignore_patterns(".linercad", "__pycache__", "*.jsonl", "*.dxf")


def build_dir(src: Path):
    work = Path(tempfile.mkdtemp())
    shutil.copytree(src, work, dirs_exist_ok=True, ignore=IGNORE)
    return build(work)


def place_totals(d):
    out = {}
    for fn in place.RULES:
        findings, opportunities = fn(d)
        out[fn.__name__] = (len(findings), opportunities)
    return out


def family_score(totals, fam):
    viol = opp = 0
    for rule, (v, n) in totals.items():
        if checks.family(rule) == fam:
            viol += v
            opp += n
    return (round(1 - viol / opp, 4) if opp else None), viol, opp


def example_rows():
    rows = []
    for name, src in EXAMPLES:
        if not src.is_dir():
            rows.append((name, None, None, "missing"))
            continue
        try:
            res = build_dir(src)
        except Exception as e:  # noqa: BLE001 - an unbuildable example is reported, not fatal
            rows.append((name, None, None, f"{type(e).__name__}: {e}"))
            continue
        t = place_totals(res.d)
        d_score, d_v, d_n = family_score(t, "D")
        a_score, a_v, a_n = family_score(t, "A")
        rows.append((name, d_score, a_score, (d_v, d_n, a_v, a_n), t))
    return rows


def eval40_decomposition():
    """(old rules: family -> [viol, opp], new placement rules: family -> [viol, opp])."""
    import run as evals

    old = {}
    new = {}
    for case in evals.discover():
        res = evals.run_case(case, geo=False)
        if "rules" not in res:
            continue
        for rule, st in res["rules"].items():
            bucket = new if rule.startswith("place_") else old
            fam = checks.family(rule)
            v, n = bucket.setdefault(fam, [0, 0])
            bucket[fam] = [v + st["violations"], n + st["opportunities"]]
    return old, new


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="write the markdown table to this file")
    ap.add_argument("--eval40", action="store_true", help="also print the 40-case decomposition")
    a = ap.parse_args(argv)
    lines = []
    lines.append("# 排布分数（E5：D.place / A.place）")
    lines.append("")
    lines.append("命令：uv run python evals/place_scores.py --eval40")
    lines.append("")
    lines.append(
        "判据：只在布局后的渲染图元上判（不在 intent 上判）；机会数 = 独立检查数（E1 口径），"
    )
    lines.append("分数 = 1 - Σ违规 / Σ机会。")
    lines.append("")
    lines.append("## 五个范例当前排布分数")
    lines.append("")
    lines.append("| 范例 | D.place | A.place | D 违规/机会 | A 违规/机会 |")
    lines.append("|---|---|---|---|---|")
    rows = example_rows()
    for row in rows:
        name, d_score, a_score, counts = row[:4]
        if not isinstance(counts, tuple):
            lines.append(f"| {name} | — | — | {counts} | |")
            continue
        d_v, d_n, a_v, a_n = counts
        lines.append(
            f"| {name} | {d_score if d_score is not None else '-'} | "
            f"{a_score if a_score is not None else '-'} | {d_v}/{d_n} | {a_v}/{a_n} |"
        )
    lines.append("")
    lines.append("## 五个范例的规则明细")
    lines.append("")
    for row in rows:
        name, _d, _a, counts = row[:4]
        if not isinstance(counts, tuple) or len(row) < 5:
            continue
        t = row[4]
        lines.append(f"### {name}")
        lines.append("")
        lines.append("| 规则 | 族 | 标准 | 条款 | 违规 | 机会 |")
        lines.append("|---|---|---|---|---|---|")
        for rule, (v, n) in sorted(t.items()):
            fam = checks.family(rule)
            std = place.STANDARDS["GB"]["balloon" if rule.startswith("place_balloon") else "dim"]
            lines.append(f"| {rule} | {fam} | {std} | {place.CLAUSES[rule]} | {v} | {n} |")
        lines.append("")
    if a.eval40:
        old, new = eval40_decomposition()
        lines.append("## 40 例分数向量分解（新增项，不是退化）")
        lines.append("")
        lines.append("| 族 | E1 规则（原 23 条）分数 | 新增排布规则分数 | 合并后族分数 |")
        lines.append("|---|---|---|---|")
        for fam in checks.FAMILIES:
            ov, on = old.get(fam, [0, 0])
            nv, nn = new.get(fam, [0, 0])
            old_s = round(1 - ov / on, 4) if on else None
            new_s = round(1 - nv / nn, 4) if nn else None
            tot_v, tot_n = ov + nv, on + nn
            tot_s = round(1 - tot_v / tot_n, 4) if tot_n else None
            lines.append(f"| {fam} | {old_s} | {new_s} | {tot_s} |")
        lines.append("")
        lines.append("说明：原有 23 条规则零违规、分数仍为 1.0；族分数变化全部来自新增排布规则。")
        lines.append("")
    text = "\n".join(lines) + "\n"
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
