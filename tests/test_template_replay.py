"""PR-2 / R10: baseline revision solidification, model_hash, logo packaging, init replay & undo."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from linercad import commands, runtime, txn, versions
from linercad.errors import LinerError, UndoError

BASE_SRC = (
    "from linercad import Drawing, Param\n"
    'd = Drawing(sheet="A3", std="GB", scale="1:1")\n'
    "P = d.params(\n"
    '    L=Param(100, min=40, max=220, unit="mm", label="长度"),\n'
    '    H=Param(50, min=20, max=120, unit="mm", label="高度"),\n'
    '    W=Param(10, min=4, max=20, unit="mm", label="边距"),\n'
    ")\n"
    'front = d.view("front")\n'
    'front.rect((0, 0), P.L, P.H, name="body")\n'
    'front.dim.linear("L", (0, 0), (P.L, 0), value=P.L, side="bottom")\n'
    'front.dim.linear("H", (0, 0), (0, P.H), value=P.H, side="left")\n'
    'd.title(name="基线模板", drawing_no="LC-R10-01", material="45")\n'
)


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LCAD_TEMPLATES", str(tmp_path / "user-templates"))
    monkeypatch.delenv("LCAD_PROJECT_ROOT", raising=False)


def _cli(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(
        [sys.executable, "-m", "linercad", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=cwd,
    )
    return r.returncode, json.loads(r.stdout)


def _init_part(path: Path, src: str = BASE_SRC) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "drawing.py").write_text(src, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "add", "drawing.py"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "e0 · init"], cwd=path, check=True)
    return path


def test_is_semantic_op_and_filter_keeps_semantic_ops_drops_geometric():
    from linercad.usertemplates import filter_baseline_ops, is_semantic_op

    assert is_semantic_op({"edit": "e1", "op": "accept", "id": "E.front.body.1", "args": {}})
    assert is_semantic_op({"edit": "e1", "op": "general_tol", "id": None, "args": {}})
    assert is_semantic_op({"edit": "e1", "op": "rough_default", "id": None, "args": {}})
    for prefix in (
        "D.L",
        "N.tech.1",
        "G.g1",
        "R.r1",
        "DT.A",
        "T.title.material",
        "A.b1",
        "B.bom",
        "K.c1",
        "V.front",
    ):
        assert is_semantic_op({"edit": "e2", "op": "set", "id": prefix, "args": {}}), prefix
    for non_sem in (
        "E.front.body.1",
        "C.front.b.c",
        "F.front.thr",
        "X.front.s",
        "H.front.h1",
        "S.A",
    ):
        assert not is_semantic_op({"edit": "e2", "op": "move", "id": non_sem, "args": {}}), non_sem

    raw = [
        {"edit": "e1", "op": "place", "id": "D.L", "args": {"side": "top"}},
        {"edit": "e1", "op": "notes.tech", "id": "N.tech.1", "args": {"text": "去毛刺。"}},
        {
            "edit": "e2",
            "op": "accept",
            "id": "overlap",
            "args": {"rule": "overlap", "reason": "ok"},
        },
        {"edit": "e2", "op": "move", "id": "E.front.body.1", "args": {"dx": 1}},
        {"edit": "e2", "op": "move", "id": "C.front.c1", "args": {"dx": 1}},
        {"edit": "e3", "op": "move", "id": "F.front.f1", "args": {"dx": 1}},
        {"edit": "e3", "op": "move", "id": "X.front.x1", "args": {"dx": 1}},
        {"edit": "e3", "op": "move", "id": "H.front.h1", "args": {"dx": 1}},
        {"edit": "e4", "op": "move", "id": "S.A", "args": {"dx": 1}},
    ]
    kept, lines, stats = filter_baseline_ops(raw)
    assert len(kept) == 3 and all(op["edit"] == "e0" for op in kept)
    assert len(lines) == 3 and '"edit":"e0"' in lines[0]
    assert stats["kept"] == 3 and stats["dropped"] == 6
    assert len(stats["dropped_samples"]) == 5


def test_baseline_solidify_model_hash_set_params_undo_e0_e1_and_tag_log(tmp_path):
    from linercad.usertemplates import model_hash

    proj = tmp_path / "proj"
    proj.mkdir()
    src_draw = _init_part(proj / "src-part")
    script = src_draw / ".linercad" / "tmp" / "revise.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "def apply(d):\n"
        '    d["D.L"].place(side="top")\n'
        '    d["T.title.material"].set(text_height=5.0, bold=True, align="left")\n'
        '    d.notes.tech("全部未注倒角 C1。")\n',
        encoding="utf-8",
    )
    assert txn.edit(src_draw, script, "调整尺寸位置、标题栏字体与技术要求")["ok"]

    code, saved = _cli(
        "-C",
        str(src_draw),
        "template",
        "save",
        "part-base",
        "--scope",
        "project",
        "--project",
        str(proj),
        "--tag",
        "r2",
    )
    assert code == 0 and saved["ok"]
    tpl_dir = proj / "lcad-templates" / "part-base"
    assert (tpl_dir / "baseline.actions.jsonl").is_file()
    manifest = saved["template"]
    assert manifest["model_hash"].startswith("sha256:")
    assert "baseline.actions.jsonl" in manifest["files"]
    base_lines = [
        json.loads(ln)
        for ln in (tpl_dir / "baseline.actions.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert len(base_lines) == 3 and all(op["edit"] == "e0" for op in base_lines)

    # Same-parameter instantiation matches model_hash, preserves single actions log, allows undo e1, blocks undo e0
    inst = proj / "inst-same"
    code, out = _cli("-C", str(proj), "init", str(inst), "--from", "part-base")
    assert code == 0 and out["ok"] and out["errors"] == 0
    assert (inst / "drawing.actions.jsonl").is_file()
    assert not (inst / "baseline.actions.jsonl").exists()
    rebuilt = runtime.build(inst)
    assert model_hash(rebuilt.d) == manifest["model_hash"]
    assert rebuilt.d["D.L"].placement["side"] == "top"
    assert rebuilt.d["T.title.material"].text_height == 5.0

    # Commit title includes @r2
    log_entries = versions.log(inst)
    assert log_entries[0]["edit"] == "e0"
    assert log_entries[0]["message"] == "init --from part-base@r2"
    with pytest.raises(UndoError):
        txn.undo(inst, "e0")

    # Follow-up e1 can be undone without wiping e0 baseline
    sc2 = inst / ".linercad" / "tmp" / "m2.py"
    sc2.write_text('def apply(d):\n    d["D.H"].place(side="right")\n', encoding="utf-8")
    assert txn.edit(inst, sc2, "移动 H 到右侧")["ok"]
    diff_res = versions.diff(inst, "e0", "e1")
    assert "D.H" in diff_res["layout_changed"]
    assert txn.undo(inst, "e1")["ok"]
    after_undo = runtime.build(inst)
    assert after_undo.d["D.L"].placement["side"] == "top"
    assert after_undo.d["D.H"].placement["side"] == "left"

    # Untag version init omits '@' in commit title
    saved_untagged = commands.save_template(
        src_draw, "part-notag", scope="project", project=str(proj)
    )
    assert saved_untagged["ok"]
    inst_nt = proj / "inst-notag"
    assert txn.init(inst_nt, from_="part-notag", project=str(proj))["ok"]
    assert versions.log(inst_nt)[0]["message"] == "init --from part-notag"

    # Instantiate 3 different --set parameter combinations: all 0 errors
    for idx, (l_v, h_v, w_v) in enumerate([(80, 40, 8), (140, 75, 12), (200, 110, 16)], 1):
        p_inst = proj / f"param-{idx}"
        code, pout = _cli(
            "-C",
            str(proj),
            "init",
            str(p_inst),
            "--from",
            "part-base",
            "--set",
            f"L={l_v}",
            f"H={h_v}",
            f"W={w_v}",
        )
        assert code == 0 and pout["ok"] and pout["errors"] == 0 and "baseline_warnings" in pout
        chk = commands.check(p_inst)
        assert chk["errors"] == 0


def test_init_model_hash_mismatch_rollback_and_missing_baseline_warning(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    src_draw = _init_part(proj / "src-part")
    assert commands.save_template(src_draw, "hash-tpl", scope="project", project=str(proj))["ok"]
    tpl_dir = proj / "lcad-templates" / "hash-tpl"
    manifest_p = tpl_dir / "template.json"
    doc = json.loads(manifest_p.read_text(encoding="utf-8"))
    doc["model_hash"] = "sha256:0000000000000000"
    manifest_p.write_text(json.dumps(doc), encoding="utf-8")

    # Tampered model_hash with unchanged params MUST fail and roll back new dir
    bad_target = proj / "bad-hash-inst"
    with pytest.raises(LinerError):
        txn.init(bad_target, from_="hash-tpl", project=str(proj))
    assert not bad_target.exists()

    # Missing baseline.actions.jsonl despite manifest declaration warns gracefully
    doc["model_hash"] = None
    doc["files"] = ["drawing.py", "baseline.actions.jsonl"]
    manifest_p.write_text(json.dumps(doc), encoding="utf-8")
    warn_target = proj / "missing-base-inst"
    out = txn.init(warn_target, from_="hash-tpl", project=str(proj))
    assert out["ok"] and any("baseline" in str(w).lower() for w in out["baseline_warnings"])


def test_template_save_packages_logo_assets_and_rejects_external_image(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    src_in = _init_part(
        proj / "logo-in",
        BASE_SRC + 'd.logo("company", path="assets/logo.png", align="left")\n',
    )
    (src_in / "assets").mkdir()
    Image.new("RGBA", (32, 16), (0, 90, 200, 255)).save(src_in / "assets" / "logo.png")
    subprocess.run(["git", "add", "assets"], cwd=src_in, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add assets"], cwd=src_in, check=True)

    saved = commands.save_template(src_in, "with-logo", scope="project", project=str(proj))
    assert saved["ok"] and "assets/logo.png" in saved["template"]["files"]
    assert (proj / "lcad-templates" / "with-logo" / "assets" / "logo.png").is_file()

    inst = proj / "inst-logo"
    out = txn.init(inst, from_="with-logo", project=str(proj))
    assert out["ok"] and out["errors"] == 0
    assert (inst / "assets" / "logo.png").is_file()
    assert txn.dirty_sources(inst) == []

    # External image outside drawing directory MUST be rejected with path before saving
    ext_png = tmp_path / "outside.png"
    Image.new("RGBA", (24, 12), (200, 0, 0, 255)).save(ext_png)
    src_out = _init_part(
        proj / "logo-out",
        BASE_SRC + 'd.logo("company", path="../../outside.png", align="left")\n',
    )
    with pytest.raises(LinerError) as err:
        commands.save_template(src_out, "bad-logo", scope="project", project=str(proj))
    assert "outside.png" in str(err.value.to_dict())
    assert not (proj / "lcad-templates" / "bad-logo").exists()
