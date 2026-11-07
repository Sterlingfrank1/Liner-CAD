"""`lcad` command line. Every command prints exactly one JSON object (SPEC §8.3).

Exit codes: 0 success, 1 transaction failed and rolled back, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    sys.stdout.flush()


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse calls this on bad usage
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="lcad", description="Liner-CAD harness CLI")
    p.add_argument("--version", action="store_true", help="print the version as JSON")
    p.add_subparsers(dest="cmd", parser_class=_Parser)
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except UsageError as e:
        emit({"ok": False, "error": {"code": "usage", "message": str(e)}})
        return 2
    if args.version:
        emit({"ok": True, "version": __version__})
        return 0
    emit({"ok": False, "error": {"code": "usage", "message": parser.format_usage().strip()}})
    return 2
