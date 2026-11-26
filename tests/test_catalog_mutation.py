"""E2: rule catalog, mutation framework (detection / false-positive rates), the radial-leader
crossing rule and the opportunity-count unification.

The catalog is shipped data (`catalog.toml`) and must stay in lock-step with the code: every rule
that `checks.RULES` knows has to be in it, every catalog entry has to resolve to a real function, and
every `done` rule has to have a mutation operator that provably breaks it. The mutation report is
the evidence: detection rate 1.0 on mutated reference drawings, zero false positives on the
reference drawings themselves (the frozen E5 placement debt counts as known true positives).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

import mutate  # noqa: E402

from linercad import Drawing, catalog, checks, place
from linercad.layout import Line, layout

REPO = Path(__file__).resolve().parents[1]

#: rules whose clause number was read from the standard (A4: GB/T 1182-2018 / 17851-2010)
READ_CLAUSES = {
    "gtol_syntax": ("GB/T 1182-2018", "表1"),
    "gtol_target": ("GB/T 1182-2018", "表1"),
}


@pytest.fixture(scope="module")
def report():
    # the reference pass builds the L1/L2 cases, some of which take their geometry from build123d
    pytest.importorskip("build123d")
    return mutate.run_report()


def test_catalog_covers_every_rule():
    entries = catalog.load()["rule"]
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
    assert set(ids) == set(checks.RULES)


def test_catalog_entry_schema_and_functions():
    functions = mutate.rule_functions()
    for e in catalog.load()["rule"]:
        for key in (
            "id",
            "pack",
            "family",
            "statement",
            "std",
            "clause",
            "clause_status",
            "status",
            "positive",
            "negative",
        ):
            assert key in e, (e.get("id"), key)
        assert e["pack"] == checks.RULES[e["id"]]
        assert e["family"] == checks.family(e["id"])
        assert e["status"] == "done"
        assert e["fn"] == e["id"]
        assert e["fn"] in functions
        assert isinstance(e["statement"], str) and e["statement"].strip()
        assert e["clause_status"] in ("read", "pending", "design")
        assert e["positive"].strip() and e["negative"].strip()
        assert "参考图" in e["positive"] or "fixture" in e["positive"], e["id"]
        if "FIXTURES[" in e["positive"]:  # a named fixture must exist in the mutation framework
            name = e["positive"].split("FIXTURES[")[1].split("]")[0].strip("'")
            assert name in mutate.FIXTURES, (e["id"], name)
        if e["clause_status"] == "pending":
            # no clause / table number may be invented: the clause is the standard number only
            assert e["clause"] == e["std"], e["id"]
        elif e["clause_status"] == "read":
            assert e["clause"].startswith(e["std"])
            assert len(e["clause"]) > len(e["std"])
        else:  # design: the authority is DESIGN.md, not a standard clause
            assert e["clause"].startswith("DESIGN §")


def test_clause_precision_policy():
    by_id = {e["id"]: e for e in catalog.load()["rule"]}
    for rule, (std, marker) in READ_CLAUSES.items():
        e = by_id[rule]
        assert e["std"] == std
        assert e["clause_status"] == "read"
        assert marker in e["clause"], e["clause"]
    # two rules take their authority from DESIGN.md; datum_letter is pending with a lineage note
    # (res/datum.toml itself marks 6.2 unverified); everything else says so instead of guessing
    for rule, e in by_id.items():
        if rule in READ_CLAUSES:
            continue
        if rule in ("param_cover", "stale_op", "table_overflow", "logo_external_ref"):
            assert e["clause_status"] == "design", rule
            assert e["clause"].startswith("DESIGN §"), rule
        else:
            assert e["clause_status"] == "pending", rule
    datum = by_id["datum_letter"]
    assert datum["clause_status"] == "pending"
    assert datum["clause"] == datum["std"] == "GB/T 17851-2010"
    assert "verified=false" in datum["clause_note"] and "6.2" in datum["clause_note"]


def test_catalog_meta_declares_the_known_blind_spots_and_double_counting():
    meta = catalog.load()["meta"]
    assert "place_dim_cross" in meta["dual_counting"]
    assert "77→97" in meta["dual_counting"] or "77" in meta["dual_counting"]
    assert "尺寸界线" in meta["coverage_boundary"] and "中心线" in meta["coverage_boundary"]
    assert "轮廓" in meta["coverage_boundary"]


def test_radial_text_recognition_forms():
    from linercad.layout import Text

    def radial(txt):
        return place._is_radial_text([Text(txt, (0, 0), 3.5, 0, "text", (0, 0, 1, 1))])

    for txt in ("Φ92", "⌀92", "Ø92", "ø92", "R5", "SΦ92", "SR5", "2-Φ8", "2×Φ8", "4xΦ12"):
        assert radial(txt), txt
    for txt in ("92", "M8", "R", "S", "2 个 Φ8 孔"):  # free text without a radial prefix
        assert not radial(txt), txt


def test_every_done_rule_has_a_mutation_operator():
    for e in catalog.load()["rule"]:
        assert e["id"] in mutate.MUTATORS, e["id"]


def test_mutation_detection_and_false_positive_rates(report):
    for rule, data in report["rules"].items():
        assert data["detection_rate"] == 1.0, (rule, data)
        assert data["detected"] == data["mutations"], (rule, data)
        assert data["false_positives"] == 0, (rule, data)
        assert data["base_findings"] == 0, (rule, data)
        assert data["target"] is not None, (rule, data)  # every mutation is anchored on an id
    assert report["totals"]["mutations"] >= len(checks.RULES)
    assert report["totals"]["skipped_cases"] == 0
    assert report["totals"].get("errored", 0) == 0
    assert report["totals"].get("unmutated", 0) == 0
    for rule, data in report["rules"].items():
        assert data["mutation_base_opportunities"] is not None, rule


def test_mutation_report_mentions_known_placement_debt(report):
    assert report["known_debt"]["total"] > 0  # E5's frozen debt is excluded but reported
    assert report["known_debt"]["exact"]  # the frozen signatures equal the actual reference set
    assert report["totals"]["false_positives"] == 0


def test_mutation_flag_fails_the_run_when_the_report_is_not_clean(monkeypatch, tmp_path):
    import run as evals_run

    bad = {
        "rules": {
            "closed_loop": {
                "mutations": 1,
                "detected": 0,
                "detection_rate": 0.0,
                "false_positives": 0,
                "opportunities": 1,
                "reference_opportunities": 1,
                "mutation_base_opportunities": 1,
                "base": None,
                "base_findings": 0,
                "target": None,
            }
        },
        "totals": {
            "rules": 1,
            "mutations": 1,
            "detected": 0,
            "detection_rate": 0.0,
            "false_positives": 0,
            "skipped_cases": 0,
        },
        "known_debt": {"total": 0, "cases": 0, "exact": False},
    }
    fake = type(sys)("mutate")
    fake.run_report = lambda **k: bad
    monkeypatch.setitem(sys.modules, "mutate", fake)
    code = evals_run.main(
        [
            "--level",
            "L1",
            "--case",
            "L1/thread_ext_M20",
            "--no-geo",
            "--mutation",
            "--out",
            str(tmp_path / "report.json"),
        ]
    )
    assert code == 1  # a clean summary must not hide a failed mutation report


def test_radial_leader_crossing_rule():
    rule = "place_leader_cross"
    assert rule in checks.RULES and checks.family(rule) == "D"
    assert rule in place.CLAUSES and rule in mutate.MUTATORS
    d = Drawing(sheet="A3")
    v = d.view("front")
    c = v.circle((0, 0), 30, name="outer")
    v.dim.dia("Dd", circle=c, at=45)
    v.dim.linear("X", (60, -40), (60, 40), dir="v", value=80, side="right")
    layout(d)
    assert place.place_leader_cross(d)[0] == []
    # push the second dimension line across the radial leader: a perpendicular through its middle
    info = place._leader_dim(d["D.Dd"])
    a = info["lines"][0]
    mid = ((a.p[0] + a.q[0]) / 2, (a.p[1] + a.q[1]) / 2)
    u = place._unit(a.p, a.q)
    perp = (-u[1], u[0])
    x = place._frame_dim(d["D.X"])["dim"]
    d["D.X"]._prims = [
        Line(
            (mid[0] - perp[0] * 20, mid[1] - perp[1] * 20),
            (mid[0] + perp[0] * 20, mid[1] + perp[1] * 20),
            "dim",
        )
        if p is x
        else p
        for p in d["D.X"]._prims
    ]
    findings, opportunities = place.place_leader_cross(d)
    assert opportunities >= 1
    assert findings and findings[0]["id"] == "D.Dd"
    for key in ("clause", "measured", "expected", "candidates"):
        assert key in findings[0]


def test_radial_leader_rule_is_catalogued_and_mutated():
    by_id = {e["id"]: e for e in catalog.load()["rule"]}
    entry = by_id["place_leader_cross"]
    assert entry["clause"].startswith("GB/T 4458.4")
    assert entry["status"] == "done"
    assert "place_leader_cross" in mutate.MUTATORS
    # D1 review: gear_blank Φ92 is the negative mutation example for this rule
    assert mutate.BASE_OVERRIDES["place_leader_cross"] == "L2/disc/gear_blank"


def test_general_tol_and_rough_default_opportunity_policy():
    # a fully toleranced drawing has nothing for general_tol to check -> no opportunity
    d = Drawing()
    f = d.view("front")
    f.rect((0, 0), 50, 30, name="b")
    f.dim.linear("T", (0, 0), (50, 0), value=50, tol=(0.1, -0.1))
    layout(d)
    from linercad.rules import general_tol, rough_default

    assert general_tol(d) == ([], 0)
    assert rough_default(d) == ([], 0)  # no roughness symbol -> no drawing-level check either
    f.rough("r", 0.8, ref="E.front.b.1")
    findings, opportunities = rough_default(d)
    assert findings and opportunities == 1
    # an untoleranced dimension is what the drawing-level general-tolerance check looks at
    f.dim.linear("U", (0, 10), (50, 10), value=50, side="bottom")
    layout(d)
    assert general_tol(d)[1] == 1 and general_tol(d)[0]  # no general note yet -> finding
    d.general_tol("m")
    assert general_tol(d) == ([], 1)
