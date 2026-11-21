"""Fixtures for the visual verification tests: real drawings, built once per module."""

from __future__ import annotations

import pytest

from linercad import txn
from linercad.runtime import build

EXAMPLES = ["shaft", "flange"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """{name: (drawing dir, BuildResult)} for a couple of real sheets (A3, frame, dims, PMI)."""
    out = {}
    for name in EXAMPLES:
        p = tmp_path_factory.mktemp(name) / name
        txn.init(p, from_=name)
        out[name] = (p, build(p))
    return out
