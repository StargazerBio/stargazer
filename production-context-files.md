---
title: Condensed context files for production use (separate from dev)
status: review
priority: normal
created: 2026-05-19
pr: 63
---

An agent launched from a notebook's terminal overlay opens in the workspace
directory (`app/launch-notebook.sh`), and no context file ships there; the
only condensed copy of the authoring conventions is `marimo.toml`'s `[ai]`
rules (ticket `marimo-toml`).

`app/notebook_agent.md` is the one condensed context file, baked into both notebook images at `/home/flyte/.claude/CLAUDE.md`, Claude Code's user-level memory for the `flyte` user they run as (PR #63). It covers where the agent is, marimo's conventions, the task, asset and workflow patterns from `marimo.toml`'s `[ai] rules`, and how runs go local or to the cluster. Verified in a local build of both images and a Union remote build: the file is at that path, readable by `flyte`, `/workspace` untouched, and Claude Code 2.1.153 sends it as user memory (captured with a fake Messages API).
