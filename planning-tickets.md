---
title: planning-tickets
status: done
priority: normal
created: 2026-10-09
pr: 20
---

The roadmap and numbered plans become one ticket per file on the `planning` branch, checked
out once at the main checkout's `planning/` and shared by every session and the Obsidian board.
`main` keeps no planning files and refers to tickets by slug. Branch `chore/planning-tickets`.

## Outcome

Shipped in #20 (2026-10-12). `main` holds no planning files: the roadmap and plans are tickets
on this branch, checked out once at the main checkout's `planning/`, which `main` gitignores.
AGENTS.md documents the conventions, and `main` mentions tickets by slug.

Verified: every ticket's frontmatter round-trips through the `yaml` stringify options Obsidian
1.14.4 uses; the pre-commit check rejects a frontmatter comment, an unknown status or priority,
an inline list and a dangling `blocked_by`; the first lifecycle edit (these two tickets to
`review`) went through it.

Left: the board hasn't been opened in Obsidian yet, so a real card drag is unchecked.
