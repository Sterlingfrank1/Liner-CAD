"""F1 docs sync: README / skill / PLAN deviation records for v0.1.1."""

import re
from importlib import resources
from pathlib import Path

from linercad import commands

ROOT = Path(__file__).parent.parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_readme_versions_and_v011_capabilities():
    text = read("README.md")
    assert "**v0.1.1**" in text
    for needle in (
        "--dry-run",
        "template save",
        "template list",
        "--no-view",
        "Ctrl+Alt+C",
        "@sel",
        "放射",
        "多层",
        "序号",
        "吸收",
        "识别到的",
        "未命名",
        "fallback",
        "2–12",
    ):
        assert needle in text, needle


def test_readme_cross_agent_wording_follows_the_70_evidence():
    text = read("README.md")
    assert "首图速度取决于 Agent" in text
    assert "Claude" in text and "DeepSeek Harness" in text
    assert "713" in text and "1265" in text  # dsh first drawing range
    assert "修改轮次" in text
    assert "Sonnet" not in text and "V4.1" not in text  # no pinned model versions


def test_plan_records_the_four_f1_deviations():
    text = read("docs/milestones/v0.1.1/PLAN.md")
    for n, card, evidence in (
        (13, "#96", "b3-viewer-violations.md"),
        (14, "#83", "d1-radial-leaders.md"),
        (15, "#79", "dxf-import.md"),
        (16, "#85", "d3-balloon-sequences.md"),
    ):
        item = re.search(rf"^{n}\. \*\*.*?$", text, re.MULTILINE)
        assert item, f"PLAN §9 missing deviation {n}"
        item_text = text[item.start() : item.end() + 600]
        assert card in item_text, (n, card)
        assert evidence in item_text, (n, evidence)


def test_skill_covers_h1_dry_run_and_h3_auto_viewer():
    skill = read("src/linercad/skill/SKILL.md")
    assert "--dry-run" in skill
    assert "试改" in skill
    viewer = read("src/linercad/skill/pages/viewer.md")
    for needle in ("--no-view", "LCAD_NO_VIEW", "CI", "空闲", "opened", "url"):
        assert needle in viewer, needle


def test_skill_checks_page_documents_e1_finding_fields():
    page = read("src/linercad/skill/pages/checks.md")
    for needle in ("measured", "expected", "candidates", "clause", "opportunities"):
        assert needle in page, needle


def test_skill_api_documents_import_layout_and_dry_run():
    page = read("src/linercad/skill/pages/api.md")
    for needle in (
        "--dry-run",
        "inspect",
        "TEXT",
        "MTEXT",
        "HATCH",
        "吸收",
        "放射",
        "多层",
        "corridors",
    ):
        assert needle in page, needle


def test_skill_assembly_documents_d3_ordering():
    page = read("src/linercad/skill/pages/assembly.md")
    for needle in ("旋转方向", "单调", "间距", "交叉", "fallback", "2–12", "BALLOON_PLAN_LIMIT"):
        assert needle in page, needle


def test_b3_evidence_matches_the_current_preview_scenario():
    text = read("docs/milestones/v0.1.1/evidence/b3-viewer-violations.md")
    assert 'PREVIEW_VIOLATION = {"D": 200}' in text
    assert "D2" in text
    assert "历史截图（D=150）" in text  # the remaining D=150 mention is explicitly historical


def test_skill_install_copies_the_packaged_skill_byte_for_byte(tmp_path):
    out = commands.skill_install("claude", tmp_path)
    assert out["ok"]
    installed = tmp_path / ".claude" / "skills" / "linercad"
    src_root = Path(str(resources.files("linercad") / "skill"))
    rels = sorted(p.relative_to(src_root) for p in src_root.rglob("*") if p.is_file())
    assert rels
    for rel in rels:
        target = installed / rel
        assert target.is_file(), rel
        assert target.read_bytes() == (src_root / rel).read_bytes(), rel
