"""E7 (issue #108): iteration-speed metrics and the two invocation modes in cross_agent.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

import cross_agent  # noqa: E402

CLAUDE = "\n".join(
    [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s-1"}),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Bash", "input": {"command": "lcad build"}},
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "lcad -C drawing check"},
                        },
                    ]
                },
            }
        ),
        json.dumps(
            {"type": "result", "usage": {"input_tokens": 10, "output_tokens": 5}, "result": "ok"}
        ),
    ]
)

DSH = "\n".join(
    [
        json.dumps({"type": "session", "sessionId": "session-1"}),
        json.dumps({"type": "tool_call", "tool": "pwsh", "input": {"command": "lcad render"}}),
        json.dumps(
            {
                "type": "status",
                "phase": "step_end",
                "usage": {
                    "inputTokens": 20,
                    "outputTokens": 7,
                    "cacheReadTokens": 11,
                    "cacheWriteTokens": 2,
                },
            }
        ),
        json.dumps({"type": "final", "text": "done"}),
    ]
)

CODEX = "\n".join(
    [
        json.dumps({"type": "thread.started", "thread_id": "t-1"}),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "lcad build",
                },
            }
        ),
        json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}),
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 30, "cached_input_tokens": 2, "output_tokens": 3},
            }
        ),
    ]
)


def test_parse_claude_stream_metrics():
    m = cross_agent.parse_events("claude", CLAUDE)
    assert m["steps"] == 1 and m["tools"] == {"Bash": 2}
    assert m["lcad"] == {"build": 1, "check": 1}
    assert m["usage"]["input"] == 10 and m["usage"]["output"] == 5
    assert m["session"] == "s-1"


def test_parse_dsh_stream_metrics():
    m = cross_agent.parse_events("dsh", DSH)
    assert m["steps"] == 1 and m["tools"] == {"pwsh": 1}
    assert m["lcad"] == {"render": 1}
    assert m["usage"]["input"] == 20 and m["usage"]["output"] == 7
    assert m["usage"]["cache_read"] == 11 and m["usage"]["cache_write"] == 2
    assert m["session"] == "session-1"


def test_parse_codex_json_metrics():
    m = cross_agent.parse_events("codex", CODEX)
    assert m["steps"] == 2 and m["tools"] == {"shell": 1}
    assert m["lcad"] == {"build": 1}
    assert m["usage"]["input"] == 30 and m["usage"]["output"] == 3
    assert m["usage"]["cache_read"] == 2
    assert m["session"] == "t-1" and m["tokens_total"] == 35


def test_command_for_distinguishes_fresh_and_conversation(tmp_path, monkeypatch):
    monkeypatch.setattr(cross_agent, "exe", lambda root, name: name)
    log = tmp_path / "round-0.log"
    dsh_fresh = cross_agent.command_for("dsh", tmp_path, tmp_path, log)
    dsh_conv = cross_agent.command_for(
        "dsh", tmp_path, tmp_path, log, mode="conversation", session="S"
    )
    assert "--json" in dsh_fresh and "--session-id" not in dsh_fresh
    assert "--session-id" in dsh_conv and "S" in dsh_conv
    codex_fresh = cross_agent.command_for("codex", tmp_path, tmp_path, log)
    codex_conv = cross_agent.command_for(
        "codex", tmp_path, tmp_path, log, mode="conversation", session="T"
    )
    assert codex_fresh[1] == "exec" and "resume" not in codex_fresh
    assert "resume" in codex_conv and "T" in codex_conv
    claude_fresh = cross_agent.command_for("claude", tmp_path, tmp_path, log)
    claude_conv = cross_agent.command_for(
        "claude", tmp_path, tmp_path, log, mode="conversation", session="C"
    )
    assert "stream-json" in claude_fresh and "--resume" not in claude_fresh
    assert "--resume" in claude_conv and "C" in claude_conv


def test_p_summary_reports_both_modes():
    out = {
        "codex/box": {
            "rounds": [
                {
                    "round": 0,
                    "mode": "fresh",
                    "code": 0,
                    "seconds": 10,
                    "tokens_total": 100,
                    "steps": 4,
                    "check": {"errors": 0},
                },
                {
                    "round": 1,
                    "mode": "fresh",
                    "code": 0,
                    "seconds": 5,
                    "tokens_total": 50,
                    "steps": 2,
                    "check": {"errors": 0},
                },
            ]
        },
        "dsh/box": {
            "rounds": [
                {
                    "round": 0,
                    "mode": "conversation",
                    "code": 0,
                    "seconds": 20,
                    "tokens_total": 200,
                    "steps": 6,
                    "check": {"errors": 2},
                },
                {
                    "round": 1,
                    "mode": "conversation",
                    "code": 0,
                    "seconds": 8,
                    "tokens_total": 80,
                    "steps": 3,
                    "check": {"errors": 0},
                },
            ]
        },
    }
    p = cross_agent._p_summary(out)
    assert p["modes"]["fresh"]["first_pass_rate"] == 1.0
    assert p["modes"]["fresh"]["mean_rounds"] == 0.0
    assert p["modes"]["conversation"]["first_pass_rate"] == 0.0
    assert p["modes"]["conversation"]["mean_rounds"] == 1.0
    assert p["modes"]["fresh"]["mean_seconds"] == 7.5
    assert p["modes"]["conversation"]["mean_new_tokens"] == 140


def test_import_demo_replays_run_demo_results(tmp_path):
    for name, agent in (("dsh-tool", "dsh"), ("codex-tool", "codex")):
        d = tmp_path / name
        d.mkdir()
        events = DSH if agent == "dsh" else CODEX
        (d / "events.jsonl").write_text(events, encoding="utf-8")
        (d / "metrics.json").write_text(
            json.dumps(
                {
                    "agent": agent,
                    "task": "tool",
                    "seconds": 12.5,
                    "code": 0,
                    "check": {"errors": 0, "warnings": 0},
                }
            ),
            encoding="utf-8",
        )
    out = tmp_path / "report.json"
    res = cross_agent.import_demo(tmp_path, out)
    assert res["cases"] == 2
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["P"]["modes"]["fresh"]["first_pass_rate"] == 1.0
    assert report["dsh/tool"]["rounds"][0]["seconds"] == 12.5
    assert report["codex/tool"]["rounds"][0]["lcad"] == {"build": 1}


def test_demo_tasks_are_merged_into_the_task_set():
    ids = {t["id"] for t in cross_agent.TASKS}
    assert {"box", "fork", "asm", "tool", "motor"} <= ids
    tool = next(t for t in cross_agent.TASKS if t["id"] == "tool")
    assert tool["rounds"] and "牛鼻" in tool["first"]


def test_new_tokens_do_not_count_replayed_cache():
    assert cross_agent._new_tokens({"usage": {"input": 10, "output": 5, "cache_read": 999}}) == 15
    assert cross_agent._new_tokens({"tokens_total": 42}) == 42


def test_p_summary_skips_baseline_and_marks_mixed_mode_incremental():
    out = {
        "baseline/box": {
            "rounds": [{"round": 0, "mode": "fresh", "seconds": 1, "check": {"errors": 9}}]
        },
        "codex/tool": {
            "rounds": [
                {"round": 0, "mode": "fresh", "code": 0, "seconds": 10, "check": {"errors": 0}},
                {
                    "round": 1,
                    "mode": "conversation",
                    "code": 0,
                    "seconds": 5,
                    "check": {"errors": 0},
                },
            ]
        },
    }
    p = cross_agent._p_summary(out)
    assert p["modes"]["fresh"]["cases"] == 1
    assert p["modes"]["fresh"]["first_pass_rate"] == 1.0
    assert p["incremental"]
    assert p["incremental"][0]["mode"] == "conversation"
    assert p["incremental"][0]["first_pass"] is None
    assert all(r["agent"] != "baseline" for r in p["rows"])


def test_p_summary_does_not_count_a_failed_round_as_green():
    out = {
        "codex/tool": {
            "rounds": [
                {"round": 0, "mode": "fresh", "code": 1, "seconds": 1, "check": {"errors": 0}},
            ]
        }
    }
    p = cross_agent._p_summary(out)
    assert p["modes"]["fresh"]["first_pass_rate"] == 0.0
    assert p["rows"][0]["first_pass"] is False


def test_p_summary_skips_manual_record_without_check():
    out = {"doubao/box": {"rounds": [{"round": 0, "mode": "fresh", "seconds": 95}]}}
    assert cross_agent._p_summary(out) is None


def test_p_summary_counts_cost_of_failed_attempts():
    out = {
        "codex/tool": {
            "rounds": [
                {"round": 0, "mode": "fresh", "code": 1, "seconds": 10, "check": {"errors": None}},
                {"round": 1, "mode": "fresh", "code": 0, "seconds": 20, "check": {"errors": 0}},
            ]
        }
    }
    p = cross_agent._p_summary(out)
    row = p["rows"][0]
    assert row["first_pass"] is False
    assert row["rounds_to_green"] == 1
    assert row["seconds"] == 30
    assert p["modes"]["fresh"]["mean_seconds"] == 15.0
