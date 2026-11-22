"""H2: user parameterised templates — save / list / init --from --set."""

import json
import os
import subprocess
import sys

import pytest

from linercad import commands, txn
from linercad.errors import LinerError


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LCAD_TEMPLATES", str(tmp_path / "user-templates"))


@pytest.fixture
def drawing(tmp_path):
    p = tmp_path / "d"
    txn.init(p, from_="shaft")
    return p


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


def test_save_template_writes_manifest_and_list_shows_it(drawing):
    out = commands.save_template(drawing, "my-shaft", "轴类起步模板")
    assert out["ok"] and out["template"]["name"] == "my-shaft"
    params = {p["name"]: p for p in out["template"]["params"]}
    assert params["L"]["value"] and params["L"]["min"] < params["L"]["max"]
    listed = commands.template_list()
    assert [t["name"] for t in listed["templates"]] == ["my-shaft"]
    assert listed["templates"][0]["description"] == "轴类起步模板"


def test_save_template_requires_check_zero_errors(tmp_path):
    # a thread feature without its required dimension is a check error (conv_dim), not a build crash
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "drawing.py").write_text(
        "from linercad import Drawing\n"
        'd = Drawing(sheet="A3", std="GB", scale="1:1")\n'
        'front = d.view("front")\n'
        'front.thread("thr", "M20x1.5", 0, 20, axis=0)\n'
        'd.title(name="未命名零件")\n',
        encoding="utf-8",
    )
    with pytest.raises(LinerError) as err:
        commands.save_template(bad, "bad")
    assert "error" in err.value.message and "conv_dim" not in str(err.value)
    assert commands.template_list()["templates"] == []


def test_save_template_warns_when_the_revision_layer_exists(drawing):
    script = drawing / ".linercad" / "tmp" / "m.py"
    script.write_text('def apply(d):\n    d["D.L"].place(side="top")\n', encoding="utf-8")
    assert txn.edit(drawing, script, "挪")["ok"]
    out = commands.save_template(drawing, "with-actions", "带修订层")
    assert "修订层" in out["warning"] and "不保存" in out["warning"]
    assert "drawing.actions.jsonl" not in out["template"]["files"]


def test_save_template_rejects_builtin_names_and_needs_force(drawing):
    with pytest.raises(LinerError) as err:
        commands.save_template(drawing, "shaft")
    assert "内置范例名" in err.value.message
    commands.save_template(drawing, "mine")
    with pytest.raises(LinerError):
        commands.save_template(drawing, "mine")
    assert commands.save_template(drawing, "mine", force=True)["ok"]


def test_init_from_user_template_with_set_one_shot(tmp_path, drawing):
    commands.save_template(drawing, "shaft-tpl", "轴模板")
    target = tmp_path / "new-shaft"
    code, out = _cli("init", str(target), "--from", "shaft-tpl", "--set", "L=220", "l1=36")
    assert code == 0 and out["ok"] and out["template"] == "shaft-tpl"
    text = (target / "drawing.py").read_text(encoding="utf-8")
    compact = text.replace(" ", "")
    assert "L=Param(220" in compact and "l1=Param(36" in compact
    ctx = commands.context(target)
    values = {p["name"]: p["value"] for p in ctx["params"]}
    assert values["L"] == 220 and values["l1"] == 36
    assert out["errors"] == 0


def test_init_set_unknown_param_fails_and_rolls_back(tmp_path, drawing):
    commands.save_template(drawing, "tpl-rollback")
    target = tmp_path / "rolled"
    code, out = _cli("init", str(target), "--from", "tpl-rollback", "--set", "NOPE=1")
    assert code == 1 and not out["ok"]
    assert "NOPE" in out["error"]["message"]
    assert not (target / "drawing.py").exists()


def test_init_unknown_template_lists_examples_and_user_templates(tmp_path, drawing):
    commands.save_template(drawing, "known-tpl")
    code, out = _cli("init", str(tmp_path / "x"), "--from", "missing-tpl")
    assert code == 1 and "missing-tpl" in out["error"]["message"]
    assert "shaft" in out["error"]["candidates"] and "known-tpl" in out["error"]["candidates"]


def test_template_list_empty_is_ok():
    out = commands.template_list()
    assert out["ok"] and out["templates"] == [] and out["home"]


def test_template_copies_model_py_and_init_without_set(tmp_path, drawing):
    (drawing / "model.py").write_text("# 3D 来源占位\n", encoding="utf-8")
    commands.save_template(drawing, "with-model", "含 model.py")
    target = tmp_path / "from-model"
    code, out = _cli("init", str(target), "--from", "with-model")
    assert code == 0 and out["ok"] and out.get("template") == "with-model"
    assert (target / "model.py").is_file() and (target / "drawing.py").is_file()


def test_template_list_cli(tmp_path, drawing):
    commands.save_template(drawing, "cli-list-tpl", "CLI 列出")
    code, out = _cli("template", "list")
    assert code == 0 and out["ok"]
    assert [t["name"] for t in out["templates"]] == ["cli-list-tpl"]


def test_init_from_user_template_rejects_sheet_override(tmp_path, drawing):
    commands.save_template(drawing, "sheet-fixed")
    code, out = _cli("init", str(tmp_path / "s"), "--from", "sheet-fixed", "--sheet", "A4")
    assert code == 1 and "--sheet" in out["error"]["message"]


def test_init_set_rejects_non_finite_values(tmp_path, drawing):
    commands.save_template(drawing, "finite-tpl")
    for raw in ("nan", "inf", "-inf"):
        code, out = _cli(
            "init",
            str(tmp_path / f"nf-{raw.replace('-', 'm')}"),
            "--from",
            "finite-tpl",
            "--set",
            f"L={raw}",
        )
        assert code == 1 and "有限" in out["error"]["message"], (raw, out)


def test_init_template_name_cannot_escape_the_template_root(tmp_path):
    code, out = _cli("init", str(tmp_path / "esc"), "--from", "../escape")
    assert code == 1 and "没有范例或用户模板" in out["error"]["message"]
    assert out["error"]["candidates"]  # lists the real templates, not the escaped path
    assert not (tmp_path / "esc" / "drawing.py").exists()


def test_set_unknown_parameter_lists_template_params(tmp_path, drawing):
    commands.save_template(drawing, "cand-tpl")
    code, out = _cli("init", str(tmp_path / "cand"), "--from", "cand-tpl", "--set", "NOPE=1")
    assert code == 1 and {"L", "l1"} & set(out["error"]["candidates"])


def test_save_template_name_is_normalized(drawing):
    out = commands.save_template(drawing, "  foo  ")
    assert out["template"]["name"] == "foo"
    assert out["path"].endswith(os.sep + "foo")


def test_cli_help_mentions_template_commands_and_set():
    from linercad.cli import COMMANDS

    assert "save" in COMMANDS["template"] and "list" in COMMANDS["template"]
    assert "--set" in COMMANDS["init"]
