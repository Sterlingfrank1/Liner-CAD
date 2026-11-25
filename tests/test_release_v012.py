"""R1 release acceptance (issue #160): version 0.1.2, release notes, HANDOVER, ROADMAP and README.

G2: committed before the version bump / docs and expected to fail on main.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CARDS = {
    "C1": (151, "#152"),
    "C2": (153, "#154"),
    "V1": (155, "#157"),
    "C3": (158, "#159"),
    "R1": (160, "本 PR"),
}


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pyproject_lock_and_package_version_are_0_1_2():
    project = tomllib.loads(read("pyproject.toml"))
    assert project["project"]["version"] == "0.1.2"
    lock = tomllib.loads(read("uv.lock"))
    versions = [p["version"] for p in lock["package"] if p["name"] == "linercad"]
    assert versions == ["0.1.2"], versions
    import linercad

    assert linercad.__version__ == "0.1.2"


def test_release_notes_v012_have_required_sections_and_v1_numbers():
    text = read("docs/releases/v0.1.2.md")
    for heading in (
        "## 范围",
        "## 交付",
        "## 安装",
        "## 质量与证据",
        "## 已知缺口",
        "## 与 v0.1.1 的差异",
    ):
        assert heading in text, heading

    for needle in (
        "v0.1.2",
        "lcad skill install --target dsh",
        "--png",
        "d.table",
        "table_overflow",
        "HANDOVER",
        "uv tool install",
        "lcad --version",
        "偏离 17",
        "#156",
        "623.0 s",
        "41",
        "2269.6 s",
        "174",
        "跨 harness",
        "18",
        "19",
        "286",
        "295",
        "7",
        "151",
        "96",
        "728.0 s",
        "75",
        "scripts/release.py 0.1.2",
    ):
        assert needle in text, needle


def test_release_and_handover_evidence_paths_exist():
    pattern = re.compile(
        r"(?:docs/milestones/v0\.1\.2/|(?:\.\./)+milestones/v0\.1\.2/)?"
        r"evidence/[A-Za-z0-9._-]+\.(?:md|json|png)"
    )
    milestone_dir = ROOT / "docs/milestones/v0.1.2"
    for rel in ("docs/releases/v0.1.2.md", "docs/milestones/v0.1.2/HANDOVER.md"):
        refs = set(pattern.findall(read(rel)))
        assert refs, rel
        for ref in refs:
            candidates = [(ROOT / rel).parent / ref, milestone_dir / ref, ROOT / ref]
            assert any(path.is_file() for path in candidates), (rel, ref)


def test_handover_v012_lists_all_5_cards_gates_and_deviations():
    text = read("docs/milestones/v0.1.2/HANDOVER.md")
    for card, (issue, pr_ref) in CARDS.items():
        row = next(
            (line for line in text.splitlines() if line.startswith(f"| {card} |")),
            None,
        )
        assert row is not None, f"Missing row for {card}"
        assert f"#{issue}" in row, (card, issue, row)
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[2] == pr_ref, (card, cells)

    for needle in (
        "偏离 17",
        "#156",
        "uv run pytest",
        "uv run ruff check",
        "uv run ruff format --check",
        "evals/run.py --baseline",
        "evals/mutate.py",
        "uv tool install --force",
        "scripts/release.py 0.1.2",
        "623.0 s",
        "41",
        "2269.6 s",
        "174",
        "跨 harness",
    ):
        assert needle in text, needle


def test_roadmap_and_readme_updated_for_v012():
    roadmap = read("docs/ROADMAP.md")
    board_row = next(line for line in roadmap.splitlines() if re.match(r"^\|\s*v0\.1\.2\b", line))
    assert "完成" in board_row and "计划中" not in board_row, board_row
    assert re.search(r"^\|\s*v0\.1\.2\b.*docs/milestones/v0\.1\.2/HANDOVER\.md", roadmap, re.M)

    readme = read("README.md")
    assert "**v0.1.2**" in readme
    assert "docs/releases/v0.1.2.md" in readme
    assert "## v0.1.2 新增" in readme
    for needle in (
        "d.table",
        "--png",
        "lcad skill install --target dsh",
        "uv tool install --force",
        "lcad --version",
    ):
        assert needle in readme, needle
