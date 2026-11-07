"""`lcad` command line. Every command prints exactly one JSON object (SPEC §8.3).

Exit codes: 0 success, 1 transaction failed and rolled back, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .errors import LinerError


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    sys.stdout.flush()


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("add_help", False)
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):  # argparse calls this on bad usage
        raise UsageError(message)


COMMANDS: dict[str, str] = {}  # name -> one-line help; filled as commands are added


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="lcad", description="Liner-CAD harness CLI")
    p.add_argument("--version", action="store_true", help="版本号（JSON）")
    p.add_argument("-h", "--help", action="store_true", help="帮助（JSON）")
    p.add_subparsers(dest="cmd", parser_class=_Parser)
    return p


def _usage(parser, message: str) -> int:
    emit(
        {
            "ok": False,
            "error": {
                "code": "usage",
                "message": message,
                "candidates": sorted(COMMANDS),
                "hint": "lcad --help 查看用法",
            },
        }
    )
    return 2


def _run(args, parser) -> int:
    if args.help:
        emit({"ok": True, "help": parser.format_help(), "commands": COMMANDS})
        return 0
    if args.version:
        emit({"ok": True, "version": __version__})
        return 0
    return _usage(parser, "缺少子命令")


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except UsageError as e:
        return _usage(parser, f"用法错误：{e}")
    try:
        return _run(args, parser)
    except LinerError as e:
        emit({"ok": False, "error": e.to_dict()})
        return 1
    except Exception as e:  # noqa: BLE001 - the contract is one JSON object, even on bugs
        emit({"ok": False, "error": {"code": "internal", "message": f"{type(e).__name__}: {e}"}})
        return 1
