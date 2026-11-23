"""E3: expect.py constraint semantics and geometry-signature matching (issue #81)."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "evals"))
sys.path.insert(0, str(REPO / "src"))

import run as evals  # noqa: E402

from linercad import expect  # noqa: E402
from linercad.runtime import build  # noqa: E402

L2 = list(evals.discover(level="L2"))


def _build(case):
    work = Path(tempfile.mkdtemp())
    (work / "drawing.py").write_text(case["drawing_src"], encoding="utf-8")
    for f in Path(case["dir"]).iterdir():
        if f.is_file() and f.suffix in (".py", ".step", ".stp") and f.name != "drawing.py":
            shutil.copy2(f, work / f.name)
    try:
        return build(work).d
    finally:
        shutil.rmtree(work, ignore_errors=True)


pytestmark = pytest.mark.skipif(
    not any((Path(c["dir"]) / "expect.py").exists() for c in L2),
    reason="L2 expect files not generated yet",
)


@pytest.mark.parametrize("case", L2, ids=[c["id"] for c in L2])
def test_reference_drawings_pass_their_expect(case):
    pytest.importorskip("build123d")
    d = _build(case)
    res = expect.evaluate(case["dir"] / "expect.py", d)
    assert res["pass"], [f for f in res["findings"] if f["severity"] == "error"]


def _one_case(case_id="L2/box/bearing_seat"):
    case = next(c for c in L2 if c["id"] == case_id)
    d = _build(case)
    return case, d


def test_every_l2_case_has_an_expect_file():
    for case in L2:
        assert (Path(case["dir"]) / "expect.py").exists(), case["id"]


def test_matching_is_by_geometry_not_element_id():
    pytest.importorskip("build123d")
    case, d = _one_case()
    before = expect.evaluate(case["dir"] / "expect.py", d)
    obs = expect.observed(d)
    assert obs["dims"], "reference drawing has dimensions to match"
    # renaming/reordering the ids (the matcher must not hard-code them) keeps the result;
    # PMI refs are remapped with the ids so the drawing stays semantically valid
    mapping = {eid: eid + "_renamed" for eid, el in d._els.items() if el.kind == "dim"}
    renamed = {}
    for eid, el in list(d._els.items()):
        if el.kind == "dim":
            el._id = mapping[eid]
            renamed[el._id] = el
            del d._els[eid]
    d._els.update(renamed)
    for el in d._els.values():
        ref = el._intent.get("ref")
        if ref in mapping:
            el._intent["ref"] = mapping[ref]
    after = expect.evaluate(case["dir"] / "expect.py", d)
    assert after["pass"] == before["pass"]


def test_missing_required_dimension_is_caught():
    pytest.importorskip("build123d")
    case, d = _one_case()
    refs = expect.referenced_dims(case["dir"] / "expect.py", d)
    assert refs, "the reference expect must reference at least one dimension"
    d._els.pop(refs[0])
    res = expect.evaluate(case["dir"] / "expect.py", d)
    assert not res["pass"]
    assert any(f["rule"] == "expect_dim" for f in res["findings"])


def test_changed_fit_is_caught():
    pytest.importorskip("build123d")
    case, d = _one_case()
    fits = [
        e
        for e in d._els.values()
        if e.kind == "dim" and (e._intent.get("tolerance") or {}).get("kind") == "fit"
    ]
    assert fits, "bearing_seat carries an H7 fit"
    fit = fits[0]
    fit._intent["tolerance"]["code"] = "H8"
    res = expect.evaluate(case["dir"] / "expect.py", d)
    assert not res["pass"]
    assert any(f["rule"] == "expect_dim" for f in res["findings"])


def test_any_of_and_must_should(tmp_path):
    pytest.importorskip("build123d")
    case, d = _one_case()
    mod = tmp_path / "expect.py"
    mod.write_text(
        "def expect(e):\n"
        "    e.view('front')\n"
        "    e.any_of(e.view('left'), e.view('right'))\n"
        "    e.note(contains='不存在的技术要求', must=False)\n",
        encoding="utf-8",
    )
    res = expect.evaluate(mod, d)
    assert res["pass"]  # the should-note is allowed to fail
    assert any(f["severity"] == "warn" for f in res["findings"])
    assert any(f["rule"] == "expect_note" for f in res["findings"])


def test_target_and_value_must_both_match(tmp_path):
    pytest.importorskip("build123d")
    case, d = _one_case()
    bad = tmp_path / "bad.py"
    bad.write_text(
        "def expect(e):\n    e.dim(e.feature(cyl=40), value=41, fit='H7')\n", encoding="utf-8"
    )
    assert not expect.evaluate(bad, d)["pass"]
    good = tmp_path / "good.py"
    good.write_text(
        "def expect(e):\n    e.dim(e.feature(cyl=40), value=40, fit='H7')\n", encoding="utf-8"
    )
    assert expect.evaluate(good, d)["pass"]


def _fit_sides(d):
    obs = expect.observed(d)
    out = {}
    for dim in obs["dims"]:
        if (dim.get("tolerance") or {}).get("kind") == "fit" and dim["type"] == "dia":
            out.setdefault(dim["values"][0] if dim["values"] else None, []).append(
                expect._dim_side(dim, obs)
            )
    return out


def test_boolean_feature_signatures_are_distinct(tmp_path):
    pytest.importorskip("build123d")
    case = next(c for c in L2 if c["id"] == "L2/shaft/pump_shaft")
    d = _build(case)
    sides = _fit_sides(d).get(20.0)
    assert sides and "left" in sides and "right" in sides
    mod = tmp_path / "expect.py"
    mod.write_text(
        "def expect(e):\n"
        "    e.dim(e.feature(cyl=20, where='left'), fit='k6')\n"
        "    e.dim(e.feature(cyl=20, where='right'), fit='k6')\n",
        encoding="utf-8",
    )
    assert expect.evaluate(mod, d)["pass"]
    mod.write_text(
        "def expect(e):\n    e.dim(e.feature(cyl=20, where='right'), fit='k6')\n"
        "    e.dim(e.feature(cyl=20, where='left'), fit='k6')\n",
        encoding="utf-8",
    )
    assert expect.evaluate(mod, d)["pass"]  # order does not matter, side does
    mod.write_text(
        "def expect(e):\n    e.dim(e.feature(cyl=20, where='top'), fit='k6')\n",
        encoding="utf-8",
    )
    assert not expect.evaluate(mod, d)["pass"]


def test_section_semantics_are_checked(tmp_path):
    pytest.importorskip("build123d")
    case = next(c for c in L2 if c["id"] == "L2/disc/gear_blank")
    d = _build(case)
    good = tmp_path / "good.py"
    good.write_text("def expect(e):\n    e.view('front', section='full')\n", encoding="utf-8")
    assert expect.evaluate(good, d)["pass"]
    bad = tmp_path / "bad.py"
    bad.write_text("def expect(e):\n    e.view('front', section='removed')\n", encoding="utf-8")
    assert not expect.evaluate(bad, d)["pass"]


def test_face_binding_follows_the_referenced_geometry(tmp_path):
    pytest.importorskip("build123d")
    case = next(c for c in L2 if c["id"] == "L2/disc/flange")
    d = _build(case)
    obs = expect.observed(d)
    gtols = [g for g in obs["gtols"] if g["char"] == "perpendicularity"]
    assert gtols
    ref = gtols[0]["ref"]
    view = gtols[0]["view"]
    good_side = next(
        side
        for side in ("left", "right", "top", "bottom")
        if expect._ref_matches_side(obs, ref, side, view)
    )
    good = tmp_path / "good.py"
    good.write_text(
        "def expect(e):\n"
        f"    e.gtol('perpendicularity', on=e.face({good_side!r}), datums=['A'], max=0.03)\n",
        encoding="utf-8",
    )
    assert expect.evaluate(good, d)["pass"]
    bad = tmp_path / "bad.py"
    bad.write_text(
        "def expect(e):\n"
        "    e.gtol('perpendicularity', on=e.face('bottom'), datums=['A'], max=0.03)\n",
        encoding="utf-8",
    )
    assert not expect.evaluate(bad, d)["pass"]


def test_every_l2_case_mutation_is_detected():
    pytest.importorskip("build123d")
    import expect_mutation

    for case in L2:
        d = _build(case)
        mod = Path(case["dir"]) / "expect.py"
        rep = expect_mutation.run_case(mod, d)
        assert rep["base_pass"], case["id"]
        assert rep["detection_rate"] == 1.0, (case["id"], rep)


def test_mutation_operators_catch_deleted_dim_and_changed_fit():
    pytest.importorskip("build123d")
    import expect_mutation

    case, d = _one_case()
    mod = case["dir"] / "expect.py"
    loc = expect_mutation.find_mutations(expect.evaluate(mod, d), d, mod)
    assert loc["delete_dim"] and loc["change_fit"]
    assert expect_mutation.run_case(mod, d)["detection_rate"] == 1.0
