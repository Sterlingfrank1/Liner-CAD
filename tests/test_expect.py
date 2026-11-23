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

L2 = [c for c in evals.discover(level="L2") if c.get("source") == "3d"]


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
    # renaming the ids (the matcher must not look at them) keeps the same result
    renamed = {}
    for eid, el in list(d._els.items()):
        if el.kind == "dim":
            new = eid + "_renamed"
            el._id = new
            renamed[new] = el
            del d._els[eid]
    d._els.update(renamed)
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


def test_mutation_operators_catch_deleted_dim_and_changed_fit():
    pytest.importorskip("build123d")
    import expect_mutation

    case, d = _one_case()
    mod = case["dir"] / "expect.py"
    loc = expect_mutation.find_mutations(expect.evaluate(mod, d), d, mod)
    assert loc["delete_dim"] and loc["change_fit"]
    assert expect_mutation.run_case(mod, d)["detection_rate"] == 1.0
