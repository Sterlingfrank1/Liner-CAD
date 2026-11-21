"""Evaluation runner (SPEC M1 §8): builds every L1 / L2 case, runs the checks and the geometry
comparison, writes report.json. Adding a case means adding files, never code.

    uv run python evals/run.py [--level L1|L2] [--case ID] [--drawings DIR] [--out report.json]
    uv run python evals/run.py --baseline evals/baseline.json   # nonzero exit on regression
    uv run python evals/run.py --save-baseline evals/baseline.json

The summary carries a score vector: G / D / T / A, each 1 - violations / opportunities weighted by
the number of objects the rules examined (docs/proposals/benchmark-metrics.md section 3.6); P
(process: stale_op plus the round metrics) is listed apart. --baseline compares the run with a
committed vector and exits nonzero when a family score drops or the error count grows (E1).

A case whose case.toml says ``source = "3d"`` (drawing projects model.py) is checked with
completeness.py (required dimensions inferred from the model, missing ones listed) instead of
geocmp.

``--drawings DIR`` evaluates drawings made by an agent instead of the reference ones: DIR/<case
id with / replaced by __>/drawing.py (a lcad drawing directory; its git history gives the rounds).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import completeness  # noqa: E402
import geocmp  # noqa: E402

from linercad.checks import FAMILIES, family  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover(level=None, case=None):
    """[{id, level, family, dir?, template?, params?, views, drawing_src, model()}]"""
    out = []
    if level in (None, "L1"):
        cases = tomllib.loads((HERE / "L1" / "cases.toml").read_text(encoding="utf-8"))
        for c in cases.get("case", []):
            tpl = _load(HERE / "L1" / "templates" / f"{c['template']}.py", f"l1_{c['template']}")
            params = c.get("params", {})
            out.append(
                {
                    "id": f"L1/{c['id']}",
                    "level": "L1",
                    "family": c["template"],
                    "drawing_src": tpl.drawing(**params),
                    "model": (lambda tpl=tpl, params=params: tpl.model(**params))
                    if hasattr(tpl, "model")
                    else None,
                    "views": getattr(tpl, "VIEWS", [{"name": "front", "mode": "plain"}]),
                }
            )
    if level in (None, "L2"):
        for cfile in sorted((HERE / "L2").glob("*/*/case.toml")):
            d = cfile.parent
            meta = tomllib.loads(cfile.read_text(encoding="utf-8"))
            mp = d / "model.py"
            out.append(
                {
                    "id": f"L2/{d.parent.name}/{d.name}",
                    "level": "L2",
                    "family": d.parent.name,
                    "dir": d,
                    "drawing_src": (d / "drawing.py").read_text(encoding="utf-8"),
                    "model": (lambda mp=mp: _load(mp, f"m_{mp.parent.name}").model())
                    if mp.exists()
                    else None,
                    "views": meta.get("view", [{"name": "front", "mode": "plain"}]),
                    "title": meta.get("title"),
                    "source": meta.get("source"),
                }
            )
    if case:
        out = [c for c in out if c["id"] == case or c["id"].endswith("/" + case)]
    return out


def has_3d():
    return importlib.util.find_spec("build123d") is not None


def project(shape, view, hidden=False):
    """``hlr.project`` with the smooth (tangent) edges split off into ``"smooth"``: a drawing
    leaves a tangent junction out or draws it thin (GB/T 4458.1), so those edges may match a
    drawn edge but a missing one does not lower the model coverage (casting / slot outlines)."""
    from OCP.BRepLib import BRepLib

    from linercad import hlr

    BRepLib.EncodeRegularity_s(shape.wrapped)  # booleans (cuts) drop the tangency flags HLR needs
    out = {"visible": [], "smooth": []}
    if hidden:
        out["hidden"] = []
    for cls, vis, e in hlr.project_classes(shape, view, hidden):
        out["smooth" if cls == "smooth" else ("visible" if vis else "hidden")].append(
            hlr._sample(e)
        )
    return out


def geometry(d, case):
    """Compare every listed view (and every removed section) with the model's projection."""
    from linercad import hlr

    shape = case["model"]()
    res = {}
    for v in case["views"]:
        name, mode = v["name"], v.get("mode", "plain")
        if mode == "plain":
            proj = project(shape, name, hidden=bool(v.get("hidden")))
        else:
            cut = hlr.section(shape, name, mode, v.get("half", "top"))
            proj = project(cut, name, hidden=bool(v.get("hidden")))
            if mode == "half":  # the median of a half section is the centre line, not an edge
                proj = {
                    k: [pl for pl in pls if any(abs(p[1]) > 1e-6 for p in pl)]
                    for k, pls in proj.items()
                }
        roles = ("thick", "hidden") if v.get("hidden") else ("thick",)
        res[name] = geocmp.compare(d, name, proj, roles)
    for s in d._els.values():
        if s.kind == "section" and s._intent.get("kind") == "removed":
            view = d[f"V.{s._intent['view']}"]
            proj = hlr.slice_view(
                shape, s._intent["cut_in"], view._intent["trace"], view._intent["axes"]
            )
            res[view.name] = geocmp.compare(d, view.name, proj)
    return res


def _rounds(ddir):
    try:
        out = subprocess.run(
            ["git", "-C", str(ddir), "log", "--format=%s"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    subjects = [s for s in out.stdout.splitlines() if s.strip()]
    return max(0, len(subjects) - 1)  # minus the init commit


def run_case(case, drawings=None, geo=True):
    from linercad.runtime import build

    r = {"id": case["id"], "level": case["level"], "family": case["family"]}
    src_dir = None
    if drawings is not None:
        src_dir = Path(drawings) / case["id"].split("/", 1)[1].replace("/", "__")
        if not (src_dir / "drawing.py").exists():
            r.update(error="no agent drawing", passed=False)
            return r
        r["rounds"] = _rounds(src_dir)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if src_dir is not None:
            shutil.copytree(
                src_dir,
                work,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git", ".linercad"),
            )
        else:
            (work / "drawing.py").write_text(case["drawing_src"], encoding="utf-8")
            if case.get("source") == "3d" and case.get("dir"):  # d.model("model.py") reads it
                for f in case["dir"].iterdir():
                    if (
                        f.is_file()
                        and f.suffix in (".py", ".step", ".stp")
                        and f.name != "drawing.py"
                    ):
                        shutil.copy2(f, work / f.name)
        try:
            res = build(work)
        except Exception as e:  # noqa: BLE001 - a broken case is a result, not a crash
            r.update(error=f"{type(e).__name__}: {e}", passed=False)
            return r
        errors = [f for f in res.findings if f.get("severity") == "error"]
        r["errors"] = len(errors)
        r["warnings"] = len(res.findings) - len(errors)
        opps = dict(getattr(res.findings, "opportunities", {}))
        violations = {}
        for f in res.findings:
            violations[f["rule"]] = violations.get(f["rule"], 0) + 1
        r["rules"] = {
            rule: {"opportunities": opps.get(rule, 0), "violations": violations.get(rule, 0)}
            for rule in sorted(set(opps) | set(violations))
        }
        r["findings"] = [
            {k: f.get(k) for k in ("rule", "id", "severity", "message")} for f in res.findings
        ]
        if geo and case.get("model") and has_3d():
            if (
                case.get("source") == "3d"
            ):  # the drawing is the model's projection: check what it says
                r["completeness"] = completeness.compare(res.d, case["model"]())
                r["missing"] = [m["name"] for m in r["completeness"]["missing"]]
            else:
                r["geo"] = geometry(res.d, case)
        ok_geo = all(v["pass"] for v in r.get("geo", {}).values())
        ok_cmp = r.get("completeness", {}).get("pass", True)
        r["passed"] = not errors and ok_geo and ok_cmp
    return r


def rule_totals(results):
    """{rule: {opportunities, violations}} over every case (a rule repeats across cases)."""
    out = {}
    for r in results:
        for rule, st in (r.get("rules") or {}).items():
            t = out.setdefault(rule, {"opportunities": 0, "violations": 0})
            t["opportunities"] += int(st.get("opportunities") or 0)
            t["violations"] += int(st.get("violations") or 0)
    return out


def family_scores(results):
    """({family: {score, opportunities, violations, rules}}, {rule: totals} for P).

    score = 1 - violations / opportunities, weighted by the objects each rule examined; a family
    with no opportunities is None (nothing to score, e.g. A before assembly rules exist). P is not
    part of the vector: it holds the process rules (stale_op) plus the round metrics.
    """
    totals = rule_totals(results)
    fams = {f: {"score": None, "opportunities": 0, "violations": 0, "rules": {}} for f in FAMILIES}
    proc = {}
    for rule, t in sorted(totals.items()):
        fam = family(rule)
        if fam == "P":
            proc[rule] = t
            continue
        bucket = fams[fam]
        bucket["opportunities"] += t["opportunities"]
        bucket["violations"] += t["violations"]
        bucket["rules"][rule] = t
    for bucket in fams.values():
        if bucket["opportunities"]:
            bucket["score"] = round(
                max(0.0, 1.0 - bucket["violations"] / bucket["opportunities"]), 6
            )
    return fams, proc


def summary(results):
    n = len(results)
    built = [r for r in results if "errors" in r]
    geo = [r for r in results if r.get("geo")]
    cmp = [r for r in results if r.get("completeness")]
    rounds = [r["rounds"] for r in results if r.get("rounds") is not None]
    fams, proc = family_scores(results)
    first_pass = (
        round(sum(1 for r in results if r.get("rounds") == 0 and r.get("passed")) / len(rounds), 4)
        if rounds
        else None
    )
    mean_rounds = round(sum(rounds) / len(rounds), 2) if rounds else None
    return {
        "cases": n,
        "built": len(built),
        "geometry_cases": len(geo),
        "completeness_cases": len(cmp),
        "zero_error_rate": round(sum(1 for r in built if r["errors"] == 0) / n, 4) if n else 0,
        "geometry_pass_rate": round(
            sum(1 for r in geo if all(v["pass"] for v in r["geo"].values())) / len(geo), 4
        )
        if geo
        else None,
        "completeness_pass_rate": round(
            sum(1 for r in cmp if r["completeness"]["pass"]) / len(cmp), 4
        )
        if cmp
        else None,
        "violations": sum(r.get("errors", 0) + r.get("warnings", 0) for r in results),
        "first_pass_rate": first_pass,
        "mean_rounds": mean_rounds,
        "passed": sum(1 for r in results if r.get("passed")),
        "families": fams,
        "P": {"first_pass_rate": first_pass, "mean_rounds": mean_rounds, "rules": proc},
    }


def case_errors(report):
    return sum(int(c.get("errors") or 0) for c in report["cases"])


def baseline_vector(report):
    """The committed baseline (evals/baseline.json): family scores, opportunities, pass rates."""
    s = report["summary"]
    return {
        "version": 1,
        "cases": s["cases"],
        "case_ids": sorted(c["id"] for c in report["cases"] if c.get("id")),
        "errors": case_errors(report),
        "zero_error_rate": s["zero_error_rate"],
        "geometry_pass_rate": s["geometry_pass_rate"],
        "geometry_cases": s["geometry_cases"],
        "completeness_pass_rate": s["completeness_pass_rate"],
        "completeness_cases": s["completeness_cases"],
        "families": {
            fam: {
                "score": v["score"],
                "opportunities": v["opportunities"],
                "violations": v["violations"],
            }
            for fam, v in s["families"].items()
        },
        "P": {
            "first_pass_rate": s["P"]["first_pass_rate"],
            "mean_rounds": s["P"]["mean_rounds"],
            "rules": {
                rule: {"opportunities": t["opportunities"], "violations": t["violations"]}
                for rule, t in s["P"]["rules"].items()
            },
        },
    }


def _is_int(value, low=0):
    """A real (non-bool) integer >= low."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= low


def _is_finite(value):
    """A real (non-bool) finite number."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _baseline_problems(base):
    """Fail-closed check that a committed baseline is usable: a hole here silences the gate."""
    out = []
    if not isinstance(base, dict):
        return ["baseline: not a JSON object"]
    if base.get("version") != 1:
        out.append(f"baseline: unsupported version {base.get('version')!r}")
    errors = base.get("errors")
    if not _is_int(errors):
        out.append("baseline: errors missing or negative")
    cases = base.get("cases")
    if not _is_int(cases, 1):
        out.append("baseline: cases missing or zero")
    ids = base.get("case_ids")
    if not isinstance(ids, list) or not ids:
        out.append("baseline: case_ids missing or empty")
    else:
        if len(set(ids)) != len(ids):
            out.append("baseline: case_ids has duplicates")
        if _is_int(cases) and len(ids) != cases:
            out.append("baseline: case_ids length does not match cases")
    fams = base.get("families")
    if not isinstance(fams, dict) or not fams:
        out.append("baseline: no families vector")
        fams = {}
    else:
        missing = [f for f in FAMILIES if f not in fams]
        if missing:
            out.append(f"baseline: families missing {missing}")
        extra = sorted(set(fams) - set(FAMILIES))
        if extra:
            out.append(f"baseline: unknown families {extra}")
    for fam, entry in fams.items():
        if not isinstance(entry, dict):
            out.append(f"baseline: family {fam} is not an object")
            continue
        score, opps, viol = entry.get("score"), entry.get("opportunities"), entry.get("violations")
        if not _is_int(opps):
            out.append(f"baseline: family {fam} opportunities missing or negative")
            opps = None
        if not _is_int(viol) or (opps is not None and viol > opps):
            out.append(f"baseline: family {fam} violations missing or outside [0, opportunities]")
            viol = None
        if score is None:
            if opps:
                out.append(f"baseline: family {fam} has opportunities but no score")
        elif not _is_finite(score):
            out.append(f"baseline: family {fam} score {score!r} is not a finite number")
        elif not 0.0 <= score <= 1.0:
            out.append(f"baseline: family {fam} score {score!r} is outside [0, 1]")
        elif opps == 0:
            out.append(f"baseline: family {fam} has a score but no opportunities")
        elif opps and viol is not None:
            expected = round(max(0.0, 1.0 - viol / opps), 6)
            if abs(score - expected) > 1e-6:
                out.append(
                    f"baseline: family {fam} score {score!r} does not match "
                    f"{viol}/{opps} = {expected}"
                )
    rate = base.get("zero_error_rate")
    if not _is_finite(rate) or not 0.0 <= rate <= 1.0:
        out.append(f"baseline: zero_error_rate {rate!r} is not a rate")
    proc = base.get("P")
    if not isinstance(proc, dict):
        out.append("baseline: P block missing")
    else:
        for key in ("first_pass_rate", "mean_rounds"):
            value = proc.get(key)
            if value is None:
                continue
            if not _is_finite(value) or value < 0 or (key == "first_pass_rate" and value > 1):
                out.append(f"baseline: P.{key} {value!r} is not usable")
        rules = proc.get("rules")
        if not isinstance(rules, dict):
            out.append("baseline: P.rules missing")
        else:
            for rule, st in rules.items():
                if not isinstance(st, dict):
                    out.append(f"baseline: P.rules.{rule} is not an object")
                    continue
                o, v = st.get("opportunities"), st.get("violations")
                if not _is_int(o) or not _is_int(v) or v > o:
                    out.append(f"baseline: P.rules.{rule} counters are not usable")
    for key, count_key in (
        ("geometry_pass_rate", "geometry_cases"),
        ("completeness_pass_rate", "completeness_cases"),
    ):
        if key not in base:
            out.append(f"baseline: {key} missing")
            continue
        value = base.get(key)
        count = base.get(count_key)
        if not _is_int(count, 1):
            out.append(f"baseline: {count_key} missing or zero")
            continue
        if value is None:
            out.append(f"baseline: {key} is null but {count} cases were compared")
        elif not _is_finite(value):
            out.append(f"baseline: {key} {value!r} is not a finite number")
        elif not 0.0 <= value <= 1.0:
            out.append(f"baseline: {key} {value!r} is outside [0, 1]")
    return out


def compare_baseline(report, base):
    """Regression messages of a run against base; an empty list means no regression.

    Fail-closed: an unusable baseline (unknown version, missing family / pass rate, null where the
    baseline compared cases, NaN) is itself a regression, so a broken vector cannot silence the gate.
    A regression is: more errors than the baseline, a scored family that dropped (or can no longer
    be scored), a geometry / completeness comparison that lost cases or dropped, or removed cases.
    Per-rule opportunities are not compared - adding a rule is not a regression.
    """
    s = report["summary"]
    out = _baseline_problems(base)
    if not isinstance(base, dict):  # unreadable file: the validation above already failed it
        return out
    fams = base.get("families") if isinstance(base.get("families"), dict) else {}
    errors = case_errors(report)
    if isinstance(base.get("errors"), int) and errors > base["errors"]:
        out.append(f"errors: {errors} > baseline {base['errors']}")
    for fam in FAMILIES:
        entry = fams.get(fam) or {}
        before = entry.get("score")
        if not isinstance(before, (int, float)) or not math.isfinite(before):
            continue
        cur = (s.get("families") or {}).get(fam) or {}
        now = cur.get("score")
        if now is None:
            out.append(f"{fam}: cannot be scored (baseline {before:g})")
        elif not isinstance(now, (int, float)) or not math.isfinite(now) or now < before - 1e-9:
            out.append(f"{fam}: {now} < baseline {before:g}")
        base_opps, now_opps = entry.get("opportunities"), cur.get("opportunities")
        if isinstance(base_opps, int) and isinstance(now_opps, int) and now_opps < base_opps:
            out.append(f"{fam}: opportunities {now_opps} < baseline {base_opps}")
    for key, count_key, label in (
        ("geometry_pass_rate", "geometry_cases", "geometry"),
        ("completeness_pass_rate", "completeness_cases", "completeness"),
    ):
        before = base.get(key)
        count = base.get(count_key)
        if not isinstance(before, (int, float)) or not math.isfinite(before) or not count:
            continue
        now_count = s.get(count_key)
        if not isinstance(now_count, int):
            now_count = 0
        if now_count < count:
            out.append(f"{label}: compared {now_count} cases < baseline {count}")
        now = s.get(key)
        if now is None:
            out.append(f"{label}: not compared now (baseline {before:g}); install linercad[3d]")
        elif not isinstance(now, (int, float)) or not math.isfinite(now) or now < before - 1e-9:
            out.append(f"{label}: {now} < baseline {before:g}")
    cases = s["cases"]
    if isinstance(base.get("cases"), int) and cases < base["cases"]:
        out.append(f"cases: {cases} < baseline {base['cases']}")
    have = {c["id"] for c in report["cases"] if c.get("id")}
    gone = sorted(set(base.get("case_ids") or []) - have)
    if gone:
        out.append(f"cases removed: {', '.join(gone[:5])}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--level", choices=["L1", "L2"])
    ap.add_argument("--case")
    ap.add_argument("--drawings")
    ap.add_argument("--no-geo", action="store_true")
    ap.add_argument("--out", default="report.json")
    ap.add_argument(
        "--baseline", metavar="PATH", help="regression gate against a baseline vector (E1)"
    )
    ap.add_argument("--save-baseline", metavar="PATH", help="write this run's vector as a baseline")
    a = ap.parse_args(argv)
    results = [run_case(c, a.drawings, not a.no_geo) for c in discover(a.level, a.case)]
    if not results:  # a typo in --case must not look like a clean run
        print(
            json.dumps(
                {"error": "no cases matched", "level": a.level, "case": a.case},
                ensure_ascii=False,
            )
        )
        return 1
    rep = {"summary": summary(results), "cases": results}
    Path(a.out).write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    print(json.dumps(rep["summary"], ensure_ascii=False))
    problems = []
    if a.baseline:
        try:
            base = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:  # unreadable / malformed file: fail closed
            problems = [f"baseline: cannot read {a.baseline}: {type(e).__name__}"]
        else:
            problems = compare_baseline(rep, base)
    clean = rep["summary"]["passed"] == rep["summary"]["cases"]
    failed = not clean or bool(problems)
    if a.save_baseline:
        vector = baseline_vector(rep)
        blocked = list(problems)
        if not clean:
            blocked.append("run is not clean (passed != cases)")
        if a.level or a.case or a.no_geo or a.drawings:
            blocked.append(
                "partial run (--level / --case / --no-geo / --drawings) cannot seed a baseline"
            )
        blocked += _baseline_problems(vector)
        if blocked:
            failed = True
            print(
                json.dumps(
                    {"baseline": str(a.save_baseline), "written": False, "problems": blocked},
                    ensure_ascii=False,
                )
            )
        else:
            Path(a.save_baseline).write_text(
                json.dumps(vector, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(
                json.dumps({"baseline": str(a.save_baseline), "written": True}, ensure_ascii=False)
            )
    if a.baseline:
        print(
            json.dumps({"baseline": str(a.baseline), "regressions": problems}, ensure_ascii=False)
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
