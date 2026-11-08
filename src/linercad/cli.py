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


COMMANDS = {
    "init": "新建图纸目录：lcad init <dir> [--from <范例>] [--sheet A3]（范例见 lcad skill 的零件族卡片）",
    "build": '重建产物；-m "<原话>" 时提交源文件改动',
    "edit": '事务执行临时脚本：lcad edit <script.py> -m "<用户原话>"',
    "undo": "撤销某一轮：lcad undo eK [-m ...]",
    "context": "图纸摘要，或 lcad context <ID>... 看元素详情",
    "render": "出 PNG 自检：lcad render [--focus ID]",
    "check": "全部检查结果，按规则包分组（drafting / dimensioning / tolerancing / surface / layout）",
    "skill": "打印 SKILL.md，或 lcad skill <零件族> 打印零件族卡片",
    "view": "打开 Viewer（本机 127.0.0.1）：lcad view [--port 8765] [--no-open]",
    "template": '企业档：lcad template import <file.dxf> --name <名> → templates/<名>.toml，Drawing(overlay="<名>") 叠加',
}


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="lcad", description="Liner-CAD harness CLI")
    p.add_argument("--version", action="store_true", help="版本号（JSON）")
    p.add_argument("-h", "--help", action="store_true", help="帮助（JSON）")
    p.add_argument("-C", dest="dir", default=".", help="图纸目录（默认当前目录）")
    sub = p.add_subparsers(dest="cmd", parser_class=_Parser)
    s = sub.add_parser("init")
    s.add_argument("path")
    s.add_argument("--from", dest="from_", default=None)
    s.add_argument("--sheet", default="A3")
    s = sub.add_parser("build")
    s.add_argument("-m", dest="msg", default=None)
    s = sub.add_parser("edit")
    s.add_argument("script")
    s.add_argument("-m", dest="msg", default=None)
    s = sub.add_parser("undo")
    s.add_argument("edit")
    s.add_argument("-m", dest="msg", default=None)
    s = sub.add_parser("context")
    s.add_argument("ids", nargs="*")
    s = sub.add_parser("render")
    s.add_argument("--focus", default=None)
    s.add_argument("-o", dest="out", default=None)
    s.add_argument("--dpi", type=int, default=None)
    sub.add_parser("check")
    s = sub.add_parser("view")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-open", action="store_true")
    s = sub.add_parser("skill")
    s.add_argument("family", nargs="?", default=None)
    s = sub.add_parser("template").add_subparsers(dest="action", parser_class=_Parser)
    s = s.add_parser("import")
    s.add_argument("file")
    s.add_argument("--name", required=True)
    return p


def _usage(message: str) -> int:
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
    from . import commands, txn

    if args.help:
        emit({"ok": True, "help": parser.format_help(), "commands": COMMANDS})
        return 0
    if args.version:
        emit({"ok": True, "version": __version__})
        return 0
    if args.cmd is None:
        return _usage("缺少子命令")
    d = args.dir
    if args.cmd == "init":
        out = txn.init(args.path, args.from_, args.sheet)
    elif args.cmd == "build":
        out = txn.build_commit(d, args.msg)
    elif args.cmd == "edit":
        out = txn.edit(d, args.script, args.msg)
    elif args.cmd == "undo":
        out = txn.undo(d, args.edit, args.msg)
    elif args.cmd == "context":
        out = commands.context(d, args.ids)
    elif args.cmd == "view":
        from .viewer import serve

        serve(d, args.port, not args.no_open)
        return 0
    elif args.cmd == "check":
        out = commands.check(d)
    elif args.cmd == "skill":
        out = commands.skill(args.family)
    elif args.cmd == "template":
        if args.action != "import":
            return _usage("lcad template 只有子命令 import")
        out = commands.template_import(d, args.file, args.name)
    else:
        out = commands.render(d, args.focus, args.out, args.dpi)
    emit(out)
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except UsageError as e:
        return _usage(f"用法错误：{e}")
    try:
        return _run(args, parser)
    except LinerError as e:
        emit(
            {
                "ok": False,
                "rolled_back": args.cmd in ("edit", "undo", "build", "init"),
                "error": e.to_dict(),
            }
        )
        return 1
    except Exception as e:  # the contract is one JSON object, even on bugs
        emit({"ok": False, "error": {"code": "internal", "message": f"{type(e).__name__}: {e}"}})
        return 1
