---
title: Small gaps found while testing on the devbox
status: backlog
priority: high
created: 2026-10-09
---

- [ ] `gatk_env` sets no `resources=`, which AGENTS.md requires of every
      TaskEnvironment for the devbox's ~7.5 GiB node.
- [ ] `apply_bqsr` stores the recalibrated BAM but not its index, unlike
      `mark_duplicates` and `sort_sam`. The germline workflow still finishes
      on the devbox, so a later step may be indexing it again (inferred).
