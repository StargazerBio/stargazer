---
title: marimo-toml
status: done
priority: low
created: 2026-06-10
pr: 63
---

A root `marimo.toml` exists with `[ai] rules` carrying stargazer authoring conventions, but it's an ad-hoc artifact — no story for how it's baked into the notebook image, kept in sync with the conventions in AGENTS.md/docs, or extended (completions, per-notebook overrides). Design one deliberate marimo-config surface and remove the duplication.

Ticket `production-context-files` added `app/notebook_agent.md`, the condensed context file baked into both notebook images as the terminal agent's `~/.claude/CLAUDE.md`. Its task, asset and workflow sections are `[ai] rules` with the repo-maintainer parts trimmed, so the dedupe converges on that file: the rules should come from it rather than keep a second copy.

Not in scope: wiring the stargazer MCP server into marimo's chat panel. Agents
in a notebook pod run in the terminal overlay with a full agent harness, so
marimo's own MCP client isn't needed (decided 2026-10-14).

Decided 2026-10-20: no marimo-config surface. `marimo.toml` held only the `[ai] rules`, so it's deleted in PR #63 (ticket `production-context-files`), leaving `app/notebook_agent.md` as the one condensed context.

## Outcome

Shipped in PR #63 (merge `956ea36`): `marimo.toml` is deleted, and `app/notebook_agent.md` is the one condensed context, baked as `/workspace/AGENTS.md` (ticket `production-context-files`). Verified: nothing else in the repo read the file. Left: marimo's own AI chat panel gets no Stargazer rules when run from a checkout.
