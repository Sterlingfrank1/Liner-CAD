"""R1 release acceptance (issue #160): version 0.1.2, release notes, HANDOVER, ROADMAP and README.

G2: committed before the version bump / docs and expected to fail on main.
"""

from __future__ import annotations

import json
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
    ev = json.loads(read("docs/milestones/v0.1.2/evidence/v1-planetary-rerun.json"))
    base = ev["baseline_dsh_deepseek_v4_1_flash"]
    r1 = ev["run1"]
    r2 = ev["run2"]

    for heading in (
        "## 范围",
        "## 交付",
        "## 安装",
        "## 质量与证据",
        "## 已知缺口",
        "## 与 v0.1.1 的差异",
    ):
        assert heading in text, heading

    assert re.search(r"^\| R1 \|.*#160\b", text, re.MULTILINE)

    for needle in (
        "# Liner-CAD v0.1.2 发布说明",
        "lcad skill install --target dsh",
        "--png",
        "d.table",
        "table_overflow",
        "HANDOVER",
        "uv tool install",
        "lcad --version",
        "偏离 17",
        "#156",
        "跨 harness",
        f"{base['wall_seconds']} s",
        f"{base['tool_calls']} tool calls",
        f"{r2['wall_seconds']} s",
        f"`{r2['tool_calls']}` tool calls",
        f"`{r2['init_to_e1_build_calls']}` 步 / `{r2['init_to_e1_build_seconds']} s`",
        f"`{r2['init_to_e1_incl_png_calls']}` 步 / `{r2['init_to_e1_incl_png_seconds']} s`",
        f"`{r2['e1_to_e2_calls']}` 步 / `{r2['e1_to_e2_seconds']} s`",
        f"`{r2['e2_to_e3_calls']}` 步 / `{r2['e2_to_e3_seconds']} s`",
        f"`{r2['e3_to_e4_calls']}` 步 / `{r2['e3_to_e4_seconds']} s`",
        f"看图 **`{r2['image_reads']}` 次**",
        f"源码读取 **`{r2['source_repo_reads']}` 次**",
        f"{r1['wall_seconds']} s",
        f"`{r1['tool_calls']}` tool calls",
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
    ev = json.loads(read("docs/milestones/v0.1.2/evidence/v1-planetary-rerun.json"))
    base = ev["baseline_dsh_deepseek_v4_1_flash"]
    r1 = ev["run1"]
    r2 = ev["run2"]

    for card, (issue, pr_ref) in CARDS.items():
        row = next(
            (line for line in text.splitlines() if line.startswith(f"| {card} |")),
            None,
        )
        assert row is not None, f"Missing row for {card}"
        assert f"#{issue}" in row, (card, issue, row)
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[2] == pr_ref, (card, cells)

    stage_calls = (
        f"{r2['init_to_e1_build_calls']}–{r2['init_to_e1_incl_png_calls']}"
        f" / {r2['e1_to_e2_calls']} / {r2['e2_to_e3_calls']} / {r2['e3_to_e4_calls']}"
    )
    stage_secs = (
        f"{int(r2['init_to_e1_build_seconds'])}–{int(r2['init_to_e1_incl_png_seconds'])}"
        f" / {int(r2['e1_to_e2_seconds'])} / {int(r2['e2_to_e3_seconds'])} / {int(r2['e3_to_e4_seconds'])}"
    )

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
        f"{r2['wall_seconds']} s",
        f"`{r2['tool_calls']}` tool calls",
        f"{base['wall_seconds']} s",
        f"`{base['tool_calls']}` tool calls",
        f"{r1['wall_seconds']} s / {r1['tool_calls']} tool calls",
        stage_calls,
        stage_secs,
        "跨 harness",
    ):
        assert needle in text, needle


def test_roadmap_and_readme_updated_for_v012():
    roadmap = read("docs/ROADMAP.md")
    board_row = next(line for line in roadmap.splitlines() if re.match(r"^\|\s*v0\.1\.2\b", line))
    board_cells = [cell.strip() for cell in board_row.strip("|").split("|")]
    assert board_cells[0] == "v0.1.2", board_cells
    assert board_cells[3] == "完成", board_cells
    assert board_cells[4] == "待打（`v0.1.2`）", board_cells
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
