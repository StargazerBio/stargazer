---
title: Old dashboard revisions keep running after a redeploy
status: doing
priority: high
created: 2026-10-08
---

Each deploy makes a new Knative revision, and the old one keeps its pod for up to an
hour (`autoscaling.knative.dev/window: 1h`): three were running at once on
the devbox after three deploys (measured 2026-10-08). If each pod's
Litestream replicates its own copy of the index to the same bucket path,
that breaks Litestream's one-writer rule, and a restore could come back
from a stale copy (inferred; the restart test still found every row).
Applies to `upgrade` on Union too. The devbox tests deploy once per
session, so they add revisions quickly.

## Findings (2026-10-18)

- **No coordination between writers.** The dashboard runs Litestream 0.5.17
  (`_LITESTREAM` in `app/admin_app.py`), started as `litestream replicate
  -exec …` (`app/dashboard_launch.py`). 0.5.8 added an S3 leaser to the
  library: a `lock.json` written with `If-Match`/`If-None-Match`, with a 30 s
  TTL (litestream#1073). But nothing in `cmd/litestream` uses it at v0.5.17,
  so the `replicate` command takes no lease. Two dashboard pods running at
  once replicate to the same path without knowing about each other
  (inferred from the source).
- **What the replica looks like.** The test account's replica
  (`users/387300641116005877/index/`) held 27 LTX files across compaction
  levels 0–3 and 9. The newest files are from around each of that day's
  deploys. Levels 1–3 are rewritten by compaction, which each running
  Litestream process does on its own. So an old pod could rewrite compacted
  files even with no writes of its own (inferred, not observed).

Next: a controlled check. Deploy, write a row, redeploy, write another, and
watch whether the superseded pod keeps running and writing to the replica.
Then a restart, to see whether the restore has both rows.
