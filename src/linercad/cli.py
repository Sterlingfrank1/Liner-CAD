"""`lcad` command line. Every command prints exactly one JSON object (SPEC §8.3).

Exit codes: 0 success, 1 transaction failed and rolled back, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from . import __version__
from .errors import InvalidArgument, LinerError


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
    "init": "新建图纸目录：lcad init <dir> [--from <范例|用户模板> | --from-dxf x.dxf] [--sheet A3] [--set 参数=值 …]（范例见 lcad skill 的零件族卡片；用户模板见 lcad template save/list）",
    "build": '重建产物；-m "<原话>" 时提交源文件改动',
    "edit": '事务执行临时脚本：lcad edit <script.py> [-m "<用户原话>"] [--dry-run]；--dry-run 试改不写日志/不提交，只出预览，可省略 -m（真实提交仍需 -m）',
    "undo": "撤销某一轮：lcad undo eK [-m ...]",
    "context": "图纸摘要，或 lcad context <ID>... 看元素详情",
    "render": "出 PNG 自检：lcad render [--focus ID]",
    "check": "全部检查结果，按规则包分组（drafting / dimensioning / tolerancing / surface / layout）",
    "skill": "打印 SKILL.md；lcad skill <页|零件族> 打印分页或零件族卡片；lcad skill install --target claude|codex|opencode|generic|dsh [--dir .] 装进 Agent 的工作目录（dsh 全局装到 ~/.agents/skills/linercad/）",
    "view": "打开 Viewer（本机 127.0.0.1）：lcad view [--port 8765] [--no-open]",
    "log": "版本列表（每次成功修改一条，新的在前）：lcad log",
    "diff": "两个版本的差异：lcad diff e1 e3（编号 / 提交 / HEAD / 标签；缺省 B = 工作区）→ 增删改的 ID + 叠加 SVG",
    "export": "定稿：lcad export --to <目录> [--formats dxf,pdf]，标题栏加修订、提交并打标签 rev-A、rev-B …",
    "inspect": "看一份 DXF：lcad inspect x.dxf → 图层、实体统计、范围、导入映射和一张临时 PNG",
    "template": "模板：lcad template import <file.dxf> --name <名> 生成企业档 templates/<名>.toml；lcad template save <名> [--description …] [--force] 把当前图纸存为用户模板；lcad template list 列出用户模板",
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
    s.add_argument("--from-dxf", dest="from_dxf", default=None)
    s.add_argument("--sheet", default=None)
    s.add_argument(
        "--set",
        dest="set",
        nargs="+",
        default=None,
        metavar="参数=值",
        help="一步改模板参数，如 --set D=6 R=0.5",
    )
    s = sub.add_parser("build")
    s.add_argument("-m", dest="msg", default=None)
    s.add_argument("--no-view", dest="no_view", action="store_true")
    s = sub.add_parser("edit")
    s.add_argument("script")
    s.add_argument("-m", dest="msg", default=None)
    s.add_argument("--dry-run", dest="dry_run", action="store_true")
    s.add_argument("--no-view", dest="no_view", action="store_true")
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
    sub.add_parser("log")
    s = sub.add_parser("diff")
    s.add_argument("a")
    s.add_argument("b", nargs="?", default=None)
    s = sub.add_parser("export")
    s.add_argument("--to", required=True)
    s.add_argument("--formats", default=None)
    s = sub.add_parser("skill")
    s.add_argument("family", nargs="?", default=None)
    s.add_argument("--target", default=None)
    s.add_argument("--dir", default=".")
    s = sub.add_parser("inspect")
    s.add_argument("file")
    ts = sub.add_parser("template").add_subparsers(dest="action", parser_class=_Parser)
    s = ts.add_parser("import")
    s.add_argument("file")
    s.add_argument("--name", required=True)
    s = ts.add_parser("save")
    s.add_argument("name")
    s.add_argument("--description", default="")
    s.add_argument("--force", action="store_true")
    ts.add_parser("list")
    return p


def _parse_sets(pairs):
    """K=V pairs of lcad init --set → {name: number}; bad pairs fail before any directory is made."""
    if not pairs:
        return None
    out = {}
    for pair in pairs:
        k, sep, v = str(pair).partition("=")
        k = k.strip()
        if not sep or not k:
            raise InvalidArgument(f"--set {pair!r} 不是 参数=值", hint="例如 --set D=6 R=0.5")
        if k in out:
            raise InvalidArgument(f"--set 参数 {k!r} 重复")
        try:
            value = float(v)
        except ValueError as e:
            raise InvalidArgument(f"--set {k}={v} 的值不是数字") from e
        if not math.isfinite(value):
            raise InvalidArgument(f"--set {k}={v} 不是有限数字")
        out[k] = value
    return out


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
    from . import commands, txn, versions

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
        sets = _parse_sets(getattr(args, "set", None))
        out = txn.init(args.path, args.from_, args.sheet, args.from_dxf, sets=sets)
    elif args.cmd == "build":
        out = txn.build_commit(d, args.msg)
    elif args.cmd == "edit":
        out = txn.edit(d, args.script, args.msg, dry_run=getattr(args, "dry_run", False))
    elif args.cmd == "undo":
        out = txn.undo(d, args.edit, args.msg)
    elif args.cmd == "context":
        out = commands.context(d, args.ids)
    elif args.cmd == "view":
        from .viewer import serve

        serve(d, args.port, not args.no_open)
        return 0
    elif args.cmd == "log":
        out = {"ok": True, "log": versions.log(d)}
    elif args.cmd == "diff":
        out = versions.diff(d, args.a, args.b)
    elif args.cmd == "export":
        out = versions.export(d, args.to, args.formats)
    elif args.cmd == "check":
        out = commands.check(d)
    elif args.cmd == "skill":
        if args.family == "install":
            out = commands.skill_install(args.target, args.dir)
        else:
            out = commands.skill(args.family)
    elif args.cmd == "inspect":
        out = commands.inspect_dxf(d, args.file)
    elif args.cmd == "template":
        if args.action == "import":
            out = commands.template_import(d, args.file, args.name)
        elif args.action == "save":
            out = commands.save_template(d, args.name, args.description, args.force)
        elif args.action == "list":
            out = commands.template_list()
        else:
            return _usage("lcad template 有子命令 import / save / list")
    else:
        out = commands.render(d, args.focus, args.out, args.dpi)
    # H3: the first successful build / edit starts the background Viewer and opens it once; an
    # already running Viewer is only refreshed (the page polls). --no-view / LCAD_NO_VIEW / CI off.
    if args.cmd in ("build", "edit") and out.get("ok") and not getattr(args, "dry_run", False):
        try:
            from .viewer import autostart

            state = autostart(d, disabled=bool(getattr(args, "no_view", False)))
        except Exception as e:  # noqa: BLE001 - a Viewer problem must not fail the transaction
            state = {"url": None, "opened": False, "error": f"{type(e).__name__}: {e}"}
        if state is not None:
            out["viewer"] = state
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
                "rolled_back": args.cmd in ("edit", "undo", "build", "init", "export"),
                "error": e.to_dict(),
            }
        )
        return 1
    except Exception as e:  # the contract is one JSON object, even on bugs
        emit({"ok": False, "error": {"code": "internal", "message": f"{type(e).__name__}: {e}"}})
        return 1
