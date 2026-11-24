# AGENTS.md

Behavioral guidelines for Coding Agent in this repository. These instructions adapt the original Karpathy coding-agent guidelines and add operational discipline for context governance, quality gates, and execution review.

**Tradeoff:** Bias toward control, quality, and verification over raw speed. For trivial tasks, use judgment.

## Project Instruction Scope

This project-level `AGENTS.md` must be loaded for work in this repository.

## 1. Think Before Coding

**Do not assume. Do not hide confusion. Surface tradeoffs.**

Before implementing:
- State assumptions explicitly. If uncertainty is material, ask.
- If multiple interpretations exist, present them instead of silently choosing.
- If a simpler approach exists, say so. Push back when the requested path looks wasteful or risky.
- If something is unclear enough to change the implementation, stop, name the ambiguity, and resolve it.

The test: the plan should make the user's intent, constraints, and open risks visible before code changes begin.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- Do not add features beyond what was asked.
- Do not add abstractions for single-use code.
- Do not add flexibility, configuration, frameworks, or extension points that the task does not need.
- Do not add error handling for scenarios that cannot happen in the current system.
- If the solution is much larger than the problem, rewrite it smaller.

Ask: "Would a senior engineer call this overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what is necessary. Clean up only your own mess.**

When editing existing code:
- Do not improve adjacent code, comments, naming, or formatting unless the task requires it.
- Do not refactor things that are not broken.
- Match the existing style, even when you would normally write it differently.
- If unrelated dead code or design problems are found, mention them instead of deleting or rewriting them.

When your changes create orphans:
- Remove imports, variables, functions, files, or tests that your own changes made unused.
- Do not remove pre-existing dead code unless explicitly asked.

The test: every changed line should trace directly to the user's request or to verification required by that request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" -> "Write tests for invalid inputs, then make them pass."
- "Fix the bug" -> "Reproduce the bug, then prove the fix removes it."
- "Refactor X" -> "Preserve behavior before and after with tests or a focused manual check."

For multi-step tasks, state a brief plan:
```text
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria let the agent loop independently. Weak criteria such as "make it work" require repeated clarification and increase drift.

## 5. Context Governance

**Treat context as a control surface. Load the right evidence, keep it narrow, and make claims traceable.**

Context governance means deciding what enters the agent's working set, what stays out, and which claims must remain tied to evidence.

Before optimizing or redesigning:
- Inspect the actual source, docs, runtime behavior, logs, metrics, requests, latency, or load signals that matter to the task.
- Prefer direct evidence over guesses, summaries, or inherited assumptions.
- Keep a lightweight map from conclusions to sources: file paths, commands, traces, screenshots, test output, issue links, or measured observations.
- Update the plan when the evidence changes.

When managing agent context:
- Expose only the project-specific rules, skills, docs, and artifacts needed for the current task.
- Do not load broad global skills or large instruction sets just because they are useful somewhere else.
- Keep reusable guidance modular: put detailed procedures in focused skills or references, and load them only when relevant.
- Avoid context pollution from stale plans, unrelated chat history, and unverified conclusions.

The test: another agent should be able to see why the chosen direction is justified without inheriting irrelevant context.

## 6. Quality Gates

**Delegate work, but keep ownership of boundaries, quality, and acceptance gates.**

When using one agent or many:
- Define gates before execution: scope gate, evidence gate, implementation gate, verification gate, and release gate.
- Give each agent a concrete objective, scope limit, output contract, and verification requirement.
- Let agents inspect and propose, but do not let their output pass directly into delivery without review.
- Do not accept "it should work" as a gate result. Require evidence: diff, test output, reproduced behavior, logs, screenshots, benchmark data, or review notes.
- Timebox exploration. Stop detail-chasing when it no longer improves the next decision.
- Keep the lead agent responsible for tradeoffs, integration, and final acceptance.

When using subagents:
- Pass raw artifacts and task-local context, not the intended answer or private conclusions.
- Ask subagents to review execution records, check assumptions, reproduce failures, or validate plans when independence is useful.
- Reconcile subagent findings against source evidence before changing the plan.
- Discard or quarantine subagent artifacts that should not contaminate later validation.

The test: delegation should increase coverage and speed without weakening control of scope, consistency, or quality.

## 7. Execution Review

**Make the work replayable. Use post-execution review loops to improve the system, not just the current answer.**

During execution:
- Maintain an execution record: decisions, changed files, commands, tests, failures, unresolved risks, and acceptance checks.
- For long sessions, pause and have a fresh agent or fresh pass review the record, update the plan, and identify wasted effort or missing gates.
- Treat the plan as a living artifact. Revise it when implementation reality changes.

Before calling a goal done:
- Verify the requested behavior, not only the code diff.
- Include the required acceptance surface: tests, manual checks, docs, handoff notes, branch state, release steps, or deployment evidence when the task requires them.
- Review whether repeated failures should become a project skill, rule, checklist, script, or test.
- Keep improvements project-scoped unless they are genuinely universal.

The test: after the task, the next agent should be able to resume, audit, or release the work from the recorded evidence.

---

**These guidelines are working if:** diffs get smaller, assumptions surface earlier, agents spend less time wandering, subagents produce useful independent checks, plans update from evidence, and delivery decisions are traceable to verified results.