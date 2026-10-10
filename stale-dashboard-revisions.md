---
title: Old dashboard revisions keep running after a redeploy
status: backlog
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
