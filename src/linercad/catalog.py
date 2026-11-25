"""Rule catalog (benchmark-metrics §5.2): shipped data for the implemented rules.

``res/catalog.toml`` lists every rule ``checks.run`` can report: the metric id, its standard, the
clause (a table / clause number when the standard text was read, otherwise only the standard number
and ``clause_status = "pending"` - a clause number is never invented), the clause statement, the
function that implements it, its status and the references to a positive and a negative fixture.
The mutation framework (``evals/mutate.py``) and the tests keep the catalog, the code and the
fixtures in lock-step.
"""

from __future__ import annotations

import tomllib
from importlib import resources

__all__ = ["by_id", "check", "load", "rule_functions"]


def load() -> dict:
    """The parsed catalog (a fresh dict each call)."""
    node = resources.files("linercad") / "res" / "catalog.toml"
    return tomllib.loads(node.read_text(encoding="utf-8"))


def rules() -> list[dict]:
    return list(load().get("rule", []))


def by_id() -> dict:
    return {entry["id"]: entry for entry in rules()}


def rule_functions() -> dict:
    """{metric id: callable} for every implemented rule (rule packs, layout pack, placement pack)."""
    from . import checks, place
    from .rules import PACKS

    out = {}
    for fns in PACKS.values():
        for fn in fns:
            out[fn.__name__] = fn
    out.update(
        {
            "overlap": checks._overlaps,
            "out_of_frame": checks._out_of_frame,
            "view_align": checks._view_align,
            "table_overflow": checks._table_overflow,
            "stale_op": checks._stale,
        }
    )
    for fn in place.RULES:
        out[fn.__name__] = fn
    return out


def check() -> list[str]:
    """Consistency problems between the catalog and the code (empty = consistent)."""
    from . import checks

    problems = []
    entries = rules()
    ids = [e.get("id") for e in entries]
    if len(set(ids)) != len(ids):
        problems.append("duplicate rule id in catalog")
    missing = sorted(set(checks.RULES) - set(ids))
    extra = sorted(set(ids) - set(checks.RULES))
    if missing:
        problems.append(f"rules missing from catalog: {missing}")
    if extra:
        problems.append(f"catalog rules without a check: {extra}")
    functions = rule_functions()
    for e in entries:
        rid = e.get("id")
        for key in (
            "id",
            "pack",
            "family",
            "fn",
            "statement",
            "std",
            "clause",
            "clause_status",
            "status",
            "positive",
            "negative",
        ):
            if key not in e:
                problems.append(f"{rid}: missing {key}")
        if e.get("pack") != checks.RULES.get(rid):
            problems.append(f"{rid}: pack {e.get('pack')} != {checks.RULES.get(rid)}")
        if e.get("family") != checks.family(rid):
            problems.append(f"{rid}: family {e.get('family')} != {checks.family(rid)}")
        if e.get("fn") not in functions:
            problems.append(f"{rid}: function {e.get('fn')} not found")
        if e.get("status") not in ("done", "J-only", "todo"):
            problems.append(f"{rid}: bad status {e.get('status')}")
        if e.get("clause_status") not in ("read", "pending", "design"):
            problems.append(f"{rid}: bad clause_status {e.get('clause_status')}")
        if e.get("clause_status") == "pending" and e.get("clause") != e.get("std"):
            problems.append(f"{rid}: pending clause must be the standard number only")
        if e.get("clause_status") == "design" and not str(e.get("clause", "")).startswith(
            "DESIGN §"
        ):
            problems.append(f"{rid}: design clause must be a DESIGN section")
    return problems
