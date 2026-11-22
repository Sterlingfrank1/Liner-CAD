"""Liner-CAD: a generic 2D engineering-drawing harness for coding agents."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from . import catalog, errors, features, place, res  # noqa: F401  (features attaches drawing tools)
from .model import Drawing
from .params import Param

try:
    __version__ = _version("linercad")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.0.0+unknown"

__all__ = ["Drawing", "Param", "__version__", "errors", "res"]
