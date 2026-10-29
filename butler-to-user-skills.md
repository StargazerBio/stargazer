---
title: butler-to-user-skills
status: done
priority: low
created: 2026-10-25
pr: 83
---

Butler sweeps all of the user's repos (every checkout at and below the working directory, each by its own instructions), so it moves from `.claude/skills/butler` here to the user's `~/.claude/skills/butler`, and its row leaves `AGENTS.md`.

## Outcome

Shipped in PR #83 (`15d653f`, merged 2026-10-25 as `80dfd7e`): `.claude/skills/butler/` and its `AGENTS.md` row are gone, and butler lives in `~/.claude/skills/butler`. Verified by running the user-level skill's repo discovery from a stargazer worktree, `infra/` and `stargazerbio/`, and by the sweep that closed this ticket. Nothing left.
