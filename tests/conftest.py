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
