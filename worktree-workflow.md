---
title: A worktree for every change
status: done
priority: normal
created: 2026-10-09
pr: 19
---

Every change gets its own worktree under `.claude/worktrees/`, on a branch cut from
`origin/main`, with the gitignored Flyte configs and test secrets linked in from the main
checkout. The main checkout stays on `main` and is pulled after each merge. Branch
`docs/worktree-workflow`.

## Outcome

Shipped in #19 (2026-10-12). AGENTS.md and the contributing guide cut one worktree per change
under `.claude/worktrees/` from `origin/main`, link the gitignored Flyte configs and test
secrets in from the main checkout, and pull `main` there after each merge. The `tests/.secrets`
ignore now matches a worktree's symlink, which had shown as untracked.

Verified: a worktree made with the documented command read the linked `.flyte/config.yaml`, and
a read-only pinata test passed through the linked secrets.
