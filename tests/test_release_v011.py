"""V1 release acceptance (issue #102): version pinning, release notes and HANDOVER.

G2: this file is committed before the version bump / docs and is expected to fail on main.
"""

import hashlib
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The 33 cards of milestone v0.1.1 (A1 / A3 were closed with PR #69 before the W streams
# started, so they are not part of this table).
CARDS = {
    "E1": 73,
    "E5": 74,
    "E2": 75,
    "C1": 76,
    "C2": 77,
    "C3": 78,
    "C4": 79,
    "E6": 80,
    "E3": 81,
    "E4": 82,
    "D1": 83,
    "D2": 84,
    "D3": 85,
    "D5": 86,
    "D4": 87,
    "D6": 88,
    "D7": 89,
    "A2": 92,
    "A4": 93,
    "B1": 94,
    "B2": 95,
    "B3": 96,
    "B4": 97,
    "B5": 98,
    "B6": 99,
    "B7": 100,
    "F1": 101,
    "V1": 102,
    "H1": 104,
    "H2": 105,
    "H3": 106,
    "H4": 107,
    "E7": 108,
}


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pyproject_and_lock_are_at_0_1_1():
    # v0.1.1+ milestone floor; exact current version is pinned by tests/test_release_v012.py
    project = tomllib.loads(read("pyproject.toml"))
    ver = project["project"]["version"]
    assert tuple(int(p) for p in ver.split("-", 1)[0].split(".")[:3]) >= (0, 1, 1), ver
    lock = tomllib.loads(read("uv.lock"))
    versions = [p["version"] for p in lock["package"] if p["name"] == "linercad"]
    assert versions == [ver], versions


def test_installed_package_reports_the_pyproject_version():
    import linercad

    declared = tomllib.loads(read("pyproject.toml"))["project"]["version"]
    assert linercad.__version__ == declared


def test_release_notes_have_the_required_sections():
    text = read("docs/releases/v0.1.1.md")
    for heading in (
        "## 范围",
        "## 交付",
        "## 安装",
        "## 质量与证据",
        "## 已知缺口",
        "## 与 v0.1.0 的差异",
    ):
        assert heading in text, heading
    for needle in ("v0.1.1", "HANDOVER", "uv sync --extra 3d", "40 / 40", "baseline"):
        assert needle in text, needle


def test_docs_point_at_existing_evidence_files():
    pattern = re.compile(
        r"(?:docs/milestones/v0\.1\.1/|(?:\.\./)+milestones/v0\.1\.1/)?"
        r"evidence/[A-Za-z0-9._-]+\.(?:md|json)"
    )
    evidence_dir = ROOT / "docs/milestones/v0.1.1"
    for rel in ("docs/releases/v0.1.1.md", "docs/milestones/v0.1.1/HANDOVER.md"):
        refs = set(pattern.findall(read(rel)))
        assert refs, rel
        for ref in refs:
            candidates = [(ROOT / rel).parent / ref, evidence_dir / ref, ROOT / ref]
            assert any(path.is_file() for path in candidates), (rel, ref)


def test_handover_lists_all_33_cards_with_issue_numbers():
    text = read("docs/milestones/v0.1.1/HANDOVER.md")
    for card, issue in CARDS.items():
        assert re.search(rf"^\| {card} \|.*#{issue}\b", text, re.MULTILINE), (card, issue)
    rows = re.findall(r"^\| (?:E\d|C\d|D\d|A\d|B\d|H\d|F1|V1) \|", text, re.MULTILINE)
    assert len(rows) == 33, len(rows)


def test_handover_records_deviations_13_to_16_and_the_known_gaps():
    text = read("docs/milestones/v0.1.1/HANDOVER.md")
    for number, evidence in (
        (13, "b3-viewer-violations.md"),
        (14, "d1-radial-leaders.md"),
        (15, "dxf-import.md"),
        (16, "d3-balloon-sequences.md"),
    ):
        assert f"偏离 {number}" in text, number
        assert evidence in text, evidence
    for needle in ("折线", "GB/T 4249", "DEEPSEEK_API_KEY", "402", "ci.yml", "v0.2"):
        assert needle in text, needle


def test_handover_documents_how_to_run_the_gates():
    text = read("docs/milestones/v0.1.1/HANDOVER.md")
    for command in (
        "uv sync --extra 3d",
        "uv run pytest",
        "uv run ruff check",
        "uv run ruff format --check",
        "evals/run.py --baseline",
        "place_scores",
        "--mutation",
    ):
        assert command in text, command


def test_handover_pairs_every_card_with_a_pr_reference():
    text = read("docs/milestones/v0.1.1/HANDOVER.md")
    for card in CARDS:
        row = next(line for line in text.splitlines() if line.startswith(f"| {card} |"))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[0] == card
        if card == "V1":
            assert cells[2] == "本 PR", row
        else:
            assert re.fullmatch(r"#\d+", cells[2]), (card, cells[2])


def test_release_notes_quote_the_final_placement_numbers_with_evidence():
    rel = read("docs/releases/v0.1.1.md")
    handover = read("docs/milestones/v0.1.1/HANDOVER.md")
    evidence = {
        name: read(f"docs/milestones/v0.1.1/evidence/{name}")
        for name in ("d2-multi-layer.md", "d3-balloon-sequences.md", "d5-parts-list.md")
    }
    # Every value printed in the release notes / HANDOVER must be traceable to a card evidence file
    # (D2 for flange / pulley / gear_cover / jack D; D3 or D5 for the assembly A.place values).
    numbers = {
        "flange D": ("0/45", "d2-multi-layer.md"),
        "pulley D": ("0.9756", "d2-multi-layer.md"),
        "pulley D violations": ("2/82", "d2-multi-layer.md"),
        "gear_cover D": ("0/82", "d2-multi-layer.md"),
        "jack D": ("0/30", "d2-multi-layer.md"),
        "jack A": ("0/25", "d3-balloon-sequences.md"),
        "vise D": ("0.9583", "d5-parts-list.md"),
        "vise D violations": ("1/24", "d5-parts-list.md"),
        "vise A": ("0/59", "d5-parts-list.md"),
    }
    for label, (number, source) in numbers.items():
        assert number in rel, (label, number)
        assert number in handover, (label, number)
        assert number in evidence[source], (label, number, source)
    for doc in (rel, handover):
        assert "d2-multi-layer.md" in doc
        assert "d5-parts-list.md" in doc


def test_release_notes_reference_existing_new_modules():
    text = read("docs/releases/v0.1.1.md")
    assert "src/linercad/place.py" in text
    assert "evals/place.py" not in text
    for rel in (
        "src/linercad/place.py",
        "src/linercad/expect.py",
        "evals/mutate.py",
        "evals/known-debt.json",
        "evals/dxf_only.py",
        "evals/dxf_import.py",
        "evals/gtol_coverage.py",
        "evals/expect_mutation.py",
        "evals/place_scores.py",
        "evals/cross_agent.py",
    ):
        assert (ROOT / rel).exists(), rel


def test_no_pending_verification_placeholders_before_merge():
    for rel in (
        "docs/releases/v0.1.1.md",
        "docs/milestones/v0.1.1/HANDOVER.md",
        "docs/milestones/v0.1.1/evidence/v1-g5-cross-agent.md",
    ):
        assert "TBD-V1-" not in read(rel), rel


def test_pending_verification_numbers_use_the_agreed_markers():
    for rel in (
        "docs/releases/v0.1.1.md",
        "docs/milestones/v0.1.1/HANDOVER.md",
        "docs/milestones/v0.1.1/evidence/v1-g5-cross-agent.md",
    ):
        for token in re.findall(r"TBD-[A-Za-z0-9-]+", read(rel)):
            assert token.startswith("TBD-V1-"), (rel, token)


def test_g5_evidence_artifacts_match_the_recorded_numbers():
    ev = "docs/milestones/v0.1.1/evidence/"
    report = json.loads(read(ev + "v1-g5-codex-report.json"))
    rounds = report["codex/tool"]["rounds"]
    assert [(r["round"], r["mode"], r["seconds"], r["steps"]) for r in rounds] == [
        (0, "conversation", 386.5, 78),
        (1, "conversation", 86.0, 14),
    ]
    for row in rounds:
        assert row["check"] == {"errors": 0, "warnings": 0}
    p = report["P"]["modes"]["conversation"]
    assert (p["first_pass_rate"], p["mean_seconds"], p["mean_steps"]) == (1.0, 236.2, 46.0)

    check = json.loads(read(ev + "v1-g5-dsh-check-e3.json"))
    assert check["ok"] is True and check["errors"] == 0 and check["warnings"] == 0
    log = json.loads(read(ev + "v1-g5-dsh-log.json"))
    assert [row["edit"] for row in log["log"]] == ["e3", "e2", "e1", "e0"]
    render = (ROOT / ev / "v1-g5-dsh-final-render-e3.png").read_bytes()
    assert (
        hashlib.sha256(render).hexdigest().upper()
        == "FCA2B9DC6037D7DA462B7EAD1ADDA61501C2BF54ACCDDA72CD2922107940BA30"
    )
    for name in (
        "v1-g5-dsh-final-render-e3.png",
        "v1-g5-mo-tou-final-render.png",
        "v1-g5-mo-tou-compare-stack.png",
    ):
        assert (ROOT / ev / name).is_file(), name

    text = read(ev + "v1-g5-cross-agent.md")
    for needle in (
        "PASS WITH NOTES",
        "#145",
        "#146",
        "#147",
        "1,549,992",
        "1 条 `place_nesting`",
        "④ 整体可读 **4**",
    ):
        assert needle in text, needle


def test_cross_agent_evidence_file_covers_the_card_contract():
    text = read("docs/milestones/v0.1.1/evidence/v1-g5-cross-agent.md")
    for needle in (
        "dsh",
        "Codex",
        "干净 clone",
        "出图评审",
        "uv sync --extra 3d",
        "磨头",
        "回转体",
        "是非题",
        "v0.1.0",
    ):
        assert needle in text, needle
