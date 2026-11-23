"""Small mutation operators for expect.py (E3): delete a required dimension, change a fit.

The E2 mutation framework proves R-rules can be broken; this module does the same for the
declarative contracts: build a reference drawing, evaluate its expect.py, inject one defect into
a *copy* of the semantic model, and check that the expect evaluator catches it.

    uv run python evals/expect_mutation.py [--out expect-mutation-report.json]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from linercad import expect  # noqa: E402


def _clone(d):
    return copy.deepcopy(d)


def _fit_dims(d):
    return [
        e
        for e in d._els.values()
        if e.kind == "dim" and (e._intent.get("tolerance") or {}).get("kind") == "fit"
    ]


def find_mutations(result, d, mod):
    """Which reference dimensions/features can this expect.py be broken against?"""
    refs = [i for i in (result.get("referenced_dims") or []) if i in d._els]
    fits = [e.id for e in _fit_dims(d)]
    one_dup = None
    for req in result.get("dim_requirements") or ():
        sig = req.get("signature") or ()
        side = sig[3] if len(sig) > 3 else None
        if side is None:
            continue
        did = req.get("matched")
        el = d._els.get(did)
        if el is None:
            continue
        vals = [v for v in (el._intent.get("value"), el._intent.get("measured")) if v is not None]
        peers = [
            e.id
            for e in d._els.values()
            if e.kind == "dim"
            and e.id != did
            and any(
                abs(v - w) <= 0.01
                for v in (e._intent.get("value"), e._intent.get("measured"))
                if v is not None
                for w in vals
            )
        ]
        if peers:
            one_dup = did
            break
    return {
        "delete_dim": refs[0] if refs else None,
        "change_fit": fits[0] if fits else None,
        "delete_one_duplicate": one_dup,
    }


def mutate_delete_dim(d, dim_id):
    """Remove the dimension cover for one requirement (all dims that offer the same value)."""
    out = _clone(d)
    el = out._els.get(dim_id)
    vals = []
    if el is not None:
        i = el._intent
        vals = [v for v in (i.get("value"), i.get("measured")) if v is not None]
    if vals:
        for eid, e in list(out._els.items()):
            if e.kind != "dim":
                continue
            iv = [v for v in (e._intent.get("value"), e._intent.get("measured")) if v is not None]
            if any(abs(v - w) <= 0.01 for v in iv for w in vals):
                out._els.pop(eid, None)
    else:
        out._els.pop(dim_id, None)
    return out


def mutate_delete_one_duplicate(d, dim_id):
    """Delete only one member of a duplicated feature (the single-feature mutation)."""
    out = _clone(d)
    out._els.pop(dim_id, None)
    return out


def mutate_change_fit(d, fit_id, code=None):
    """Change every fit designation to a code different from the chosen reference fit."""
    out = _clone(d)
    if code is None:
        el = out._els.get(fit_id)
        cur = str(((el._intent.get("tolerance") or {}).get("code")) if el is not None else "H7")
        code = "H8" if cur.upper() != "H8" else "H7"
    for e in out._els.values():
        if e.kind != "dim":
            continue
        tol = e._intent.get("tolerance")
        if isinstance(tol, dict) and tol.get("kind") == "fit":
            tol["code"] = code
            e._intent["tol"] = code
    return out


def run_case(mod, d):
    """Apply the independent operators to one drawing; report detection per operator."""
    base = expect.evaluate(mod, d)
    where = find_mutations(base, d, mod)
    outcomes = {}
    if where["delete_dim"]:
        res = expect.evaluate(mod, mutate_delete_dim(d, where["delete_dim"]))
        outcomes["delete_dim"] = {"caught": bool(res["violations"]), "why": where["delete_dim"]}
    if where["change_fit"]:
        res = expect.evaluate(mod, mutate_change_fit(d, where["change_fit"]))
        outcomes["change_fit"] = {"caught": bool(res["violations"]), "why": where["change_fit"]}
    if where["delete_one_duplicate"]:
        res = expect.evaluate(mod, mutate_delete_one_duplicate(d, where["delete_one_duplicate"]))
        outcomes["delete_one_duplicate"] = {
            "caught": bool(res["violations"]),
            "why": where["delete_one_duplicate"],
        }
    caught = sum(1 for v in outcomes.values() if v["caught"])
    return {
        "base_pass": base["pass"],
        "mutations": len(outcomes),
        "detected": caught,
        "detection_rate": round(caught / len(outcomes), 4) if outcomes else None,
        "outcomes": outcomes,
    }


def _build_case(case):
    import shutil
    import tempfile

    from linercad.runtime import build

    work = Path(tempfile.mkdtemp())
    try:
        (work / "drawing.py").write_text(case["drawing_src"], encoding="utf-8")
        for f in Path(case["dir"]).iterdir():
            if f.is_file() and f.suffix in (".py", ".step", ".stp") and f.name != "drawing.py":
                shutil.copy2(f, work / f.name)
        return build(work).d
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_report():
    import run as evals

    rows = []
    for case in evals.discover(level="L2"):
        mod = Path(case["dir"]) / "expect.py"
        if not mod.exists():
            rows.append({"case": case["id"], "error": "no expect.py"})
            continue
        d = _build_case(case)
        out = run_case(mod, d)
        out["case"] = case["id"]
        rows.append(out)
    cases = [r for r in rows if "error" not in r]
    unmet = [r for r in cases if not r["base_pass"]]
    mutations = sum(r["mutations"] for r in cases)
    detected = sum(r["detected"] for r in cases)
    return {
        "cases": len(rows),
        "reference_pass": len(cases) - len(unmet),
        "reference_pass_rate": round((len(cases) - len(unmet)) / len(cases), 4) if cases else None,
        "mutations": mutations,
        "detected": detected,
        "detection_rate": round(detected / mutations, 4) if mutations else None,
        "rows": rows,
    }


def markdown(report):
    lines = [
        "# L2 expect 变异报告（E3）",
        "",
        "命令：uv run python evals/expect_mutation.py --out <file>",
        "",
        "| 用例 | expect 通过 | 变异 | 检出 | 检出率 |",
        "|---|---|---|---|---|",
    ]
    for r in report["rows"]:
        if "error" in r:
            lines.append("| " + r["case"] + " | err | — | — | " + r["error"] + " |")
            continue
        lines.append(
            "| "
            + r["case"]
            + " | "
            + ("是" if r["base_pass"] else "否")
            + " | "
            + str(r["mutations"])
            + " | "
            + str(r["detected"])
            + " | "
            + (f"{r['detection_rate']:.0%}" if r["detection_rate"] is not None else "—")
            + " |"
        )
    lines += [
        "",
        f"- 参考图 expect 通过：{report['reference_pass']}/{report['cases']}",
        f"- 变异检出：{report['detected']}/{report['mutations']}（{report['detection_rate']:.0%}）",
        "",
        "变异算子：删除一个必需尺寸的全部覆盖（同一值的所有尺寸）；把配合代号改错（整图 fit 统一改成不同的代号）。",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    rep = run_report()
    text = markdown(rep)
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8", newline="\n")
    if a.json:
        Path(a.json).write_text(
            json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
    return 0 if (rep["detection_rate"] == 1.0 and rep["reference_pass"] == rep["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
