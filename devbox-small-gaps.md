---
title: devbox-small-gaps
status: done
priority: high
created: 2026-10-09
pr: 34
---

- [x] `gatk_env` sets no `resources=`, which AGENTS.md requires of every
      TaskEnvironment for the devbox's ~7.5 GiB node.
- [x] `apply_bqsr` stores the recalibrated BAM but not its index, unlike
      `mark_duplicates` and `sort_sam`. The germline workflow still finishes
      on the devbox, so a later step may be indexing it again (inferred).

## Verification

Branch `fix/devbox-small-gaps`, measured 2026-10-14.

- `apply_bqsr` now stores `<name>.bai` as an `AlignmentIndex`. Its test finds
  none before the fix and one after. The ticket's guess was wrong: the
  germline workflow finishes because it runs no BQSR without known sites,
  not because a later step re-indexes.
- `gatk_env` requests 1Gi with a 6Gi limit. Before, its pods got the
  platform default (256Mi/512Mi). 1Gi rather than 2Gi because the germline
  workflow holds three `gatk_env` pods at once, and the devbox node has
  ~5.8GiB of requests free beside the cluster and the dashboard.
- Tasks tier 37 + 15 passed. Devbox germline passes; all 11 of its pods ran
  at 1Gi/6Gi.

## Outcome

Shipped in PR #34 (merged 2026-10-15). `apply_bqsr` stores its BAM index as
an `AlignmentIndex`, like `mark_duplicates` and `sort_sam`, and `gatk_env`
requests 1Gi of memory with a 6Gi limit instead of the platform's
256Mi/512Mi.

Verified with the `apply_bqsr` test (no index before, one after), the tasks
tier, and the devbox germline workflow, all 11 of its pods at 1Gi/6Gi.

Left: the germline workflow runs no BQSR without known sites, so the stored
index is covered by the tasks-tier test only.

Related: [[flyte-task-environments]], [[gatk]], [[board]].
