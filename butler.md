---
title: butler
status: done
priority: normal
created: 2026-10-20
pr: 64
---

Saying "butler" runs the routine sweep the user otherwise asks for piece by
piece: pull `main` and `planning`, clean up merged PRs (read their comments,
turn follow-ups into tickets or an urgent branch, close their tickets,
remove their worktrees and branches), answer review comments on open PRs
with commits, rebase open PRs that fell behind or conflict, and report the
board. A skill rather than a subagent, so it runs in the user's session
and can stop to ask before anything irreversible.

## Outcome

PR #64 (`1e95bd0`, merged 2026-10-21): `.claude/skills/butler/SKILL.md`,
listed in `AGENTS.md`'s skill table. Its first run, right after the merge,
was the test: it closed this ticket and answered #60's review feedback.
Not done: a report-only check for apps and runs left up on the tenant.

Related: [[butler-to-user-skills]], [[board]].
