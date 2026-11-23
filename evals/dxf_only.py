"""E6: DXF-only score vector for arbitrary DXF files (issue #80).

    uv run python evals/dxf_only.py --sample-dir <dir> --m3 tests/data/dxf/sample_part.dxf --out docs/milestones/v0.1.1/evidence/dxf-only-metrics.md

The ruler uses rendered DXF entities only (see linercad/dxfonly.py); it does not import the file
into the semantic model and does not replace the C1 ruler in evals/dxf_import.py (that one judges
the importer's output with a different scope).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from linercad import dxfonly  # noqa: E402


def _points(reports, family):
    opp = sum(r.get("families", {}).get(family, {}).get("opportunities", 0) for r in reports)
    vio = sum(r.get("families", {}).get(family, {}).get("violations", 0) for r in reports)
    score = round(max(0.0, 1.0 - vio / opp), 6) if opp else None
    return opp, vio, score


def markdown(reports) -> str:
    lines = [
        "# 仅 DXF 模式分数（E6）",
        "",
        "命令（样例目录不进仓库；M3 基线用仓库内基线图）：",
        "",
        "    uv run python evals/dxf_only.py --sample-dir <4 个用户样例所在目录> "
        "--m3 tests/data/dxf/sample_part.dxf --out <this file>",
        "",
        "口径：只看 DXF 图元（LINE/ARC/CIRCLE/LWPOLYLINE/TEXT/DIMENSION/HATCH …），"
        "不经过导入器、不读语义模型的 intent；与 C1 尺子（evals/dxf_import.py）并存、互不替代。",
        "",
        "## 可判规则（进入向量）",
        "",
        "| 规则 | 族 | benchmark 条目 | 判据 |",
        "|---|---|---|---|",
    ]
    for rid, info in dxfonly.RULE_TABLE.items():
        lines.append(f"| {rid} | {info['family']} | {info['basis']} | {info['description']} |")
    lines += [
        "",
        "## 不可判（依赖 intent / 语义模型，只列出不评分）",
        "",
        "| 规则 | 族 | 原因 |",
        "|---|---|---|",
    ]
    for u in dxfonly.unavailable_rules():
        lines.append(f"| {u['rule']} | {u['family']} | {u['reason']} |")
    lines += [
        "",
        "## 4 个用户样例 DXF + M3 基线图",
        "",
        "| 文件 | G | D | T | A | 规则违规/机会 | 说明 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        if not r.get("ok"):
            lines.append(f"| {r.get('file')} | — | — | — | — | — | {r.get('error')} |")
            continue
        fam = r["families"]
        rules = "; ".join(
            f"{rid} {v['violations']}/{v['opportunities']}" for rid, v in r["rules"].items()
        )
        note = r["rules"].get("dxf_out_of_frame", {}).get("note", "")
        lines.append(
            f"| {r['file']} | {fam['G']['score']} | {fam['D']['score']} | "
            f"{fam['T']['score']} | {fam['A']['score']} | {rules} | {note} |"
        )
    g = _points(reports, "G")
    d = _points(reports, "D")
    lines += [
        "",
        "### 汇总（按机会数加权）",
        "",
        f"- G（G.layout + G.conv 可判部分）：**{g[2]}**（{g[1]}/{g[0]} 违规/机会）",
        f"- D（D.place 可判部分）：**{d[2]}**（{d[1]}/{d[0]} 违规/机会）",
        "- T / A / P：不可判（见上表）",
        "",
        "## 说明与局限",
        "",
        "- 文字外框按 DXF 的字高/MTEXT 宽度/附件点近似；文字-文字重叠用 IoU>0.1 判"
        "（小于此的贴边/包含不算），不与 C1 的导入器口径混用。",
        "- 图框从图元本身探测（最大的轴对齐闭合矩形，且面积 >= 图面 bbox 的 50%）；"
        "探测不到时 dxf_out_of_frame 不适用（记为 0 机会，不扣分）。",
        "- DIMENSION 文字缺失、箭头检查只看 DXF 可读属性/几何块；半径/直径尺寸允许单箭头。",
        "- 标题栏模板语义、视图归属、形位公差/装配/过程指标都不可判，明确列在不可判表。",
        "- M3 基线图 = tests/data/dxf/sample_part.dxf（M3 验收用的 ezdxf 原生尺寸基线图例；"
        "不是用户样例，可随仓库分发）。",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample-dir", default=None, help="directory with the 4 user sample DXFs")
    ap.add_argument("--m3", default=str(ROOT / "tests" / "data" / "dxf" / "sample_part.dxf"))
    ap.add_argument("--out", default=None, help="write the markdown report to this file")
    ap.add_argument("--json-out", default=None, help="write the raw JSON reports to this file")
    a = ap.parse_args(argv)
    files = []
    if a.sample_dir:
        files += sorted(Path(a.sample_dir).glob("*.dxf"))
    if a.m3:
        files.append(Path(a.m3))
    reports = [dxfonly.score_file(p) for p in files]
    md = markdown(reports)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md + "\n", encoding="utf-8")
    if a.json_out:
        Path(a.json_out).write_text(
            json.dumps({"mode": "dxf-only", "reports": reports}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
