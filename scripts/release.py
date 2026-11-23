#!/usr/bin/env python
"""给 Liner-CAD 打版本 tag 并创建 GitHub Release。

一个版本收尾时执行。所有校验通过才会动手，任何一项不过就直接退出、不做改动：

  1. 当前在 main 分支，工作区干净，与 origin/main 一致
  2. pyproject.toml 的 version 与 tag 一致
  3. docs/releases/<tag>.md 存在
  4. tag 在本地和远端都没被占用
  5. main 最新 CI 全绿，且就是当前 commit

用法：
    uv run python scripts/release.py 0.1.1 --dry-run
    uv run python scripts/release.py 0.1.1

规则见 docs/RELEASING.md。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TAG_PATTERN = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
                         r"(?:-(?P<pre>rc|beta|alpha)\.?(?P<pre_num>\d+))?$")
VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


class ReleaseError(RuntimeError):
    """校验或命令执行失败。"""


def normalize_tag(raw: str) -> str:
    """把 0.1.1 / v0.1.1 统一成 v0.1.1，并校验形状。"""
    tag = raw.strip()
    if not tag.startswith("v"):
        tag = "v" + tag
    if not TAG_PATTERN.match(tag):
        raise ReleaseError(f"版本号形状不对：{raw!r}（要 0.1.1 或 v0.1.1 这种）")
    return tag


def read_version(pyproject_text: str) -> str:
    """从 pyproject.toml 文本里取出 version。"""
    match = VERSION_PATTERN.search(pyproject_text)
    if match is None:
        raise ReleaseError("读不到 pyproject.toml 的 version")
    return match.group(1)


def is_prerelease(tag: str) -> bool:
    return "-" in tag


def release_notes_path(tag: str, root: Path = REPO_ROOT) -> Path:
    return root / "docs" / "releases" / f"{tag}.md"


def run(cmd: list[str], *, cwd: Path = REPO_ROOT, capture: bool = False) -> str:
    """跑一条命令；非零退出直接抛错。"""
    result = subprocess.run(
        cmd, cwd=cwd, text=True, encoding="utf-8",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ReleaseError(f"命令失败：{' '.join(cmd)}" + (f"\n{detail}" if detail else ""))
    return (result.stdout or "").strip()


def check_repo_state() -> str:
    """校验分支、工作区、与远端一致，返回当前 commit。"""
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True)
    if branch != "main":
        raise ReleaseError(f"当前在 {branch}，先切到 main 并完成版本 PR 的合并")
    if run(["git", "status", "--porcelain"], capture=True):
        raise ReleaseError("工作区不干净，先提交或 stash")
    run(["git", "fetch", "origin", "--quiet"], capture=True)
    head = run(["git", "rev-parse", "HEAD"], capture=True)
    remote = run(["git", "rev-parse", "origin/main"], capture=True)
    if head != remote:
        raise ReleaseError("本地 main 与 origin/main 不一致，先 git pull --ff-only")
    return head


def check_version(tag: str) -> None:
    """要求 pyproject 的 version 与 tag 一致。"""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = read_version(text)
    if version != tag[1:]:
        raise ReleaseError(
            f"pyproject version={version} 与 tag {tag} 不一致；先改版本号、合并，再发布"
        )


def check_notes(tag: str) -> Path:
    path = release_notes_path(tag)
    if not path.is_file():
        raise ReleaseError(f"缺少发布说明 {path.relative_to(REPO_ROOT)}")
    return path


def check_tag_free(tag: str) -> None:
    """本地和远端都不能已有同名 tag。"""
    local = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
                           cwd=REPO_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if local.returncode == 0:
        raise ReleaseError(f"本地已存在 tag {tag}")
    remote = run(["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"], capture=True)
    if remote:
        raise ReleaseError(f"远端已存在 tag {tag}")


def check_ci(head: str) -> None:
    """main 最新一次 CI 必须成功，且就是当前 commit。"""
    raw = run(["gh", "run", "list", "--branch", "main", "--workflow", "CI", "--limit", "1",
               "--json", "headSha,status,conclusion"], capture=True)
    import json
    runs = json.loads(raw or "[]")
    if not runs:
        raise ReleaseError("查不到 main 的 CI 记录")
    latest = runs[0]
    if latest.get("headSha") != head:
        raise ReleaseError(
            f"main 最新 CI 停在 {str(latest.get('headSha'))[:7]}，不是当前 commit；等它跑完再发布"
        )
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise ReleaseError(
            f"main 最新 CI 未通过：{latest.get('status')}/{latest.get('conclusion')}"
        )


def release_command(tag: str, notes: Path) -> list[str]:
    cmd = ["gh", "release", "create", tag,
           "--title", f"Liner-CAD {tag}",
           "--notes-file", str(notes),
           "--verify-tag"]
    if is_prerelease(tag):
        cmd.append("--prerelease")
    return cmd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="给 Liner-CAD 打版本 tag 并建 GitHub Release")
    parser.add_argument("version", help="版本号，0.1.1 或 v0.1.1")
    parser.add_argument("--dry-run", action="store_true", help="只校验并打印计划，不改仓库、不推送")
    args = parser.parse_args(argv)

    try:
        if shutil.which("gh") is None:
            raise ReleaseError("找不到 gh CLI，先安装并 gh auth login")

        tag = normalize_tag(args.version)
        print(f"> 校验（tag={tag}）")
        head = check_repo_state()
        check_version(tag)
        notes = check_notes(tag)
        check_tag_free(tag)
        check_ci(head)

        message = f"{tag} — 见 docs/releases/{tag}.md"
        cmd = release_command(tag, notes)
        print("> 计划")
        print(f"  commit  : {head}")
        print(f"  notes   : docs/releases/{tag}.md")
        print(f"  commands: git tag -a {tag} -m '{message}'; git push origin {tag}; {' '.join(cmd)}")

        if args.dry_run:
            print("\nDryRun：未做任何改动。")
            return 0

        print("> 创建 annotated tag")
        run(["git", "tag", "-a", tag, "-m", message])
        print("> 推送 tag")
        run(["git", "push", "origin", tag])
        print("> 创建 GitHub Release")
        url = run(cmd, capture=True)
        print(f"\n完成：{tag} -> {url}")
        return 0
    except ReleaseError as exc:
        print(f"X {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
