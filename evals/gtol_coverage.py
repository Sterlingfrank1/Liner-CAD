"""E4: GB/T 1182-2018 clause coverage of the T.syntax / T.target / T.hier rules.

    uv run python evals/gtol_coverage.py --out docs/milestones/v0.1.1/evidence/gtol-coverage.md

Coverage is read from the A4 data (res/gtol.toml, 19 table-1 rows with their subclauses) and the
E2 catalog: a row counts as covered when all three rules have data for it (datum rule, zone
shapes, modifiers, Phi; target kinds/natures; category for hierarchy). Clauses the A4 resource
itself marks unread are not invented here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from linercad import catalog, res  # noqa: E402

RULE_IDS = ("gtol_syntax", "gtol_target", "gtol_hier")


def report() -> dict:
    rows = res.gtol_rows()
    catalog_rules = {e["id"]: e for e in catalog.load()["rule"]}
    per_row = []
    clause_refs = set()
    for row in rows:
        refs = list(row.get("clause_refs", ()))
        clause_refs.update(refs)
        per_row.append(
            {
                "id": row["id"],
                "char": row["char"],
                "clause": row["clause"],
                "clause_refs": refs,
                "syntax": bool(row.get("datum") and row.get("zone_shapes")),
                "target": bool(row.get("targets") and row.get("target_natures")),
                "hier": bool(row.get("category")),
            }
        )
    covered = sum(1 for r in per_row if r["syntax"] and r["target"] and r["hier"])
    meta = res._table("gtol")["meta"]
    return {
        "std": "GB/T 1182-2018",
        "verified": bool(meta.get("verified", False)),
        "rows": len(per_row),
        "rows_covered": covered,
        "row_rate": round(covered / len(per_row), 4) if per_row else None,
        "clause_refs": sorted(clause_refs),
        "clause_ref_count": len(clause_refs),
        "table1_clauses": sorted({r["clause"] for r in per_row}),
        "per_row": per_row,
        "rules": {rid: catalog_rules.get(rid) for rid in RULE_IDS},
        "catalog_t_rules": {
            rid: {
                "clause": e.get("clause"),
                "clause_status": e.get("clause_status"),
                "status": e.get("status"),
            }
            for rid, e in catalog_rules.items()
            if e.get("family") == "T" or e.get("pack") == "tolerancing"
        },
    }


def markdown(rep) -> str:
    lines = [
        "# GB/T 1182-2018 形位公差条款覆盖率（E4）",
        "",
        "命令：uv run python evals/gtol_coverage.py --out <this file>",
        "",
        "- 数据源：src/linercad/res/gtol.toml（A4；自记 verified="
        + str(rep["verified"])
        + "，只读到一份 PDF 谱系）",
        "- 表1 行覆盖率：**"
        + str(rep["rows_covered"])
        + "/"
        + str(rep["rows"])
        + " = "
        + f"{rep['row_rate']:.0%}"
        + "**",
        "- 表1 子条款号："
        + str(len(rep["table1_clauses"]))
        + " 个（"
        + "、".join(rep["table1_clauses"])
        + "）",
        "- clause_refs："
        + str(rep["clause_ref_count"])
        + " 个（"
        + "、".join(rep["clause_refs"])
        + "）",
        "",
        "## 三条规则与 catalog 条款",
        "",
        "| 规则 | benchmark | 条款（catalog） | 条款状态 | 规则状态 |",
        "|---|---|---|---|---|",
    ]
    for rid in RULE_IDS:
        e = rep["rules"].get(rid) or {}
        bench = {"gtol_syntax": "T.syntax", "gtol_target": "T.target", "gtol_hier": "T.hier"}[rid]
        lines.append(
            "| "
            + rid
            + " | "
            + bench
            + " | "
            + str(e.get("clause", "—"))
            + " | "
            + str(e.get("clause_status", "—"))
            + " | "
            + str(e.get("status", "—"))
            + " |"
        )
    lines += [
        "",
        "## 表1 逐行覆盖（19 行）",
        "",
        "| 行 | 特征项目 | 表1 子条款 | T.syntax 数据 | T.target 数据 | T.hier 类别 |",
        "|---|---|---|---|---|---|",
    ]
    for r in rep["per_row"]:
        lines.append(
            "| "
            + r["id"]
            + " | "
            + r["char"]
            + " | "
            + r["clause"]
            + " | "
            + ("是" if r["syntax"] else "否")
            + " | "
            + ("是" if r["target"] else "否")
            + " | "
            + ("是" if r["hier"] else "否")
            + " |"
        )
    lines += [
        "",
        "## 说明",
        "",
        "- T.syntax 按行数据判：基准有无（datum）、公差带形状（zone_shapes）、修饰符（modifiers / modifier_conditions）、轴线 + 圆柱带的 Φ、基准引用已定义；",
        "- T.target 按行数据判：被测要素 targets / target_natures（形状类要素进一步按引用几何约束），基准 target 字段与引用几何一致；",
        "- T.hier 按行 category 判形状/方向/位置/跳动递进；尺寸公差与形位公差的比较只取可比口径（配合偏差仅在形状公差时比较，显式偏差公差全类别比较），GB/T 4249-2018 原文未读，catalog 条款状态为 pending；",
        "- 未读条款（A4 meta.unread：1182 第9章、17851 部分、17852 规则 D-H 等）不在本报告声称覆盖；M/L/R/F 等来自未读标准的修饰符按 modifiers_unverified 报为不可判。",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    rep = report()
    text = markdown(rep)
    print(
        json.dumps(
            {k: rep[k] for k in ("rows", "rows_covered", "row_rate", "clause_ref_count")},
            ensure_ascii=False,
        )
    )
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8", newline="\n")
    if a.json:
        Path(a.json).write_text(
            json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
