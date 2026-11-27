"""R16 release acceptance (issue #172): version 0.1.3, release notes, HANDOVER, ROADMAP and README.

RED: committed before the version bump / docs and expected to fail on main.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CARDS = {
    "C1": (164, "#165"),
    "C1b": (166, "#167"),
    "C3": (168, "#169"),
    "C2": (170, "#171"),
    "R16": (172, "本 PR"),
}


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pyproject_lock_and_package_version_are_0_1_3():
    project = tomllib.loads(read("pyproject.toml"))
    assert project["project"]["version"] == "0.1.3"
    lock = tomllib.loads(read("uv.lock"))
    versions = [p["version"] for p in lock["package"] if p["name"] == "linercad"]
    assert versions == ["0.1.3"], versions
    import linercad

    assert linercad.__version__ == "0.1.3"


def test_release_notes_v013_have_required_sections_and_facts():
    text = read("docs/releases/v0.1.3.md")
    assert "file:///" not in text

    for heading in (
        "## 范围",
        "## 交付",
        "## 安装",
        "## 质量与证据",
        "## 已知缺口",
        "## 与 v0.1.2 的差异",
    ):
        assert heading in text, heading

    assert re.search(r"^\| R16 \|.*#172\b", text, re.MULTILINE)

    for needle in (
        "# Liner-CAD v0.1.3 发布说明",
        "--ensure-viewer",
        "--no-viewer",
        "linercad.project.toml",
        "baseline.actions.jsonl",
        "--force-probe-fail",
        "d.logo",
        "title_style_gb",
        "table_style_gb",
        "logo_external_ref",
        "HANDOVER",
        "uv tool install",
        "lcad --version",
        "scripts/release.py 0.1.3",
        "#164",
        "#165",
        "#166",
        "#167",
        "#168",
        "#169",
        "#170",
        "#171",
    ):
        assert needle in text, needle


def test_release_and_handover_evidence_paths_exist():
    pattern = re.compile(
        r"(?:docs/milestones/v0\.1\.3/|(?:\.\./)+milestones/v0\.1\.3/)?"
        r"evidence/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+\.(?:md|json|png)"
    )
    milestone_dir = ROOT / "docs/milestones/v0.1.3"
    for rel in ("docs/releases/v0.1.3.md", "docs/milestones/v0.1.3/HANDOVER.md"):
        content = read(rel)
        assert "file:///" not in content, rel
        refs = set(pattern.findall(content))
        assert refs, rel
        for ref in refs:
            candidates = [(ROOT / rel).parent / ref, milestone_dir / ref, ROOT / ref]
            assert any(path.is_file() for path in candidates), (rel, ref)


def test_handover_v013_lists_all_5_cards_and_gates():
    text = read("docs/milestones/v0.1.3/HANDOVER.md")
    assert "file:///" not in text

    for heading in (
        "## 1. 交付",
        "## 2. 怎么验证",
        "## 3. 5 卡清单与去向",
        "## 4. 验收与证据",
        "## 5. 偏离记录",
        "## 6. 遗留事项与 v0.2 建议",
    ):
        assert heading in text, heading

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
        "uv run pytest",
        "uv run ruff check",
        "uv run ruff format --check",
        "evals/run.py --baseline",
        "evals/mutate.py",
        "uv tool install --force",
        "scripts/release.py 0.1.3",
    ):
        assert needle in text, needle


def test_roadmap_and_readme_updated_for_v013():
    roadmap = read("docs/ROADMAP.md")

    v012_row = next(line for line in roadmap.splitlines() if re.match(r"^\|\s*v0\.1\.2\b", line))
    v012_cells = [cell.strip() for cell in v012_row.strip("|").split("|")]
    assert v012_cells[3] == "完成", v012_cells
    assert v012_cells[4] == "`v0.1.2`", v012_cells

    v013_row = next(line for line in roadmap.splitlines() if re.match(r"^\|\s*v0\.1\.3\b", line))
    v013_cells = [cell.strip() for cell in v013_row.strip("|").split("|")]
    assert v013_cells[0] == "v0.1.3", v013_cells
    assert v013_cells[3] == "完成", v013_cells
    assert v013_cells[4] == "待打（`v0.1.3`）", v013_cells
    assert re.search(r"^\|\s*v0\.1\.3\b.*docs/milestones/v0\.1\.3/HANDOVER\.md", roadmap, re.M)

    readme = read("README.md")
    assert "**v0.1.3**" in readme
    assert "docs/releases/v0.1.3.md" in readme
    assert "## v0.1.3 新增" in readme
    for needle in (
        "--ensure-viewer",
        "linercad.project.toml",
        "d.logo",
        "uv tool install --force",
        "lcad --version",
        "0.1.3",
    ):
        assert needle in readme, needle
