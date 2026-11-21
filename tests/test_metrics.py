"""E1 (v0.1.1): every finding carries clause / measured / expected / candidates, every rule
reports the number of objects it checked (opportunities), and evals/run.py turns those numbers into
a per-family score vector plus a baseline that fails on regression.

The rule fixtures below are deliberately broken drawings: each one is written to make one or more
rules fire, so the schema and the opportunity counts are checked on real findings, not on a
hand-made dict.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from linercad import Drawing, Param, checks, commands
from linercad.layout import layout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

import run as evals  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def run(d, stale=()):
    layout(d)
    return checks.run(d, stale)


# ---- broken drawings (one per group of rules) ----------------------------------------------------


def _layout_problems():
    """overlap (an over-full dimension row), view_align (长对正), out_of_frame (an oversized view)."""
    d = Drawing(sheet="A3")
    fr, tp, lf = d.view("front"), d.view("top"), d.view("left")
    fr.rect((0, 0), 80, 60, name="body")
    tp.rect((0, 0), 80, 50, name="body")
    lf.rect((0, 0), 400, 50, name="huge")
    for k in range(8):  # more fixed-row dimensions than the candidates can separate
        fr.dim.linear(f"x{k}", (0, 20), (80, 20), side="top", row=1)
    tp.rect((0, 0), 85, 10, name="extra")  # 长对正 mismatch against front
    return d


def _profile_problems():
    """line_width (series + 2:1), text_height (series / dim height), scale, sheet."""
    d = Drawing(sheet="A3", scale="1:7")
    d.std["lines"]["thick"]["width"] = 0.31
    d.std["text"]["heights"] = [2.5]
    d.std["dim"]["text_height"] = 5.0
    d.template["size"] = [111.0, 222.0]
    v = d.view("front")
    v.rect((0, 0), 50, 30, name="b")
    v.dim.linear("w", (0, 0), (50, 0))
    return d


def _annotation_problems():
    """conv_dim, duplicate, closed_loop, param_cover, gtol_syntax, datum_letter, rough_syntax,
    rough_default, rough_fit, general_tol, chain_limit, center_mark, missing."""
    d = Drawing()
    P = d.params(D=Param(30), L=Param(120), unused=Param(5))
    f = d.view("front")
    f.turned("b", [(0, P.D / 2), (P.L, P.D / 2)])
    f.thread("m20", "M20", 0, 30)  # thread without its designation dimension
    f.circle((0, 90), 10, name="o")  # full circle, no centre line
    f.dim.dia("D", (20, P.D / 2), (20, -P.D / 2), value=P.D, side="inside")
    f.dim.linear("L", (0, -15), (P.L, -15), value=P.L, side="bottom")
    f.dim.linear("L2", (0, -15), (P.L, -15), value=P.L, side="bottom", row=2)  # duplicate
    f.gtol("run", "circular_runout", 0.02, datums=["A"], ref="E.front.b")  # datum A undefined
    f.datum("I", ref="D.D")  # discouraged letter (GB/T 17851-2010 6.2 note 2)
    f.rough("r", 3.0, ref="E.front.b")  # not a GB/T 1031 preferred value; no rough_default
    d.chain("rest", closing="L2", increase=["D.L"], decrease=["D.L2"], require=(-0.1, 0.1))
    top = d.view("top")
    top.turned("t", [(0, 20), (40, 20), (40, 40)])  # steps without links -> missing
    left = d.view("left")
    c = left.circle((0, 0), 30, name="bore")
    left.dim.dia("bore", circle=c, value=60, tol="H7")  # IT7 fit face without roughness
    return d


def _dev_order(d):
    d["D.L"]._intent["tolerance"] = {"kind": "dev", "upper": -0.1, "lower": 0.1}


def _section_ref(d):
    d["S.A"]._intent["view"] = "ghost"  # the section points at a view that is not there


def _section_problems():
    d = Drawing(sheet="A3")
    fr, lf = d.view("front"), d.view("left")
    fr.rect((0, 0), 80, 60, name="body")
    lf.circle((0, 0), 60, name="body")
    d.section("A", view="front", cut_in="left", through=[(0, -70), (0, 70)])
    return d


# name -> (builder, after-layout mutation)
FIXTURES = {
    "layout": (_layout_problems, None),
    "profile": (_profile_problems, None),
    "annotation": (_annotation_problems, _dev_order),
    "section": (_section_problems, _section_ref),
}

STALE = [
    {
        "edit": "e3",
        "line": 4,
        "op": "set",
        "id": "D.gone",
        "reason": "目标不存在",
        "candidates": ["D.g"],
    }
]


def all_findings():
    """(fired rule set, findings) over the broken fixtures and one stale action log."""
    fired, found = set(), []
    for make, after in FIXTURES.values():
        d = make()
        layout(d)
        if after is not None:
            after(d)
        got = checks.run(d)
        fired |= {f["rule"] for f in got}
        found += got
    d = Drawing()
    got = checks.run(d, STALE)
    fired |= {f["rule"] for f in got}
    found += got
    return fired, found


# ---- finding schema ------------------------------------------------------------------------------


def test_every_rule_fires_in_the_fixtures():
    """The schema test below is only meaningful if it sees a finding of every rule."""
    fired, found = all_findings()
    assert fired == set(checks.RULES), sorted(set(checks.RULES) - fired)
    assert found


def test_findings_carry_clause_measured_expected_candidates():
    _, found = all_findings()
    for f in found:
        for key in ("clause", "measured", "expected", "candidates"):
            assert key in f, (f["rule"], f["id"], key)
        assert isinstance(f["clause"], str) and f["clause"].strip(), f
        assert isinstance(f["measured"], dict) and f["measured"], f
        assert isinstance(f["expected"], dict) and f["expected"], f
        assert isinstance(f["candidates"], list), f
        # the fields the old contract promised are unchanged
        assert f["pack"] in ("drafting", "dimensioning", "tolerancing", "surface", "layout")
        assert f["severity"] in ("error", "warn") and f["std"]
        assert isinstance(f["message"], str) and f["message"]


def test_clause_follows_the_active_standard_profile():
    """The clause is the standard number of the profile; ISO drawings must not say GB."""
    d = Drawing(std="ISO")
    f = d.view("front")
    f.circle((0, 0), 20, name="o")  # center_mark fires on every view
    found = run(d)
    mark = [x for x in found if x["rule"] == "center_mark"]
    assert mark and mark[0]["clause"].startswith("ISO")


# ---- opportunities -------------------------------------------------------------------------------


def test_every_rule_reports_opportunities():
    d = Drawing()
    d.view("front").rect((0, 0), 50, 30, name="b")
    opps = run(d).opportunities
    assert set(opps) == set(checks.RULES)
    assert all(isinstance(n, int) and n >= 0 for n in opps.values())


def test_opportunities_count_the_checked_objects():
    d = Drawing()
    P = d.params(D=Param(30), unused=Param(5))
    f = d.view("front")
    f.turned("b", [(0, P.D / 2), (50, P.D / 2)])
    f.dim.dia("D", (20, P.D / 2), (20, -P.D / 2), value=P.D, side="inside")
    f.dim.linear("L", (0, -15), (50, -15), value=50, side="bottom")
    f.rough("r", 0.8, ref="E.front.b")
    opps = run(d).opportunities
    assert opps["param_cover"] == 2  # the two parameters
    assert opps["rough_syntax"] == 1  # one roughness symbol
    assert opps["rough_default"] == 1  # one drawing-level question
    assert opps["duplicate"] == 2  # two keyable dimensions
    assert opps["sheet"] == 1  # one sheet
    assert opps["scale"] == 1  # the title-block scale (no view carries its own here)


def test_fired_rules_never_check_fewer_objects_than_findings():
    _, found = all_findings()
    by_rule = {}
    for f in found:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    d = _annotation_problems()
    layout(d)
    opps = checks.run(d).opportunities
    for rule, n in by_rule.items():
        assert opps[rule] >= n, (rule, opps[rule], n)


def test_lcad_check_outputs_opportunities(tmp_path):
    (tmp_path / "drawing.py").write_text(
        "from linercad import Drawing\n"
        "d = Drawing()\n"
        "d.view('front').rect((0, 0), 50, 30, name='b')\n",
        encoding="utf-8",
    )
    out = commands.check(tmp_path)
    assert out["ok"] and "opportunities" in out
    assert set(out["opportunities"]) == set(checks.RULES)
    assert out["errors"] == 0 and out["warnings"] == 0


# ---- family score vector -------------------------------------------------------------------------


def _case(rules=None, errors=0, passed=True):
    return {"errors": errors, "warnings": 0, "passed": passed, "rules": rules or {}}


def test_family_scores_are_weighted_by_opportunities():
    results = [
        _case({"duplicate": {"opportunities": 4, "violations": 1}}),
        _case({"missing": {"opportunities": 6, "violations": 0}}),
        _case({"gtol_syntax": {"opportunities": 3, "violations": 1}}),
        _case({"rough_syntax": {"opportunities": 1, "violations": 0}}),
    ]
    s = evals.summary(results)
    fam = s["families"]
    assert set(fam) == set(evals.FAMILIES)
    assert fam["D"]["opportunities"] == 10 and fam["D"]["violations"] == 1
    assert fam["D"]["score"] == pytest.approx(0.9)
    assert fam["T"]["opportunities"] == 4 and fam["T"]["score"] == pytest.approx(0.75)
    assert fam["G"]["score"] is None and fam["G"]["opportunities"] == 0
    assert fam["A"]["score"] is None
    assert fam["D"]["rules"]["duplicate"] == {"opportunities": 4, "violations": 1}


def test_process_family_stays_separate():
    results = [_case({"stale_op": {"opportunities": 2, "violations": 1}})]
    s = evals.summary(results)
    assert "P" not in s["families"]
    assert s["P"]["rules"]["stale_op"] == {"opportunities": 2, "violations": 1}
    assert s["P"]["first_pass_rate"] is None and s["P"]["mean_rounds"] is None


def test_every_rule_has_a_family():
    for rule in checks.RULES:
        assert checks.family(rule) in ("G", "D", "T", "A", "P"), rule


# ---- baseline ------------------------------------------------------------------------------------


def _report(*results):
    return {"summary": evals.summary(list(results)), "cases": list(results)}


def test_baseline_roundtrip_is_clean(tmp_path):
    rep = _report(
        _case({"duplicate": {"opportunities": 4, "violations": 0}}),
        _case({"overlap": {"opportunities": 2, "violations": 0}}),
    )
    base = evals.baseline_vector(rep)
    assert base["version"] == 1 and base["cases"] == 2 and base["errors"] == 0
    assert base["families"]["D"]["score"] == pytest.approx(1.0)
    assert base["families"]["A"]["score"] is None
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    assert evals.compare_baseline(rep, json.loads(path.read_text(encoding="utf-8"))) == []


def test_baseline_flags_a_family_drop():
    good = _report(_case({"duplicate": {"opportunities": 4, "violations": 0}}))
    base = evals.baseline_vector(good)
    bad = _report(_case({"duplicate": {"opportunities": 4, "violations": 1}}))
    problems = evals.compare_baseline(bad, base)
    assert problems and "D" in problems[0]


def test_baseline_flags_more_errors_and_a_lost_family():
    good = _report(_case({"duplicate": {"opportunities": 4, "violations": 0}}))
    base = evals.baseline_vector(good)
    assert any("error" in p for p in evals.compare_baseline(_report(_case(errors=1)), base))
    # a family that the baseline scored but the current run cannot (e.g. no build123d)
    assert any("D" in p for p in evals.compare_baseline(_report(_case()), base))


def test_baseline_cli_exits_nonzero_on_regression(monkeypatch, tmp_path):
    monkeypatch.setattr(
        evals,
        "discover",
        lambda level=None, case=None: [
            {"id": "L1/x", "level": "L1", "family": "x", "drawing_src": "", "views": []}
        ],
    )

    def case(ok):
        rules = {"duplicate": {"opportunities": 2, "violations": 0 if ok else 1}}
        return {
            "id": "L1/x",
            "level": "L1",
            "family": "x",
            "errors": 0,
            "warnings": 0,
            "findings": [],
            "rules": rules,
            "passed": True,
        }

    monkeypatch.setattr(evals, "run_case", lambda c, drawings=None, geo=True: case(True))
    baseline = tmp_path / "baseline.json"
    out = tmp_path / "report.json"
    assert evals.main(["--save-baseline", str(baseline), "--out", str(out)]) == 0
    assert baseline.is_file()
    assert evals.main(["--baseline", str(baseline), "--out", str(out)]) == 0
    monkeypatch.setattr(evals, "run_case", lambda c, drawings=None, geo=True: case(False))
    assert evals.main(["--baseline", str(baseline), "--out", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["passed"] == 1


def test_repo_baseline_is_present_and_complete():
    path = REPO / "evals" / "baseline.json"
    assert path.is_file(), "E1 ships evals/baseline.json"
    base = json.loads(path.read_text(encoding="utf-8"))
    assert base["version"] == 1
    assert base["cases"] == 40 and base["errors"] == 0
    assert base["zero_error_rate"] == 1.0
    assert base["geometry_pass_rate"] == 1.0
    assert base["completeness_pass_rate"] == 1.0
    fam = base["families"]
    assert set(fam) == set(evals.FAMILIES)
    for key in ("G", "D", "T"):
        assert fam[key]["score"] == 1.0 and fam[key]["opportunities"] > 0, key
    assert fam["A"]["score"] is None  # no assembly rules yet
    assert "P" in base and "stale_op" in base["P"]["rules"]
