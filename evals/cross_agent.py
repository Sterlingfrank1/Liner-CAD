"""Cross-agent evaluation (SPEC M3 §1.8): coding agents with only the installed skill, and a
bare-ezdxf baseline, on the same requirement texts (evals/cross/tasks.toml).

    python evals/cross_agent.py setup --root R --clone C      # venv with linercad[3d] from clone C
    python evals/cross_agent.py run --root R --agent codex|claude|dsh|baseline --task box [--rounds 3]
    python evals/cross_agent.py prompt --root R --agent doubao --task box --round 0   # GUI agents
    python evals/cross_agent.py record --root R --agent doubao --task box --round 0 --seconds 95
    python evals/cross_agent.py score --root R --out report.json

Each (agent, task) gets R/<agent>/<task>/ outside any repo; ``lcad`` comes from R/venv. Every round
is a fresh non-interactive invocation (like a user coming back), output kept in round-<k>.log.

dsh is DeepSeek Harness headless (``dsh.cmd`` from $DSH or PATH; DEEPSEEK_API_KEY in the
environment; model from --dsh-model). GUI agents (doubao = 豆包工作 desktop) are driven by hand or by
computer use, in 云电脑 mode (a cloud VM): attach the wheel from ``uv build`` to the first message;
``prompt`` prints the round's text, ``record`` appends the measured round to runs.json; unzip the
returned drawing.zip into R/doubao/<task>/drawing and ``score`` treats it like the others.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = tomllib.loads((HERE / "cross" / "tasks.toml").read_text(encoding="utf-8"))["task"]
TIMEOUT = 20 * 60
AGENTS = ("codex", "claude", "dsh", "doubao", "baseline")
SKILL_TARGET = {"codex": "codex", "dsh": "codex", "claude": "claude"}
SKILL_DOC = {"codex": "AGENTS.md", "dsh": "AGENTS.md"}  # others: .claude/skills/linercad/SKILL.md

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
        target = SKILL_TARGET.get(agent)
        if target:
            subprocess.run(
                [exe(root, "lcad"), "skill", "install", "--target", target, "--dir", str(w)],
                check=True,
                env=env(root),
                capture_output=True,
            )
    return w


DSH_MODEL = "deepseek-flash:high"  # DeepSeek-V4.1-Flash, reasoning effort high

LCAD_RE = re.compile(
    r"(?:\blcad(?:\.exe)?|-m\s+linercad)\s+(?:-C\s+\S+\s+)?([a-z][a-z-]*)(?:\s+([a-z0-9_-]+))?"
)


def lcad_calls(cmd):
    """lcad subcommands in a shell command, as run_demo.py counted them."""
    out = []
    for m in LCAD_RE.finditer(cmd or ""):
        sub, arg = m.group(1), m.group(2)
        if sub in ("skill", "template") and arg and re.fullmatch(r"[a-z0-9_]+", arg):
            sub = f"{sub} {arg}"
        out.append(sub)
    return out


def _empty_metrics():
    return {
        "tools": collections.Counter(),
        "lcad": collections.Counter(),
        "steps": 0,
        "usage": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0},
        "final": "",
    }


def _add_usage(m, u, in_key="input", out_key="output"):
    if not isinstance(u, dict):
        return
    m["usage"]["input"] += int(u.get(in_key) or 0)
    m["usage"]["output"] += int(u.get(out_key) or 0)
    m["usage"]["cache_read"] += int(u.get("cache_read") or u.get("cached_input_tokens") or 0)
    m["usage"]["cache_write"] += int(u.get("cache_write") or u.get("cache_write_input_tokens") or 0)


def parse_events(agent, text):
    """Per-round process metrics from the CLI event stream (run_demo.py parsers, merged here)."""
    m = _empty_metrics()
    for line in text.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        t = ev.get("type")
        if agent == "claude":
            if t == "system" and ev.get("subtype") == "init":
                m["session"] = ev.get("session_id")
            elif t == "assistant":
                m["steps"] += 1
                for c in (ev.get("message") or {}).get("content", ()):
                    if c.get("type") == "tool_use":
                        m["tools"][c.get("name", "tool")] += 1
                        inp = c.get("input") or {}
                        for s in lcad_calls(
                            inp.get("command", "") if isinstance(inp, dict) else ""
                        ):
                            m["lcad"][s] += 1
            elif t == "result":
                u = ev.get("usage") or {}
                m["usage"] = {
                    "input": int(u.get("input_tokens") or 0),
                    "output": int(u.get("output_tokens") or 0),
                    "cache_read": int(u.get("cache_read_input_tokens") or 0),
                    "cache_write": int(u.get("cache_creation_input_tokens") or 0),
                }
                m["final"] = ev.get("result", "") or m["final"]
        elif agent == "dsh":
            if t == "session":
                m["session"] = ev.get("sessionId")
            elif t == "tool_call":
                m["tools"][ev.get("tool", "tool")] += 1
                inp = ev.get("input") or {}
                cmd = inp.get("command", "") if isinstance(inp, dict) else str(inp)
                for s in lcad_calls(cmd):
                    m["lcad"][s] += 1
            elif t == "status" and ev.get("phase") == "step_end":
                m["steps"] += 1
                _add_usage(m, ev.get("usage"), "inputTokens", "outputTokens")
            elif t == "final":
                m["final"] = ev.get("text", "") or m["final"]
        elif agent == "codex":
            if t == "thread.started":
                m["session"] = ev.get("thread_id")
            elif t == "item.completed":
                item = ev.get("item") or {}
                kind = item.get("type")
                if kind == "command_execution":
                    m["steps"] += 1
                    m["tools"]["shell"] += 1
                    for s in lcad_calls(item.get("command", "")):
                        m["lcad"][s] += 1
                elif kind == "agent_message":
                    m["steps"] += 1
                    m["final"] = item.get("text", "") or m["final"]
                elif kind == "reasoning":
                    m["steps"] += 1
            elif t == "turn.completed":
                _add_usage(m, ev.get("usage"), "input_tokens", "output_tokens")
    m["tools"], m["lcad"] = dict(m["tools"]), dict(m["lcad"])
    m["tokens_total"] = sum(m["usage"].values())
    return m


def command_for(agent, w, root, log, dsh_model=DSH_MODEL, mode="fresh", session=None):
    """CLI argv for one round. fresh = a new session every round; conversation = resume."""
    resume = mode == "conversation" and bool(session)
    if agent == "dsh":
        cmd = [
            os.environ.get("DSH") or exe(root, "dsh"),
            "--profile",
            "headless",
            "--patch",
            str(dsh_patch(root, dsh_model)),
            "--json",
            "--permission-mode",
            "workspace-write",
            "--approval-policy",
            "never",
        ]
        if resume:
            cmd += ["--session-id", session]
        cmd += ["-"]
        return cmd
    if agent == "codex":
        if resume:
            return [
                exe(root, "codex"),
                "exec",
                "resume",
                session,
                "--json",
                "--skip-git-repo-check",
                "--dangerously-bypass-approvals-and-sandbox",
                "-C",
                str(w),
                "-",
            ]
        return [
            exe(root, "codex"),
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-C",
            str(w),
            "-o",
            str(log.with_suffix(".last.txt")),
            "-",
        ]
    cmd = [
        exe(root, "claude"),
        "-p",
        "--model",
        "sonnet",
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "stream-json",
        "--verbose",
        "--setting-sources",
        "project",
    ]
    if resume:
        cmd += ["--resume", session]
    return cmd


def dsh_patch(root, model):
    """Profile overlay picking the model ("<id>:<effort>", effort off|low|high|max)."""
    mid, _, effort = model.partition(":")
    p = root / f"dsh-{mid}-{effort or 'default'}.yml"
    cfg = f"    provider: deepseek-official\n    model: {mid}\n"
    if effort:
        cfg += f"    reasoningEffort: {effort}\n"
    p.write_text(f"- id: agent-default-model\n  config:\n{cfg}", encoding="utf-8")
    return p


def invoke(agent, w, prompt, root, log, dsh_model=DSH_MODEL, mode="fresh", session=None):
    cmd = command_for(agent, w, root, log, dsh_model, mode, session)
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
    metrics = parse_events(agent, out)
    metrics.pop("session", None)
    return {"code": code, "seconds": round(time.time() - t, 1), **metrics}


def task_of(tid):
    return next(t for t in TASKS if t["id"] == tid)


def prompt_for(root, agent, task, k):
    req = [task["first"], *task["rounds"]][k]
    if agent == "baseline":
        return BASELINE.format(req=req)
    if (
        agent == "doubao"
    ):  # 云电脑: a cloud VM, so the wheel is attached and the result comes back zipped
        pre = (
            '（第一次）附件里的 linercad-*.whl 是工程图工具，先 `pip install "<该 whl>[3d]"`，'
            "装好后命令 `lcad` 可用。\n"
            if k == 0
            else ""
        )
        p = HARNESS.format(doc="`lcad skill` 的输出", req=req)
        return pre + p + "\n\n做完后把 ./drawing 整个目录（含 .git）打包成 drawing.zip 发给我。"
    return HARNESS.format(doc=SKILL_DOC.get(agent, ".claude/skills/linercad/SKILL.md"), req=req)


def save_runs(w, res):
    (w / "runs.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


def load_runs(w, upto=None):
    prev = w / "runs.json"
    res = json.loads(prev.read_text(encoding="utf-8")) if prev.exists() else []
    return res if upto is None else [r for r in res if r["round"] < upto]


def run(root, agent, tid, rounds, start=0, dsh_model=DSH_MODEL, mode="fresh"):
    """Run rounds in fresh mode (new session each round) or conversation mode (resume)."""
    task = task_of(tid)
    w = workdir(root, agent, task)
    res = load_runs(w, start) if start else []
    session = None
    if mode == "conversation" and res:
        session = res[-1].get("session")
    for k in range(start, rounds + 1):
        cli = agent if agent in ("codex", "dsh") else "claude"  # baseline: claude without skill
        r = invoke(
            cli,
            w,
            prompt_for(root, agent, task, k),
            root,
            w / f"round-{k}.log",
            dsh_model,
            mode=mode,
            session=session,
        )
        if mode == "conversation" and r.get("session"):
            session = r["session"]
        check = {"errors": None, "warnings": None}
        drawing = w / "drawing"
        if drawing.exists():
            try:
                chk = lcad(root, "-C", str(drawing), "check")
                check = {
                    "errors": chk.get("errors"),
                    "warnings": len(chk.get("packs", {}).get("layout", ())),
                }
            except Exception:  # noqa: BLE001 - a broken check must not hide the round metrics
                pass
        res.append({"round": k, "mode": mode, "check": check, **r})
        if agent == "dsh":
            res[-1]["model"] = dsh_model
        save_runs(w, res)
    return res


def record(root, agent, tid, k, seconds, code=0, note=None):
    w = workdir(root, agent, task_of(tid))
    res = load_runs(w, k)
    res.append({"round": k, "code": code, "seconds": seconds, **({"note": note} if note else {})})
    save_runs(w, res)
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


def _p_summary(out):
    """P (process) family: first-pass rate / mean rounds / timing, split by mode and agent."""
    rows = []
    for key, rec in out.items():
        if key == "P":
            continue
        runs = rec.get("rounds") or []
        if not runs:
            continue
        agent, task = key.split("/", 1)
        modes = {}
        for r in runs:
            modes.setdefault(r.get("mode", "fresh"), []).append(r)
        for mode, rs in modes.items():
            errors = [r.get("check", {}).get("errors") for r in rs]
            green = next((i for i, e in enumerate(errors) if e == 0), None)
            rows.append(
                {
                    "agent": agent,
                    "task": task,
                    "mode": mode,
                    "rounds": len(rs),
                    "first_pass": errors[0] == 0 if errors else False,
                    "rounds_to_green": green,
                    "seconds": sum(float(r.get("seconds") or 0) for r in rs),
                    "new_tokens": sum(int(r.get("tokens_total") or 0) for r in rs),
                    "steps": sum(int(r.get("steps") or 0) for r in rs),
                }
            )
    if not rows:
        return None
    by_mode = {}
    for row in rows:
        by_mode.setdefault(row["mode"], []).append(row)
    summary = {}
    for mode, rs in sorted(by_mode.items()):
        summary[mode] = {
            "cases": len(rs),
            "first_pass_rate": round(sum(1 for r in rs if r["first_pass"]) / len(rs), 4),
            "mean_rounds": round(
                sum(
                    r["rounds_to_green"] if r["rounds_to_green"] is not None else r["rounds"]
                    for r in rs
                )
                / len(rs),
                2,
            ),
            "mean_seconds": round(sum(r["seconds"] for r in rs) / sum(r["rounds"] for r in rs), 1),
            "mean_new_tokens": round(
                sum(r["new_tokens"] for r in rs) / sum(r["rounds"] for r in rs)
            ),
            "mean_steps": round(sum(r["steps"] for r in rs) / sum(r["rounds"] for r in rs), 1),
        }
    return {"modes": summary, "rows": rows}


def import_demo(results, out=None):
    """Replay run_demo.py results (events.jsonl + metrics.json) through the merged metrics parser.

    run_demo.py itself is kept outside the repo (issue #108); this command is the migration path:
    each <agent>-<task> directory becomes one fresh-mode round in the cross_agent report.
    """
    report = {}
    for d in sorted(Path(results).glob("*-*")):
        if not d.is_dir():
            continue
        agent, task = d.name.split("-", 1)
        events = (d / "events.jsonl").read_text(encoding="utf-8", errors="replace")
        base = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
        m = parse_events(agent, events)
        round_rec = {
            "round": 0,
            "mode": "fresh",
            "code": base.get("code", 0),
            "seconds": base.get("seconds"),
            "tokens_total": m["tokens_total"],
            "steps": m["steps"],
            "tools": m["tools"],
            "lcad": m["lcad"],
            "usage": m["usage"],
            "check": {
                "errors": (base.get("check") or {}).get("errors"),
                "warnings": (base.get("check") or {}).get("warnings"),
            },
        }
        report[f"{agent}/{task}"] = {"rounds": [round_rec], "source": str(d)}
    report["P"] = _p_summary(report)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    return {"cases": len(report) - 1, "P": report["P"]}


def score(root):
    out = {}
    for agent in AGENTS:
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
    out["P"] = _p_summary(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["setup", "run", "prompt", "record", "score", "import-demo"])
    ap.add_argument("--root", required=True)
    ap.add_argument("--clone")
    ap.add_argument("--agent")
    ap.add_argument("--task")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--start", type=int, default=0, help="resume from this round")
    ap.add_argument(
        "--mode",
        choices=["fresh", "conversation"],
        default="fresh",
        help="new session per round or resume the same session",
    )
    ap.add_argument("--round", type=int, default=0)
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--code", type=int, default=0)
    ap.add_argument("--note")
    ap.add_argument("--dsh-model", default=DSH_MODEL, help="<model id>:<effort>")
    ap.add_argument("--out")
    ap.add_argument("--results", help="run_demo results directory (import-demo)")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if a.cmd == "setup":
        setup(root, a.clone)
    elif a.cmd == "run":
        res = run(root, a.agent, a.task, a.rounds, a.start, a.dsh_model, a.mode)
        print(json.dumps(res, ensure_ascii=False))
    elif a.cmd == "prompt":
        print(prompt_for(root, a.agent, task_of(a.task), a.round))
    elif a.cmd == "record":
        res = record(root, a.agent, a.task, a.round, a.seconds, a.code, a.note)
        print(json.dumps(res, ensure_ascii=False))
    else:
        rep = score(root)
        text = json.dumps(rep, ensure_ascii=False, indent=1)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")
        print(text)


if __name__ == "__main__":
    sys.exit(main())
