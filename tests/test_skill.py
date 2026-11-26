import re
from importlib import resources

from linercad.cli import COMMANDS


def test_skill_is_short_and_mentions_only_real_commands():
    text = (resources.files("linercad") / "skill" / "SKILL.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 300
    used = set(re.findall(r"lcad ([a-z]+)", text))
    assert used and used <= set(COMMANDS), used - set(COMMANDS)


def test_skill_is_a_router_of_at_most_120_lines_with_pages():
    from linercad import commands

    text = (resources.files("linercad") / "skill" / "SKILL.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 120
    for page in ("api", "viewer", "3d", "assembly", "checks"):
        out = commands.skill(page)
        assert out["ok"] and out["path"] == f"pages/{page}.md"
        used = set(re.findall(r"lcad ([a-z]+)", out["text"]))
        assert used <= set(COMMANDS), (page, used - set(COMMANDS))


def test_skill_install_targets(tmp_path):
    from linercad import commands

    for t in ("claude", "opencode"):
        out = commands.skill_install(t, tmp_path)
        base = ".claude" if t == "claude" else ".opencode"
        assert f"{base}/skills/linercad/SKILL.md" in out["files"]
        assert (tmp_path / base / "skills/linercad/pages/api.md").is_file()
    commands.skill_install("generic", tmp_path)
    assert not (tmp_path / "LINERCAD.md").read_text(encoding="utf-8").startswith("---")
    (tmp_path / "AGENTS.md").write_text("# 我的项目\n\n别动这一段。\n", encoding="utf-8")
    commands.skill_install("codex", tmp_path)
    commands.skill_install("codex", tmp_path)  # idempotent: one section, user text kept
    a = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert a.count(commands.MARK_BEGIN) == 1 and "别动这一段。" in a and "lcad context" in a


def test_skill_install_cli_rejects_unknown_target(tmp_path):
    import json
    import subprocess
    import sys

    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "linercad",
            "skill",
            "install",
            "--target",
            "vim",
            "--dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out = json.loads(r.stdout)
    assert not out["ok"] and "codex" in out["error"]["candidates"]


def test_skill_explains_selection_sync_and_deixis():
    from linercad import commands

    page = commands.skill("viewer")["text"]
    for needle in (
        "复制引用",
        "Ctrl+Alt+C",
        "@D.d1（",
        'lcad context "@sel"',
        "选中的",
        "这个",
        "当前没有有效选中",
        "不要猜",
        "过期",
    ):
        assert needle in page, needle
    main = (resources.files("linercad") / "skill" / "SKILL.md").read_text(encoding="utf-8")
    for needle in ("@sel", "选中的", "那个", "不要猜"):
        assert needle in main, needle


def test_skill_api_documents_user_templates():
    from linercad import commands

    page = commands.skill("api")["text"]
    for needle in (
        "template save",
        "template list",
        "lcad init",
        "--set",
        "从模板起步",
        "LCAD_TEMPLATES",
        "修订层",
    ):
        assert needle in page, needle


def test_skill_install_dsh_writes_to_user_home_idempotently(tmp_path):
    import json
    import os
    import subprocess
    import sys

    home = tmp_path / "home"
    work = tmp_path / "any_work_dir"
    home.mkdir()
    work.mkdir()
    env = {**os.environ, "USERPROFILE": str(home), "HOME": str(home), "PYTHONIOENCODING": "utf-8"}

    def run_install():
        return subprocess.run(
            [sys.executable, "-m", "linercad", "skill", "install", "--target", "dsh"],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    r = run_install()
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["ok"] and out["target"] == "dsh", out
    dest = home / ".agents" / "skills" / "linercad" / "SKILL.md"
    assert dest.is_file()
    packaged = (resources.files("linercad") / "skill" / "SKILL.md").read_text(encoding="utf-8")
    content = dest.read_text(encoding="utf-8")
    assert content.startswith("---") and "name: linercad" in content
    assert content == packaged

    # Idempotent overwrite on re-install (no duplicate files)
    dest.write_text("stale content\n", encoding="utf-8")
    r2 = run_install()
    out2 = json.loads(r2.stdout)
    assert r2.returncode == 0 and out2["ok"]
    assert dest.read_text(encoding="utf-8") == packaged
    assert list(dest.parent.iterdir()) == [dest]


def test_skill_help_lists_dsh():
    import json
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "-m", "linercad", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out = json.loads(r.stdout)
    assert r.returncode == 0 and "dsh" in out["commands"]["skill"]


def test_skill_documents_project_templates_and_trust():
    from linercad import commands

    main_skill = (resources.files("linercad") / "skill" / "SKILL.md").read_text(encoding="utf-8")
    assert len(main_skill.splitlines()) <= 120
    for needle in ("linercad.project.toml", "--scope project", "--tag", "trust"):
        assert needle in main_skill, needle

    api_page = commands.skill("api")["text"]
    for needle in (
        "linercad.project.toml",
        "lcad-templates",
        "--scope project",
        "--project",
        "--tag",
        "baseline.actions.jsonl",
        "--force-probe-fail",
        "--no-probe",
        "trust",
        "当前用户模板",
    ):
        assert needle in api_page, needle
