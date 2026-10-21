---
title: A butler skill for the routine repo sweep
status: review
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
