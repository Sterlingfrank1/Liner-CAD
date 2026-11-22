"""Shared pytest setup.

H3: tests and CI never auto-start a background Viewer or open a browser. Explicit autostart tests
remove this variable locally.
"""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _no_auto_viewer():
    old = os.environ.get("LCAD_NO_VIEW")
    os.environ["LCAD_NO_VIEW"] = "1"
    yield
    if old is None:
        os.environ.pop("LCAD_NO_VIEW", None)
    else:
        os.environ["LCAD_NO_VIEW"] = old


@pytest.fixture(autouse=True, scope="session")
def _isolated_user_templates(tmp_path_factory):
    """H2: never read/write the machine's real user template directory during tests."""
    old = os.environ.get("LCAD_TEMPLATES")
    os.environ["LCAD_TEMPLATES"] = str(tmp_path_factory.mktemp("user-templates"))
    yield
    if old is None:
        os.environ.pop("LCAD_TEMPLATES", None)
    else:
        os.environ["LCAD_TEMPLATES"] = old
