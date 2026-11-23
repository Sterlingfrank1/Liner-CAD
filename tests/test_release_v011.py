"""V1 release acceptance (issue #102): version pinning, release notes and HANDOVER.

G2: this file is committed before the version bump / docs and is expected to fail on main.
"""

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
    project = tomllib.loads(read("pyproject.toml"))
    assert project["project"]["version"] == "0.1.1"
    lock = tomllib.loads(read("uv.lock"))
    versions = [p["version"] for p in lock["package"] if p["name"] == "linercad"]
    assert versions == ["0.1.1"], versions


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
    pattern = re.compile(r"docs/milestones/v0\.1\.1/evidence/[A-Za-z0-9._-]+\.(?:md|json)")
    for rel in ("docs/releases/v0.1.1.md", "docs/milestones/v0.1.1/HANDOVER.md"):
        refs = set(pattern.findall(read(rel)))
        assert refs, rel
        for ref in refs:
            assert (ROOT / ref).is_file(), (rel, ref)


def test_handover_lists_all_33_cards_with_issue_numbers():
    text = read("docs/milestones/v0.1.1/HANDOVER.md")
    for card, issue in CARDS.items():
        assert re.search(rf"^\| {card} \|.*#{issue}\b", text, re.MULTILINE), (card, issue)
    rows = re.findall(
        r"^\| (?:E\d|C\d|D\d|A\d|B\d|H\d|F1|V1) \|", text, re.MULTILINE
    )
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


def test_cross_agent_evidence_file_has_the_g5_sections():
    text = read("docs/milestones/v0.1.1/evidence/v1-g5-cross-agent.md")
    for needle in ("dsh", "Codex", "干净 clone", "出图评审", "uv sync --extra 3d"):
        assert needle in text, needle
