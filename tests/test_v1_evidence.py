"""V1 evidence acceptance (issue #155): timed planetary-gear rerun + Deviation 17."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "docs" / "milestones" / "v0.1.2" / "evidence"


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
    assert r1["lcad_check_errors"] == 0
    assert r1["lcad_check_warnings"] == 0

    r2 = data["run2"]
    assert r2["wall_seconds"] == 623.0
    assert r2["model_turns"] == 35
    assert r2["tool_calls"] == 41
    assert r2["image_reads"] == 4
    assert r2["failed_commands"] == 7
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

    md = md_path.read_text(encoding="utf-8")
    for needle in (
        "跨 harness",
        "偏离 17",
        "18",
        "19",
        "7",
        "286",
        "295",
        "151",
        "96",
        "623",
        "41",
        "2269.6",
        "174",
        "F.front.body",
        "#156",
        "v1-planetary-r2-render.png",
    ):
        assert needle in md, needle
