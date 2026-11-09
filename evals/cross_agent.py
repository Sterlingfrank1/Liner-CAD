"""Cross-agent evaluation (SPEC M3 §1.8): Codex and Claude with only the installed skill, and a
bare-ezdxf baseline, on the same requirement texts (evals/cross/tasks.toml).

    python evals/cross_agent.py setup --root R --clone C      # venv with linercad[3d] from clone C
    python evals/cross_agent.py run --root R --agent codex|claude|baseline --task box [--rounds 3]
    python evals/cross_agent.py score --root R --out report.json

Each (agent, task) gets R/<agent>/<task>/ outside any repo; ``lcad`` comes from R/venv. Every round
is a fresh non-interactive invocation (like a user coming back), output kept in round-<k>.log.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = tomllib.loads((HERE / "cross" / "tasks.toml").read_text(encoding="utf-8"))["task"]
TIMEOUT = 20 * 60

HARNESS = (
    "你是用户的编码助手。工作目录就是当前目录。命令 `lcad`（Liner-CAD 工程图工具）已在 PATH 上；"
    "怎么用只看{doc}，以及 `lcad skill <页>`。图纸目录固定为 ./drawing（第一次用 `lcad init drawing` 或"
    "从合适的范例 `lcad init drawing --from <范例>` 建）。不要读取 linercad 包的源代码。"
    "完成后用不超过 5 行说明做了什么。\n\n用户请求：{req}"
)
BASELINE = (
    "你是用户的编码助手。工作目录就是当前目录。只能用 Python 和 ezdxf（已安装，`python` 可用）。"
    "写 / 修改脚本 make.py，运行它生成 ./drawing.dxf（GB 制图习惯：图框、标题栏、粗细线型分图层、"
    "尺寸必须用 ezdxf 的原生 DIMENSION 实体（add_linear_dim / add_diameter_dim 等）并 render()）。"
    "完成后用不超过 5 行说明做了什么。\n\n用户请求：{req}"
)


def env(root):
    e = dict(os.environ)
    scripts = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
    e["PATH"] = str(scripts) + os.pathsep + e["PATH"]
    e["PYTHONUTF8"] = "1"
    e["MPLCONFIGDIR"] = str(root / "mpl")
    return e


def setup(root, clone):
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["uv", "venv", str(root / "venv"), "--python", "3.13"], check=True)
    py = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(["uv", "pip", "install", "--python", str(py), f"{clone}[3d]"], check=True)


def exe(root, name):
    """Full path of a command as found on the eval PATH (Windows .exe/.cmd shims included)."""
    found = shutil.which(name, path=env(root)["PATH"])
    if not found:
        raise SystemExit(f"{name} not found on PATH")
    return found


def workdir(root, agent, task):
    w = root / agent / task["id"]
    if not w.exists():
        w.mkdir(parents=True)
        target = {"codex": "codex", "claude": "claude"}.get(agent)
        if target:
            subprocess.run(
                [exe(root, "lcad"), "skill", "install", "--target", target, "--dir", str(w)],
                check=True,
                env=env(root),
                capture_output=True,
            )
    return w


def invoke(agent, w, prompt, root, log):
    if agent == "codex":
        cmd = [
            exe(root, "codex"),
            "exec",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-C",
            str(w),
            "-o",
            str(log.with_suffix(".last.txt")),
            "-",
        ]
    else:  # claude and baseline: same CLI, same model
        cmd = [
            exe(root, "claude"),
            "-p",
            "--model",
            "sonnet",
            "--permission-mode",
            "bypassPermissions",
            "--output-format",
            "json",
            "--setting-sources",
            "project",
        ]
    t = time.time()
    try:
        r = subprocess.run(
            cmd,
            input=prompt,
            cwd=w,
            env=env(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT,
        )
        out, code = r.stdout + "\n--- stderr ---\n" + r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        out, code = f"TIMEOUT {e}", -1
    log.write_text(out, encoding="utf-8")
    return {"code": code, "seconds": round(time.time() - t, 1)}


def run(root, agent, tid, rounds, start=0):
    task = next(t for t in TASKS if t["id"] == tid)
    w = workdir(root, agent, task)
    reqs = [task["first"], *task["rounds"][:rounds]]
    prev = w / "runs.json"
    res = json.loads(prev.read_text(encoding="utf-8"))[:start] if start and prev.exists() else []
    for k, req in enumerate(reqs):
        if k < start:
            continue
        if agent == "baseline":
            prompt = BASELINE.format(req=req)
        else:
            doc = "AGENTS.md" if agent == "codex" else ".claude/skills/linercad/SKILL.md"
            prompt = HARNESS.format(doc=doc, req=req)
        r = invoke("codex" if agent == "codex" else "claude", w, prompt, root, w / f"round-{k}.log")
        res.append({"round": k, **r})
        (w / "runs.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return res


def lcad(root, *args, cwd=None):
    r = subprocess.run(
        [exe(root, "lcad"), *args],
        cwd=cwd,
        env=env(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"ok": False, "raw": r.stdout[-2000:] + r.stderr[-2000:]}


def score(root):
    out = {}
    for agent in ("codex", "claude", "baseline"):
        for task in TASKS:
            w = root / agent / task["id"]
            if not w.exists():
                continue
            runs = (
                json.loads((w / "runs.json").read_text(encoding="utf-8"))
                if (w / "runs.json").exists()
                else []
            )
            rec = {"rounds": runs}
            if agent == "baseline":
                dxf = w / "drawing.dxf"
                imp = w / "_imported"
                shutil.rmtree(imp, ignore_errors=True)
                rec["init"] = (
                    lcad(root, "init", str(imp), "--from-dxf", str(dxf))
                    if dxf.exists()
                    else {"ok": False, "error": "no drawing.dxf"}
                )
                d = imp
            else:
                d = w / "drawing"
                git = subprocess.run(
                    ["git", "log", "--format=%s"],
                    cwd=d if d.exists() else w,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                rec["commits"] = git.stdout.splitlines()
            if d.exists():
                chk = lcad(root, "-C", str(d), "check")
                rec["errors"] = chk.get("errors")
                rec["warnings"] = sorted(
                    f"{f['rule']}:{f.get('id')}"
                    for p in chk.get("packs", {}).values()
                    for f in p
                    if f.get("severity") == "warn"
                )
                ren = lcad(root, "-C", str(d), "render")
                rec["png"] = str(d / ren["png"]) if ren.get("png") else None
                kinds = {}
                try:
                    m = json.loads((d / ".linercad/build/model.json").read_text(encoding="utf-8"))
                    for e in m.get("elements", []):
                        kinds[e.get("kind")] = kinds.get(e.get("kind"), 0) + 1
                except (OSError, ValueError):
                    pass
                rec["kinds"] = kinds
            if agent == "baseline" and (w / "drawing.dxf").exists():
                ins = lcad(root, "inspect", str(w / "drawing.dxf"))
                rec["dxf_entities"] = ins.get("entities")
                rec["dxf_png"] = ins.get("png")
            out[f"{agent}/{task['id']}"] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "run", "score"])
    ap.add_argument("--root", required=True)
    ap.add_argument("--clone")
    ap.add_argument("--agent")
    ap.add_argument("--task")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--start", type=int, default=0, help="resume from this round")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if a.cmd == "setup":
        setup(root, a.clone)
    elif a.cmd == "run":
        print(json.dumps(run(root, a.agent, a.task, a.rounds, a.start), ensure_ascii=False))
    else:
        rep = score(root)
        text = json.dumps(rep, ensure_ascii=False, indent=1)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")
        print(text)


if __name__ == "__main__":
    sys.exit(main())
