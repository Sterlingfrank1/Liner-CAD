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
    "datum_letter": ("GB/T 17851-2010", "6.2"),
}


@pytest.fixture(scope="module")
def report():
    return mutate.run_report()


def test_catalog_covers_every_rule():
    entries = catalog.load()["rule"]
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
    assert set(ids) == set(checks.RULES)


def test_catalog_entry_schema_and_functions(report):
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
        assert e["clause_status"] in ("read", "pending")
        assert e["positive"].strip() and e["negative"].strip()
        if e["clause_status"] == "pending":
            # no clause / table number may be invented: the clause is the standard number only
            assert e["clause"] == e["std"], e["id"]
        else:
            assert e["clause"].startswith(e["std"])
            assert len(e["clause"]) > len(e["std"])


def test_clause_precision_policy():
    by_id = {e["id"]: e for e in catalog.load()["rule"]}
    for rule, (std, marker) in READ_CLAUSES.items():
        e = by_id[rule]
        assert e["std"] == std
        assert e["clause_status"] == "read"
        assert marker in e["clause"], e["clause"]
    # everything else has not been read clause by clause, and says so instead of guessing
    for rule, e in by_id.items():
        if rule not in READ_CLAUSES:
            assert e["clause_status"] == "pending", rule


def test_every_done_rule_has_a_mutation_operator(report):
    ops = mutate.MUTATORS
    for e in catalog.load()["rule"]:
        assert e["id"] in ops, e["id"]
        assert report["rules"][e["id"]]["mutations"] >= 1, e["id"]


def test_mutation_detection_and_false_positive_rates(report):
    for rule, data in report["rules"].items():
        assert data["detection_rate"] == 1.0, (rule, data)
        assert data["detected"] == data["mutations"], (rule, data)
        assert data["false_positives"] == 0, (rule, data)
    assert report["totals"]["mutations"] >= len(checks.RULES)


def test_mutation_report_mentions_known_placement_debt(report):
    assert report["known_debt"]["total"] > 0  # E5's frozen debt is excluded but reported
    assert report["totals"]["false_positives"] == 0


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
    # push the second dimension line across the radial leader
    x = place._frame_dim(d["D.X"])["dim"]
    d["D.X"]._prims = [
        Line((20.0, 0.0), (20.0, 50.0), "dim") if p is x else p for p in d["D.X"]._prims
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


def test_general_tol_and_rough_default_opportunity_policy():
    # a fully toleranced drawing has nothing for general_tol to check -> no opportunity
    d = Drawing()
    f = d.view("front")
    f.rect((0, 0), 50, 30, name="b")
    f.dim.linear("L", (0, 0), (50, 0), value=50, tol=(0.1, -0.1))
    layout(d)
    from linercad.rules import general_tol, rough_default

    assert general_tol(d) == ([], 0)
    assert rough_default(d) == ([], 0)  # no roughness symbol -> no drawing-level check either
    f.rough("r", 0.8, ref="E.front.b.1")
    findings, opportunities = rough_default(d)
    assert findings and opportunities == 1
    d.general_tol("m")
    assert general_tol(d)[1] == 1
