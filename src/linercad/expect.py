"""Declarative constraints for evaluation cases (E3, benchmark-metrics section 4).

A case directory may carry an expect.py file:

    def expect(e):
        bore = e.feature(cyl=30)
        e.dim(bore, fit="H7")
        e.datum("A", on=bore, axis=True)
        e.gtol("perpendicularity", datums=["A"], max=0.02)
        e.rough(bore, ra_max=1.6)
        e.note(contains="调质")
        e.view("front", section=("full", "half"))
        e.any_of(e.gtol("runout", datums=["A"]), e.gtol("coaxiality", datums=["A"]))

Matching is by geometry signature (values, diameters, fit codes, PMI content), never by element
ID. Every constraint is must (error) by default; must=False is a should (warning): it still
counts as an opportunity but does not make the case fail.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

TOL = 0.01


class Target:
    """A geometry signature: cylinder by diameter, named face, or any."""

    def __init__(self, kind="any", value=None, name=None):
        self.kind = kind
        self.value = value
        self.name = name


class Constraint:
    def __init__(self, rule, must, message, measured, expected, check):
        self.rule = rule
        self.must = must
        self.message = message
        self.measured = measured
        self.expected = expected
        self.check = check
        self.ok = False
        self.matched = None

    def evaluate(self, obs):
        self.matched = None
        self.ok, self.matched = self.check(obs)
        return self.ok


class Expect:
    """The object handed to a case expect(e) function."""

    def __init__(self):
        self.constraints = []

    def feature(self, cyl=None, name=None):
        return Target("cyl", float(cyl) if cyl is not None else None, name)

    def face(self, name):
        return Target("face", name=name)

    def dim(self, target=None, value=None, fit=None, kind=None, must=True):
        target = target if isinstance(target, Target) else Target("any")
        if value is not None:
            target = Target("value", float(value))

        def check(obs):
            for dim in obs["dims"]:
                if kind and dim["type"] not in _kind_set(kind):
                    continue
                if not _target_matches_dim(target, dim):
                    continue
                if fit and not _dim_has_fit(dim, fit):
                    continue
                return True, dim["id"]
            return False, None

        self.constraints.append(
            Constraint(
                "expect_dim",
                must,
                _msg("尺寸", _target_text(target), "fit " + str(fit) if fit else ""),
                {},
                {"dim": _target_text(target), "fit": fit},
                check,
            )
        )
        return target

    def datum(self, letter, on=None, axis=None, must=True):
        on = on if isinstance(on, Target) else Target("any")

        def check(obs):
            vals = _dim_values(obs)
            for dt in obs["datums"]:
                if str(dt["letter"]).upper() != str(letter).upper():
                    continue
                if axis is not None and (dt["target"] == "axis") != bool(axis):
                    continue
                if on.kind == "cyl":
                    refv = vals.get(dt.get("ref"))
                    if refv is None or not any(abs(v - on.value) <= TOL for v in refv):
                        continue
                return True, dt["id"]
            return False, None

        self.constraints.append(
            Constraint(
                "expect_datum",
                must,
                _msg("基准", str(letter), "轴线" if axis else ""),
                {},
                {"letter": letter, "axis": axis},
                check,
            )
        )

    def gtol(self, char, on=None, datums=None, max=None, must=True):
        on = on if isinstance(on, Target) else Target("any")
        wanted = [str(d).upper() for d in (datums or [])]

        def check(obs):
            vals = _dim_values(obs)
            for g in obs["gtols"]:
                if str(g["char"]).lower() != str(char).lower():
                    continue
                have = {str(x).upper() for x in g["datums"]}
                if not set(wanted) <= have:
                    continue
                if max is not None and float(g["value"]) > float(max) + TOL:
                    continue
                if on.kind == "cyl":
                    refv = vals.get(g.get("ref"))
                    if refv is None or not any(abs(v - on.value) <= TOL for v in refv):
                        continue
                return True, g["id"]
            return False, None

        self.constraints.append(
            Constraint(
                "expect_gtol",
                must,
                _msg(str(char), "公差", "基准 " + ",".join(wanted) if wanted else ""),
                {},
                {"char": char, "datums": wanted, "max": max},
                check,
            )
        )

    def rough(self, target=None, ra_max=None, param="Ra", must=True):
        target = target if isinstance(target, Target) else Target("any")

        def check(obs):
            vals = _dim_values(obs)
            for r in obs["roughs"]:
                if param and r["param"] != param:
                    continue
                if ra_max is not None and float(r["value"]) > float(ra_max) + TOL:
                    continue
                if target.kind == "cyl":
                    refv = vals.get(r.get("ref"))
                    if refv is None or not any(abs(v - target.value) <= TOL for v in refv):
                        continue
                return True, r["id"]
            return False, None

        self.constraints.append(
            Constraint(
                "expect_rough",
                must,
                _msg("粗糙度", "Ra<=" + str(ra_max) if ra_max is not None else ""),
                {},
                {"param": param, "ra_max": ra_max},
                check,
            )
        )

    def note(self, contains, must=True):
        def check(obs):
            for text in obs["texts"]:
                if contains in text:
                    return True, text
            return False, None

        self.constraints.append(
            Constraint(
                "expect_note",
                must,
                "技术要求应包含 " + repr(contains),
                {},
                {"contains": contains},
                check,
            )
        )

    def view(self, name, section=None, must=True):
        def check(obs):
            for v in obs["views"]:
                if v["name"] == name:
                    return True, v["id"]
            return False, None

        self.constraints.append(
            Constraint(
                "expect_view",
                must,
                "应有视图 " + str(name),
                {},
                {"view": name, "section": section},
                check,
            )
        )

    def any_of(self, *constraints, must=True):
        subs = [c for c in constraints if isinstance(c, Constraint)]
        if not subs:
            # the API methods return None today; take the constraints their argument calls just
            # appended (the alternatives), so they are not also counted as separate musts
            n = sum(1 for c in constraints if c is None)
            subs = self.constraints[-n:] if n else []
        drop = {id(c) for c in subs}
        self.constraints = [c for c in self.constraints if id(c) not in drop]

        def check(obs):
            for c in subs:
                if c.evaluate(obs):
                    return True, c.matched
            return False, None

        self.constraints.append(
            Constraint(
                "expect_any_of",
                must,
                "至少满足一种等效要求",
                {"any_of": [c.message for c in subs]},
                {"any_of": len(subs)},
                check,
            )
        )


def _kind_set(kind):
    if isinstance(kind, (tuple, list, set)):
        return set(kind)
    return {kind}


def _target_text(target):
    if target.kind == "cyl":
        return "Φ" + str(target.value)
    if target.kind == "value":
        return str(target.value)
    if target.kind == "face":
        return "面 " + str(target.name)
    return "任意"


def _msg(*parts):
    return " ".join(p for p in parts if p)


def _diameterish(dim):
    return dim["type"] in ("dia", "rad") or "Φ" in (dim.get("prefix") or "") + (
        dim.get("text") or ""
    )


def _dim_values_here(dim):
    if dim["type"] == "rad":
        return [2 * v for v in dim["values"]]
    return list(dim["values"])


def _dim_values(obs):
    return {dim["id"]: _dim_values_here(dim) for dim in obs["dims"]}


def _target_matches_dim(target, dim):
    if target.kind == "cyl":
        return _diameterish(dim) and any(
            abs(v - target.value) <= TOL for v in _dim_values_here(dim)
        )
    if target.kind == "value":
        return any(abs(v - target.value) <= TOL for v in _dim_values_here(dim))
    return True


def _dim_has_fit(dim, fit):
    fit = str(fit).upper()
    tol = dim.get("tolerance") or {}
    if tol.get("kind") == "fit":
        return str(tol.get("code") or "").upper() == fit  # the semantic fit is authoritative
    if str(dim.get("tol") or "").upper() == fit:
        return True
    return fit in (str(dim.get("text") or "") + str(dim.get("suffix") or "")).upper()


def observed(d):
    """The semantic facts of a built drawing that expect.py may match against."""
    dims, datums, gtols, roughs, texts, views = [], [], [], [], [], []
    for e in d._els.values():
        i = e._intent
        if e.kind == "dim":
            vals = [v for v in (i.get("value"), i.get("measured")) if v is not None]
            dims.append(
                {
                    "id": e.id,
                    "type": i.get("type"),
                    "values": vals,
                    "prefix": i.get("prefix") or "",
                    "text": i.get("text") or "",
                    "suffix": i.get("suffix") or "",
                    "tol": i.get("tol"),
                    "tolerance": i.get("tolerance"),
                    "designation": i.get("designation"),
                }
            )
        elif e.kind == "datum":
            datums.append(
                {
                    "id": e.id,
                    "letter": i.get("letter"),
                    "target": i.get("target"),
                    "ref": i.get("ref"),
                    "view": i.get("view"),
                }
            )
        elif e.kind == "gtol":
            letters = []
            for group in i.get("datums") or ():
                if isinstance(group, dict):
                    letters.extend(group.get("letters") or [])
                else:
                    letters.extend(group or [])
            gtols.append(
                {
                    "id": e.id,
                    "char": i.get("char"),
                    "value": i.get("value"),
                    "datums": letters,
                    "ref": i.get("ref"),
                    "view": i.get("view"),
                }
            )
        elif e.kind == "rough":
            roughs.append(
                {
                    "id": e.id,
                    "param": i.get("param"),
                    "value": i.get("value"),
                    "ref": i.get("ref"),
                    "default": bool(i.get("default")),
                }
            )
        elif e.kind in ("note", "text", "label"):
            texts.append(str(i.get("text") or ""))
        elif e.kind == "view":
            views.append({"id": e.id, "name": i.get("name")})
    return {
        "dims": dims,
        "datums": datums,
        "gtols": gtols,
        "roughs": roughs,
        "texts": texts,
        "views": views,
    }


def load(path):
    path = Path(path)
    spec = importlib.util.spec_from_file_location("expect_" + path.parent.name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def evaluate(path, d):
    """Run one case expect.py against a built drawing."""
    mod = path if hasattr(path, "expect") else load(path)
    e = Expect()
    if hasattr(mod, "expect"):
        mod.expect(e)
    obs = observed(d)
    findings, rules, referenced = [], {}, []
    for c in e.constraints:
        ok = c.evaluate(obs)
        st = rules.setdefault(c.rule, {"opportunities": 0, "violations": 0, "warnings": 0})
        st["opportunities"] += 1
        if ok:
            if c.rule == "expect_dim" and c.matched:
                referenced.append(c.matched)
        else:
            severity = "error" if c.must else "warn"
            if c.must:
                st["violations"] += 1
            else:
                st["warnings"] += 1
            findings.append(
                {
                    "rule": c.rule,
                    "severity": severity,
                    "id": "expect",
                    "message": c.message,
                    "measured": c.measured,
                    "expected": c.expected,
                    "candidates": [],
                }
            )
    return {
        "pass": not any(f["severity"] == "error" for f in findings),
        "checks": sum(v["opportunities"] for v in rules.values()),
        "violations": sum(v["violations"] for v in rules.values()),
        "warnings": sum(v["warnings"] for v in rules.values()),
        "rules": rules,
        "findings": findings,
        "referenced_dims": list(dict.fromkeys(referenced)),
    }


def referenced_dims(path, d):
    return evaluate(path, d)["referenced_dims"]
