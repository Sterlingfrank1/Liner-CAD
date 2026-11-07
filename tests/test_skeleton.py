import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import linercad
from linercad import errors

LCAD = shutil.which("lcad", path=str(Path(sys.executable).parent)) or shutil.which("lcad")
ENTRIES = [
    pytest.param([LCAD], id="lcad"),
    pytest.param([sys.executable, "-m", "linercad"], id="python-m"),
]


def run(cmd, *args):
    if cmd[0] is None:
        pytest.skip("lcad entry point not installed")
    r = subprocess.run([*cmd, *args], capture_output=True)
    return r.returncode, r.stdout, r.stderr


def as_json(raw: bytes):
    assert b"\r" not in raw, "stdout must use LF line endings"
    return json.loads(raw.decode("utf-8"))


def test_version_is_exposed():
    assert linercad.__version__.startswith("0.1")


@pytest.mark.parametrize("cmd", ENTRIES)
def test_version_cli_outputs_json(cmd):
    code, out, err = run(cmd, "--version")
    assert code == 0, err
    assert as_json(out) == {"ok": True, "version": linercad.__version__}


@pytest.mark.parametrize("cmd", ENTRIES)
@pytest.mark.parametrize("args", [["no-such-command"], [], ["轴"], ["--ver"]])
def test_usage_errors_are_json_with_exit_2(cmd, args):
    code, out, err = run(cmd, *args)
    assert code == 2
    assert err == b""
    o = as_json(out)
    assert o["ok"] is False
    assert o["error"]["code"] == "usage"
    assert o["error"]["hint"]


@pytest.mark.parametrize("cmd", ENTRIES)
@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_is_json(cmd, flag):
    code, out, err = run(cmd, flag)
    assert code == 0 and err == b""
    o = as_json(out)
    assert o["ok"] is True and "lcad" in o["help"]


@pytest.mark.parametrize(
    "exc,code",
    [
        (errors.NotFound("找不到元素 D.DD", id="D.DD", candidates=["D.D"]), "not_found"),
        (KeyError("x"), "internal"),
    ],
)
def test_main_turns_errors_into_json(monkeypatch, capsys, exc, code):
    from linercad import cli

    def boom(args, parser):
        raise exc

    monkeypatch.setattr(cli, "_run", boom)
    assert cli.main(["--version"]) == 1
    o = json.loads(capsys.readouterr().out)
    assert o["ok"] is False and o["error"]["code"] == code


def test_liner_error_to_dict():
    e = errors.NotFound(
        "找不到元素 D.DD", id="D.DD", candidates=["D.D"], values={"n": 0}, hint="lcad context"
    )
    assert isinstance(e, errors.LinerError)
    assert e.to_dict() == {
        "code": "not_found",
        "message": "找不到元素 D.DD",
        "id": "D.DD",
        "candidates": ["D.D"],
        "values": {"n": 0},
        "hint": "lcad context",
    }


@pytest.mark.parametrize(
    "cls,code",
    [
        ("NotFound", "not_found"),
        ("CountMismatch", "count_mismatch"),
        ("InvalidArgument", "invalid_arg"),
        ("DuplicateId", "duplicate_id"),
        ("ParamError", "param"),
        ("StaleOp", "stale"),
        ("ScriptError", "script"),
        ("BuildError", "build"),
        ("GitError", "git"),
        ("UndoError", "undo"),
        ("NoOps", "no_ops"),
        ("DirtySource", "dirty"),
    ],
)
def test_error_codes(cls, code):
    e = getattr(errors, cls)("x")
    assert e.code == code
    assert e.to_dict()["code"] == code
    assert e.to_dict()["candidates"] == []


def test_error_str_mentions_candidates_and_hint():
    e = errors.NotFound("找不到元素", candidates=["D.D", "D.d1"], hint="用 lcad context")
    s = str(e)
    assert s.startswith("找不到元素")
    tail = s.split("候选", 1)[1]
    assert "D.D" in tail and "D.d1" in tail
    assert "用 lcad context" in s
