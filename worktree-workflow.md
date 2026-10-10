---
title: A worktree for every change
status: doing
priority: normal
created: 2026-10-09
---

Every change gets its own worktree under `.claude/worktrees/`, on a branch cut from
`origin/main`, with the gitignored Flyte configs and test secrets linked in from the main
checkout. The main checkout stays on `main` and is pulled after each merge. Branch
`docs/worktree-workflow`.
