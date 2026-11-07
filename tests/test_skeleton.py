import json
import subprocess
import sys

import pytest

import linercad
from linercad import errors


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")


def test_version_is_exposed():
    assert linercad.__version__.startswith("0.1")


@pytest.mark.parametrize(
    "cmd",
    [
        ["lcad", "--version"],
        [sys.executable, "-m", "linercad", "--version"],
    ],
)
def test_version_cli_outputs_json(cmd):
    r = run(*cmd)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out == {"ok": True, "version": linercad.__version__}


def test_lcad_and_python_m_are_equivalent():
    a = run("lcad", "--version")
    b = run(sys.executable, "-m", "linercad", "--version")
    assert a.stdout == b.stdout


def test_usage_error_is_json_with_exit_2():
    r = run(sys.executable, "-m", "linercad", "no-such-command")
    assert r.returncode == 2
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert out["error"]["code"] == "usage"


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


def test_error_str_mentions_candidates():
    e = errors.NotFound("找不到元素 D.DD", candidates=["D.D", "D.d1"])
    s = str(e)
    assert "D.DD" in s and "D.D" in s and "D.d1" in s
