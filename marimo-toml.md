---
title: Cohesive marimo.toml integration
status: backlog
priority: low
created: 2026-06-10
blocked_by:
  - production-context-files
---

A root `marimo.toml` exists with `[ai] rules` carrying stargazer authoring conventions, but it's an ad-hoc artifact — no story for how it's baked into the notebook image, kept in sync with the conventions in AGENTS.md/docs, or extended (completions, per-notebook overrides). Design one deliberate marimo-config surface and remove the duplication.

Ticket `production-context-files` added `app/notebook_agent.md`, the condensed context file baked into both notebook images as the terminal agent's `~/.claude/CLAUDE.md`. Its task, asset and workflow sections are `[ai] rules` with the repo-maintainer parts trimmed, so the dedupe converges on that file: the rules should come from it rather than keep a second copy.

Not in scope: wiring the stargazer MCP server into marimo's chat panel. Agents
in a notebook pod run in the terminal overlay with a full agent harness, so
marimo's own MCP client isn't needed (decided 2026-10-14).
