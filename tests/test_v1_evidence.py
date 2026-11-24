"""V1 evidence acceptance (issue #155): timed planetary-gear rerun + Deviation 17."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "docs" / "milestones" / "v0.1.2" / "evidence"


def _parse_md_table(md_text: str) -> dict[str, list[str]]:
    rows = {}
    for line in md_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and not cells[0].startswith("---"):
            rows[cells[0]] = cells[1:]
    return rows


def test_gitignore_excludes_tmp_review_and_pytest_dirs():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".tmp-*" in gi.splitlines()


def test_v1_evidence_artifacts_and_unbeautified_metrics():
    json_path = EV / "v1-planetary-rerun.json"
    md_path = EV / "v1-planetary-rerun.md"
    png_path = EV / "v1-planetary-r2-render.png"

    assert json_path.is_file(), json_path
    assert md_path.is_file(), md_path
    assert png_path.is_file(), png_path

    raw_png = png_path.read_bytes()
    assert raw_png.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(raw_png) < 300_000

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["issue"] == 155
    assert data["v013_friction_issue"] == 156
    assert data["deviation"] == 17
    assert "跨 harness" in data["cross_harness_note"]

    r1 = data["run1"]
    assert r1["source_repo_reads"] == 0
    assert r1["wall_seconds"] == 728.0
    assert r1["tool_calls"] == 75
    assert r1["lcad_cmd_invocations"] == sum(r1["lcad_subcommands"].values()) == 45
    assert r1["lcad_shell_calls"] == 37
    assert r1["lcad_check_errors"] == 0
    assert r1["lcad_check_warnings"] == 0

    r2 = data["run2"]
    assert r2["wall_seconds"] == 623.0
    assert r2["model_turns"] == 35
    assert r2["tool_calls"] == 41
    assert r2["image_reads"] == 4
    assert r2["failed_commands"] == 7
    assert r2["lcad_cmd_invocations"] == sum(r2["lcad_subcommands"].values()) == 22
    assert r2["lcad_shell_calls"] == 19
    assert r2["lcad_cmd_seconds"] == 63.0
    assert r2["source_repo_reads"] == 0
    assert r2["init_to_e1_build_calls"] == 18
    assert r2["init_to_e1_incl_png_calls"] == 19
    assert r2["init_to_e1_build_seconds"] == 286.0
    assert r2["init_to_e1_incl_png_seconds"] == 295.0
    assert r2["e1_to_e2_calls"] == 7
    assert r2["e1_to_e2_seconds"] == 151.0
    assert r2["e2_to_e3_calls"] == 7
    assert r2["e2_to_e3_seconds"] == 96.0
    assert r2["lcad_check_errors"] == 0
    assert r2["lcad_check_warnings"] == 0
    assert r2["accept_count"] == 1
    assert (
        r2["tested_skill_sha256"]
        == "A9C1AD22439EB62096B4FCF12AC710116DD02B2E5F159B86B093EEE6BA299F94"
    )
    sl = r2["skill_loading"]
    assert sl["agy_discovered_path"] == "~/.gemini/antigravity-cli/skills/linercad/SKILL.md"
    assert sl["c1_dsh_install_path"] == "~/.agents/skills/linercad/SKILL.md"
    assert sl["sha256"] == r2["tested_skill_sha256"]
    assert sl["hashes_identical_at_run_time"] is True
    assert "harness 路径替代，不影响结论" in sl["note"]
    clar = data["deviation_17"]["post_run2_doc_clarification"]
    assert clar["tested_skill_sha256"] == r2["tested_skill_sha256"]
    assert (
        clar["pr_head_skill_sha256"]
        == "B257208849D635D88CD8248F4745430AC75CE222B4F6BEE1D0B6A3691F3E19DD"
    )
    assert clar["re_run_performed"] is False

    plan_text = (ROOT / "docs" / "milestones" / "v0.1.2" / "PLAN.md").read_text(encoding="utf-8")
    for needle in (
        "## 9. 偏离记录",
        "17.",
        "11.1",
        "Gemini 4 Neon",
        "Gemini 4 Hydrogen",
        "2026-11-24",
        "v0.1.3",
        "286.0",
        "295.0",
        "151.0",
        "96.0",
    ):
        assert needle in plan_text, needle

    skill_text = (ROOT / "src" / "linercad" / "skill" / "SKILL.md").read_text(encoding="utf-8")
    assert 'd.template["frame"]' in skill_text
    assert 'd.template["title_block"]' in skill_text
    assert "GB 档 A3 默认" in skill_text

    md = md_path.read_text(encoding="utf-8")
    assert "Run 2 做到首图一次写全、每次迭代批量脚本、看图 4 次（Run 1 看图 6 次）" in md
    assert "harness 路径替代，不影响结论" in md
    assert clar["pr_head_skill_sha256"] in md
    assert "未单独复跑 V1" in md
    table = _parse_md_table(md)
    assert "2269.6 s" in table["总墙钟时间"][0]
    assert "623.0 s" in table["总墙钟时间"][2]
    assert "148 步 / 174 tool calls" in table["模型轮次 / 工具调用"][0]
    assert "35 turns / 41 tool calls" in table["模型轮次 / 工具调用"][2]
    assert "55 calls / 235.0 s" in table["`lcad` CLI 调用 / 耗时"][0]
    assert "45 invocations" in table["`lcad` CLI 调用 / 耗时"][1]
    assert "22 invocations (19 shell) / 63.0 s" in table["`lcad` CLI 调用 / 耗时"][2]
    assert "60.0%" in table["`lcad` CLI 调用 / 耗时"][3]
    assert table["看图次数（PNG）"][2].startswith("**4 次**")
    assert table["失败命令数"][2] == "**7 次**"
    assert table["**源码读取次数**"][1] == "**0**" and table["**源码读取次数**"][2] == "**0**"
    assert re.search(r"18 calls / 286\.0 s.*19 calls / 295\.0 s", table["**`init → e1`**"][2])
    assert "7 calls / 151.0 s" in table["**`e1 → e2`**（批量修）"][2]
    assert "7 calls / 96.0 s" in table["**`e2 → e3`**"][2]
    assert "4 calls / 33.0 s" in table["**`e3 → e4`**"][2]
    assert "0 error / 0 warning（1 accept）" in table["终态 `lcad check`"][2]

    for needle in ("跨 harness", "偏离 17", "F.front.body", "#156", "v1-planetary-r2-render.png"):
        assert needle in md, needle
