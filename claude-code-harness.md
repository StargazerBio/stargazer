---
title: Agent harness on Claude Code defaults
status: review
priority: normal
created: 2026-10-26
pr: 84
---

The agent harness was set up for OpenCode (`.opencode/agent/` personas, `.opencode/reference/`), which Claude Code doesn't discover. Move it to Claude Code's defaults, keeping AGENTS.md as the one instructions file, since Claude Code, OpenCode and Codex all read it.

- [x] OpenCode agents become broad skills (`tasks-and-workflows`, `write-tests`, `architecture`, `write-docs`), and code-review the `code-reviewer` subagent
- [x] `.opencode/reference/` moves unchanged to `.claude/reference/`; none of it is a skill
- [x] Brainstorm moves to `.claude/brainstorm/` (local, ignored by `.claude/*`)
- [x] Paths repointed in AGENTS.md, docs, `pyproject.toml`, `tests/conftest.py`, `.gitignore`, `.dockerignore`
- [x] infra's `CLAUDE.md` (an `@AGENTS.md` import) deleted
- [x] Verified: a headless `claude -p` session in the worktree lists exactly the seven project skills by their own descriptions and the `code-reviewer` subagent; one in infra loads `AGENTS.md` with no `CLAUDE.md`
