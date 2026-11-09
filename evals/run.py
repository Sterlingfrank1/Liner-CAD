"""Evaluation runner (SPEC M1 §8): builds every L1 / L2 case, runs the checks and the geometry
comparison, writes report.json. Adding a case means adding files, never code.

    uv run python evals/run.py [--level L1|L2] [--case ID] [--drawings DIR] [--out report.json]

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


def summary(results):
    n = len(results)
    built = [r for r in results if "errors" in r]
    geo = [r for r in results if r.get("geo")]
    cmp = [r for r in results if r.get("completeness")]
    rounds = [r["rounds"] for r in results if r.get("rounds") is not None]
    return {
        "cases": n,
        "built": len(built),
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
        "first_pass_rate": round(
            sum(1 for r in results if r.get("rounds") == 0 and r.get("passed")) / len(rounds), 4
        )
        if rounds
        else None,
        "mean_rounds": round(sum(rounds) / len(rounds), 2) if rounds else None,
        "passed": sum(1 for r in results if r.get("passed")),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--level", choices=["L1", "L2"])
    ap.add_argument("--case")
    ap.add_argument("--drawings")
    ap.add_argument("--no-geo", action="store_true")
    ap.add_argument("--out", default="report.json")
    a = ap.parse_args(argv)
    results = [run_case(c, a.drawings, not a.no_geo) for c in discover(a.level, a.case)]
    rep = {"summary": summary(results), "cases": results}
    Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep["summary"], ensure_ascii=False))
    return 0 if rep["summary"]["passed"] == rep["summary"]["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
