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

    def __init__(self, kind="any", value=None, name=None, side=None):
        self.kind = kind
        self.value = value
        self.name = name
        self.side = side


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

    def feature(self, cyl=None, name=None, where=None):
        return Target("cyl", float(cyl) if cyl is not None else None, name, where)

    def face(self, name):
        return Target("face", name=name, side=_face_side(name))

    def dim(self, target=None, value=None, fit=None, kind=None, must=True):
        target = target if isinstance(target, Target) else Target("any")
        want_value = float(value) if value is not None else None
        if want_value is not None and target.kind == "any":
            target = Target("value", want_value)

        def check(obs):
            for dim in obs["dims"]:
                if kind and dim["type"] not in _kind_set(kind):
                    continue
                if not _target_matches_dim(target, dim, obs):
                    continue
                if want_value is not None:
                    ann = dim.get("value") if dim.get("value") is not None else dim.get("measured")
                    if ann is None or abs(ann - want_value) > TOL:
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
                elif on.kind == "face":
                    if not _ref_matches_side(obs, dt.get("ref"), on.side, dt.get("view")):
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
                elif on.kind == "face":
                    if not _ref_matches_side(obs, g.get("ref"), on.side, g.get("view")):
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
                elif target.kind == "face":
                    if not _ref_matches_side(obs, r.get("ref"), target.side, r.get("view")):
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
            allowed = section
            if isinstance(allowed, str):
                allowed = (allowed,)
            for v in obs["views"]:
                if v["name"] != name:
                    continue
                if allowed:
                    kinds = [s["kind"] for s in obs["sections"] if s["view"] == name]
                    if not any(k in allowed for k in kinds):
                        continue
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
        if len(subs) < len(constraints):
            # each argument call appended exactly one constraint (dim returns a Target, the
            # others return None), so the alternatives are the last len(constraints) constraints
            n = len(constraints)
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


def _dim_side(dim, obs):
    """Geometry signature used for duplicate features: rank among dims with the same value."""
    if not dim.get("p1") or not dim.get("p2"):
        return None
    ann = dim.get("value") if dim.get("value") is not None else dim.get("measured")
    if ann is None:
        return None
    peers = [
        d
        for d in obs["dims"]
        if d.get("p1")
        and d.get("p2")
        and abs((d.get("value") if d.get("value") is not None else d.get("measured", 0)) - ann)
        <= TOL
    ]
    if len(peers) >= 2:
        xs = sorted((x["p1"][0] + x["p2"][0]) / 2 for x in peers)
        median = xs[len(xs) // 2]
        cx = (dim["p1"][0] + dim["p2"][0]) / 2
        return "left" if cx < median else "right"
    d = obs.get("_d")
    view = dim.get("view")
    eboxes = []
    if d is not None:
        for e in d._els.values():
            if e.kind in ("edge", "feature") and (view is None or e._intent.get("view") == view):
                eboxes.extend(getattr(pr, "box", None) for pr in getattr(e, "_prims", ()))
    eboxes = [b for b in eboxes if b]
    if eboxes:
        ref = (
            min(b[0] for b in eboxes),
            min(b[1] for b in eboxes),
            max(b[2] for b in eboxes),
            max(b[3] for b in eboxes),
        )
    else:
        anchors = [x for x in obs["dims"] if x.get("p1") and x.get("p2")]
        xs = [x["p1"][0] for x in anchors] + [x["p2"][0] for x in anchors]
        ys = [x["p1"][1] for x in anchors] + [x["p2"][1] for x in anchors]
        ref = (min(xs), min(ys), max(xs), max(ys))
    x0, y0 = min(dim["p1"][0], dim["p2"][0]), min(dim["p1"][1], dim["p2"][1])
    x1, y1 = max(dim["p1"][0], dim["p2"][0]), max(dim["p1"][1], dim["p2"][1])
    if dim.get("type") in ("dia", "rad") or abs(x1 - x0) >= abs(y1 - y0):
        return "left" if (x0 + x1) / 2 < (ref[0] + ref[2]) / 2 else "right"
    return "bottom" if (y0 + y1) / 2 < (ref[1] + ref[3]) / 2 else "top"


def _target_matches_dim(target, dim, obs):
    if target.kind == "cyl":
        geom = [v for v in (dim.get("value"), dim.get("measured")) if v is not None]
        return (
            _diameterish(dim)
            and any(abs(v - target.value) <= TOL for v in geom)
            and (target.side is None or _dim_side(dim, obs) == target.side)
        )
    if target.kind == "value":
        ann = dim.get("value") if dim.get("value") is not None else dim.get("measured")
        return (
            ann is not None
            and abs(ann - target.value) <= TOL
            and (target.side is None or _dim_side(dim, obs) == target.side)
        )
    return True


def _dim_has_fit(dim, fit):
    fit = str(fit).upper()
    tol = dim.get("tolerance") or {}
    if tol.get("kind") == "fit":
        return str(tol.get("code") or "").upper() == fit  # the semantic fit is authoritative
    if str(dim.get("tol") or "").upper() == fit:
        return True
    return fit in (str(dim.get("text") or "") + str(dim.get("suffix") or "")).upper()


def _face_side(name):
    low = str(name).lower()
    for side in ("left", "right", "top", "bottom", "front", "back"):
        if side in low:
            return side
    return low


def _side_of_box(box, ref):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    midx, midy = (ref[0] + ref[2]) / 2, (ref[1] + ref[3]) / 2
    if abs(cx - midx) >= abs(cy - midy):
        return "left" if cx < midx else "right"
    return "bottom" if cy < midy else "top"


def _prim_bbox(prims):
    from .layout import prims_bbox

    try:
        return prims_bbox(list(prims))
    except Exception:  # noqa: BLE001 - unmeasurable prims simply do not bind a face
        return None


def _ref_matches_side(obs, ref, side, view=None):
    """A PMI target matches a named face when its referenced geometry sits on that side."""
    if side in (None, "any", "surface"):
        return True
    if not ref:
        return False  # a named face must have a resolvable reference
    d = obs.get("_d")
    if d is None or ref not in d._els:
        return False
    el = d._els[ref]
    box = _prim_bbox(getattr(el, "_prims", ()))
    if box is None:
        return False
    view_els = [
        e
        for e in d._els.values()
        if e.kind in ("edge", "feature") and (view is None or e._intent.get("view") == view)
    ]
    ebox = _prim_bbox([pr for e in view_els for pr in getattr(e, "_prims", ())])
    if ebox is None:
        return False
    return _side_of_box(tuple(box), tuple(ebox)) == side


def observed(d):
    """The semantic facts of a built drawing that expect.py may match against."""
    dims, datums, gtols, roughs, texts, views, sections = [], [], [], [], [], [], []
    for e in d._els.values():
        i = e._intent
        if e.kind == "dim":
            vals = [v for v in (i.get("value"), i.get("measured")) if v is not None]
            dims.append(
                {
                    "id": e.id,
                    "type": i.get("type"),
                    "values": vals,
                    "value": i.get("value"),
                    "measured": i.get("measured"),
                    "prefix": i.get("prefix") or "",
                    "text": i.get("text") or "",
                    "suffix": i.get("suffix") or "",
                    "tol": i.get("tol"),
                    "tolerance": i.get("tolerance"),
                    "designation": i.get("designation"),
                    "view": i.get("view"),
                    "p1": i.get("p1"),
                    "p2": i.get("p2"),
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
                    "view": i.get("view"),
                    "default": bool(i.get("default")),
                }
            )
        elif e.kind in ("note", "text", "label"):
            texts.append(str(i.get("text") or ""))
        elif e.kind == "view":
            views.append({"id": e.id, "name": i.get("name")})
        elif e.kind == "section":
            sections.append({"id": e.id, "view": i.get("view"), "kind": i.get("kind")})
    return {
        "dims": dims,
        "datums": datums,
        "gtols": gtols,
        "roughs": roughs,
        "texts": texts,
        "views": views,
        "sections": sections,
        "_d": d,
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
