"""scripts/release.py 的纯函数测试（发布脚本不参与打包，也不在这里跑真发布）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release.py"


@pytest.fixture(scope="module")
def release():
    spec = importlib.util.spec_from_file_location("liner_cad_release_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_tag_adds_prefix(release):
    assert release.normalize_tag("0.1.1") == "v0.1.1"


def test_normalize_tag_keeps_existing_prefix(release):
    assert release.normalize_tag("v0.2.0-rc1") == "v0.2.0-rc1"


@pytest.mark.parametrize("bad", ["1.2", "v0.1", "latest", "v0.1.1-rc"])
def test_normalize_tag_rejects_bad_shape(release, bad):
    with pytest.raises(release.ReleaseError):
        release.normalize_tag(bad)


def test_read_version(release):
    assert release.read_version('name = "linercad"\nversion = "0.1.1"\n') == "0.1.1"


def test_read_version_missing_raises(release):
    with pytest.raises(release.ReleaseError):
        release.read_version('name = "linercad"\n')


def test_is_prerelease(release):
    assert release.is_prerelease("v0.2.0-rc1")
    assert not release.is_prerelease("v0.2.0")


def test_release_command_marks_prerelease(release, tmp_path):
    cmd = release.release_command("v0.2.0-rc1", tmp_path / "notes.md")
    assert "--prerelease" in cmd
    assert "v0.2.0-rc1" in cmd
    assert "--verify-tag" in cmd


def test_release_command_stable_has_no_prerelease(release, tmp_path):
    assert "--prerelease" not in release.release_command("v0.2.0", tmp_path / "notes.md")
