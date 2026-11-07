"""Liner-CAD: a generic 2D engineering-drawing harness for coding agents."""

from importlib.metadata import version as _version

from . import errors

__version__ = _version("linercad")

__all__ = ["__version__", "errors"]
