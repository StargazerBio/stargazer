---
title: claude-code-harness
status: done
priority: normal
created: 2026-10-26
pr: 84
---

The agent harness was set up for OpenCode (`.opencode/agent/` personas, `.opencode/reference/`), which Claude Code doesn't discover. Move it to Claude Code's defaults, keeping AGENTS.md as the one instructions file, since Claude Code, OpenCode and Codex all read it.

- [x] OpenCode agents become broad skills (`tasks-and-workflows`, `write-tests`, `architecture`, `write-docs`), and code-review the `code-reviewer` subagent
- [x] `.opencode/reference/` moves unchanged to `.claude/reference/`; none of it is a skill
- [x] `verify-stargazer` and `code-reviewer` hold nothing feature-specific: the `features/` recipes, scRNA-only scripts and per-type provenance fields are gone, and AGENTS.md forbids them
- [x] Verification recipes live in their change's ticket (`## Verification recipe: <feature>`); the four removed ones are copied into `normalize-counts-layer`, `devbox-postgres-index` and `notebook-environment`, and the scRNA one reran from its ticket (export `0`, 14 checks `ok`)
- [x] Brainstorm moves to `.claude/brainstorm/` (local, ignored by `.claude/*`)
- [x] Paths repointed in AGENTS.md, docs, `pyproject.toml`, `tests/conftest.py`, `.gitignore`, `.dockerignore`
- [x] infra's `CLAUDE.md` (an `@AGENTS.md` import) deleted
- [x] Verified: a headless `claude -p` session in the worktree lists exactly the seven project skills by their own descriptions and the `code-reviewer` subagent; one in infra loads `AGENTS.md` with no `CLAUDE.md`

## Outcome

Shipped in PR #84 (merge `2075be4`). The harness is on Claude Code's defaults: AGENTS.md is the one instructions file, seven broad skills in `.claude/skills/`, the `code-reviewer` subagent in `.claude/agents/`, reference material unchanged in `.claude/reference/`, brainstorm local at `.claude/brainstorm/`. Nothing feature-specific lives in a skill or subagent; a change's verification recipe lives in its ticket. infra's `CLAUDE.md` is gone (`0716bcc`). Verified with headless `claude -p` sessions listing exactly the seven skills and the subagent, and by rerunning the scRNA recipe from its ticket (export `0`, 14 checks `ok`). Nothing left; no review comments.
