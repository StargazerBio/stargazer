---
title: Butler moves to the user's own skills
status: review
priority: low
created: 2026-10-25
pr: 83
---

Butler sweeps all of the user's repos (every checkout at and below the working directory, each by its own instructions), so it moves from `.claude/skills/butler` here to the user's `~/.claude/skills/butler`, and its row leaves `AGENTS.md`.
