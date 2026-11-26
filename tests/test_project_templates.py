"""PR-2 / R9: project-level templates, root marker resolution, tag, dry-run, list & lookup."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from linercad import commands, txn
from linercad.errors import LinerError

SIMPLE_DRAWING = (
    "from linercad import Drawing, Param\n"
    'd = Drawing(sheet="A3", std="GB", scale="1:1")\n'
    'P = d.params(L=Param(100, min=40, max=200, unit="mm", label="长度"), '
    'H=Param(50, min=20, max=100, unit="mm", label="高度"))\n'
    'front = d.view("front")\n'
    'front.rect((0, 0), P.L, P.H, name="body")\n'
    'front.dim.linear("L", (0, 0), (P.L, 0), value=P.L, side="bottom")\n'
    'front.dim.linear("H", (0, 0), (0, P.H), value=P.H, side="left")\n'
    'd.title(name="测试件", drawing_no="LC-T-01", material="45")\n'
)


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LCAD_TEMPLATES", str(tmp_path / "user-templates"))
    monkeypatch.delenv("LCAD_PROJECT_ROOT", raising=False)


def _make_drawing(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "drawing.py").write_text(SIMPLE_DRAWING, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "add", "drawing.py"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "e0 · init"], cwd=path, check=True)
    return path


def _cli(*args, cwd=None, env=None):
    merged = dict(os.environ)
    merged["PYTHONIOENCODING"] = "utf-8"
    if env:
        merged.update(env)
    r = subprocess.run(
        [sys.executable, "-m", "linercad", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=merged,
        cwd=cwd,
    )
    return r.returncode, json.loads(r.stdout)


def test_project_root_precedence_cli_env_marker_parent(tmp_path, monkeypatch):
    from linercad.project import MARKER, resolve_project

    cli_root = tmp_path / "cli-root"
    env_root = tmp_path / "env-root"
    mark_root = tmp_path / "marked-root"
    cli_root.mkdir()
    env_root.mkdir()
    mark_root.mkdir()
    (mark_root / MARKER).write_text('version = 1\n[templates]\ndir = "lcad-templates"\n')

    draw = _make_drawing(mark_root / "parts" / "p1")
    monkeypatch.setenv("LCAD_PROJECT_ROOT", str(env_root))

    # 1. --project wins over LCAD_PROJECT_ROOT and upward marker
    ctx = resolve_project(draw, project=cli_root, allow_create=True)
    assert ctx is not None and ctx.root == cli_root.resolve() and ctx.resolved_by == "cli"

    # 2. LCAD_PROJECT_ROOT wins over upward marker
    ctx = resolve_project(draw, allow_create=True)
    assert ctx is not None and ctx.root == env_root.resolve() and ctx.resolved_by == "env"

    # 3. Upward marker (skips drawing's own .git)
    monkeypatch.delenv("LCAD_PROJECT_ROOT")
    ctx = resolve_project(draw, allow_create=False)
    assert ctx is not None and ctx.root == mark_root.resolve() and ctx.resolved_by == "marker"

    # 4. Ancestor .git stops upward search AFTER checking that .git dir
    outer = tmp_path / "outer"
    inner_repo = outer / "inner-repo"
    outer.mkdir()
    inner_repo.mkdir()
    (outer / MARKER).write_text('version = 1\n[templates]\ndir = "lcad-templates"\n')
    (inner_repo / ".git").mkdir()
    draw2 = _make_drawing(inner_repo / "sub" / "d2")
    assert resolve_project(draw2, allow_create=False) is None
    # With allow_create=True inside drawing dir, fallback is drawing.parent (never inside draw2!)
    fb = resolve_project(draw2, allow_create=True)
    assert fb is not None and fb.root == draw2.parent.resolve() and fb.resolved_by == "fallback"
    assert not str(fb.root).startswith(str(draw2.resolve()))

    # Marker living in the SAME directory as ancestor .git IS found before stopping
    (inner_repo / MARKER).write_text('version = 1\n[templates]\ndir = "lcad-templates"\n')
    ctx_same = resolve_project(draw2, allow_create=False)
    assert ctx_same is not None and ctx_same.root == inner_repo.resolve()


def test_iron_rule_never_create_marker_inside_drawing_dir_or_drive_root(tmp_path):
    from linercad.project import MARKER, resolve_project

    draw = _make_drawing(tmp_path / "my-drawing")
    with pytest.raises(LinerError):
        resolve_project(draw, project=draw, allow_create=True)

    drive_root = Path(draw.resolve().anchor)
    if not (drive_root / MARKER).is_file():
        with pytest.raises(LinerError):
            resolve_project(draw, project=drive_root, allow_create=True)

    with pytest.raises(LinerError):
        commands.save_template(draw, "x", scope="user", project=str(tmp_path))


def test_dry_run_and_scope_project_save_with_tag_and_no_git_tag(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    draw = _make_drawing(proj / "draw1")

    # --dry-run creates NO marker or template directory
    code, dry = _cli(
        "-C",
        str(draw),
        "template",
        "save",
        "flange-std",
        "--scope",
        "project",
        "--project",
        str(proj),
        "--tag",
        "r1",
        "--dry-run",
    )
    assert code == 0 and dry["ok"] and dry["dry_run"] is True
    assert dry["scope"] == "project"
    assert dry["will_create_marker"] is True
    assert not (proj / "linercad.project.toml").exists()
    assert not (proj / "lcad-templates").exists()

    # Real save creates marker, lcad-templates/<name>, schema=2 manifest with tag, and NO git tag
    code, saved = _cli(
        "-C",
        str(draw),
        "template",
        "save",
        "flange-std",
        "--scope",
        "project",
        "--project",
        str(proj),
        "--tag",
        "r1",
    )
    assert code == 0 and saved["ok"]
    assert saved["scope"] == "project"
    assert (proj / "linercad.project.toml").is_file()
    tpl_dir = proj / "lcad-templates" / "flange-std"
    assert (tpl_dir / "drawing.py").is_file()
    manifest = json.loads((tpl_dir / "template.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == 2 and manifest["tag"] == "r1"
    assert "kind" not in manifest
    assert isinstance(manifest["source"], dict) and manifest["source"]["dir"]
    # Neither linercad.project.toml nor git tag lives inside drawing dir; no git tag created in proj
    assert not (draw / "linercad.project.toml").exists()
    assert not (draw / "lcad-templates").exists()
    tags = subprocess.run(["git", "tag"], cwd=proj, capture_output=True, text=True).stdout.strip()
    assert tags == ""


def test_lookup_precedence_project_over_user_over_example_and_list_fields(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    draw = _make_drawing(proj / "src-draw")

    # Save identical name into BOTH user and project with distinguishable titles/descriptions
    assert (
        _cli("-C", str(draw), "template", "save", "shared-tpl", "--scope", "user", "--tag", "u1")[0]
        == 0
    )
    # Modify title so project copy is distinct
    (draw / "drawing.py").write_text(
        SIMPLE_DRAWING.replace('name="测试件"', 'name="项目版"'), encoding="utf-8"
    )
    assert (
        _cli(
            "-C",
            str(draw),
            "template",
            "save",
            "shared-tpl",
            "--scope",
            "project",
            "--project",
            str(proj),
            "--tag",
            "p2",
        )[0]
        == 0
    )

    code, listed = _cli("-C", str(draw), "template", "list")
    assert code == 0 and listed["ok"]
    assert len(listed["templates"]) == 2
    first, second = listed["templates"]
    assert first["scope"] == "project" and first["tag"] == "p2" and "kind" not in first
    assert first["param_count"] == 2 and "has_baseline" in first and "path" in first
    assert second["scope"] == "user" and second["shadowed"] is True and "kind" not in second

    # init --from selects project scope cleanly
    target = proj / "new-part"
    code, out = _cli("-C", str(proj), "init", str(target), "--from", "shared-tpl")
    assert code == 0 and out["ok"]
    assert out["template"]["scope"] == "project"
    assert out["template"]["tag"] == "p2"
    assert 'name="项目版"' in (target / "drawing.py").read_text(encoding="utf-8")

    # Without explicit --scope/--project inside a marked project, save defaults to project scope
    assert _cli("-C", str(draw), "template", "save", "auto-proj")[1]["scope"] == "project"

    # Outside any project marker, save defaults to user scope without creating any marker
    loose_parent = tmp_path / "loose"
    loose_draw = _make_drawing(loose_parent / "d")
    out_loose = commands.save_template(loose_draw, "auto-user")
    assert out_loose["scope"] == "user"
    assert not (loose_parent / "linercad.project.toml").exists()
    txn_ex = txn.init(tmp_path / "ex-init", from_="shaft")
    assert txn_ex["template"]["scope"] == "example" and txn_ex["template"]["trust"] == "builtin"
